from django.db import models

from accounts.models import SoftDeleteMixin


class SalarySlip(SoftDeleteMixin):
    """
    Immutable salary-slip document generated from a PayrollRecord.

    All employee / designation / rate values are snapshotted at
    generation time so the slip remains an accurate historical record
    even if master data changes later.

    Slip number auto-format: SLIP/<year>/<mm>/<employee_code>
    Example:                 SLIP/2025/04/EMP001
    """

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("GENERATED", "Generated"),
        ("DISPATCHED", "Dispatched"),
    )

    payroll_record = models.OneToOneField(
        "payroll.PayrollRecord",
        on_delete=models.PROTECT,
        related_name="salary_slip",
        db_column="payroll_record_id",
    )

    employee = models.ForeignKey(
        "employees.EmployeeProfile",
        on_delete=models.PROTECT,
        related_name="salary_slips",
        db_column="employee_id",
    )

    slip_month = models.PositiveSmallIntegerField(
        db_column="slip_month",
        help_text="Salary month (1 – 12)",
    )

    slip_year = models.PositiveIntegerField(
        db_column="slip_year",
    )

    slip_number = models.CharField(
        max_length=60,
        unique=True,
        db_column="slip_number",
        help_text="Auto-generated unique reference — SLIP/<year>/<mm>/<emp_code>",
    )

    # ── Employee Snapshots ───────────────────────────────────────────────────

    employee_code_snapshot = models.CharField(
        max_length=50,
        db_column="employee_code_snapshot",
    )

    employee_name_snapshot = models.CharField(
        max_length=200,
        db_column="employee_name_snapshot",
    )

    designation_snapshot = models.CharField(
        max_length=200,
        db_column="designation_snapshot",
    )

    department_snapshot = models.CharField(
        max_length=200,
        db_column="department_snapshot",
    )

    bank_name_snapshot = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        db_column="bank_name_snapshot",
    )

    bank_account_snapshot = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_column="bank_account_snapshot",
    )

    bank_ifsc_snapshot = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_column="bank_ifsc_snapshot",
    )

    pan_snapshot = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_column="pan_snapshot",
        help_text="PAN at time of generation (required for TDS slips)",
    )

    uan_snapshot = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_column="uan_snapshot",
        help_text="UAN at time of generation (required for EPF slips)",
    )

    # ── Attendance ───────────────────────────────────────────────────────────

    total_working_days = models.PositiveSmallIntegerField(
        default=0,
        db_column="total_working_days",
    )

    days_present = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=0,
        db_column="days_present",
        help_text="Effective payable days (half-days counted as 0.5)",
    )

    days_absent = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=0,
        db_column="days_absent",
    )

    # ── Earnings ─────────────────────────────────────────────────────────────

    monthly_honorarium = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="monthly_honorarium",
        help_text="Full monthly honorarium before pro-ration",
    )

    gross_pay = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="gross_pay",
        help_text="Pro-rated gross = honorarium × (days_present / total_working_days)",
    )

    # ── Deductions (snapshotted rates + computed amounts) ────────────────────

    tds_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        db_column="tds_rate",
        help_text="TDS rate applied (% snapshot from SalaryStructure)",
    )

    tds_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column="tds_amount",
    )

    epf_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        db_column="epf_rate",
        help_text="EPF rate applied (% snapshot)",
    )

    epf_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column="epf_amount",
    )

    esic_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        db_column="esic_rate",
        help_text="ESIC rate applied (% snapshot)",
    )

    esic_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column="esic_amount",
    )

    other_deductions = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column="other_deductions",
    )

    total_deductions = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column="total_deductions",
    )

    net_pay = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="net_pay",
    )

    net_pay_in_words = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        db_column="net_pay_in_words",
        help_text="e.g. 'Rupees Forty-Two Thousand Only'",
    )

    # ── Generation Metadata ──────────────────────────────────────────────────

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
        db_column="status",
    )

    generated_at = models.DateTimeField(
        null=True,
        blank=True,
        db_column="generated_at",
    )

    generated_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_salary_slips",
        db_column="generated_by",
    )

    pdf_file = models.FileField(
        upload_to="salary_slips/pdfs/",
        null=True,
        blank=True,
        db_column="pdf_file",
        help_text="Rendered PDF; populated after generation",
    )

    remarks = models.TextField(
        null=True,
        blank=True,
        db_column="remarks",
    )

    # ── Auto-generate slip number ────────────────────────────────────────────

    def save(self, *args, **kwargs):
        if not self.slip_number:
            emp_code = (
                self.employee.user.employee_code
                or self.employee_code_snapshot
                or "UNKNOWN"
            )
            self.slip_number = (
                f"SLIP/{self.slip_year}/{self.slip_month:02d}/{emp_code}"
            )
        super().save(*args, **kwargs)

    class Meta:
        db_table = "slip_salary_slips"
        unique_together = [["employee", "slip_month", "slip_year"]]
        ordering = ["-slip_year", "-slip_month", "employee__user__employee_code"]

    def __str__(self):
        return (
            f"{self.slip_number} – "
            f"{self.employee_name_snapshot} "
            f"[{self.slip_month:02d}/{self.slip_year}] ₹{self.net_pay}"
        )
