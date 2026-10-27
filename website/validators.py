import re
from urllib.parse import urlsplit
from django.core.exceptions import ValidationError

def validate_link(value):
    if not value:
        return
    if re.search(r'[\s\\\x00-\x1f\x7f]', value) or value.startswith("//"):
        raise ValidationError("Use a site path, #anchor, https://, http://, mailto: or tel: link.")
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme.lower() not in {"https", "http", "mailto", "tel"}:
        raise ValidationError("This link type is not allowed.")
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        raise ValidationError("Enter a complete web address.")

def validate_image_size(file):
    if file.size > 3 * 1024 * 1024:
        raise ValidationError("Maximum image size is 3 MB.")

def validate_choices(value):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValidationError("Enter a JSON list of text choices.")
    if len(value) != len(set(value)):
        raise ValidationError("Choices must be unique.")
