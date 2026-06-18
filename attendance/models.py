from django.db import models
from accounts.models import SoftDeleteMixin

class LeaveApplication(SoftDeleteMixin):
    """
    Tracks leave requests submitted by employees.
    """
    LEAVE_TYPES = (
        ("MATERNITY", "Maternity Leave (ML)"),
        ("CASUAL", "Casual Leave (CL)"),
        ("SICK", "Sick Leave (SL)"),
    )
    
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    employee = models.ForeignKey(
        "employees.EmployeeProfile",
        on_delete=models.CASCADE,
        related_name="leave_applications"
    )
    leave_type = models.CharField(max_length=10, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="approved_leaves"
    )
    
    class Meta:
        db_table = "att_leave_applications"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.employee.user.employee_code} - {self.leave_type} ({self.start_date} to {self.end_date})"


class DailyAttendance(SoftDeleteMixin):
    """
    Tracks the attendance status for a single employee on a specific date.
    """
    STATUS_CHOICES = (
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("WEEKEND", "Weekend (Saturday/Sunday)"),
        ("HOLIDAY", "Public Holiday"),
        ("PAID_LEAVE", "Paid Leave"),
        ("CASUAL_LEAVE", "Casual Leave"),
        ("SICK_LEAVE", "Sick Leave"),
    )

    employee = models.ForeignKey(
        "employees.EmployeeProfile",
        on_delete=models.CASCADE,
        related_name="daily_attendance"
    )
    date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="PRESENT")
    
    # Flag to tell the daily cron script to skip this row (e.g., if a manager manually changed it or a leave was approved)
    is_locked = models.BooleanField(default=False)

    class Meta:
        db_table = "att_daily_records"
        unique_together = [["employee", "date"]]
        ordering = ["-date", "employee__user__employee_code"]

    def __str__(self):
        return f"{self.employee.user.employee_code} - {self.date} [{self.status}]"
        

class AttendanceUpload(SoftDeleteMixin):
    """
    A single end-of-month attendance batch submitted by a department
    manager or HR representative.

    One upload per (department, month, year).  For corrections after
    the fact, soft-delete the old upload and create a new one, or
    update individual AttendanceRecords in place.
    """

    STATUS_CHOICES = (
        ("UPLOADED", "Uploaded"),
        ("VERIFIED", "Verified"),
        ("REJECTED", "Rejected"),
    )

    department = models.ForeignKey(
        "departments.Department",
        on_delete=models.PROTECT,
        related_name="attendance_uploads",
        db_column="department_id",
    )

    att_month = models.PositiveSmallIntegerField(
        db_column="att_month",
        help_text="Attendance month (1 – 12)",
    )

    att_year = models.PositiveIntegerField(
        db_column="att_year",
    )

    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="submitted_attendance_uploads",
        db_column="uploaded_by",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="UPLOADED",
        db_column="status",
    )

    # Optional: preserve the original Excel / CSV the manager sent
    source_file = models.FileField(
        upload_to="attendance/source_files/",
        null=True,
        blank=True,
        db_column="source_file",
        help_text="Original spreadsheet uploaded by the manager (optional)",
    )

    verified_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_attendance_uploads",
        db_column="verified_by",
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        db_column="verified_at",
    )

    remarks = models.TextField(
        null=True,
        blank=True,
        db_column="remarks",
    )

    class Meta:
        db_table = "att_uploads"
        unique_together = [["department", "att_month", "att_year"]]
        ordering = ["-att_year", "-att_month", "department"]

    def __str__(self):
        return (
            f"{self.department.name} – "
            f"{self.att_month:02d}/{self.att_year} "
            f"[{self.get_status_display()}]"
        )


class AttendanceRecord(SoftDeleteMixin):
    """
    Monthly attendance summary for one employee within an
    AttendanceUpload batch.

    Day-type hierarchy
    ──────────────────
      days_present      → full days in office
      paid_leave   → approved leave; still paid in full      
      casual_leave     → number of casual leave days
      sick_leave       → number of sick leave days
      days_absent       → unauthorised / unmarked absence

    effective_days (property) = days_present + paid_leave

    The payroll service uses effective_days as the numerator when
    pro-rating the monthly honorarium.
    """

    upload = models.ForeignKey(
        AttendanceUpload,
        on_delete=models.CASCADE,
        related_name="records",
        db_column="upload_id",
    )

    employee = models.ForeignKey(
        "employees.EmployeeProfile",
        on_delete=models.PROTECT,
        related_name="attendance_records",
        db_column="employee_id",
    )

    # ── Calendar data ────────────────────────────────────────────────────────

    total_working_days = models.PositiveSmallIntegerField(
        default=0,
        db_column="total_working_days",
        help_text="Total scheduled working days in this month (set by the manager)",
    )

    days_present = models.PositiveSmallIntegerField(
        default=0,
        db_column="days_present",
        help_text="Full days present in office",
    )

    paid_leave = models.PositiveSmallIntegerField(
        default=0,
        db_column="paid_leave",
        help_text="Approved paid-leave days (treated as present for salary calculation)",
    )

    casual_leave = models.PositiveSmallIntegerField(
        default=0,
        db_column="casual_leave",
        help_text="Number of casual leave days",
    )

    sick_leave = models.PositiveSmallIntegerField(
        default=0,
        db_column="sick_leave",
        help_text="Number of sick leave days",
    )

    days_absent = models.PositiveSmallIntegerField(
        default=0,
        db_column="days_absent",
        help_text="Unauthorised / unmarked absences",
    )

    remarks = models.TextField(
        null=True,
        blank=True,
        db_column="remarks",
    )

    # ── Computed property ────────────────────────────────────────────────────

    @property
    def effective_days(self) -> float:
        """
        Payable days used to pro-rate the monthly honorarium.

        effective_days = days_present + paid_leave
        """
        return (
            self.days_present
            + self.paid_leave
        )

    class Meta:
        db_table = "att_records"
        unique_together = [["upload", "employee"]]
        ordering = ["upload", "employee__user__employee_code"]

    def __str__(self):
        return (
            f"{self.employee.user.employee_code} – "
            f"{self.upload.att_month:02d}/{self.upload.att_year} "
            f"[P:{self.days_present} PL:{self.paid_leave}"
            f"CL:{self.casual_leave} SL:{self.sick_leave}"
            f"A:{self.days_absent}]"
        )
