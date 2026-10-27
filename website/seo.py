"""Stable public addresses retained from the previously indexed PHP website."""
from urllib.parse import urlencode, urlsplit

ABOUT_SECTIONS = {
    "who-we-are": "Who We Are",
    "governing-board": "Governing Board",
    "our-team": "Our Team",
    "contact-us": "Contact Us",
}
ABOUT_PATHS = {section: f"/views/About/{section}.php" for section in ABOUT_SECTIONS}
FOUNDER_PATH = "/views/About/founder-story.php"


def stable_internal_link(value):
    """Use stable page paths without changing an editor's stored content."""
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return value
    path = parsed.path
    if path in {"/about.php", "/about/"}:
        path = ABOUT_PATHS.get(parsed.fragment, ABOUT_PATHS["who-we-are"])
        return path + ("?" + parsed.query if parsed.query else "")
    if path in {"/founder-story.php", "/founder-story/"}:
        return FOUNDER_PATH + ("?" + parsed.query if parsed.query else "")
    return value


def canonical_path(request):
    path = request.path
    if path == "/" or path == "/index.php":
        return "/"
    if path in ABOUT_PATHS.values() or path == FOUNDER_PATH:
        return path
    if path in {"/about.php", "/about/"}:
        return ABOUT_PATHS["who-we-are"]
    if path in {"/founder-story.php", "/founder-story/"}:
        return FOUNDER_PATH
    for name in ("programs", "publications", "events", "survey"):
        if path in {f"/{name}.php", f"/{name}/"}:
            return f"/{name}.php"
    match = request.resolver_match
    if match and match.url_name in {"publication-detail", "opportunity-detail"}:
        name = "publication" if match.url_name == "publication-detail" else "opportunity"
        return f"/{name}.php?" + urlencode({"slug": match.kwargs["slug"]})
    if path in {"/publication.php", "/opportunity.php"}:
        slug = request.GET.get("slug", "")
        return path + ("?" + urlencode({"slug": slug}) if slug else "")
    return None
