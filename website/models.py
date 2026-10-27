from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .validators import validate_link, validate_image_size, validate_choices

IMAGE_VALIDATORS = [validate_image_size]

class RequestLimit(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

class AssignedContent(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="%(class)s_items", help_text="This person may edit this item when given its model permission.")
    editor_group = models.ForeignKey("auth.Group", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="%(class)s_items", help_text="Members may edit this item when given its model permission.")
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class ContentBlock(AssignedContent):
    key = models.SlugField(max_length=160, unique=True)
    page = models.CharField(max_length=80, db_index=True)
    label = models.CharField(max_length=240)
    kind = models.CharField(max_length=12, choices=[("text", "Text"), ("link", "Link"), ("image", "Image")], default="text")
    value = models.TextField(blank=True)
    image = models.ImageField(upload_to="content/%Y/%m/", blank=True, validators=IMAGE_VALIDATORS)
    class Meta:
        ordering = ["page", "key"]
    def __str__(self):
        return f"{self.page}: {self.label}"
    def clean(self):
        if self.kind in {"link", "image"}:
            validate_link(self.value)

class HeroSlide(AssignedContent):
    title = models.CharField(max_length=160, help_text="Internal label and accessible image description")
    image = models.ImageField(upload_to="hero/%Y/%m/", blank=True, validators=IMAGE_VALIDATORS)
    image_path = models.CharField(max_length=500, blank=True, validators=[validate_link], help_text="Existing image path or URL; upload takes priority")
    position = models.CharField(max_length=80, default="center center", help_text="CSS background-position, e.g. center 45%")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ["order", "pk"]
    def clean(self):
        if not self.image and not self.image_path:
            raise ValidationError("Upload an image or provide its path.")
    def __str__(self):
        return self.title

class TeamMember(AssignedContent):
    name = models.CharField(max_length=180)
    role = models.CharField(max_length=180)
    section = models.CharField(max_length=16, choices=[("board", "Governing board"), ("team", "Executive team"), ("advisory", "Advisory board")])
    photo = models.ImageField(upload_to="people/%Y/%m/", blank=True, validators=IMAGE_VALIDATORS)
    photo_path = models.CharField(max_length=500, blank=True, validators=[validate_link])
    photo_id = models.SlugField(blank=True, help_text="Existing CSS hook, normally leave unchanged")
    biography = models.TextField(blank=True)
    profile_link = models.CharField(max_length=500, blank=True, validators=[validate_link])
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ["order", "pk"]
    def __str__(self):
        return self.name

class NavigationLink(models.Model):
    location = models.CharField(max_length=12, choices=[("header", "Header"), ("footer", "Footer quick links"), ("social", "Social links")])
    label = models.CharField(max_length=120)
    url = models.CharField(max_length=500, blank=True, validators=[validate_link])
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    route = models.SlugField(blank=True, help_text="Existing section anchor, if applicable")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_disabled = models.BooleanField(default=False)
    new_tab = models.BooleanField(default=False)
    class Meta:
        ordering = ["order", "pk"]
    def clean(self):
        if self.parent_id and (self.parent_id == self.pk or self.parent.parent_id or self.parent.location != self.location):
            raise ValidationError("Choose a top-level parent in the same menu.")
    def __str__(self):
        return f"{self.location}: {self.label}"

class PublishedContent(AssignedContent):
    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=260, unique=True)
    summary = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    legacy_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True, editable=False)
    class Meta:
        abstract = True
        ordering = ["-is_featured", "-created_at"]
    def __str__(self):
        return self.title

class Publication(PublishedContent):
    publication_type = models.CharField(max_length=20, choices=[(v, v) for v in ["Blog", "Newsletter", "Report"]])
    full_content = models.TextField(blank=True, help_text="Formatted HTML: paragraphs, headings, lists, emphasis and links")
    author = models.CharField(max_length=180, blank=True)
    publication_date = models.DateField(null=True, blank=True)
    cover = models.ImageField(upload_to="publications/%Y/%m/", blank=True, validators=IMAGE_VALIDATORS)
    cover_image = models.CharField(max_length=500, blank=True, validators=[validate_link])
    document_link = models.CharField(max_length=500, blank=True, validators=[validate_link])
    class Meta(PublishedContent.Meta):
        permissions = [("publish_publication", "Can publish publications")]

