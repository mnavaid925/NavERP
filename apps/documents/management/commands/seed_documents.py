from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed demo data for the Document Management System (DMS) module"

    def handle(self, *args, **options):
        self.stdout.write("Documents seeder placeholder.")
