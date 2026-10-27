from django import template
from website.content import public_url, rich_text, image_url
register = template.Library()

@register.simple_tag(takes_context=True)
def editable(context, key):
    return context.get("content", {}).get(key, "")

register.filter("public_url", public_url)
register.filter("rich_text", rich_text)

@register.simple_tag
def picture(file, fallback=""):
    return image_url(file, fallback)