class PublicationImage(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="publications/gallery/%Y/%m/", blank=True, validators=IMAGE_VALIDATORS)
    image_path = models.CharField(max_length=500, blank=True, validators=[validate_link])
    order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["order", "pk"]
    def clean(self):
        if not self.image and not self.image_path:
            raise ValidationError("Upload an image or provide its path.")
    def __str__(self):
        return f"{self.publication}: image {self.order + 1}"

class Opportunity(PublishedContent):
    category = models.CharField(max_length=40, choices=[(v, v) for v in ["Scholarship", "Fellowship", "Internship", "Grant", "Conference", "Training", "Job", "Research Opportunity", "Other"]])
    full_description = models.TextField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[(v, v) for v in ["Open", "Closing Soon", "Closed"]], default="Open")
    country = models.CharField(max_length=180, blank=True)
    host_organization = models.CharField(max_length=240, blank=True)
    application_link = models.CharField(max_length=500, blank=True, validators=[validate_link])
    class Meta(PublishedContent.Meta):
        verbose_name_plural = "Opportunities"
        permissions = [("publish_opportunity", "Can publish opportunities")]

class FounderStory(models.Model):
    founder_name = models.CharField(max_length=180)
    role_title = models.CharField(max_length=180, blank=True)
    photo = models.ImageField(upload_to="founder/%Y/%m/", blank=True, validators=IMAGE_VALIDATORS)
    photo_url = models.CharField(max_length=500, blank=True, validators=[validate_link])
    is_published = models.BooleanField(default=False)
    def __str__(self):
        return self.founder_name

class StorySection(models.Model):
    story = models.ForeignKey(FounderStory, on_delete=models.CASCADE, related_name="sections")
    heading = models.CharField(max_length=240, blank=True)
    body = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["order", "pk"]
    def __str__(self):
        return self.heading or "Story section"

class Event(PublishedContent):
    body = models.TextField(blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=240, blank=True)
    image = models.ImageField(upload_to="events/%Y/%m/", blank=True, validators=IMAGE_VALIDATORS)
    registration_link = models.CharField(max_length=500, blank=True, validators=[validate_link])
    class Meta(PublishedContent.Meta):
        permissions = [("publish_event", "Can publish events")]

class ContactMessage(models.Model):
    full_name = models.CharField(max_length=180)
    email = models.EmailField()
    subject = models.CharField(max_length=240, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    legacy_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True, editable=False)
    class Meta:
        ordering = ["-created_at"]
    def __str__(self):
        return f"{self.full_name}: {self.email}"

class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.email

class Survey(models.Model):
    slug = models.SlugField(unique=True, default="mentorship")
    title = models.CharField(max_length=240)
    subtitle = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.title

class SurveyQuestion(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="questions")
    key = models.SlugField(max_length=32)
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=600)
    help = models.TextField(blank=True)
    type = models.CharField(max_length=12, choices=[(v, v) for v in ["radio", "checkbox", "text", "textarea", "scale"]])
    required = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True, validators=[validate_choices])
    other = models.BooleanField(default=False)
    other_label = models.CharField(max_length=120, default="Other (please specify)")
    other_maxlength = models.PositiveIntegerField(default=300)
    maxlength = models.PositiveIntegerField(default=2000)
    min = models.IntegerField(default=1)
    max = models.IntegerField(default=10)
    min_label = models.CharField(max_length=120, blank=True)
    max_label = models.CharField(max_length=120, blank=True)
    class Meta:
        ordering = ["number", "pk"]
        constraints = [models.UniqueConstraint(fields=["survey", "key"], name="unique_survey_key")]
    def clean(self):
        if self.max < self.min or self.max - self.min > 100:
            raise ValidationError("Scale must have between 1 and 101 values.")
        if self.type in {"radio", "checkbox"} and not self.options:
            raise ValidationError("Choice questions need options.")
    def __str__(self):
        return f"{self.number}. {self.title}"

class SurveyResponse(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.PROTECT, related_name="responses")
    answers = models.JSONField(default=dict)
    question_snapshot = models.JSONField(default=list, help_text="Question wording at submission time")
    submitted_at = models.DateTimeField(auto_now_add=True)
    legacy_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True, editable=False)
    class Meta:
        ordering = ["-submitted_at"]
    def __str__(self):
        return f"Response {self.pk} — {self.submitted_at:%Y-%m-%d}"
