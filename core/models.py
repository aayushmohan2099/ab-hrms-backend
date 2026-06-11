from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import SoftDeleteMixin


class SalaryStructure(SoftDeleteMixin):
    """
    Department-level deduction-rate configuration.

    Multiple versions per department are allowed to track rate changes
    over time.  During payroll processing, the service layer should pick
    the version whose effective_from date is ≤ the payroll month and
    whose effective_to is either NULL or ≥ the payroll month.

    Defaults match current business rules:
        TDS   → 10 %   (State Mission Manager, Mission Manager, Young Professional)
        EPF   → 12 %   (Office Assistant, Data Entry Operator, Steno)
        ESIC  →  3.85 % (Office Assistant only, alongside EPF)

    Which designation gets which deductions is governed separately by
    payroll.DesignationPayrollRule.
    """

    department = models.ForeignKey(
        "departments.Department",
        on_delete=models.PROTECT,
        related_name="salary_structures",
        db_column="department_id",
    )

    tds_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        db_column="tds_rate",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="TDS percentage, e.g. 10.00 for 10 %",
    )

    epf_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=12.00,
        db_column="epf_rate",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="EPF percentage, e.g. 12.00 for 12 %",
    )

    esic_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=3.85,
        db_column="esic_rate",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="ESIC percentage, e.g. 3.85 for 3.85 %",
    )

    effective_from = models.DateField(
        db_column="effective_from",
        help_text="First date on which these rates apply",
    )

    effective_to = models.DateField(
        null=True,
        blank=True,
        db_column="effective_to",
        help_text="Leave blank if this is the current active structure",
    )

    remarks = models.TextField(
        null=True,
        blank=True,
        db_column="remarks",
    )

    class Meta:
        db_table = "core_salary_structures"
        ordering = ["department", "-effective_from"]

    def __str__(self):
        return (
            f"{self.department.name} | "
            f"TDS {self.tds_rate}% | EPF {self.epf_rate}% | "
            f"ESIC {self.esic_rate}% | from {self.effective_from}"
        )
