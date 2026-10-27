import json
import time
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.forms import inlineformset_factory
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from . import models
from .access import assigned_to, can_publish
from .content import image_url, public_url
from .forms import ContactForm, NewsletterForm, PublicationForm, OpportunityForm, TeamMemberForm, ContentBlockForm, HeroSlideForm, EventForm
from .limits import allow_request
from .search import matching_items
from .seo import ABOUT_PATHS, ABOUT_SECTIONS, FOUNDER_PATH

class TeamLoginView(LoginView):
    template_name = "team/login.html"
    def post(self, request, *args, **kwargs):
        if not allow_request(request, "team-login", 20, seconds=300):
            form = self.get_form()
            form.add_error(None, "Too many sign-in attempts. Please try again in five minutes.")
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

@require_GET
@ensure_csrf_cookie
def page(request, name="index", section=None):
    context = {}
    if name == "about":
        people = models.TeamMember.objects.filter(is_active=True)
        context = {"board_members": people.filter(section="board"), "team_members": people.filter(section="team"),
                   "advisory_members": people.filter(section="advisory"),
                   "standalone_section": section, "initial_route": section or "who-we-are",
                   "section_title": ABOUT_SECTIONS.get(section, "")}
    if name == "events":
        context["events"] = models.Event.objects.filter(is_published=True)
        context["noindex"] = not context["events"].exists()
    if name == "programs":
        # This retained route is still the old Publications placeholder.
        context["noindex"] = True
    if name == "publications":
        context["noindex"] = not (models.Publication.objects.filter(is_published=True).exists() or models.Opportunity.objects.filter(is_published=True).exists())
    return render(request, f"pages/{name}.html", context)

@require_GET
def hero_slides(request):
    return JsonResponse([{"src": image_url(x.image, x.image_path), "position": x.position, "alt": x.title}
                         for x in models.HeroSlide.objects.filter(is_active=True)], safe=False)

@require_GET
def publications_api(request):
    items = models.Publication.objects.filter(is_published=True)
    kind = request.GET.get("type", "")
    if kind:
        if kind not in {"Blog", "Newsletter", "Report"}:
            return JsonResponse({"success": False, "publications": [], "message": "Invalid publication type."}, status=422)
        items = items.filter(publication_type=kind)
    items = items.order_by("-is_featured", F("publication_date").desc(nulls_last=True), "-created_at")
    data = [{"title": p.title, "slug": p.slug, "publication_type": p.publication_type, "summary": p.summary,
             "author": p.author, "publication_date": p.publication_date, "cover_image": image_url(p.cover, p.cover_image),
             "document_link": public_url(p.document_link), "is_featured": p.is_featured, "created_at": p.created_at} for p in items]
    return JsonResponse({"success": True, "count": len(data), "publications": data})

@require_GET
def opportunities_api(request):
    items = models.Opportunity.objects.filter(is_published=True).order_by("-is_featured", F("deadline").asc(nulls_last=True), "-created_at")
    data = list(items.values("title", "slug", "category", "summary", "deadline", "status", "country", "host_organization", "application_link", "is_featured", "created_at"))
    for row in data:
        row["application_link"] = public_url(row["application_link"])
    return JsonResponse({"success": True, "count": len(data), "opportunities": data})

@require_GET
def publication(request, slug=None):
    item = get_object_or_404(models.Publication, slug=slug or request.GET.get("slug", ""), is_published=True)
    gallery = [image_url(x.image, x.image_path) for x in item.images.all()]
    cover = image_url(item.cover, item.cover_image)
    lightbox = gallery or ([cover] if cover else [])
    return render(request, "pages/publication.html", {"publication": item, "gallery": gallery, "cover_url": cover,
        "lightboxImages": lightbox, "lightbox_json": json.dumps(lightbox), "publication_type_json": json.dumps(item.publication_type)})

@require_GET
def opportunity(request, slug=None):
    return render(request, "pages/opportunity.html", {"opportunity": get_object_or_404(models.Opportunity,
        slug=slug or request.GET.get("slug", ""), is_published=True)})

