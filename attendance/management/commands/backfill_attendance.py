from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from employees.models import EmployeeProfile
from attendance.models import DailyAttendance, LeaveApplication

class Command(BaseCommand):
    help = 'Backfills daily attendance records starting from June 1, 2026.'

    def handle(self, *args, **kwargs):
        start_date = date(2026, 6, 1)
        end_date = date.today()

        if start_date >= end_date:
            self.stdout.write(self.style.WARNING('Start date is in the future or is today. Nothing to backfill.'))
            return

        active_employees = EmployeeProfile.objects.filter(is_active=True)
        
        created_count = 0

        with transaction.atomic():
            current_date = start_date
            
            while current_date <= end_date:
                is_weekend = current_date.weekday() in [5, 6]

                for emp in active_employees:
                    # Skip if employee hasn't joined yet
                    if emp.date_of_joining > current_date:
                        continue
                        
                    # Skip if employee had left before this date
                    if emp.date_of_leaving and emp.date_of_leaving < current_date:
                        continue

                    # Check if record already exists
                    if DailyAttendance.objects.filter(employee=emp, date=current_date).exists():
                        continue

                    # Check for Approved Leaves
                    approved_leave = LeaveApplication.objects.filter(
                        employee=emp,
                        status="APPROVED",
                        start_date__lte=current_date,
                        end_date__gte=current_date,
                        is_active=True
                    ).first()

                    status = "PRESENT"
                    is_locked = False

                    if approved_leave:
                        if approved_leave.leave_type == "PAID":
                            status = "PAID_LEAVE"
                        elif approved_leave.leave_type == "CASUAL":
                            status = "CASUAL_LEAVE"
                        elif approved_leave.leave_type == "SICK":
                            status = "SICK_LEAVE"
                        is_locked = True
                    elif is_weekend:
                        status = "WEEKEND"

                    DailyAttendance.objects.create(
                        employee=emp,
                        date=current_date,
                        status=status,
                        is_locked=is_locked
                    )
                    created_count += 1
                
                # Move to next day
                current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f'Successfully backfilled {created_count} attendance records.'))