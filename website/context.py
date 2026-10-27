from .models import ContentBlock, NavigationLink
from .content import image_url, public_url
from .seo import canonical_path, stable_internal_link

def site_content(request):
    if request.path.startswith("/admin/"):
        return {}
    blocks = {}
    for block in ContentBlock.objects.all():
        blocks[block.key] = image_url(block.image, block.value) if block.kind == "image" else (stable_internal_link(public_url(block.value)) if block.kind == "link" else block.value)
    links = list(NavigationLink.objects.filter(is_active=True))
    for link in links:
        link.public_url = stable_internal_link(public_url(link.url)) or "#"
        link.items = [child for child in links if child.parent_id == link.pk]
    path = canonical_path(request)
    return {"canonical_url": request.build_absolute_uri(path) if path else None, "content": blocks, "header_links": [x for x in links if x.location == "header" and not x.parent_id],
            "footer_links": [x for x in links if x.location == "footer" and not x.parent_id],
            "social_links": [x for x in links if x.location == "social" and not x.parent_id]}
