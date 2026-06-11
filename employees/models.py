from django.db import models

from accounts.models import SoftDeleteMixin


class EmployeeProfile(SoftDeleteMixin):
    """
    Extended HR profile for a User.

    The accounts.User already holds authentication-level fields
    (employee_code, phone_number, profile_picture, employee_type, role,
    reporting_manager).  This model stores everything the HR/payroll
    side needs: department, designation, base pay, bank details,
    statutory numbers, and contact information.
    """

    GENDER_CHOICES = (
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other / Prefer not to say"),
    )

    # ── Core Identity ────────────────────────────────────────────────────────

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="employee_profile",
        db_column="user_id",
    )

    department = models.ForeignKey(
        "departments.Department",
        on_delete=models.PROTECT,
        related_name="employees",
        db_column="department_id",
    )

    designation = models.ForeignKey(
        "designations.Designation",
        on_delete=models.PROTECT,
        related_name="employees",
        db_column="designation_id",
    )

    # ── Service Dates ────────────────────────────────────────────────────────

    date_of_joining = models.DateField(
        db_column="date_of_joining",
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        db_column="date_of_birth",
    )

    date_of_leaving = models.DateField(
        null=True,
        blank=True,
        db_column="date_of_leaving",
        help_text="Populated on separation / resignation",
    )

    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        null=True,
        blank=True,
        db_column="gender",
    )

    # ── Monthly Honorarium ───────────────────────────────────────────────────

    monthly_honorarium = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="monthly_honorarium",
        help_text="Gross base pay (Monthly Honorarium) in INR — the figure before any deductions",
    )

    # ── Bank Details ─────────────────────────────────────────────────────────

    bank_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        db_column="bank_name",
    )

    bank_account_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_column="bank_account_number",
    )

    bank_ifsc = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_column="bank_ifsc",
    )

    bank_branch = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        db_column="bank_branch",
    )

    # ── Statutory / Compliance Numbers ───────────────────────────────────────

    pan_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_column="pan_number",
        help_text="Permanent Account Number — mandatory for TDS deductions",
    )

    uan_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_column="uan_number",
        help_text="Universal Account Number — mandatory for EPF deductions",
    )

    esic_ip_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_column="esic_ip_number",
        help_text="ESIC Insurance Policy (IP) Number",
    )

    aadhaar_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_column="aadhaar_number",
    )

    # ── Address ──────────────────────────────────────────────────────────────

    address = models.TextField(
        null=True,
        blank=True,
        db_column="address",
    )

    city = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column="city",
    )

    state = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column="state",
    )

    pincode = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        db_column="pincode",
    )

    # ── Emergency Contact ────────────────────────────────────────────────────

    emergency_contact_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        db_column="emergency_contact_name",
    )

    emergency_contact_phone = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        db_column="emergency_contact_phone",
    )

    emergency_contact_relation = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column="emergency_contact_relation",
    )

    class Meta:
        db_table = "emp_profiles"
        ordering = ["user__employee_code"]

    def __str__(self):
        return (
            f"{self.user.employee_code} – "
            f"{self.user.get_full_name()} "
            f"[{self.designation.name}]"
        )
