from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from scraper.models import ScrapingJob
from scraper.services import ScrapingService, CompaniesHouseScraper
import logging

logger = logging.getLogger('scraper')


class Command(BaseCommand):
    help = 'Test Companies House director scraping functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-number',
            type=str,
            default='00445790',
            help='Company number to test (default: 00445790)'
        )
        parser.add_argument(
            '--company-name',
            type=str,
            help='Company name to search for'
        )
        parser.add_argument(
            '--create-job',
            action='store_true',
            help='Create a scraping job and run it through the service'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Testing Companies House Director Scraping')
        )
        self.stdout.write('=' * 60)

        company_number = options['company_number']
        company_name = options.get('company_name')
        create_job = options['create_job']

        if create_job and company_name:
            self.test_full_scraping_job(company_name)
        elif company_name:
            self.test_company_search_and_scraping(company_name)
        else:
            self.test_direct_scraping(company_number)

    def test_direct_scraping(self, company_number):
        """Test direct scraping of a specific company"""
        self.stdout.write(f'\nTesting direct scraping for company: {company_number}')
        self.stdout.write('-' * 50)

        scraper = CompaniesHouseScraper()

        # Test the officers page directly
        officers_url = f"{scraper.BASE_URL}/company/{company_number}/officers"
        
        try:
            directors = scraper.scrape_directors_page(officers_url)
            
            self.stdout.write(
                self.style.SUCCESS(f'Found {len(directors)} directors from officers page')
            )
            
            for i, director in enumerate(directors, 1):
                self.stdout.write(f'\n{i}. Director Details:')
                self.stdout.write(f'   Name: {director.get("name", "Unknown")}')
                self.stdout.write(f'   Role: {director.get("officer_role", "Unknown")}')
                
                if director.get('appointed_on'):
                    self.stdout.write(f'   Appointed: {director.get("appointed_on")}')
                if director.get('resigned_on'):
                    self.stdout.write(f'   Resigned: {director.get("resigned_on")}')
                if director.get('nationality'):
                    self.stdout.write(f'   Nationality: {director.get("nationality")}')
                if director.get('occupation'):
                    self.stdout.write(f'   Occupation: {director.get("occupation")}')
                
                address = director.get('address', {})
                if address and address.get('full_address'):
                    self.stdout.write(f'   Address: {address.get("full_address")}')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error scraping directors: {str(e)}')
            )

    def test_company_search_and_scraping(self, company_name):
        """Test company search and director scraping"""
        self.stdout.write(f'\nTesting search and scraping for company: {company_name}')
        self.stdout.write('-' * 50)

        scraper = CompaniesHouseScraper()

        try:
            # Search for companies
            search_results = scraper.search_company(company_name, max_results=3)
            
            if not search_results:
                self.stdout.write(
                    self.style.WARNING('No companies found for the search term')
                )
                return

            self.stdout.write(
                self.style.SUCCESS(f'Found {len(search_results)} companies')
            )

            for i, company in enumerate(search_results, 1):
                self.stdout.write(f'\n{i}. Company: {company.get("name")}')
                self.stdout.write(f'   Number: {company.get("company_number")}')
                self.stdout.write(f'   Status: {company.get("status")}')
                self.stdout.write(f'   URL: {company.get("url")}')

                # Scrape detailed information including directors
                if company.get('url'):
                    detailed_data = scraper.scrape_company_details(company['url'])
                    if detailed_data:
                        directors = detailed_data.get('directors', [])
                        self.stdout.write(f'   Directors found: {len(directors)}')
                        
                        for j, director in enumerate(directors[:3], 1):  # Show first 3 directors
                            self.stdout.write(f'     {j}. {director.get("name", "Unknown")} - {director.get("officer_role", "Unknown role")}')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during search and scraping: {str(e)}')
            )

    def test_full_scraping_job(self, company_name):
        """Test creating and running a full scraping job"""
        self.stdout.write(f'\nTesting full scraping job for company: {company_name}')
        self.stdout.write('-' * 50)

        try:
            # Get or create a test user
            user, created = User.objects.get_or_create(
                username='test_scraper',
                defaults={'email': 'test@example.com'}
            )

            if created:
                self.stdout.write('Created test user: test_scraper')

            # Create a scraping job
            job = ScrapingJob.objects.create(
                user=user,
                company_name=company_name,
                status='pending'
            )

            self.stdout.write(f'Created scraping job: {job.id}')

            # Run the scraping job
            scraping_service = ScrapingService()
            scraping_service.start_scraping_job(job.id)

            # Refresh job from database
            job.refresh_from_db()

            self.stdout.write(f'Job completed with status: {job.status}')
            
            if job.status == 'completed':
                companies = job.companies.all()
                self.stdout.write(f'Scraped {companies.count()} companies')

                for company in companies:
                    directors = company.directors.all()
                    self.stdout.write(
                        f'\nCompany: {company.name} ({company.company_number})'
                    )
                    self.stdout.write(f'Directors: {directors.count()}')
                    
                    for director in directors:
                        self.stdout.write(f'  - {director.name} ({director.officer_role})')
                        if director.appointed_on:
                            self.stdout.write(f'    Appointed: {director.appointed_on}')
                        if director.resigned_on:
                            self.stdout.write(f'    Resigned: {director.resigned_on}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'Job failed with error: {job.error_message}')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating/running scraping job: {str(e)}')
            )

        self.stdout.write('\nTest completed!')
