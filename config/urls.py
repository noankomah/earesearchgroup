from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import path
from website import views
from website.admin import site

urlpatterns = [
    path("admin/", site.urls),
    path("", views.page, name="home"),
    path("robots.txt", views.robots),
    path("sitemap.xml", views.sitemap),
    path("api/hero/", views.hero_slides, name="hero-slides"),
    path("api/publications.php", views.publications_api),
    path("api/opportunities.php", views.opportunities_api),
    path("api/survey.php", views.survey_submit),
    path("publication.php", views.publication),
    path("opportunity.php", views.opportunity),
    path("publications/<slug:slug>/", views.publication, name="publication-detail"),
    path("opportunities/<slug:slug>/", views.opportunity, name="opportunity-detail"),
    path("founder-story.php", views.founder_story),
    path("founder-story/", views.founder_story, name="founder-story"),
    path("views/About/who-we-are.php", views.page, {"name": "about", "section": "who-we-are"}, name="legacy-who-we-are"),
    path("views/About/governing-board.php", views.page, {"name": "about", "section": "governing-board"}, name="legacy-governing-board"),
    path("views/About/our-team.php", views.page, {"name": "about", "section": "our-team"}, name="legacy-our-team"),
    path("views/About/contact-us.php", views.page, {"name": "about", "section": "contact-us"}, name="legacy-contact-us"),
    path("views/About/founder-story.php", views.founder_story, name="legacy-founder-story"),
    path("contact.php", views.contact),
    path("contact/send/", views.contact, name="contact-submit"),
    path("newsletter.php", views.newsletter),
    path("survey.php", views.survey),
    path("survey/", views.survey, name="survey"),
    path("team/login/", views.TeamLoginView.as_view(), name="login"),
    path("team/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("team/password/", auth_views.PasswordChangeView.as_view(template_name="team/password.html", success_url="/team/"), name="password-change"),
    path("team/", views.team_dashboard, name="team-dashboard"),
    path("team/<slug:kind>/new/", views.team_edit, name="team-create"),
    path("team/<slug:kind>/<int:pk>/", views.team_edit, name="team-edit"),
]
for name in ["index", "about", "programs", "publications", "events"]:
    urlpatterns.append(path(f"{name}.php", views.page, {"name": name}))
    if name != "index":
        urlpatterns.append(path(f"{name}/", views.page, {"name": name}, name=name))
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
