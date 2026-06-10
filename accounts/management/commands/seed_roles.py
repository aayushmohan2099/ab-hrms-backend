from django.core.management.base import BaseCommand

from accounts.models import Role


class Command(BaseCommand):
    help = "Seed default HRMS roles"

    def handle(self, *args, **kwargs):

        roles = [
            {
                "name": "Administrator",
                "code": "ADM1N7233",
                "description": "Full HRMS access including employee, payroll, attendance, reports and system administration."
            },
            {
                "name": "Manager",
                "code": "MAN4GER55",
                "description": "Department manager with access to employees under their reporting hierarchy."
            },
            {
                "name": "Employee",
                "code": "EMPL0YEE91",
                "description": "Regular employee with access to self-service HRMS features."
            },
        ]

        for role in roles:
            obj, created = Role.objects.get_or_create(
                code=role["code"],
                defaults={
                    "name": role["name"],
                    "description": role["description"],
                }
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created Role: {obj.name}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Role already exists: {obj.name}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Default HRMS roles seeded successfully."
            )
        )