import csv
import json
from collections import Counter
from django import forms
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path
from . import models
from .widgets import RichTextWidget

class RichTextAdminMixin:
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in {"full_content", "full_description", "body"}:
            kwargs["widget"] = RichTextWidget()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

class EARGAdminSite(admin.AdminSite):
    site_header = "EA Research Group administration"
    site_title = "EARG admin"
    index_title = "Content, people and access"
    def has_permission(self, request):
        return request.user.is_active and request.user.is_staff and request.user.is_superuser

site = EARGAdminSite(name="admin")
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
site.register(User, UserAdmin)
site.register(Group, GroupAdmin)

class AssignedAdmin(RichTextAdminMixin, admin.ModelAdmin):
    autocomplete_fields = ["owner", "editor_group"]
    save_on_top = True

@admin.register(models.ContentBlock, site=site)
class ContentBlockAdmin(AssignedAdmin):
    list_display = ["label", "page", "kind", "owner", "editor_group"]
    list_filter = ["page", "kind"]
    search_fields = ["label", "key", "value"]
    readonly_fields = ["key", "page", "kind"]
    def get_queryset(self, request):
        return super().get_queryset(request).exclude(page="system")
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(models.HeroSlide, site=site)
class HeroSlideAdmin(AssignedAdmin):
    list_display = ["title", "order", "is_active"]
    list_editable = ["order", "is_active"]

@admin.register(models.TeamMember, site=site)
class TeamMemberAdmin(AssignedAdmin):
    list_display = ["name", "role", "section", "order", "is_active", "owner"]
    list_filter = ["section", "is_active"]
    list_editable = ["order", "is_active"]
    search_fields = ["name", "role"]

@admin.register(models.NavigationLink, site=site)
class NavigationAdmin(admin.ModelAdmin):
    list_display = ["label", "location", "parent", "order", "is_active", "is_disabled"]
    list_filter = ["location"]
    list_editable = ["order", "is_active", "is_disabled"]

class PublicationImageInline(admin.TabularInline):
    model = models.PublicationImage
    extra = 1

@admin.register(models.Publication, site=site)
class PublicationAdmin(AssignedAdmin):
    list_display = ["title", "publication_type", "author", "is_published", "is_featured", "owner"]
    list_filter = ["publication_type", "is_published"]
    search_fields = ["title", "author", "summary"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [PublicationImageInline]

@admin.register(models.Opportunity, site=site)
class OpportunityAdmin(AssignedAdmin):
    list_display = ["title", "category", "status", "deadline", "is_published", "owner"]
    list_filter = ["category", "status", "is_published"]
    search_fields = ["title", "summary"]
    prepopulated_fields = {"slug": ("title",)}

class StorySectionInline(RichTextAdminMixin, admin.StackedInline):
    model = models.StorySection
    extra = 1

@admin.register(models.FounderStory, site=site)
class FounderStoryAdmin(admin.ModelAdmin):
    inlines = [StorySectionInline]
    list_display = ["founder_name", "role_title", "is_published"]
    def has_add_permission(self, request):
        return not models.FounderStory.objects.exists()

@admin.register(models.Event, site=site)
class EventAdmin(AssignedAdmin):
    list_display = ["title", "starts_at", "is_published", "owner"]
    prepopulated_fields = {"slug": ("title",)}

def csv_cell(value):
    value = str(value or "")
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

@admin.action(description="Export selected records as CSV")
def export_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="earg-export.csv"'
    writer = csv.writer(response)
    fields = [f for f in queryset.model._meta.fields if f.name not in {"legacy_id"}]
    writer.writerow([f.verbose_name for f in fields])
    for obj in queryset.iterator():
        writer.writerow([csv_cell(json.dumps(getattr(obj, f.name), ensure_ascii=False) if isinstance(getattr(obj, f.name), (dict, list)) else getattr(obj, f.name)) for f in fields])
    return response

@admin.register(models.ContactMessage, site=site)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "created_at", "is_read", "is_archived"]
    list_editable = ["is_read", "is_archived"]
    list_filter = ["is_read", "is_archived"]
    search_fields = ["full_name", "email", "message"]
    readonly_fields = ["full_name", "email", "subject", "message", "created_at", "legacy_id"]
    actions = [export_csv]
    def has_add_permission(self, request):
        return False

@admin.register(models.NewsletterSubscriber, site=site)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "subscribed_at"]
    search_fields = ["email"]
    actions = [export_csv]

class QuestionInline(admin.StackedInline):
    model = models.SurveyQuestion
    extra = 0

@admin.register(models.Survey, site=site)
class SurveyAdmin(admin.ModelAdmin):
    inlines = [QuestionInline]
    list_display = ["title", "slug", "is_active"]

@admin.register(models.SurveyResponse, site=site)
class SurveyResponseAdmin(admin.ModelAdmin):
    change_list_template = "admin/survey_response_list.html"
    list_display = ["id", "survey", "submitted_at"]
    list_filter = ["survey"]
    readonly_fields = ["survey", "answers", "question_snapshot", "submitted_at", "legacy_id"]
    actions = ["export_answers"]
    def has_add_permission(self, request):
        return False
    @admin.action(description="Export selected survey responses as CSV")
    def export_answers(self, request, queryset):
        responses = list(queryset)
        keys = sorted({key for response in responses for key in response.answers}, key=lambda key: (int(''.join(filter(str.isdigit, key)) or 0), key))
        output = HttpResponse(content_type="text/csv")
        output["Content-Disposition"] = 'attachment; filename="survey-responses.csv"'
        writer = csv.writer(output)
        writer.writerow(["response_id", "submitted_at", *keys])
        for response in responses:
            values = [response.answers.get(key, "") for key in keys]
            writer.writerow([response.pk, response.submitted_at.isoformat(), *[csv_cell("; ".join(value) if isinstance(value, list) else value) for value in values]])
        return output
    def get_urls(self):
        return [path("stats/", self.admin_site.admin_view(self.statistics), name="website_surveyresponse_stats")] + super().get_urls()
    def statistics(self, request):
        class FilterForm(forms.Form):
            start = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
            end = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
        form = FilterForm(request.GET)
        responses = models.SurveyResponse.objects.select_related("survey").all()
        if form.is_valid():
            if form.cleaned_data["start"]:
                responses = responses.filter(submitted_at__date__gte=form.cleaned_data["start"])
            if form.cleaned_data["end"]:
                responses = responses.filter(submitted_at__date__lte=form.cleaned_data["end"])
        elif request.GET:
            responses = responses.none()
        # Historical snapshots keep archived/renamed questions understandable.
        buckets = {}
        total = 0
        for response in responses.iterator():
            total += 1
            definitions = {q["key"]: q for q in response.question_snapshot}
            for key, value in response.answers.items():
                definition = definitions.get(key, {})
                if definition.get("type") not in {"radio", "checkbox", "scale"}:
                    continue
                bucket_key = (response.survey_id, key, definition.get("title", key))
                bucket = buckets.setdefault(bucket_key, {"title": definition.get("title", key), "survey": str(response.survey), "counts": Counter()})
                bucket["counts"].update(value if isinstance(value, list) else [value])
        charts = [{"title": value["title"], "survey": value["survey"], "labels": list(value["counts"]), "values": list(value["counts"].values())} for value in buckets.values()]
        return render(request, "admin/survey_statistics.html", {**self.admin_site.each_context(request), "title": "Survey statistics", "form": form, "total": total, "charts": charts})
