# attendance/api/manager_views.py

from datetime import date
from calendar import monthrange
from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from attendance.models import DailyAttendance, LeaveApplication
from employees.models import EmployeeProfile
from departments.models import Department

class ManagerDashboardStatsView(APIView):
    """
    Returns comprehensive statistics for a Manager's dashboard.
    Automatically determines the manager's department and limits data to that scope.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # 1. Verify User is a Manager (Role ID 2)
        if not user.role or user.role.id != 2:
            return Response({"detail": "Unauthorized. Only Managers can access this dashboard."}, status=status.HTTP_403_FORBIDDEN)
        
        # 2. Identify Manager's Department
        try:
            # We check which department this user heads, OR which department they belong to.
            # Assuming standard setup: Manager is the head of their department.
            department = Department.objects.filter(head=user, is_active=True).first()
            if not department:
                # Fallback: get the department they are assigned to via EmployeeProfile
                emp_profile = EmployeeProfile.objects.get(user=user, is_active=True)
                department = emp_profile.department
        except EmployeeProfile.DoesNotExist:
            return Response({"detail": "Manager profile not found."}, status=status.HTTP_404_NOT_FOUND)

        if not department:
             return Response({"detail": "No associated department found for this manager."}, status=status.HTTP_404_NOT_FOUND)

        # 3. Define Timeframes
        today = date.today()
        current_year = today.year
        current_month = today.month
        
        _, last_day_of_month = monthrange(current_year, current_month)
        month_start_date = date(current_year, current_month, 1)
        month_end_date = date(current_year, current_month, last_day_of_month)

        # 4. Fetch Department Employees
        dept_employees = EmployeeProfile.objects.filter(department=department, is_active=True)
        total_employees = dept_employees.count()

        # 5. Today's Attendance Snapshot
        todays_attendance = DailyAttendance.objects.filter(
            employee__in=dept_employees, 
            date=today, 
            is_active=True
        )
        
        present_today = todays_attendance.filter(status='PRESENT').count()
        absent_today = todays_attendance.filter(status='ABSENT').count()
        on_leave_today = todays_attendance.filter(status__in=['PAID_LEAVE', 'CASUAL_LEAVE', 'SICK_LEAVE']).count()
        unmarked_today = total_employees - (present_today + absent_today + on_leave_today)

        # 6. Current Month Attendance Overview
        monthly_attendance = DailyAttendance.objects.filter(
            employee__in=dept_employees,
            date__gte=month_start_date,
            date__lte=month_end_date,
            is_active=True
        )

        monthly_stats = monthly_attendance.aggregate(
            total_present=Count('id', filter=Q(status='PRESENT')),
            total_absent=Count('id', filter=Q(status='ABSENT')),
            total_leaves=Count('id', filter=Q(status__in=['PAID_LEAVE', 'CASUAL_LEAVE', 'SICK_LEAVE'])),
        )

        # Calculate average monthly attendance percentage
        # (Total Present / (Total Days Marked * Total Employees)) * 100
        days_passed = today.day # Number of days passed in current month
        total_possible_marks = total_employees * days_passed
        avg_attendance_percentage = 0
        if total_possible_marks > 0:
            avg_attendance_percentage = round((monthly_stats['total_present'] / total_possible_marks) * 100, 1)

        # 7. Designation-wise Attendance Percentage (Current Month)
        designation_stats = []
        # Group attendance by designation
        desig_attendance = monthly_attendance.values('employee__designation__name').annotate(
            present_count=Count('id', filter=Q(status='PRESENT')),
            total_count=Count('id')
        )
        
        for item in desig_attendance:
            desig_name = item['employee__designation__name']
            present = item['present_count']
            total = item['total_count']
            percentage = round((present / total * 100), 1) if total > 0 else 0
            
            designation_stats.append({
                "designation": desig_name,
                "attendance_percentage": percentage
            })

        # Sort by lowest attendance first to highlight areas needing attention
        designation_stats = sorted(designation_stats, key=lambda x: x['attendance_percentage'])

        # 8. Pending Leave Requests Action Items
        pending_leaves = LeaveApplication.objects.filter(
            employee__in=dept_employees,
            status='PENDING',
            is_active=True
        ).count()

        # Compile Final Response
        response_data = {
            "department_info": {
                "id": department.id,
                "name": department.name,
                "code": department.code,
                "total_employees": total_employees
            },
            "today_snapshot": {
                "date": today.strftime("%Y-%m-%d"),
                "present": present_today,
                "absent": absent_today,
                "on_leave": on_leave_today,
                "unmarked": unmarked_today
            },
            "monthly_overview": {
                "month": current_month,
                "year": current_year,
                "total_present_days": monthly_stats['total_present'],
                "total_absent_days": monthly_stats['total_absent'],
                "total_leave_days": monthly_stats['total_leaves'],
                "average_attendance_percentage": avg_attendance_percentage
            },
            "designation_attendance": designation_stats,
            "action_items": {
                "pending_leave_requests": pending_leaves
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)