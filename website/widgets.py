from django import forms
from .content import rich_text

class RichTextWidget(forms.Textarea):
    template_name = "widgets/rich_text.html"
    def format_value(self, value):
        return super().format_value(str(rich_text(value)))
    class Media:
        css = {"all": ("editor.css",)}
        js = ("editor.js",)
