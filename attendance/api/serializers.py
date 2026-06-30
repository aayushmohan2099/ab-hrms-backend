# attendance/api/serializers.py
from rest_framework import serializers
from django.utils import timezone
from datetime import date
from attendance.models import LeaveApplication, DailyAttendance
from employees.models import EmployeeProfile

# =====================================================
# DAILY ATTENDANCE (For Calendar View)
# =====================================================

class DailyAttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyAttendance
        fields = ['date', 'status', 'is_locked', 'holiday_reason']


class EmployeeMonthlyAttendanceSerializer(serializers.ModelSerializer):
    """
    Returns an employee with their summarized present days, a list of all daily records, 
    and detailed leave applications for a specific month.
    """
    employee_code = serializers.CharField(source='user.employee_code')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    designation_name = serializers.CharField(source='designation.name')
    total_leaves_this_month = serializers.IntegerField(read_only=True, default=0)

    # These fields will be dynamically populated in the view
    daily_records = serializers.SerializerMethodField()
    present_summary = serializers.SerializerMethodField()
    current_month_records = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeProfile
        fields = [
            'id', 'employee_code', 'first_name', 'last_name', 'theme',
            'designation_name', 'present_summary', 'daily_records', 'total_leaves_this_month', 'current_month_records'
        ]

    def get_current_month_records(self, obj):
        # Fetch the detailed leave applications attached dynamically in the view
        leaves = getattr(obj, 'current_month_leave_applications', [])
        return [
            {
                "id": leave.id,
                "leave_type": leave.leave_type,
                "start_date": leave.start_date,
                "end_date": leave.end_date,
                "reason": leave.reason,
                "status": leave.status
            }
            for leave in leaves
        ]

    def get_daily_records(self, obj):
        # The view attaches standard daily records to 'current_month_records' attr
        records = getattr(obj, 'current_month_records', [])
        return DailyAttendanceSerializer(records, many=True).data

    def get_present_summary(self, obj):
        records = getattr(obj, 'current_month_records', [])
        total_days = getattr(obj, 'total_days_in_month', len(records))
        # Count days that contribute to "Presence" / "Effective Days"
        present_count = sum(1 for r in records if r.status in ['PRESENT', 'PAID_LEAVE', 'HOLIDAY'])
        return f"{present_count}/{total_days}"

# =====================================================
# LEAVE APPLICATIONS
# =====================================================

class LeaveApplicationBaseSerializer(serializers.ModelSerializer):
    """
    Base serializer for validation and creation.
    """
    class Meta:
        model = LeaveApplication
        fields = [
            'id', 'leave_type', 'start_date', 'end_date', 'reason', 'status', 'created_at'
        ]
        read_only_fields = ['status']

    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        today = timezone.localdate()

        if start_date < today:
            raise serializers.ValidationError({"start_date": "Leave cannot be applied for past dates."})

        if end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})

        return data


class LeaveApplicationComprehensiveSerializer(serializers.ModelSerializer):
    """
    Rich serializer for Managers/Admins, containing deeply nested details 
    and dynamically calculated attendance summaries.
    """
    # Employee Details
    employee_code = serializers.CharField(source='employee.user.employee_code', read_only=True)
    employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    designation_name = serializers.CharField(source='employee.designation.name', read_only=True)
    employee_type = serializers.CharField(source='employee.user.employee_type', read_only=True)
    
    # Approver / Reporting Manager Details
    approver_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, default="Pending")
    approver_role = serializers.CharField(source='approved_by.role.name', read_only=True, default="N/A")
    
    # Dynamic field calculated in the serializer method
    attendance_summary = serializers.SerializerMethodField()

    class Meta:
        model = LeaveApplication
        fields = [
            'id', 'employee_code', 'employee_name', 'department_name', 'designation_name', 'employee_type',
            'leave_type', 'start_date', 'end_date', 'reason', 'status',
            'approver_name', 'approver_role', 'attendance_summary', 'created_at'
        ]

    def get_attendance_summary(self, obj):
        """
        Calculates the attendance summary for the month in which the leave STARTS.
        Returns: "14/30" (Present/Total days up to the current point in that month)
        """
        target_month = obj.start_date.month
        target_year = obj.start_date.year
        
        # Get all DailyAttendance rows for this employee in the target month
        records = DailyAttendance.objects.filter(
            employee=obj.employee,
            date__year=target_year,
            date__month=target_month,
            is_active=True
        )
        
        total_days = records.count()
        if total_days == 0:
            return "0/0"
            
        present_count = sum(1 for r in records if r.status in ['PRESENT', 'PAID_LEAVE', 'HOLIDAY'])
        return f"{present_count}/{total_days}"


class LeaveApplicationDeepDetailSerializer(LeaveApplicationComprehensiveSerializer):
    """
    Extends the comprehensive serializer by adding full employee profile and exact approver user data.
    """
    from employees.api.serializers import EmployeeProfileSerializer
    from accounts.api.serializers import UserSerializer # Assuming this exists
    
    full_employee_profile = EmployeeProfileSerializer(source='employee', read_only=True)
    
    # We use SerializerMethodField here to avoid circular imports and handle None correctly
    full_approver_details = serializers.SerializerMethodField()
    
    class Meta(LeaveApplicationComprehensiveSerializer.Meta):
        fields = LeaveApplicationComprehensiveSerializer.Meta.fields + [
            'full_employee_profile', 'full_approver_details'
        ]
        
    def get_full_approver_details(self, obj):
        if not obj.approved_by:
            return None
        # Inline import to avoid circular dependency issues if Accounts app imports Attendance app
        from accounts.api.serializers import UserSerializer
        return UserSerializer(obj.approved_by).data