from django.db import models

from accounts.models import SoftDeleteMixin


class DesignationPayrollRule(SoftDeleteMixin):
    """
    Specifies which statutory deductions apply to employees of a
    given designation.

    Business rules (seed these in a data migration):

        Designation              TDS    EPF    ESIC
        ─────────────────────────────────────────────
        State Mission Manager    True   False  False
        Mission Manager          True   False  False
        Young Professional       True   False  False
        Office Assistant         False  True   True
        Data Entry Operator      False  True   False
        Steno                    False  True   False

    The actual rates (10 %, 12 %, 3.85 %) live in core.SalaryStructure.
    """

    designation = models.OneToOneField(
        "designations.Designation",
        on_delete=models.PROTECT,
        related_name="payroll_rule",
        db_column="designation_id",
    )

    applies_tds = models.BooleanField(
        default=False,
        db_column="applies_tds",
        help_text="Deduct TDS (10 %) from Monthly Honorarium",
    )

    applies_epf = models.BooleanField(
        default=False,
        db_column="applies_epf",
        help_text="Deduct EPF (12 %) from Monthly Honorarium",
    )

    applies_esic = models.BooleanField(
        default=False,
        db_column="applies_esic",
        help_text="Deduct ESIC (3.85 %) — only valid when applies_epf is also True",
    )

    remarks = models.TextField(
        null=True,
        blank=True,
        db_column="remarks",
    )

    class Meta:
        db_table = "pay_designation_rules"
        ordering = ["designation__department", "designation__name"]

    def __str__(self):
        parts = [
            label
            for label, flag in (
                ("TDS", self.applies_tds),
                ("EPF", self.applies_epf),
                ("ESIC", self.applies_esic),
            )
            if flag
        ]
        return f"{self.designation.name} → {', '.join(parts) or 'No deductions'}"


class PayrollRun(SoftDeleteMixin):
    """
    A single monthly payroll processing run for one department.

    Flow:  DRAFT → PROCESSING → COMPLETED → APPROVED → LOCKED
    """

    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("APPROVED", "Approved"),
        ("LOCKED", "Locked"),
    )

    department = models.ForeignKey(
        "departments.Department",
        on_delete=models.PROTECT,
        related_name="payroll_runs",
        db_column="department_id",
    )

    pay_month = models.PositiveSmallIntegerField(
        db_column="pay_month",
        help_text="Calendar month (1 – 12)",
    )

    pay_year = models.PositiveIntegerField(
        db_column="pay_year",
    )

    salary_structure = models.ForeignKey(
        "core.SalaryStructure",
        on_delete=models.PROTECT,
        related_name="payroll_runs",
        db_column="salary_structure_id",
        help_text="Deduction-rate snapshot used for this run",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
        db_column="status",
    )

    # ── Aggregated Totals (populated after processing) ───────────────────────

    total_gross = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        db_column="total_gross",
    )

    total_deductions = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        db_column="total_deductions",
    )

    total_net = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        db_column="total_net",
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_column="processed_at",
    )

    approved_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_payroll_runs",
        db_column="approved_by",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        db_column="approved_at",
    )

    remarks = models.TextField(
        null=True,
        blank=True,
        db_column="remarks",
    )

    class Meta:
        db_table = "pay_payroll_runs"
        unique_together = [["department", "pay_month", "pay_year"]]
        ordering = ["-pay_year", "-pay_month", "department"]

    def __str__(self):
        return (
            f"{self.department.name} — "
            f"{self.pay_month:02d}/{self.pay_year} "
            f"[{self.get_status_display()}]"
        )


class PayrollRecord(SoftDeleteMixin):
    """
    Per-employee salary computation record inside a PayrollRun.

    Net pay formula
    ───────────────
      gross_pay    = monthly_honorarium's copy for now, attendance pro-rated in future
      tds_amount   = gross_pay × (tds_rate / 100)   if designation rule applies
      epf_amount   = gross_pay × (epf_rate / 100)   if designation rule applies
      esic_amount  = gross_pay × (esic_rate / 100)  if designation rule applies
      total_deduct = tds_amount + epf_amount + esic_amount + other_deductions
      net_pay      = gross_pay − total_deduct

    All computation happens in the payroll service layer; these fields
    are persisted results.
    """

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("COMPUTED", "Computed"),
        ("APPROVED", "Approved"),
    )

    payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name="records",
        db_column="payroll_run_id",
    )

    employee = models.ForeignKey(
        "employees.EmployeeProfile",
        on_delete=models.PROTECT,
        related_name="payroll_records",
        db_column="employee_id",
    )

    attendance_record = models.ForeignKey(
        "attendance.AttendanceRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payroll_records",
        db_column="attendance_record_id",
        help_text="Source attendance record; null if entered manually",
    )

    # ── Snapshots at time of run ─────────────────────────────────────────────

    designation_snapshot = models.CharField(
        max_length=200,
        db_column="designation_snapshot",
        help_text="Designation name at time of run (immutable record)",
    )

    # ── Attendance (mirrored / manually set) ─────────────────────────────────

    total_working_days = models.PositiveSmallIntegerField(
        default=0,
        db_column="total_working_days",
    )

    days_present = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=0,
        db_column="days_present",
        help_text="Effective days present (half-days contribute 0.5)",
    )

    days_absent = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=0,
        db_column="days_absent",
    )

    # ── Salary Components ────────────────────────────────────────────────────

    monthly_honorarium = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="monthly_honorarium",
        help_text="Honorarium snapshot at time of payroll run",
    )

    gross_pay = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        db_column="gross_pay",
        help_text="Pro-rated gross pay based on attendance in future, but monthly_honorarium copy for now",
    )

    # ── Deduction Amounts ────────────────────────────────────────────────────

    tds_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column="tds_amount",
    )

    epf_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column="epf_amount",
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
        help_text="Miscellaneous / one-off deductions",
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
        default=0,
        db_column="net_pay",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_column="status",
    )

    remarks = models.TextField(
        null=True,
        blank=True,
        db_column="remarks",
    )

    class Meta:
        db_table = "pay_payroll_records"
        unique_together = [["payroll_run", "employee"]]
        ordering = ["payroll_run", "employee__user__employee_code"]

    def __str__(self):
        return (
            f"{self.employee.user.employee_code} – "
            f"{self.payroll_run.pay_month:02d}/{self.payroll_run.pay_year} "
            f"→ ₹{self.net_pay}"
        )
