import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from website.models import ContentBlock, TeamMember, HeroSlide, NavigationLink, Survey, SurveyQuestion

class Command(BaseCommand):
    help = "Populate the original website content without overwriting edits. Creates optional team role groups."

    @transaction.atomic
    def handle(self, *args, **options):
        source = Path(__file__).resolve().parents[2] / "data" / "initial_content.json"
        data = json.loads(source.read_text())
        for row in data["blocks"]:
            ContentBlock.objects.get_or_create(key=row["key"], defaults={k: v for k, v in row.items() if k != "key"})
        # A database flag prevents reintroducing people/slides/menu items deliberately removed in admin.
        marker, first_run = ContentBlock.objects.get_or_create(key="system-initial-content-seeded", defaults={"page": "system", "label": "Initial content seeded", "value": "1"})
        if first_run:
            for row in data["people"]:
                TeamMember.objects.create(**row)
            for order, row in enumerate(data["heroes"]):
                HeroSlide.objects.create(title=f"Homepage slide {order + 1}", image_path=row["src"], position=row.get("position", "center center"), order=order)
            menu_ids = {}
            for row in data["menus"]:
                row = row.copy()
                old_id = row.pop("id")
                parent = row.pop("parent", None)
                item = NavigationLink.objects.create(parent_id=menu_ids.get(parent), **row)
                menu_ids[old_id] = item.pk
        survey, created = Survey.objects.get_or_create(slug="mentorship", defaults=data["survey"]["meta"])
        if created:
            for key, row in data["survey"]["questions"].items():
                SurveyQuestion.objects.create(survey=survey, key=key, **row)
        roles = {
            "Team authors": ["view_publication", "add_publication", "change_publication", "view_opportunity", "add_opportunity", "change_opportunity"],
            "Team profiles": ["view_teammember", "change_teammember"],
            "Assigned page editors": ["view_contentblock", "change_contentblock", "view_heroslide", "change_heroslide"],
            "Event editors": ["view_event", "add_event", "change_event"],
            "Content publishers": ["publish_publication", "publish_opportunity", "publish_event"],
        }
        for name, codenames in roles.items():
            group, created = Group.objects.get_or_create(name=name)
            if created:
                group.permissions.set(Permission.objects.filter(content_type__app_label="website", codename__in=codenames))
        self.stdout.write(self.style.SUCCESS("Original content is ready. Existing content and role changes were preserved."))
