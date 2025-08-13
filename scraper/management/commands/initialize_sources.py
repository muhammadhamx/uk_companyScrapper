from django.core.management.base import BaseCommand
from django.db import transaction
from scraper.models import ScrapingSource


class Command(BaseCommand):
    help = 'Initialize default scraping sources in the database'

    def handle(self, *args, **options):
        """Initialize scraping sources"""
        
        sources_data = [
            {
                'name': 'Companies House',
                'base_url': 'https://find-and-update.company-information.service.gov.uk',
                'rate_limit': 10,
                'is_active': True,
                'requires_proxy': False,
                'success_rate': 0.9,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            },
            {
                'name': 'LinkedIn',
                'base_url': 'https://linkedin.com',
                'rate_limit': 5,
                'is_active': True,
                'requires_proxy': True,
                'success_rate': 0.6,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            },
            {
                'name': 'Google Search',
                'base_url': 'https://google.com',
                'rate_limit': 20,
                'is_active': True,
                'requires_proxy': False,
                'success_rate': 0.8,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            },
            {
                'name': 'Company Website',
                'base_url': 'https://example.com',
                'rate_limit': 15,
                'is_active': True,
                'requires_proxy': False,
                'success_rate': 0.7,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        with transaction.atomic():
            for source_data in sources_data:
                source, created = ScrapingSource.objects.get_or_create(
                    name=source_data['name'],
                    defaults=source_data
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created source: {source.name}')
                    )
                else:
                    # Update existing source
                    for field, value in source_data.items():
                        if field != 'name':  # Don't update the name field
                            setattr(source, field, value)
                    source.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'Updated source: {source.name}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully initialized scraping sources. '
                f'Created: {created_count}, Updated: {updated_count}'
            )
        )
