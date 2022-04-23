from django.core.management.base import BaseCommand, CommandError
from secateur.models import User


class Command(BaseCommand):
    help = "Promote a user to be the Django superuser."

    def add_arguments(self, parser):
        parser.add_argument("screen_name")

    def handle(self, *args, **options):
        user = User.objects.get(screen_name=options["screen_name"])
        user.is_superuser = True
        user.is_staff = True
        user.is_twitter_api_enabled = True
        user.save()
        print(f"Promoted user {user} to superuser.")
