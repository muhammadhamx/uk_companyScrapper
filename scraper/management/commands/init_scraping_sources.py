from django.core.management.base import BaseCommand
from scraper.services import initialize_scraping_sources


class Command(BaseCommand):
    help = 'Initialize default scraping sources'

    def handle(self, *args, **options):
        self.stdout.write('Initializing scraping sources...')
        initialize_scraping_sources()
        self.stdout.write(
            self.style.SUCCESS('Successfully initialized scraping sources')
        )