@require_GET
def founder_story(request):
    story = models.FounderStory.objects.filter(is_published=True).first()
    return render(request, "pages/founder-story.html", {"story": story, "sections": story.sections.all() if story else [],
        "errorMessage": "The founder story is not available yet."}, status=200 if story else 404)

@require_POST
def contact(request):
    if not allow_request(request, "contact", 15):
        return redirect("/about/?status=error#contact-us")
    form = ContactForm(request.POST)
    if form.is_valid():
        models.ContactMessage.objects.create(full_name=form.cleaned_data["name"], email=form.cleaned_data["email"], message=form.cleaned_data["message"])
        return redirect("/about/?status=sent#contact-us")
    return redirect("/about/?status=error#contact-us")

@require_POST
def newsletter(request):
    if not allow_request(request, "newsletter", 20):
        return JsonResponse({"success": False, "message": "Please try again later."}, status=429)
    form = NewsletterForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"success": False, "message": "Please enter a valid email address."}, status=422)
    models.NewsletterSubscriber.objects.get_or_create(email=form.cleaned_data["email"].lower())
    return JsonResponse({"success": True, "message": "Thank you for subscribing!"})

@require_GET
@ensure_csrf_cookie
def survey(request):
    item = get_object_or_404(models.Survey, slug="mentorship", is_active=True)
    request.session.setdefault("survey_started", time.time())
    questions = list(item.questions.all())
    for question in questions:
        question.scale_values = range(question.min, question.max + 1)
    return render(request, "pages/survey.html", {"meta": item, "questions": questions, "alreadySubmitted": bool(request.session.get(f"survey_done_{item.pk}"))})

@require_POST
def survey_submit(request):
    item = get_object_or_404(models.Survey, slug="mentorship", is_active=True)
    if not allow_request(request, "survey", 30):
        return JsonResponse({"success": False, "message": "Please try again later."}, status=429)
    if request.session.get(f"survey_done_{item.pk}"):
        return JsonResponse({"success": False, "message": "You have already submitted this survey."}, status=409)
    if request.POST.get("website") or time.time() - request.session.get("survey_started", time.time()) < 3:
        return JsonResponse({"success": False, "message": "Please take a moment to complete the survey, then try again."}, status=422)
    errors, answers, snapshot = {}, {}, []
    for q in item.questions.all():
        key = q.key
        snapshot.append({"key": key, "title": q.title, "type": q.type, "options": q.options})
        if q.type == "checkbox":
            value = list(dict.fromkeys(request.POST.getlist(key + "[]")))
            allowed = q.options + (["Other"] if q.other else [])
            if any(v not in allowed for v in value):
                errors[key] = "Please choose from the listed options."
            if q.other and "Other" in value:
                other = request.POST.get(key + "_other", "").strip()
                if not other or len(other) > q.other_maxlength:
                    errors[key] = "Please describe your Other answer within the length limit."
                else:
                    answers[key + "_other"] = other
        else:
            value = request.POST.get(key, "").strip()
            if value and q.type == "radio" and value not in q.options:
                errors[key] = "Please choose one of the listed options."
            if value and q.type == "scale" and (not value.isdecimal() or not q.min <= int(value) <= q.max):
                errors[key] = "Please choose a value from the scale."
            if len(value) > q.maxlength:
                errors[key] = f"Please keep your answer under {q.maxlength} characters."
        if q.required and not value:
            errors[key] = "This question is required."
        if value:
            answers[key] = value
    if errors:
        return JsonResponse({"success": False, "message": "Please check the highlighted questions.", "errors": errors}, status=422)
    models.SurveyResponse.objects.create(survey=item, answers=answers, question_snapshot=snapshot)
    request.session[f"survey_done_{item.pk}"] = True
    return JsonResponse({"success": True, "message": "Thank you! Your response has been recorded."})

TEAM_TYPES = {
    "publications": (models.Publication, PublicationForm, True),
    "opportunities": (models.Opportunity, OpportunityForm, True),
    "people": (models.TeamMember, TeamMemberForm, False),
    "content": (models.ContentBlock, ContentBlockForm, False),
    "hero": (models.HeroSlide, HeroSlideForm, False),
    "events": (models.Event, EventForm, True),
}

