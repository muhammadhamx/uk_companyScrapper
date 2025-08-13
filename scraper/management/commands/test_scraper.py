from django.core.management.base import BaseCommand
from scraper.services import CompaniesHouseScraper


class Command(BaseCommand):
    help = 'Test the Companies House scraper with a company name'

    def add_arguments(self, parser):
        parser.add_argument('company_name', type=str, help='Name of the company to search for')
        parser.add_argument(
            '--max-results',
            type=int,
            default=5,
            help='Maximum number of results to return (default: 5)'
        )

    def handle(self, *args, **options):
        company_name = options['company_name']
        max_results = options['max_results']
        
        self.stdout.write(f'Testing scraper with company: {company_name}')
        self.stdout.write(f'Max results: {max_results}')
        self.stdout.write('-' * 50)
        
        try:
            scraper = CompaniesHouseScraper()
            results = scraper.search_company(company_name, max_results)
            
            if not results:
                self.stdout.write(self.style.WARNING('No companies found.'))
                return
            
            self.stdout.write(f'Found {len(results)} companies:')
            self.stdout.write('-' * 50)
            
            for i, company in enumerate(results, 1):
                self.stdout.write(f'{i}. {company.get("name", "N/A")}')
                self.stdout.write(f'   Company Number: {company.get("company_number", "N/A")}')
                self.stdout.write(f'   Status: {company.get("status", "N/A")}')
                self.stdout.write(f'   URL: {company.get("url", "N/A")}')
                self.stdout.write('')
                
                # Test detailed scraping for the first company
                if i == 1 and company.get('url'):
                    self.stdout.write('Testing detailed scraping for first company...')
                    detailed_data = scraper.scrape_company_details(company['url'])
                    if detailed_data:
                        self.stdout.write('✓ Successfully scraped detailed information')
                        if detailed_data.get('directors'):
                            self.stdout.write(f'  Directors found: {len(detailed_data["directors"])}')
                        if detailed_data.get('sic_codes'):
                            self.stdout.write(f'  SIC codes: {len(detailed_data["sic_codes"])}')
                    else:
                        self.stdout.write('✗ Failed to scrape detailed information')
                    self.stdout.write('')
            
            self.stdout.write(self.style.SUCCESS('Test completed successfully!'))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during scraping test: {str(e)}')
            )
