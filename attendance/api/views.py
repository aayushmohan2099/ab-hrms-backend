# attendance/api/views.py
import csv
import io
import requests
from datetime import date, timedelta, datetime
from calendar import monthrange
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.http import HttpResponse

from attendance.models import LeaveApplication, DailyAttendance, AttendanceUpload
from employees.models import EmployeeProfile
from departments.models import Department
from .serializers import (
    LeaveApplicationBaseSerializer, 
    LeaveApplicationComprehensiveSerializer,
    LeaveApplicationDeepDetailSerializer,
    EmployeeMonthlyAttendanceSerializer
)

# =====================================================
# MONTHLY ATTENDANCE LISTING (API 1)
# =====================================================

class DepartmentMonthlyAttendanceView(APIView):
    """
    Accepts department_id, month, and year.
    Returns all employees in that department along with their daily attendance array.
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

        # Fetch all attendance records for this department for the given month/year
        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)

        daily_records = DailyAttendance.objects.filter(
            employee__department_id=dept_id,
            date__gte=start_date,
            date__lte=end_date,
            is_active=True
        ).order_by('date')

        # Group records by employee ID
        records_by_emp = {}
        for record in daily_records:
            records_by_emp.setdefault(record.employee_id, []).append(record)

        # Attach records to the employee instances temporarily for the serializer
        for emp in employees:
            emp.current_month_records = records_by_emp.get(emp.id, [])

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
    Uploads a CSV to bulk-replace attendance.
    Automatically assigns WEEKEND for Saturdays/Sundays and fetches public
    holidays from Nager.Date (free public API) to assign HOLIDAY.
    Handles BOM and invisible whitespaces gracefully.
    """
    def get(self, request):
        if request.query_params.get('download_format') == 'true':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="attendance_bulk_upload_template.csv"'
            
            writer = csv.writer(response)
            # Standard format: Code, Date, Status
            writer.writerow(['employee_code', 'date_YYYY_MM_DD', 'status_code'])
            writer.writerow(['AB-IT-001', '2026-06-17', 'PRESENT'])
            writer.writerow(['AB-IT-002', '2026-06-18', 'ABSENT'])
            
            return response
        return Response({"detail": "Use ?download_format=true to get the template."}, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        valid_statuses = [c[0] for c in DailyAttendance.STATUS_CHOICES]
        updated_count = 0
        errors = []

        try:
            # Use utf-8-sig to automatically handle BOM (Byte Order Mark) from Windows Excel CSVs
            decoded_file = file.read().decode('utf-8-sig')
            
            # Read CSV. Fallback to tab-delimiter if standard comma parsing finds only 1 giant column
            reader = csv.DictReader(io.StringIO(decoded_file))
            rows = list(reader)
            
            if rows and len(rows[0].keys()) == 1 and '\t' in list(rows[0].keys())[0]:
                reader = csv.DictReader(io.StringIO(decoded_file), delimiter='\t')
                rows = list(reader)

            if not rows:
                return Response({"detail": "The uploaded file is empty."}, status=status.HTTP_400_BAD_REQUEST)

            # 1. Extract unique years to fetch holidays efficiently
            years_to_fetch = set()
            for row in rows:
                target_date_str = (row.get('date_YYYY_MM_DD') or '').strip()
                if target_date_str:
                    try:
                        parsed_date = datetime.strptime(target_date_str, "%Y-%m-%d")
                        years_to_fetch.add(parsed_date.year)
                    except ValueError:
                        pass # Handled during row processing

            # 2. Fetch public holidays from Free API (No Auth Required)
            holidays_cache = set()
            for year in years_to_fetch:
                try:
                    # Using Nager.Date API for India holidays
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

            # 3. Process each row
            for index, row in enumerate(rows):
                code = (row.get('employee_code') or '').strip()
                target_date_str = (row.get('date_YYYY_MM_DD') or '').strip()
                status_code = (row.get('status_code') or '').strip().upper()

                if not code or not target_date_str or not status_code:
                    errors.append(f"Row {index + 2}: Missing required fields.")
                    continue
                
                if status_code not in valid_statuses:
                    errors.append(f"Row {index + 2}: Invalid status '{status_code}'. Must be one of {valid_statuses}.")
                    continue

                try:
                    parsed_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                    
                    # --- AUTOMATIC WEEKEND & HOLIDAY ASSIGNMENT ---
                    # Check if weekend (5 = Saturday, 6 = Sunday)
                    if parsed_date.weekday() >= 5:
                        status_code = 'WEEKEND'
                    # Check if public holiday
                    elif target_date_str in holidays_cache:
                        status_code = 'HOLIDAY'

                    emp = EmployeeProfile.objects.get(user__employee_code=code, is_active=True)
                    DailyAttendance.objects.update_or_create(
                        employee=emp,
                        date=parsed_date,
                        defaults={
                            'status': status_code,
                            'is_locked': True, # Bulk uploads lock the row
                            'updated_by': request.user
                        }
                    )
                    updated_count += 1
                except ValueError:
                    errors.append(f"Row {index + 2}: Invalid date format '{target_date_str}'. Use YYYY-MM-DD.")
                except EmployeeProfile.DoesNotExist:
                    errors.append(f"Row {index + 2}: Employee {code} not found.")

        except Exception as e:
            return Response({"detail": f"Error parsing file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "detail": f"Bulk upload processed. {updated_count} records updated.",
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
    """
    @transaction.atomic
    def post(self, request):
        department_id = request.data.get('department_id')
        dates = request.data.get('dates', []) # Expected list of "YYYY-MM-DD" strings

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
                DailyAttendance.objects.update_or_create(
                    employee=emp,
                    date=target_date,
                    defaults={
                        'status': 'HOLIDAY',
                        'is_locked': True, # Lock it so cron jobs or regular uploads don't override
                        'updated_by': request.user
                    }
                )
                updated_count += 1

        return Response({
            "detail": f"Successfully marked {len(parsed_dates)} holiday(s) for {employees.count()} employee(s). Total records updated: {updated_count}."
        }, status=status.HTTP_200_OK)