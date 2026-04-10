import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from authentication.models import AdminProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Create initial super admin from env vars (idempotent — safe to run on every deploy)"

    def handle(self, *args, **options):
        email = os.getenv("ADMIN_EMAIL")
        password = os.getenv("ADMIN_PASSWORD")

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                "ADMIN_EMAIL or ADMIN_PASSWORD not set — skipping admin seed."
            ))
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write("Admin already exists — skipping.")
            return

        user = User.objects.create(
            email=email,
            role="super_admin",
            is_active=True,
            is_staff=True,
        )
        user.set_password(password)
        user.save(update_fields=["password", "is_staff"])

        AdminProfile.objects.create(user=user, level="super_admin")

        self.stdout.write(self.style.SUCCESS(f"Super admin created: {email}"))
