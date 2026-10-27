import io
import json
import tempfile
import time
from pathlib import Path
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from . import models
from .content import rich_text
from .forms import PublicationForm
from .validators import validate_link

@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class SiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_site", stdout=io.StringIO())

    def user(self, name="author", roles=("Team authors",)):
        user = User.objects.create_user(name, password="Test-password-4831")
        user.groups.set(Group.objects.filter(name__in=roles))
        return user

    def publication_data(self, **extra):
        data = {"title": "Test publication", "slug": "test-publication", "publication_type": "Blog", "summary": "A summary", "full_content": "<p>A body</p>",
                "images-TOTAL_FORMS": "0", "images-INITIAL_FORMS": "0", "images-MIN_NUM_FORMS": "0", "images-MAX_NUM_FORMS": "1000"}
        data.update(extra)
        return data

    def test_pages_and_clean_routes_render(self):
        for url in ["/", "/index.php", "/about.php", "/about/", "/programs.php", "/programs/", "/publications.php", "/publications/", "/events.php", "/survey.php", "/survey/", "/team/login/"]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "<?php")
                self.assertNotContains(response, "{%")
                self.assertNotContains(response, 'src="assets/')

    def test_content_changes_appear_and_escape_html(self):
        block = models.ContentBlock.objects.filter(page="index", kind="text").first()
        block.value = '<script>alert("test")</script>'
        block.save()
        response = self.client.get("/")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("test")</script>')
        email = models.ContentBlock.objects.get(key="contact-email")
        email.value = "hello@example.org"
        email.save()
        for path in ["/", "/about.php"]:
            self.assertContains(self.client.get(path), 'mailto:hello@example.org')

    def test_people_and_hero_are_database_driven(self):
        person = models.TeamMember.objects.filter(section="board").first()
        person.name = "Replacement board chair"
        person.save()
        self.assertContains(self.client.get("/about.php"), person.name)
        person.is_active = False
        person.save()
        self.assertNotContains(self.client.get("/about.php"), person.name)
        hero = models.HeroSlide.objects.first()
        hero.image_path = "https://example.org/changed.jpg"
        hero.save()
        self.assertEqual(self.client.get("/api/hero/").json()[0]["src"], hero.image_path)
        hero.is_active = False
        hero.save()
        self.assertEqual(len(self.client.get("/api/hero/").json()), 8)

    def test_published_content_and_gallery_render(self):
        draft = models.Publication.objects.create(title="Draft", slug="draft", publication_type="Blog")
        item = models.Publication.objects.create(title="Published", slug="published", publication_type="Blog", is_published=True,
            full_content='<h2>Heading</h2><p onclick="alert(1)">Body <a href="javascript:alert(1)">link</a></p>')
        models.PublicationImage.objects.create(publication=item, image_path="assets/images/Emma.jpg")
        self.assertEqual(self.client.get("/publication.php?slug=draft").status_code, 404)
        self.assertEqual(self.client.get("/api/publications.php").json()["count"], 1)
        response = self.client.get("/publication.php?slug=published")
        self.assertContains(response, "<h2>Heading</h2>", html=True)
        self.assertNotContains(response, 'onclick="alert(1)"')
        self.assertNotContains(response, "javascript:")
        self.assertContains(response, "/static/assets/images/Emma.jpg")
        self.assertContains(response, 'id="publication-gallery-root"', count=1)
        self.assertEqual(self.client.get("/publications/published/").status_code, 200)
        self.assertEqual(self.client.get("/api/publications.php?type=Invalid").status_code, 422)
        opportunity = models.Opportunity.objects.create(title="Scholarship", slug="scholarship", category="Scholarship", is_published=True)
        self.assertContains(self.client.get("/opportunity.php?slug=scholarship"), "Scholarship")
        self.assertEqual(self.client.get("/api/opportunities.php").json()["count"], 1)

    def test_founder_story_and_events(self):
        self.assertEqual(self.client.get("/founder-story.php").status_code, 404)
        story = models.FounderStory.objects.create(founder_name="Founder", is_published=True)
        models.StorySection.objects.create(story=story, heading="Education", body="<p>Story text</p>")
        self.assertContains(self.client.get("/founder-story.php"), "Story text")
        event = models.Event.objects.create(title="A future event", slug="future-event", is_published=True)
        self.assertContains(self.client.get("/events.php"), event.title)

    def test_seed_is_repeatable_and_preserves_admin_edits_and_deletions(self):
        block = models.ContentBlock.objects.get(key="contact-email")
        block.value = "new@example.org"
        block.save()
        models.HeroSlide.objects.first().delete()
        models.TeamMember.objects.first().delete()
        models.SurveyQuestion.objects.first().delete()
        call_command("seed_site", stdout=io.StringIO())
        self.assertEqual(models.ContentBlock.objects.get(pk=block.pk).value, "new@example.org")
        self.assertEqual(models.HeroSlide.objects.count(), 8)
        self.assertEqual(models.TeamMember.objects.count(), 7)
        self.assertEqual(models.SurveyQuestion.objects.count(), 12)

    def test_team_requires_login_and_rejects_admin_access(self):
        self.assertRedirects(self.client.get("/team/"), "/team/login/?next=/team/")
        user = self.user()
        user.is_staff = True
        user.save()
        self.client.force_login(user)
        self.assertEqual(self.client.get("/team/").status_code, 200)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.assertContains(self.client.get("/admin/login/"), "administration")
        self.assertEqual(self.client.get("/admin/website/contentblock/").status_code, 302)

    def test_team_cannot_read_or_edit_another_owners_content(self):
        user = self.user()
        other = self.user("other")
        owned = models.Publication.objects.create(owner=user, title="My assigned work", slug="mine", publication_type="Blog")
        hidden = models.Publication.objects.create(owner=other, title="Other private work", slug="other", publication_type="Blog")
        self.client.force_login(user)
        dashboard = self.client.get("/team/")
        self.assertContains(dashboard, owned.title)
        self.assertNotContains(dashboard, hidden.title)
        self.assertEqual(self.client.get(f"/team/publications/{hidden.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/team/publications/{hidden.pk}/", self.publication_data()).status_code, 404)

    def test_team_search_matches_current_content_and_exact_phrases(self):
        user = self.user(roles=("Assigned page editors",))
        block = models.ContentBlock.objects.create(key="search-example", page="about", label="Original label", value="We provide research\n capacity support.", owner=user)
        models.ContentBlock.objects.create(key="search-partial", page="about", label="Another item", value="Capacitybuilding support", owner=user)
        self.client.force_login(user)
        response = self.client.get("/team/", {"q": "RESEARCH capacity"})
        self.assertEqual(response.context["result_count"], 1)
        self.assertContains(response, "Original label")
        self.assertContains(response, "research capacity support")
        self.assertContains(response, f'href="/team/content/{block.pk}/"')
        self.assertEqual(self.client.get(f"/team/content/{block.pk}/").status_code, 200)
        self.assertEqual(self.client.get("/team/", {"q": "capacity"}).context["result_count"], 1)
        self.assertContains(self.client.get("/team/", {"q": "missing phrase"}), "No matching content.")
        self.assertContains(self.client.get("/team/", {"q": "   "}), "Another item")

    def test_team_search_preserves_ownership_groups_and_literal_matching(self):
        user = self.user(roles=("Assigned page editors",))
        other = self.user("another-editor", roles=("Assigned page editors",))
        group = Group.objects.get(name="Assigned page editors")
        models.ContentBlock.objects.create(key="search-owned", page="about", label="Owned item", value="Support C++ & research", owner=user)
        shared = models.ContentBlock.objects.create(key="search-shared", page="about", label="Shared item", value="Support <strong>C++</strong> &amp; research", editor_group=group)
        models.ContentBlock.objects.create(key="search-private", page="about", label="Private item", value="Support C++ & research", owner=other)
        # Ownership alone does not grant access to a different model type.
        models.Publication.objects.create(title="Hidden publication", slug="hidden-search", publication_type="Blog", summary="C++ & research", owner=user)
        self.client.force_login(user)
        response = self.client.get("/team/", {"q": "C++ & research"})
        self.assertEqual(response.context["result_count"], 2)
        self.assertContains(response, "Owned item")
        self.assertContains(response, "Shared item")
        self.assertNotContains(response, "Private item")
        self.assertNotContains(response, "Hidden publication")
        self.assertContains(response, f'href="/team/content/{shared.pk}/"')
        self.assertEqual(self.client.get("/team/", {"q": ".*"}).context["result_count"], 0)

    def test_group_assignment_needs_explicit_model_permission(self):
        user = self.user(roles=())
        group = Group.objects.get(name="Assigned page editors")
        block = models.ContentBlock.objects.get(key="contact-email")
        block.editor_group = group
        block.save()
        self.client.force_login(user)
        self.assertEqual(self.client.get(f"/team/content/{block.pk}/").status_code, 403)
        user.groups.add(group)
        self.assertEqual(self.client.get(f"/team/content/{block.pk}/").status_code, 200)
        self.client.post(f"/team/content/{block.pk}/", {"value": "group@example.org", "owner": user.pk, "kind": "image", "key": "tampered"})
        block.refresh_from_db()
        self.assertEqual(block.value, "group@example.org")
        self.assertEqual(block.key, "contact-email")
        self.assertIsNone(block.owner)
        self.assertEqual(block.kind, "text")

    def test_author_cannot_escalate_or_publish_using_post_fields(self):
        user = self.user()
        admin_user = User.objects.create_superuser("admin", "admin@example.org", "Admin-password-4931")
        self.client.force_login(user)
        response = self.client.post("/team/publications/new/", self.publication_data(owner=admin_user.pk, editor_group=Group.objects.get(name="Team authors").pk, is_published="on", is_featured="on"))
        self.assertRedirects(response, "/team/")
        item = models.Publication.objects.get(slug="test-publication")
        self.assertEqual(item.owner, user)
        self.assertIsNone(item.editor_group)
        self.assertFalse(item.is_published)
        self.assertFalse(item.is_featured)
        self.assertEqual(self.client.get(f"/team/publications/{item.pk}/").status_code, 200)

    def test_explicit_publishing_permission_allows_assigned_publication(self):
        user = self.user(roles=("Team authors", "Content publishers"))
        self.client.force_login(user)
        response = self.client.post("/team/publications/new/", self.publication_data(is_published="on"))
        self.assertRedirects(response, "/team/")
        self.assertTrue(models.Publication.objects.get(slug="test-publication").is_published)

    def test_profile_editor_cannot_change_role_visibility_or_access(self):
        user = self.user(roles=("Team profiles",))
        person = models.TeamMember.objects.filter(section="team").first()
        person.owner = user
        person.save()
        role = person.role
        self.client.force_login(user)
        response = self.client.post(f"/team/people/{person.pk}/", {"name": "Updated name", "biography": "Updated biography", "role": "Administrator", "is_active": "", "owner": ""})
        self.assertRedirects(response, "/team/")
        person.refresh_from_db()
        self.assertEqual(person.name, "Updated name")
        self.assertEqual(person.role, role)
        self.assertEqual(person.owner, user)
        self.assertTrue(person.is_active)
        self.assertEqual(self.client.get("/team/people/new/").status_code, 403)

    def test_csrf_is_enforced_for_contact_newsletter_survey_and_login(self):
        client = Client(enforce_csrf_checks=True)
        for path in ["/contact/send/", "/contact.php", "/newsletter.php", "/api/survey.php", "/team/login/"]:
            self.assertEqual(client.post(path, {"email": "a@example.org"}).status_code, 403)
        client.get("/")
        token = client.cookies["csrftoken"].value
        for _ in range(2):
            response = client.post("/newsletter.php", {"email": "A@example.org"}, HTTP_X_CSRFTOKEN=token)
            self.assertTrue(response.json()["success"])
        self.assertEqual(models.NewsletterSubscriber.objects.count(), 1)
        self.assertEqual(client.post("/newsletter.php", {"email": "bad"}, HTTP_X_CSRFTOKEN=token).status_code, 422)
        self.assertContains(client.get("/about/"), 'action="/contact/send/"')
        response = client.post("/contact/send/", {"name": "Visitor", "email": "v@example.org", "message": "Hello", "csrfmiddlewaretoken": token})
        self.assertEqual(response.url, "/about/?status=sent#contact-us")
        self.assertEqual(models.ContactMessage.objects.count(), 1)

    def test_survey_validation_snapshots_and_duplicate_protection(self):
        self.client.get("/survey.php")
        session = self.client.session
        session["survey_started"] = time.time() - 10
        session.save()
        response = self.client.post("/api/survey.php", {})
        self.assertEqual(response.status_code, 422)
        self.assertIn("q1", response.json()["errors"])
        data = {}
        for q in models.SurveyQuestion.objects.filter(required=True):
            data[q.key + "[]" if q.type == "checkbox" else q.key] = [q.options[0]] if q.type == "checkbox" else (q.options[0] if q.options else "Test institution")
        self.assertTrue(self.client.post("/api/survey.php", data).json()["success"])
        response = models.SurveyResponse.objects.get()
        self.assertEqual(len(response.question_snapshot), 13)
        self.assertIsInstance(response.answers["q10"], list)
        self.assertEqual(self.client.post("/api/survey.php", data).status_code, 409)
        self.assertEqual(models.SurveyResponse.objects.count(), 1)

    def test_invalid_images_and_links_are_rejected(self):
        for url in ["javascript:alert(1)", "//evil.example.org", "data:text/html,attack", "https://example.org/\\evil", "java\nscript:alert(1)"]:
            with self.subTest(url=url), self.assertRaises(ValidationError):
                validate_link(url)
        data = self.publication_data()
        form = PublicationForm(data, files={"cover": SimpleUploadedFile("photo.png", b"not an image", content_type="image/png")})
        self.assertFalse(form.is_valid())
        self.assertIn("cover", form.errors)
        self.assertNotIn('href="javascript:', str(rich_text('<a href="javascript:alert(1)">bad</a>')))

    def test_login_and_public_forms_are_rate_limited(self):
        for _ in range(20):
            response = self.client.post("/team/login/", {"username": "missing", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post("/team/login/", {"username": "missing", "password": "wrong"}).status_code, 429)
        for _ in range(20):
            self.client.post("/newsletter.php", {"email": "a@example.org"})
        self.assertEqual(self.client.post("/newsletter.php", {"email": "a@example.org"}).status_code, 429)

    def export(self, tables):
        file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"format": "earg-legacy-v1", "tables": tables}, file)
        file.close()
        self.addCleanup(Path(file.name).unlink)
        return file.name

    def test_import_is_idempotent_and_dry_run_rolls_back(self):
        file = self.export({"publications": [{"id": "9", "title": "Legacy blog", "slug": "legacy-blog", "publication_type": "Blog", "is_published": "1", "full_content": "<p>Imported</p>", "gallery_images": '["assets/uploads/publications/photo.jpg"]', "created_at": "2026-01-01 12:00:00"}],
            "opportunities": [{"id": "3", "title": "Legacy scholarship", "slug": "legacy-scholarship", "category": "Scholarship", "is_published": "1", "deadline": None}],
            "founder_story": [{"id": "1", "founder_name": "Founder", "is_published": "1", "sections": '[{"heading":"History","body":"<p>History text</p>"}]'}],
            "contact_messages": [{"id": "2", "full_name": "Visitor", "email": "v@example.org", "message": "Hello", "status": "Archived", "subject": None}],
            "newsletter_subscribers": [{"email": "a@example.org", "created_at": "2026-01-01 12:00:00"}],
            "survey_responses": [{"id": "12", "submitted_at": "2026-01-01 12:00:00"}], "survey_answers": [{"response_id": "12", "question_key": "q10", "value": "Other"}]})
        call_command("import_legacy", file, dry_run=True, stdout=io.StringIO())
        self.assertFalse(models.Publication.objects.exists())
        for _ in range(2):
            call_command("import_legacy", file, stdout=io.StringIO())
        self.assertEqual(models.Publication.objects.count(), 1)
        self.assertEqual(models.PublicationImage.objects.count(), 1)
        self.assertEqual(models.Opportunity.objects.count(), 1)
        self.assertEqual(models.StorySection.objects.count(), 1)
        self.assertEqual(models.NewsletterSubscriber.objects.count(), 1)
        self.assertTrue(models.ContactMessage.objects.get().is_archived)
        self.assertEqual(models.SurveyResponse.objects.get().answers["q10"], ["Other"])
        self.assertEqual(models.Publication.objects.get().created_at.year, 2026)
        self.assertContains(self.client.get("/publication.php?slug=legacy-blog"), "Imported")

    def test_import_failure_rolls_back_all_records(self):
        file = self.export({"publications": [{"id": 1, "title": "Valid", "slug": "valid", "publication_type": "Blog"}, {"id": 2, "title": "Invalid", "slug": "invalid", "publication_type": "Blog", "document_link": "javascript:attack"}]})
        with self.assertRaises(CommandError):
            call_command("import_legacy", file, stdout=io.StringIO())
        self.assertEqual(models.Publication.objects.count(), 0)

    def test_superuser_can_use_all_content_admin_and_formatted_editors(self):
        user = User.objects.create_superuser("admin", "admin@example.org", "Admin-password-4931")
        self.client.force_login(user)
        for path in ["/admin/", "/admin/website/contentblock/", "/admin/website/publication/add/", "/admin/website/founderstory/add/", "/admin/website/survey/1/change/"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertContains(self.client.get("/admin/website/publication/add/"), "data-editor")

    def test_survey_statistics_csv_and_search_engines(self):
        survey = models.Survey.objects.get()
        response = models.SurveyResponse.objects.create(survey=survey, answers={"q1": "20–24", "q10": ["Other"], "q12": "=formula"}, question_snapshot=[{"key": "q1", "title": "Age group", "type": "radio"}, {"key": "q10", "title": "Support", "type": "checkbox"}])
        self.assertEqual(self.client.get("/admin/website/surveyresponse/stats/").status_code, 302)
        admin_user = User.objects.create_superuser("admin", "admin@example.org", "Admin-password-4931")
        self.client.force_login(admin_user)
        report = self.client.get("/admin/website/surveyresponse/stats/")
        self.assertContains(report, "Age group")
        self.assertContains(report, "1 response")
        export = self.client.post("/admin/website/surveyresponse/", {"action": "export_answers", "_selected_action": [response.pk]})
        self.assertEqual(export["Content-Type"], "text/csv")
        self.assertIn("q1,q10,q12", export.content.decode())
        self.assertIn("'=formula", export.content.decode())
        self.assertContains(self.client.get("/robots.txt"), "Disallow: /team/")
        self.assertContains(self.client.get("/sitemap.xml"), "http://testserver/about.php")

    def test_footer_corrections_on_every_public_page(self):
        models.FounderStory.objects.create(founder_name="Founder", is_published=True)
        models.Publication.objects.create(title="Blog", slug="blog", publication_type="Blog", is_published=True)
        models.Opportunity.objects.create(title="Award", slug="award", category="Scholarship", is_published=True)
        for path in ["/", "/about.php", "/programs.php", "/publications.php", "/events.php", "/survey.php", "/founder-story.php", "/publication.php?slug=blog", "/opportunity.php?slug=award"]:
            with self.subTest(path=path):
                page = self.client.get(path)
                self.assertContains(page, '<span class="footer-placeholder">Facebook</span>', html=True)
                self.assertNotContains(page, '>Facebook</a>')
                self.assertContains(page, 'href="https://www.linkedin.com/company/ea-research-group/"')
                self.assertContains(page, 'href="https://youtube.com/@earesearchgrp24?si=FRm8RPLxO82BLVHR"')
        story = self.client.get("/founder-story.php")
        self.assertContains(story, '<p class="founder-story-label">Founder\'s Story</p>', html=True)

    def test_complete_survey_submission_with_csrf_persists_all_answer_types(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get("/survey/")
        self.assertContains(page, "csrfmiddlewaretoken")
        token = client.cookies["csrftoken"].value
        session = client.session
        session["survey_started"] = time.time() - 10
        session.save()
        answers = {"csrfmiddlewaretoken": token}
        for q in models.SurveyQuestion.objects.all():
            if q.type == "checkbox":
                answers[q.key + "[]"] = [q.options[0]]
                if q.other:
                    answers[q.key + "[]"].append("Other")
                    answers[q.key + "_other"] = "Additional support"
            elif q.type == "radio":
                answers[q.key] = q.options[0]
            elif q.type == "scale":
                answers[q.key] = str(q.max)
            else:
                answers[q.key] = "A test response"
        self.assertEqual(client.post("/api/survey.php", {k: v for k, v in answers.items() if k != "csrfmiddlewaretoken"}).status_code, 403)
        self.assertEqual(models.SurveyResponse.objects.count(), 0)
        response = client.post("/api/survey.php", answers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        saved = models.SurveyResponse.objects.get()
        self.assertEqual(saved.answers["q3"], "A test response")
        self.assertEqual(saved.answers["q6"], "10")
        self.assertIsInstance(saved.answers["q10"], list)
        self.assertEqual(saved.answers["q11_other"], "Additional support")
        self.assertEqual(len(saved.question_snapshot), 13)
        self.assertEqual(client.post("/api/survey.php", answers).status_code, 409)
        self.assertEqual(models.SurveyResponse.objects.count(), 1)
