from django import forms
from .models import Publication, Opportunity, TeamMember, ContentBlock, HeroSlide, Event
from .widgets import RichTextWidget

class ContactForm(forms.Form):
    name = forms.CharField(max_length=180)
    email = forms.EmailField()
    message = forms.CharField(max_length=10000)

class NewsletterForm(forms.Form):
    email = forms.EmailField()

class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ["title", "slug", "publication_type", "summary", "full_content", "author", "publication_date", "cover", "cover_image", "document_link"]
        widgets = {"publication_date": forms.DateInput(attrs={"type": "date"}), "full_content": RichTextWidget()}

class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = ["title", "slug", "category", "summary", "full_description", "deadline", "status", "country", "host_organization", "application_link"]
        widgets = {"deadline": forms.DateInput(attrs={"type": "date"}), "full_description": RichTextWidget()}

class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = ["name", "photo", "biography", "profile_link"]

class ContentBlockForm(forms.ModelForm):
    class Meta:
        model = ContentBlock
        fields = ["value", "image"]

class HeroSlideForm(forms.ModelForm):
    class Meta:
        model = HeroSlide
        fields = ["title", "image", "image_path", "position"]

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["title", "slug", "summary", "body", "starts_at", "location", "image", "registration_link"]
        widgets = {"starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}), "body": RichTextWidget()}
