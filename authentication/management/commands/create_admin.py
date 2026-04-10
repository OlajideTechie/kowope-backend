from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from authentication.models import AdminProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Create an admin or super_admin user for testing"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Admin email address")
        parser.add_argument("--password", required=True, help="Admin password")
        parser.add_argument(
            "--level",
            choices=["admin", "super_admin"],
            default="admin",
            help="Admin level (default: admin)",
        )

    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]
        level = options["level"]

        if User.objects.filter(email=email).exists():
            raise CommandError(f"A user with email '{email}' already exists.")

        user = User.objects.create(
            email=email,
            role=level,
            is_active=True,
            is_staff=True,
        )
        user.set_password(password)
        user.save(update_fields=["password", "is_staff"])

        AdminProfile.objects.create(user=user, level=level)

        self.stdout.write(
            self.style.SUCCESS(f"Admin user created — email: {email}, level: {level}")
        )
