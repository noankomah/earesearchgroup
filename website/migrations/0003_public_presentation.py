from django.db import migrations

OLD_LINKEDIN = "https://www.linkedin.com/in/ea-research-group-earg-298a9440b"
NEW_LINKEDIN = "https://www.linkedin.com/company/ea-research-group/"

def update_existing_content(apps, schema_editor):
    Link = apps.get_model("website", "NavigationLink")
    Block = apps.get_model("website", "ContentBlock")
    Link.objects.filter(location="social", label__iexact="Facebook").update(url="", is_disabled=True)
    Link.objects.filter(location="social", url=OLD_LINKEDIN).update(url=NEW_LINKEDIN)
    Block.objects.filter(key="header-image-001", value="assets/images/earg-logo-transparent.png").update(value="assets/images/earg-logo.png")

class Migration(migrations.Migration):
    dependencies = [("website", "0002_requestlimit")]
    operations = [migrations.RunPython(update_existing_content, migrations.RunPython.noop)]
