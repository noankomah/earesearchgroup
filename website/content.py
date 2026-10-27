import bleach
from django.templatetags.static import static
from django.utils.safestring import mark_safe
from .validators import validate_link
from django.core.exceptions import ValidationError

def public_url(value):
    value = str(value or "")
    try:
        validate_link(value)
    except (ValidationError, ValueError):
        return ""
    if value.startswith("assets/"):
        return static(value)
    if value and not value.startswith(("/", "#")) and ":" not in value:
        return "/" + value
    return value

def image_url(file, fallback=""):
    return file.url if file else public_url(fallback)

def rich_text(value):
    return mark_safe(bleach.clean(str(value or ""), tags=["h2", "h3", "p", "br", "strong", "b", "em", "i", "ul", "ol", "li", "a"],
        attributes={"a": ["href", "title"]}, protocols=["http", "https", "mailto", "tel"], strip=True))
