# attendance/api/views.py
import csv
import io
import requests
import calendar
from datetime import date, timedelta, datetime
from django.db.models import Sum, Q, F
from django.utils import timezone
from calendar import monthrange
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch

from attendance.models import *
from employees.models import EmployeeProfile
from departments.models import Department
from .serializers import *

# =====================================================
# MONTHLY ATTENDANCE LISTING (API 1)
# =====================================================
class DepartmentMonthlyAttendanceView(APIView):
    """
    Accepts department_id, month, and year.
    Returns all employees in that department along with their daily attendance array.
    Also calculates the total approved leaves taken by the employee in the specified month,
    and provides the detailed leave application records for that month.
    """
    def get(self, request, dept_id):
        try:
            month = int(request.query_params.get('month', date.today().month))
            year = int(request.query_params.get('year', date.today().year))
        except ValueError:
            return Response({"detail": "Invalid month or year."}, status=status.HTTP_400_BAD_REQUEST)

        # Get active employees for this department
        employees = EmployeeProfile.objects.select_related('user', 'designation').filter(
            department_id=dept_id, 
            is_active=True
        )

        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)

        # Fetch all attendance records for this department for the given month/year
        daily_records = DailyAttendance.objects.filter(
            employee__department_id=dept_id,
            date__gte=start_date,
            date__lte=end_date,
            is_active=True
        ).order_by('date')

        # Group daily records by employee ID
        records_by_emp = {}
        for record in daily_records:
            records_by_emp.setdefault(record.employee_id, []).append(record)

        # Fetch Approved Leaves overlapping with this month
        approved_leaves = LeaveApplication.objects.filter(
            employee__department_id=dept_id,
            status="APPROVED",
            start_date__lte=end_date,
            end_date__gte=start_date,
            is_active=True
        )

        # Calculate exact days overlapping in this specific month and group leave application details
        leaves_by_emp = {}
        leave_apps_by_emp = {}
        for leave in approved_leaves:
            # Group the detailed leave object
            leave_apps_by_emp.setdefault(leave.employee_id, []).append(leave)

            # Calculate total days overlapping
            overlap_start = max(leave.start_date, start_date)
            overlap_end = min(leave.end_date, end_date)
            
            if overlap_start <= overlap_end:
                days_taken = (overlap_end - overlap_start).days + 1
                leaves_by_emp[leave.employee_id] = leaves_by_emp.get(leave.employee_id, 0) + days_taken

        # Attach records and leave counts to the employee instances temporarily for the serializer
        for emp in employees:
            emp.current_month_records = records_by_emp.get(emp.id, []) # Used by get_daily_records and present_summary
            emp.total_leaves_this_month = leaves_by_emp.get(emp.id, 0)
            emp.current_month_leave_applications = leave_apps_by_emp.get(emp.id, []) # Used by get_current_month_records
            emp.total_days_in_month = last_day

        serializer = EmployeeMonthlyAttendanceSerializer(employees, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =====================================================
# LEAVE APPLICATION WORKFLOW
# =====================================================

class LeaveApplyView(generics.CreateAPIView):
    """
    Employee endpoint to apply for leave.
    Auto-assigns the approver to the reporting manager or department head.
    """
    serializer_class = LeaveApplicationBaseSerializer

    def perform_create(self, serializer):
        emp_profile = get_object_or_404(EmployeeProfile, user=self.request.user, is_active=True)
        
        # Determine Approver: Reporting Manager -> fallback -> Department Head -> fallback -> None
        approver = emp_profile.user.reporting_manager
        if not approver:
            approver = emp_profile.department.head
            
        serializer.save(
            employee=emp_profile, 
            created_by=self.request.user,
            approved_by=approver # Assigned to pending approver queue
        )

class ManagerLeaveApplicationListView(generics.ListAPIView):
    """
    1) Leave Application Listing API.
    - Role 1 (Admin): Sees all leave applications in the system.
    - Role 2 (Manager): Sees ONLY applications where they are the assigned reporting manager.
    - Others: Unauthorized.
    """
    serializer_class = LeaveApplicationComprehensiveSerializer

    def get_queryset(self):
        user = self.request.user
        role_id = user.role.id if user.role else None

        if role_id == 1:
            # Administrator: See everything
            return LeaveApplication.objects.select_related(
                'employee__user', 'employee__department', 'employee__designation', 'approved_by'
            ).filter(is_active=True).order_by('-start_date')
        
        elif role_id == 2:
            # Manager: See only employees reporting directly to them
            return LeaveApplication.objects.select_related(
                'employee__user', 'employee__department', 'employee__designation', 'approved_by'
            ).filter(
                employee__user__reporting_manager=user, 
                is_active=True
            ).order_by('-start_date')
            
        else:
            # Return empty queryset, the view will handle the 403 response
            return LeaveApplication.objects.none()

    def list(self, request, *args, **kwargs):
        role_id = request.user.role.id if request.user.role else None
        if role_id not in [1, 2]:
            return Response({"detail": "Unauthorized. Only Admins and Managers can access this list."}, status=status.HTTP_403_FORBIDDEN)
            
        return super().list(request, *args, **kwargs)


class LeaveApplicationDetailView(generics.RetrieveAPIView):
    """
    2) Detailed Leave Application API.
    Returns deeply nested objects for full context.
    """
    serializer_class = LeaveApplicationDeepDetailSerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'leave_id'

    def get_queryset(self):
        user = self.request.user
        role_id = user.role.id if user.role else None

        # Base queryset with necessary joins
        qs = LeaveApplication.objects.select_related(
            'employee__user', 'employee__department', 'employee__designation', 'approved_by'
        ).filter(is_active=True)

        if role_id == 1:
            return qs
        elif role_id == 2:
            return qs.filter(employee__user__reporting_manager=user)
        else:
            return LeaveApplication.objects.none()

    def retrieve(self, request, *args, **kwargs):
        role_id = request.user.role.id if request.user.role else None
        if role_id not in [1, 2]:
            return Response({"detail": "Unauthorized."}, status=status.HTTP_403_FORBIDDEN)
            
        return super().retrieve(request, *args, **kwargs)


class LeaveActionView(APIView):
    """
    Manager endpoint to Approve or Reject a leave application.
    If Approved, updates DailyAttendance.
    """
    @transaction.atomic
    def post(self, request, leave_id, action):
        if action not in ['approve', 'reject']:
            return Response({"detail": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)

        leave_app = get_object_or_404(LeaveApplication, id=leave_id, status="PENDING", is_active=True)
        
        # Check Authorization
        role_id = request.user.role.id if request.user.role else None
        
        if role_id == 2:
             if leave_app.employee.user.reporting_manager != request.user:
                 return Response({"detail": "You are not authorized to approve this leave."}, status=status.HTTP_403_FORBIDDEN)
        elif role_id != 1:
             return Response({"detail": "Unauthorized."}, status=status.HTTP_403_FORBIDDEN)

        if action == 'reject':
            leave_app.status = "REJECTED"
        elif action == 'approve':
            leave_app.status = "APPROVED"
            
            # Update Daily Attendance Rows
            current_date = leave_app.start_date
            while current_date <= leave_app.end_date:
                att_status = "PRESENT"
                if leave_app.leave_type == "PAID":
                    att_status = "PAID_LEAVE"
                elif leave_app.leave_type == "CASUAL":
                    att_status = "CASUAL_LEAVE"
                elif leave_app.leave_type == "SICK":
                    att_status = "SICK_LEAVE"

                DailyAttendance.objects.update_or_create(
                    employee=leave_app.employee,
                    date=current_date,
                    defaults={
                        'status': att_status,
                        'is_locked': True, 
                        'updated_by': request.user
                    }
                )
                current_date += timedelta(days=1)

        leave_app.approved_by = request.user
        leave_app.updated_by = request.user
        leave_app.save()

        return Response({"detail": f"Leave application {action}d successfully."}, status=status.HTTP_200_OK)

# =====================================================
# MARK ABSENT (API 3)
# =====================================================

class MarkAbsentView(APIView):
    """
    Allows a manager/HR to explicitly mark an employee absent on a specific date.
    Payload: {"employee_code": "AB-IT-001", "date": "2026-06-17"}
    """
    def post(self, request):
        emp_code = request.data.get('employee_code')
        target_date = request.data.get('date')

        if not emp_code or not target_date:
            return Response({"detail": "employee_code and date are required."}, status=status.HTTP_400_BAD_REQUEST)

        emp_profile = get_object_or_404(EmployeeProfile, user__employee_code=emp_code, is_active=True)

        DailyAttendance.objects.update_or_create(
            employee=emp_profile,
            date=target_date,
            defaults={
                'status': 'ABSENT',
                'is_locked': True, # Manager override locks it
                'updated_by': request.user
            }
        )

        return Response({"detail": f"Employee {emp_code} marked absent on {target_date}."}, status=status.HTTP_200_OK)


# =====================================================
# BULK ATTENDANCE UPLOAD (API 4)
# =====================================================

class BulkAttendanceUploadView(APIView):
    """
    Uploads a CSV to bulk-replace attendance using a monthly matrix format.
    Automatically assigns WEEKEND for Saturdays/Sundays and fetches public
    holidays from Nager.Date to assign HOLIDAY.
    """
    # Mapping exact user inputs to Database STATUS_CHOICES
    CODE_MAPPING = {
        'P': 'PRESENT',
        'A': 'ABSENT',
        'EL': 'EARNED',
        'CL': 'CASUAL',
        'SL': 'SICK',
        'LWP': 'LWP',
        'ESL': 'ESL',
        'H': 'HOLIDAY',   # Added H for HOLIDAY
        'W': 'WEEKEND',   # Added W for WEEKEND
    }

    def get(self, request):
        if request.query_params.get('download_format') == 'true':
            try:
                month = int(request.query_params.get('month', date.today().month))
                year = int(request.query_params.get('year', date.today().year))
            except ValueError:
                return Response({"detail": "Invalid month or year."}, status=status.HTTP_400_BAD_REQUEST)

            _, max_days = calendar.monthrange(year, month)

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="attendance_template_{year}_{month:02d}.csv"'
            
            writer = csv.writer(response)
            
            # Header: S.no, employee_code, 1, 2, 3, ..., max_days
            header = ['S.no', 'employee_code'] + [str(d) for d in range(1, max_days + 1)]
            writer.writerow(header)
            
            # Example Row
            example_row = ['1', 'AB-TEST-001'] + ['P'] * max_days
            writer.writerow(example_row)
            
            return response
            
        return Response({"detail": "Use ?download_format=true to get the template."}, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def post(self, request):
        file = request.FILES.get('file')
        month_str = request.data.get('month')
        year_str = request.data.get('year')

        if not file or not month_str or not year_str:
            return Response({"detail": "File, month, and year are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            month = int(month_str)
            year = int(year_str)
            _, max_days = calendar.monthrange(year, month)
        except ValueError:
            return Response({"detail": "Invalid month or year payload."}, status=status.HTTP_400_BAD_REQUEST)

        updated_count = 0
        errors = []

        try:
            # Use utf-8-sig to automatically handle BOM (Byte Order Mark) from Windows Excel CSVs
            decoded_file = file.read().decode('utf-8-sig')
            
            # Read CSV. Fallback to tab-delimiter if standard comma parsing fails
            reader = csv.DictReader(io.StringIO(decoded_file))
            rows = list(reader)
            
            if rows and len(rows[0].keys()) == 1 and '\t' in list(rows[0].keys())[0]:
                reader = csv.DictReader(io.StringIO(decoded_file), delimiter='\t')
                rows = list(reader)

            if not rows:
                return Response({"detail": "The uploaded file is empty."}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch public holidays from Free API (No Auth Required)
            holidays_cache = set()
            try:
                resp = requests.get(f"https://date.nager.at/api/v3/PublicHolidays/{year}/IN", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    for holiday in data:
                        if "date" in holiday:
                            holidays_cache.add(holiday["date"])
                else:
                    errors.append(f"Warning: Holiday API returned status {resp.status_code} for year {year}.")
            except Exception as e:
                errors.append(f"Warning: Could not fetch holidays for year {year} ({str(e)}).")

            # Pre-fetch active employees to minimize database hits inside the loop
            active_employees = {
                emp.user.employee_code: emp 
                for emp in EmployeeProfile.objects.filter(is_active=True).select_related('user')
            }

            # Pre-fetch existing attendance records to prevent overwriting existing holidays
            start_date = date(year, month, 1)
            end_date = date(year, month, max_days)
            existing_records = DailyAttendance.objects.filter(
                employee__in=active_employees.values(),
                date__range=(start_date, end_date)
            ).values('employee__user__employee_code', 'date', 'status')
            
            existing_map = {}
            for rec in existing_records:
                emp_code = rec['employee__user__employee_code']
                date_str = rec['date'].strftime("%Y-%m-%d")
                if emp_code not in existing_map:
                    existing_map[emp_code] = {}
                existing_map[emp_code][date_str] = rec['status']

            # Process each row
            for index, row in enumerate(rows):
                code = (row.get('employee_code') or '').strip()
                
                if not code:
                    continue  # Skip rows without an employee code
                
                emp = active_employees.get(code)
                if not emp:
                    errors.append(f"Row {index + 2}: Active Employee '{code}' not found.")
                    continue

                # Iterate through day columns
                for day in range(1, max_days + 1):
                    val = (row.get(str(day)) or '').strip().upper()
                    
                    if not val:
                        continue  # Skip empty cells
                    
                    status_code = self.CODE_MAPPING.get(val)
                    if not status_code:
                        errors.append(f"Row {index + 2}: Invalid attendance code '{val}' on Day {day}. Skipped.")
                        continue

                    target_date = date(year, month, day)
                    target_date_str = target_date.strftime("%Y-%m-%d")

                    # 1) If a holiday/weekend pattern exists in the DB, DO NOT OVERWRITE IT!
                    existing_status = existing_map.get(code, {}).get(target_date_str)
                    if existing_status in ['HOLIDAY', 'WEEKEND'] and status_code not in ['HOLIDAY', 'WEEKEND']:
                        continue

                    # --- AUTOMATIC WEEKEND & HOLIDAY ASSIGNMENT ---
                    # 2) User can explicitly mark 'H' or 'W' which takes priority over auto-generation
                    if status_code in ['HOLIDAY', 'WEEKEND']:
                        final_status = status_code
                    elif target_date.weekday() >= 5:  # 5 = Sat, 6 = Sun
                        final_status = 'WEEKEND'
                    elif target_date_str in holidays_cache:
                        final_status = 'HOLIDAY'
                    else:
                        final_status = status_code

                    DailyAttendance.objects.update_or_create(
                        employee=emp,
                        date=target_date,
                        defaults={
                            'status': final_status,
                            'is_locked': True,  # Bulk uploads lock the row
                            'updated_by': request.user
                        }
                    )
                    updated_count += 1

        except Exception as e:
            return Response({"detail": f"Error parsing file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "detail": f"Bulk upload processed. {updated_count} daily records updated.",
            "errors": errors
        }, status=status.HTTP_200_OK)
    
# Emplolyee Leave History
class MyLeaveApplicationListView(generics.ListAPIView):
    """
    Employee endpoint to list their own leave history.
    """
    serializer_class = LeaveApplicationBaseSerializer # Or whichever serializer you prefer for the employee view

    def get_queryset(self):
        # Fetch the EmployeeProfile for the logged-in user
        emp_profile = get_object_or_404(EmployeeProfile, user=self.request.user, is_active=True)
        # Return only leaves associated with this specific employee
        return LeaveApplication.objects.filter(employee=emp_profile, is_active=True).order_by('-start_date')    
    
# Bulk mark Holidays
class BulkMarkHolidaysView(APIView):
    """
    Accepts department_id, year, month, and a list of dates.
    Iterates through ALL active employees in the specified department
    and marks the given dates as 'HOLIDAY' in their DailyAttendance.
    Employees whose date_of_joining is AFTER the holiday date are skipped.
    """
    @transaction.atomic
    def post(self, request):
        department_id = request.data.get('department_id')
        dates = request.data.get('dates', []) # Expected list of "YYYY-MM-DD" strings
        holiday_reason = request.data.get('holiday_reason', '') # <-- ADDED: Extract reason

        if not department_id or not dates:
            return Response(
                {"detail": "department_id and a list of dates are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(dates, list):
             return Response(
                {"detail": "Dates must be provided as a list of strings."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate department
        department = get_object_or_404(Department, id=department_id, is_active=True)

        # Validate date formats
        parsed_dates = []
        for date_str in dates:
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                parsed_dates.append(parsed_date)
            except ValueError:
                return Response(
                    {"detail": f"Invalid date format: '{date_str}'. Must be YYYY-MM-DD."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Get all active employees in the department
        employees = EmployeeProfile.objects.filter(department=department, is_active=True)
        if not employees.exists():
            return Response(
                {"detail": "No active employees found in this department."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        updated_count = 0
        
        # Mark holiday for each employee for each date
        for emp in employees:
            for target_date in parsed_dates:
                # Ensure the employee had joined on or before the holiday date
                if emp.date_of_joining and emp.date_of_joining > target_date:
                    continue  # Skip marking holiday if they joined after this date

                DailyAttendance.objects.update_or_create(
                    employee=emp,
                    date=target_date,
                    defaults={
                        'status': 'HOLIDAY',
                        'holiday_reason': holiday_reason, # <-- ADDED: Save the reason
                        'is_locked': True, # Lock it so cron jobs or regular uploads don't override
                        'updated_by': request.user
                    }
                )
                updated_count += 1

        return Response({
            "detail": f"Successfully marked {len(parsed_dates)} holiday(s) for eligible employee(s). Total records updated: {updated_count}."
        }, status=status.HTTP_200_OK)

# Leave Balance API
class EmployeeLeaveBalanceView(APIView):
    """
    Calculates and returns the leave balances for an employee for the CURRENT CALENDAR YEAR.
    Automatically enforces the Casual Leave (CL) lapse rule across half-yearly cycles.
    Format: "Leaves_left / Total Allowed"
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_code):
        employee = get_object_or_404(EmployeeProfile, user__employee_code=employee_code, is_active=True)
        
        current_date = timezone.now().date()
        current_year = current_date.year
        
        # 1. Calendar year boundaries (Jan - Dec)
        year_start = date(current_year, 1, 1)
        year_end = date(current_year, 12, 31)
        
        # 2. Half-year boundaries (For specific CL lapsing rules)
        h1_start = date(current_year, 1, 1)
        h1_end = date(current_year, 6, 30)
        h2_start = date(current_year, 7, 1)
        h2_end = date(current_year, 12, 31)
        
        # 3. Fetch all Leave Limits from DB
        limits = LeaveLimits.objects.filter(is_active=True)
        limit_dict = {limit.leave_type: limit.leave_count for limit in limits}
        
        # 4. Fetch all APPROVED leaves overlapping with the current calendar year
        approved_leaves = LeaveApplication.objects.filter(
            employee=employee,
            status="APPROVED",
            start_date__lte=year_end,
            end_date__gte=year_start,
            is_active=True
        )
        
        taken_dict = {lt[0]: 0 for lt in LeaveApplication.LEAVE_TYPES}
        cl_taken_h1 = 0
        cl_taken_h2 = 0
        
        # 5. Process overlapping days from Leave Applications
        for leave in approved_leaves:
            # Overlap for the full year
            overlap_start = max(leave.start_date, year_start)
            overlap_end = min(leave.end_date, year_end)
            
            if overlap_start <= overlap_end:
                days_taken = (overlap_end - overlap_start).days + 1
                taken_dict[leave.leave_type] += days_taken
                
                # Custom Half-Yearly tracking for Casual Leave (CL)
                if leave.leave_type == "CASUAL":
                    # H1 overlap
                    h1_os = max(leave.start_date, h1_start)
                    h1_oe = min(leave.end_date, h1_end)
                    if h1_os <= h1_oe:
                        cl_taken_h1 += (h1_oe - h1_os).days + 1
                        
                    # H2 overlap
                    h2_os = max(leave.start_date, h2_start)
                    h2_oe = min(leave.end_date, h2_end)
                    if h2_os <= h2_oe:
                        cl_taken_h2 += (h2_oe - h2_os).days + 1

        # ---> NEW SURGICAL ADDITION: Process Bulk Upload AttendanceRecords <---
        # Fetch verified/uploaded attendance records for this calendar year
        att_records = AttendanceRecord.objects.filter(
            employee=employee,
            upload__att_year=current_year,
            is_active=True
        ).select_related('upload')

        for att in att_records:
            month = att.upload.att_month
            
            # Map standard record fields to the tracking dictionary
            taken_dict["CASUAL"] += att.casual_leave
            taken_dict["SICK"] += att.sick_leave
            taken_dict["EARNED"] += att.paid_leave  # Assuming paid_leave maps to EARNED limit
            
            # Apply CL H1/H2 rules based on the upload month
            if month <= 6:
                cl_taken_h1 += att.casual_leave
            else:
                cl_taken_h2 += att.casual_leave
        # ---> END SURGICAL ADDITION <---
        
        # 6. Construct Final Balance Dictionary
        response_data = {}
        total_allowed_year = 0
        total_leaves_left_year = 0
        
        for leave_type, limit in limit_dict.items():
            if leave_type == "CASUAL":
                # CL: Cannot carry forward to next 6 months.
                half_limit = limit // 2  # Assuming 10 total -> 5 per half
                rem_h1 = max(0, half_limit - cl_taken_h1)
                rem_h2 = max(0, half_limit - cl_taken_h2)
                
                if current_date <= h1_end:
                    # If in H1: You have H1 remainder, and H2 quota is untouched for later
                    leaves_left = rem_h1 + half_limit
                else:
                    # If in H2: H1 remainder is permanently lapsed. Only H2 remainder counts
                    leaves_left = rem_h2
                    
            else:
                # All other leaves (including EL which carries forward internally within the year)
                taken = taken_dict.get(leave_type, 0)
                leaves_left = max(0, limit - taken)
            
            response_data[leave_type] = f"{leaves_left} / {limit}"
            total_allowed_year += limit
            total_leaves_left_year += leaves_left
            
        # Ensure all Leave Types exist in the response even if not strictly seeded in DB limits
        for lt in LeaveApplication.LEAVE_TYPES:
            l_type = lt[0]
            if l_type not in response_data:
                response_data[l_type] = "0 / 0"
                
        total_leaves_left_year = total_leaves_left_year - 60                
        total_allowed_year = total_allowed_year - 60                
        response_data["TOTAL"] = f"{total_leaves_left_year} / {total_allowed_year}"
        
        return Response(response_data, status=status.HTTP_200_OK)

# Per employee calendar view
class EmployeeMonthlyAttendanceView(APIView):
    """
    Fetches all daily attendance records and approved leave applications 
    for a specific employee for a given month and year.
    Designed for calendar rendering on the frontend.
    """
    def get(self, request, emp_code, year, month):
        # 1. Verify Employee exists and is active
        emp = get_object_or_404(EmployeeProfile, user__employee_code=emp_code, is_active=True)

        # 2. Fetch Daily Records for the specified month
        daily_records = DailyAttendance.objects.filter(
            employee=emp,
            date__year=year,
            date__month=month,
            is_active=True
        ).order_by('date')

        # Dynamically get the last day of the month to prevent "invalid date" validation errors (e.g. June 31st)
        _, last_day = calendar.monthrange(year, month)

        # 3. Fetch Leave Applications that overlap with the specified month
        # We want leaves where the start_date is in this month, 
        # OR the end_date is in this month,
        # OR the leave spans entirely over this month.
        leave_apps = LeaveApplication.objects.filter(
            employee=emp,
            status='APPROVED',
            is_active=True
        ).filter(
            # Start date is in the target month/year
            models.Q(start_date__year=year, start_date__month=month) |
            # End date is in the target month/year
            models.Q(end_date__year=year, end_date__month=month) |
            # Target month/year is completely enclosed within the leave dates
            models.Q(start_date__lt=f"{year}-{month:02d}-01", end_date__gt=f"{year}-{month:02d}-{last_day:02d}") 
        )

        # 4. Serialize data - USING THE CORRECT SERIALIZERS
        records_data = DailyAttendanceSerializer(daily_records, many=True).data
        leaves_data = LeaveApplicationBaseSerializer(leave_apps, many=True).data

        # Safe Object Response:
        return Response({
            "daily_records": records_data, # Use this for setCurrentRecords(data.daily_records)
            "current_month_records": leaves_data # Used for setCurrentLeaveApps(data.current_month_records)
        }, status=status.HTTP_200_OK)