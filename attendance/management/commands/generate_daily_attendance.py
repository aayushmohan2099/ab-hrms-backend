from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from employees.models import EmployeeProfile
from attendance.models import DailyAttendance, LeaveApplication

class Command(BaseCommand):
    help = 'Generates daily attendance records for all active employees.'

    def handle(self, *args, **kwargs):
        today = date.today()
        # 0 = Monday, 5 = Saturday, 6 = Sunday
        is_weekend = today.weekday() in [5, 6] 

        active_employees = EmployeeProfile.objects.filter(
            is_active=True, 
            date_of_joining__lte=today
        ).exclude(
            date_of_leaving__lt=today
        )

        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for emp in active_employees:
                # 1. Check if a record already exists (maybe created manually)
                if DailyAttendance.objects.filter(employee=emp, date=today).exists():
                    skipped_count += 1
                    continue

                # 2. Check for Approved Leaves overlapping today
                approved_leave = LeaveApplication.objects.filter(
                    employee=emp,
                    status="APPROVED",
                    start_date__lte=today,
                    end_date__gte=today,
                    is_active=True
                ).first()

                # 3. Determine the default status
                status = "PRESENT"
                is_locked = False

                if approved_leave:
                    if approved_leave.leave_type == "PAID":
                        status = "PAID_LEAVE"
                    elif approved_leave.leave_type == "CASUAL":
                        status = "CASUAL_LEAVE"
                    elif approved_leave.leave_type == "SICK":
                        status = "SICK_LEAVE"
                    is_locked = True # Lock it so future adjustments don't overwrite the leave
                elif is_weekend:
                    status = "WEEKEND"

                # 4. Create the record
                DailyAttendance.objects.create(
                    employee=emp,
                    date=today,
                    status=status,
                    is_locked=is_locked
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {created_count} attendance records for {today}. Skipped {skipped_count}.'))