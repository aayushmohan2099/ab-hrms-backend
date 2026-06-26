from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import SoftDeleteMixin


class Department(SoftDeleteMixin):
    """
    Represents an organisational department within the company.
    """

    name = models.CharField(
        max_length=200,
        unique=True,
        db_column="name",
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        db_column="code",
        help_text="Short uppercase identifier, e.g. 'NHM', 'ADMIN', 'FINANCE'",
    )

    description = models.TextField(
        blank=True,
        null=True,
        db_column="description",
    )

    head = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="headed_departments",
        db_column="head_user_id",
        help_text="Department head / reporting authority",
    )

    def clean(self):
        super().clean()

        if self.head:
            existing_department = Department.objects.filter(
                head=self.head,
                is_active=True
            ).exclude(
                pk=self.pk
            ).first()

            if existing_department:
                raise ValidationError({
                    "head": (
                        f"{self.head.get_full_name()} is already assigned "
                        f"as head of department '{existing_department.name}'."
                    )
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "dept_departments"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} – {self.name}"


# News Section Models
def validate_pdf(value):
    """
    Allow only PDF files.
    """
    if value:
        if not value.name.lower().endswith(".pdf"):
            raise ValidationError("Only PDF files are allowed.")


class News(SoftDeleteMixin):
    """
    Latest Updates / News Board

    Used for displaying scrolling marquee news on the website.
    Clicking a news item may open/download the attached PDF.
    """

    title = models.CharField(
        max_length=250,
        db_column="title",
        help_text="Short heading for the news."
    )

    news_file = models.FileField(
        upload_to="news/",
        blank=True,
        null=True,
        validators=[validate_pdf],
        help_text="Optional PDF attachment."
    )

    is_active = models.BooleanField(
        default=True,
        db_column="is_active",
        help_text="Show this news on website."
    )

    is_pinned = models.BooleanField(
        default=False,
        db_column="is_pinned",
        help_text="Pinned news appears before normal news."
    )

    publish_date = models.DateTimeField(
        auto_now_add=True,
        db_column="publish_date"
    )

    expiry_date = models.DateTimeField(
        blank=True,
        null=True,
        db_column="expiry_date",
        help_text="News will stop displaying after this date."
    )

    class Meta:
        db_table = "newsboard"
        verbose_name = "News"
        verbose_name_plural = "News"
        ordering = [
            "-is_pinned",
            "-publish_date",
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["publish_date"]),
            models.Index(fields=["expiry_date"]),
        ]

    def __str__(self):
        return self.title

    @property
    def has_attachment(self):
        return bool(self.news_file)

    def clean(self):
        """
        Validation checks.
        """
        # publish_date is None on initial creation before it hits the DB
        pub_date = self.publish_date or timezone.now()
        
        if self.expiry_date and self.expiry_date < pub_date:
            raise ValidationError(
                {"expiry_date": "Expiry date cannot be earlier than publish date."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)