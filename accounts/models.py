import random
import string

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import (
    AbstractUser,
    BaseUserManager,
)


# =====================================================
# TH URID GENERATOR
# =====================================================

def generate_custom_th_urid():
    body = ''.join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=11
        )
    )
    return f"TH_{body}"


# =====================================================
# SOFT DELETE MIXIN
# =====================================================

class SoftDeleteMixin(models.Model):

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column="created_at"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        db_column="updated_at"
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_column="deleted_at"
    )

    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        db_column="created_by",
        db_constraint=False,
    )

    updated_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        db_column="updated_by",
        db_constraint=False,
    )

    deleted_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        db_column="deleted_by",
        db_constraint=False,
    )

    is_active = models.BooleanField(
        default=True,
        db_column="is_active"
    )

    th_urid = models.CharField(
        max_length=36,
        default=generate_custom_th_urid,
        editable=False,
        unique=True,
        db_column="th_urid",
    )

    class Meta:
        abstract = True

    def delete(
        self,
        using=None,
        keep_parents=False,
        by_user=None
    ):
        self.deleted_at = timezone.now()
        self.is_active = False

        if by_user:
            self.deleted_by = by_user

        self.save()

    def hard_delete(self):
        super().delete()


# =====================================================
# ROLE MODEL
# =====================================================

class Role(SoftDeleteMixin):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    code = models.CharField(
        max_length=50,
        unique=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        db_table = "acc_roles"
        ordering = ["name"]

    def __str__(self):
        return self.name


# =====================================================
# USER MANAGER
# =====================================================

class UserManager(BaseUserManager):

    def create_user(
        self,
        username,
        email,
        password=None,
        **extra_fields
    ):
        if not username:
            raise ValueError("Username is required")

        email = self.normalize_email(email)

        user = self.model(
            username=username,
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(
        self,
        username,
        email,
        password,
        **extra_fields
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(
            username,
            email,
            password,
            **extra_fields
        )


# =====================================================
# USER MODEL
# =====================================================

class User(AbstractUser, SoftDeleteMixin):

    EMPLOYEE_TYPES = (
        ("PERMANENT", "Permanent"),
        ("CONTRACT", "Contract"),
        ("INTERN", "Intern"),
        ("CONSULTANT", "Consultant"),
    )

    employee_code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True
    )

    phone_number = models.CharField(
        max_length=15,
        null=True,
        blank=True
    )

    profile_picture = models.ImageField(
        upload_to="employees/profile_photos/",
        null=True,
        blank=True
    )

    employee_type = models.CharField(
        max_length=20,
        choices=EMPLOYEE_TYPES,
        default="PERMANENT"
    )

    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users"
    )

    reporting_manager = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="team_members"
    )

    last_password_changed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    objects = UserManager()

    class Meta:
        db_table = "acc_users"
        ordering = ["id"]

    def __str__(self):
        return (
            f"{self.employee_code} - "
            f"{self.get_full_name()}"
        )