@require_GET
def robots(request):
    return HttpResponse("User-agent: *\nDisallow: /admin/\nDisallow: /team/\nSitemap: " + request.build_absolute_uri("/sitemap.xml") + "\n", content_type="text/plain")

@require_GET
def sitemap(request):
    from urllib.parse import urlencode
    paths = ["/", ABOUT_PATHS["who-we-are"], ABOUT_PATHS["contact-us"]]
    if models.TeamMember.objects.filter(section="board", is_active=True).exists():
        paths.append(ABOUT_PATHS["governing-board"])
    if models.TeamMember.objects.filter(section="team", is_active=True).exists():
        paths.append(ABOUT_PATHS["our-team"])
    if models.FounderStory.objects.filter(is_published=True).exists():
        paths.append(FOUNDER_PATH)
    publications = models.Publication.objects.filter(is_published=True)
    opportunities = models.Opportunity.objects.filter(is_published=True)
    if publications.exists() or opportunities.exists():
        paths.append("/publications.php")
    if models.Event.objects.filter(is_published=True).exists():
        paths.append("/events.php")
    # List one address per page, using the URLs existing search results used.
    paths += ["/publication.php?" + urlencode({"slug": slug}) for slug in publications.values_list("slug", flat=True)]
    paths += ["/opportunity.php?" + urlencode({"slug": slug}) for slug in opportunities.values_list("slug", flat=True)]
    return render(request, "sitemap.xml", {"locations": [request.build_absolute_uri(path) for path in paths]}, content_type="application/xml")

def type_config(kind):
    if kind not in TEAM_TYPES:
        from django.http import Http404
        raise Http404
    return TEAM_TYPES[kind]

@login_required
def team_dashboard(request):
    query = " ".join(request.GET.get("q", "").split())[:200]
    sections = []
    result_count = 0
    for kind, (model, form, allow_create) in TEAM_TYPES.items():
        if request.user.has_perm(f"website.change_{model._meta.model_name}") or request.user.has_perm(f"website.view_{model._meta.model_name}"):
            items = assigned_to(request.user, model)
            if query:
                items = matching_items(items, kind, query)
                result_count += len(items)
                if not items:
                    continue
            sections.append({"kind": kind, "label": str(model._meta.verbose_name_plural).title(), "items": items,
                "can_add": allow_create and request.user.has_perm(f"website.add_{model._meta.model_name}")})
    return render(request, "team/dashboard.html", {"sections": sections, "query": query, "result_count": result_count})

@login_required
def team_edit(request, kind, pk=None):
    model, form_class, allow_create = type_config(kind)
    permission = "change" if pk else "add"
    if not request.user.has_perm(f"website.{permission}_{model._meta.model_name}") or (not pk and not allow_create):
        raise PermissionDenied
    obj = get_object_or_404(assigned_to(request.user, model), pk=pk) if pk else model(owner=request.user)
    publisher = can_publish(request.user, model) if hasattr(obj, "is_published") else False
    form = form_class(request.POST or None, request.FILES or None, instance=obj)
    if isinstance(obj, models.ContentBlock):
        if obj.kind != "image":
            form.fields.pop("image")
        form.fields["value"].label = obj.label
    if publisher:
        form.fields["is_published"] = forms.BooleanField(required=False, initial=obj.is_published, label="Publish")
    images = None
    if model is models.Publication:
        formset = inlineformset_factory(models.Publication, models.PublicationImage, fields=["image", "image_path", "order"], extra=1)
        images = formset(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST":
        valid_form = form.is_valid()
        valid_images = images.is_valid() if images is not None else True
        if valid_form and valid_images:
            with transaction.atomic():
                obj = form.save(commit=False)
                if hasattr(obj, "is_published"):
                    obj.is_published = form.cleaned_data.get("is_published", False) if publisher else False
                obj.save()
                if images is not None:
                    images.instance = obj
                    images.save()
            messages.success(request, "Saved." if not hasattr(obj, "is_published") or obj.is_published else "Saved as a draft for administrator review.")
            return redirect("team-dashboard")
    return render(request, "team/edit.html", {"form": form, "images": images, "item": obj, "kind": kind,
        "draft_only": hasattr(obj, "is_published") and not publisher})
