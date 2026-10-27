import io
from html.parser import HTMLParser
from xml.etree import ElementTree
from django.core.management import call_command
from django.test import TestCase, override_settings
from . import models
from .seo import ABOUT_PATHS, ABOUT_SECTIONS, FOUNDER_PATH


class PageDetails(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.sections = []
        self.canonicals = []
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == "section" and "data-route" in attributes:
            self.sections.append(attributes)
        if tag == "link" and attributes.get("rel") == "canonical":
            self.canonicals.append(attributes["href"])


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class IndexedUrlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_site", stdout=io.StringIO())

    def locations(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        return [element.text for element in ElementTree.fromstring(response.content).findall("{*}url/{*}loc")]

    def test_previously_indexed_about_urls_render_the_correct_page_without_javascript(self):
        for section, path in ABOUT_PATHS.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f"<title>{ABOUT_SECTIONS[section]} | EA Research Group</title>", html=True)
                details = PageDetails(response.content.decode())
                self.assertEqual(len(details.sections), 1)
                self.assertEqual(details.sections[0]["data-route"], section)
                self.assertNotIn("hidden", details.sections[0])
                self.assertIn("is-active", details.sections[0]["class"])
                self.assertEqual(details.canonicals, ["http://testserver" + path])

    def test_old_founder_url_serves_the_story_and_unavailable_story_remains_a_true_404(self):
        self.assertEqual(self.client.get(FOUNDER_PATH).status_code, 404)
        story = models.FounderStory.objects.create(founder_name="Existing founder", is_published=True)
        models.StorySection.objects.create(story=story, heading="History", body="<p>Original founder content</p>")
        response = self.client.get(FOUNDER_PATH)
        self.assertContains(response, "Original founder content")
        self.assertEqual(PageDetails(response.content.decode()).canonicals, ["http://testserver" + FOUNDER_PATH])
        story.is_published = False
        story.save()
        self.assertEqual(self.client.get(FOUNDER_PATH).status_code, 404)

    def test_existing_hash_based_about_views_remain_available(self):
        for path in ["/about/", "/about.php"]:
            response = self.client.get(path)
            details = PageDetails(response.content.decode())
            self.assertEqual(len(details.sections), 4)
            self.assertEqual(details.sections[0]["data-route"], "who-we-are")
            self.assertNotIn("hidden", details.sections[0])
            self.assertTrue(all("hidden" in section for section in details.sections[1:]))
            self.assertEqual(details.canonicals, ["http://testserver" + ABOUT_PATHS["who-we-are"]])
            self.assertContains(response, 'window.addEventListener("hashchange"')

    def test_clean_and_query_string_article_addresses_share_the_existing_canonical(self):
        models.Publication.objects.create(title="Existing publication", slug="existing-article", publication_type="Blog", is_published=True)
        models.Opportunity.objects.create(title="Existing opportunity", slug="existing-award", category="Scholarship", is_published=True)
        for path, canonical in [
            ("/publications/existing-article/", "/publication.php?slug=existing-article"),
            ("/publication.php?slug=existing-article&utm_source=mail", "/publication.php?slug=existing-article"),
            ("/opportunities/existing-award/", "/opportunity.php?slug=existing-award"),
            ("/opportunity.php?slug=existing-award&utm_source=mail", "/opportunity.php?slug=existing-award"),
        ]:
            with self.subTest(path=path):
                response = self.client.get(path, secure=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(PageDetails(response.content.decode()).canonicals, ["https://testserver" + canonical])

    def test_public_aliases_point_to_the_old_canonical_page_address(self):
        story = models.FounderStory.objects.create(founder_name="Founder", is_published=True)
        for path, canonical in [("/index.php", "/"), ("/publications/", "/publications.php"), ("/events/", "/events.php"), ("/programs/", "/programs.php"), ("/founder-story/", FOUNDER_PATH), ("/founder-story.php", FOUNDER_PATH)]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(PageDetails(response.content.decode()).canonicals, ["http://testserver" + canonical])

    def test_sitemap_retains_meaningful_original_addresses_and_omits_empty_pages(self):
        locations = self.locations()
        expected = ["/", *ABOUT_PATHS.values()]
        self.assertCountEqual(locations, ["http://testserver" + path for path in expected])
        self.assertNotIn("http://testserver/events.php", locations)
        self.assertNotIn("http://testserver/programs.php", locations)
        self.assertNotIn("http://testserver/publications.php", locations)
        self.assertNotIn("http://testserver" + FOUNDER_PATH, locations)
        for path in ["/programs.php", "/events.php", "/publications.php"]:
            self.assertContains(self.client.get(path), '<meta name="robots" content="noindex, follow">', html=True)

    def test_sitemap_only_adds_published_content_at_existing_addresses(self):
        models.FounderStory.objects.create(founder_name="Founder", is_published=True)
        models.Event.objects.create(title="Event", slug="event", is_published=True)
        models.Publication.objects.create(title="Article", slug="article", publication_type="Blog", is_published=True)
        models.Opportunity.objects.create(title="Award", slug="award", category="Scholarship", is_published=True)
        models.Publication.objects.create(title="Unpublished", slug="draft", publication_type="Blog")
        locations = self.locations()
        for path in [FOUNDER_PATH, "/events.php", "/publications.php", "/publication.php?slug=article", "/opportunity.php?slug=award"]:
            self.assertIn("http://testserver" + path, locations)
        self.assertFalse(any("draft" in path or "/publications/article/" in path for path in locations))
        self.assertNotContains(self.client.get("/events.php"), 'content="noindex, follow"')
        self.assertNotContains(self.client.get("/publications.php"), 'content="noindex, follow"')
        for location in locations:
            path = location.removeprefix("http://testserver")
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_public_navigation_uses_old_about_addresses(self):
        response = self.client.get("/")
        for path in [*ABOUT_PATHS.values(), FOUNDER_PATH]:
            self.assertContains(response, f'href="{path}"')
        self.assertNotContains(response, 'href="/about.php#')
        self.assertNotContains(response, 'href="/founder-story.php"')

    def test_unknown_and_unpublished_urls_do_not_redirect_to_the_homepage(self):
        for path in ["/views/About/missing.php", "/not-a-page/", "/publication.php?slug=missing", "/opportunity.php?slug=missing"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("Location", response)

    def test_unrelated_old_hosting_spam_urls_stay_missing_for_users_and_googlebot(self):
        paths = [
            "/brand/manufacture/f621brqbroigx4z.htm",
            "/species/accessory/fk20brqbr2igb4z.htm",
            "/taxonomy/byproduct/eqit3v69jf64usn.htm",
            "/population/option/fc6wrjub7makjkr.htm",
        ]
        locations = self.locations()
        for path in paths:
            for agent in ("Mozilla/5.0", "Googlebot"):
                with self.subTest(path=path, agent=agent):
                    response = self.client.get(path, HTTP_USER_AGENT=agent)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn("Location", response)
            self.assertFalse(any(path in location for location in locations))
