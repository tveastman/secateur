from django.core.management.base import BaseCommand, CommandError
from secateur.models import User


class Command(BaseCommand):
    help = "Promote a user to be the Django superuser."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        user = User.objects.get(username=options["username"])
        user.is_superuser = True
        user.is_staff = True
        user.save()
        print(f"Promoted user {user} to superuser.")
