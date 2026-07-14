from django.core.management.base import BaseCommand
from django.db import transaction
from employees.models import EmployeeProfile

class Command(BaseCommand):
    help = 'Resets passwords for all active employees in department 1 to upsrlm@<last_4_digits_of_phone>'

    def handle(self, *args, **options):
        # Fetch all active employee profiles in department 1
        profiles = EmployeeProfile.objects.select_related('user').filter(
            department_id=1,
            is_active=True,
            user__is_active=True
        )

        total_profiles = profiles.count()
        if total_profiles == 0:
            self.stdout.write(self.style.WARNING("No active employees found in department_id=1."))
            return

        self.stdout.write(f"Found {total_profiles} active employees in Department 1. Starting password reset...")

        updated_count = 0
        fallback_count = 0

        with transaction.atomic():
            for profile in profiles:
                user = profile.user
                phone = user.phone_number

                # Determine the last 4 digits of the mobile number
                if phone and len(phone.strip()) >= 4:
                    last_four = phone.strip()[-4:]
                else:
                    # Fallback if the user has no phone number or it's too short
                    last_four = "1234"
                    fallback_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Warning: {user.employee_code} ({user.get_full_name()}) has no valid phone number. "
                            f"Using fallback password: upsrlm@1234"
                        )
                    )

                # Generate and set the new password
                new_password = f"upsrlm@{last_four}"
                user.set_password(new_password)
                user.save(update_fields=['password'])
                
                updated_count += 1

        # Final Summary Output
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully updated passwords for {updated_count} employees.\n"
                f"Used fallback '1234' for {fallback_count} employees."
            )
        )