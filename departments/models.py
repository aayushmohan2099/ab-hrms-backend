from django.db import models

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

    class Meta:
        db_table = "dept_departments"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} – {self.name}"
