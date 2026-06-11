from django.db import models

from accounts.models import SoftDeleteMixin


class Designation(SoftDeleteMixin):
    """
    A job title / designation that belongs to a specific department.

    Designations are department-scoped, so 'Office Assistant' under
    NHM and 'Office Assistant' under Admin are separate rows.
    """

    name = models.CharField(
        max_length=200,
        db_column="name",
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        db_column="code",
        help_text=(
            "Short globally-unique code, e.g. 'SMM', 'MM', 'YP', "
            "'OA', 'DEO', 'STENO'"
        ),
    )

    department = models.ForeignKey(
        "departments.Department",
        on_delete=models.PROTECT,
        related_name="designations",
        db_column="department_id",
    )

    description = models.TextField(
        blank=True,
        null=True,
        db_column="description",
    )

    class Meta:
        db_table = "desig_designations"
        ordering = ["department", "name"]
        unique_together = [["name", "department"]]

    def __str__(self):
        return f"{self.name} ({self.department.code})"
