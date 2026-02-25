from django.core.management.base import BaseCommand
from ticket.utils import expire_old_tickets_once_per_day

class Command(BaseCommand):
    help = "Expire old tickets daily"

    def handle(self, *args, **kwargs):
        expire_old_tickets_once_per_day()
        self.stdout.write(self.style.SUCCESS("Expired old tickets successfully"))