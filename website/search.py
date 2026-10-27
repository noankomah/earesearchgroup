import re
from html import unescape
from django.utils.html import strip_tags

TEAM_SEARCH_FIELDS = {
    "publications": ("title", "summary", "full_content", "author", "slug", "publication_type"),
    "opportunities": ("title", "summary", "full_description", "country", "host_organization", "category", "slug"),
    "people": ("name", "role", "biography"),
    "content": ("value", "label", "page", "key"),
    "hero": ("title", "image_path"),
    "events": ("title", "summary", "body", "location", "slug"),
}

def matching_items(items, kind, query):
    """Match a literal word or phrase in the content the user may access."""
    pattern = re.compile(r"(?<!\w)" + re.escape(query) + r"(?!\w)", re.IGNORECASE)
    matches = []
    for item in items:
        for field in TEAM_SEARCH_FIELDS[kind]:
            text = " ".join(unescape(strip_tags(str(getattr(item, field) or ""))).split())
            match = pattern.search(text)
            if match:
                start = max(0, match.start() - 60)
                end = min(len(text), match.end() + 100)
                item.search_excerpt = ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")
                matches.append(item)
                break
    return matches
