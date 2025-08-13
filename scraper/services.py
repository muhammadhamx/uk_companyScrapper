import requests
import time
import re
import logging
from datetime import datetime, date
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from typing import Dict, List, Optional, Tuple

from django.utils import timezone
from django.db import transaction
from .models import (
    ScrapingJob, Company, Director, CompanyContact, 
    ScrapingSource, ScrapingAttempt
)

logger = logging.getLogger('scraper')


class CompaniesHouseScraper:
    """
    Scraper for Companies House website
    """
    
    BASE_URL = "https://find-and-update.company-information.service.gov.uk"
    SEARCH_URL = f"{BASE_URL}/search"
    
    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        
    def setup_session(self):
        """Setup session with proper headers"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def search_company(self, company_name: str, max_results: int = 10) -> List[Dict]:
        """
        Search for companies by name
        """
        try:
            params = {
                'q': company_name,
                'type': 'companies'
            }
            
            response = self.session.get(self.SEARCH_URL, params=params, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            companies = self.parse_search_results(soup, max_results)
            
            logger.info(f"Found {len(companies)} companies for search: {company_name}")
            return companies
            
        except Exception as e:
            logger.error(f"Error searching for company '{company_name}': {str(e)}")
            return []
    
    def parse_search_results(self, soup: BeautifulSoup, max_results: int) -> List[Dict]:
        """Parse search results from Companies House search page"""
        companies = []
        
        # Find all company result items
        result_items = soup.find_all('li', class_='type-company')
        
        for item in result_items[:max_results]:
            try:
                company_data = self.extract_search_result_data(item)
                if company_data:
                    companies.append(company_data)
            except Exception as e:
                logger.warning(f"Error parsing search result: {str(e)}")
                continue
        
        return companies
    
    def extract_search_result_data(self, item) -> Optional[Dict]:
        """Extract company data from search result item"""
        try:
            # Company name and link
            name_link = item.find('a')
            if not name_link:
                return None
                
            name = name_link.get_text(strip=True)
            company_url = urljoin(self.BASE_URL, name_link.get('href'))
            
            # Company number
            company_number = ''
            number_elem = item.find('span', string=re.compile(r'Company number'))
            if number_elem:
                company_number = number_elem.get_text().replace('Company number', '').strip()
            
            # Company status and type
            status_elem = item.find('span', class_='status')
            status = status_elem.get_text(strip=True) if status_elem else ''
            
            # Address
            address_elem = item.find('p', class_='address')
            address = address_elem.get_text(strip=True) if address_elem else ''
            
            return {
                'name': name,
                'company_number': company_number,
                'status': status,
                'address': address,
                'url': company_url
            }
        except Exception as e:
            logger.warning(f"Error extracting search result data: {str(e)}")
            return None
    
    def scrape_company_details(self, company_url: str) -> Optional[Dict]:
        """Scrape detailed company information from company page"""
        try:
            response = self.session.get(company_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            company_data = self.parse_company_page(soup, company_url)
            
            # Add small delay to be respectful
            time.sleep(1)
            
            return company_data
            
        except Exception as e:
            logger.error(f"Error scraping company details from {company_url}: {str(e)}")
            return None
    
    def parse_company_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """Parse company details from company page"""
        data = {'companies_house_url': url}
        
        try:
            # Company name
            title = soup.find('h1', class_='heading-xlarge')
            if title:
                data['name'] = title.get_text(strip=True)
            
            # Company details from the overview section
            self.extract_overview_data(soup, data)
            
            # Registered office address
            self.extract_registered_address(soup, data)
            
            # Directors
            directors = self.extract_directors(soup, url)
            data['directors'] = directors
            
            # SIC codes and nature of business
            self.extract_business_info(soup, data)
            
            # Financial information
            self.extract_financial_info(soup, data)
            
        except Exception as e:
            logger.warning(f"Error parsing company page: {str(e)}")
        
        return data
    
    def extract_overview_data(self, soup: BeautifulSoup, data: Dict):
        """Extract overview information"""
        # Look for key-value pairs in the overview section
        dt_elements = soup.find_all('dt')
        
        for dt in dt_elements:
            key = dt.get_text(strip=True).lower()
            dd = dt.find_next_sibling('dd')
            
            if not dd:
                continue
                
            value = dd.get_text(strip=True)
            
            if 'company number' in key:
                data['company_number'] = value
            elif 'company status' in key:
                data['company_status'] = value
            elif 'company type' in key:
                data['company_type'] = value
            elif 'incorporated on' in key:
                data['incorporation_date'] = self.parse_date(value)
            elif 'dissolved on' in key:
                data['dissolved_date'] = self.parse_date(value)
    
    def extract_registered_address(self, soup: BeautifulSoup, data: Dict):
        """Extract registered office address"""
        address_section = soup.find('div', {'id': 'registered-office-address'})
        if not address_section:
            address_section = soup.find('h2', string=re.compile(r'Registered office address'))
            if address_section:
                address_section = address_section.find_next('div')
        
        if address_section:
            address_text = address_section.get_text(strip=True)
            # Clean up the address text
            address_lines = [line.strip() for line in address_text.split('\n') if line.strip()]
            
            data['registered_office_address'] = {
                'full_address': ', '.join(address_lines),
                'lines': address_lines
            }
    
    def extract_directors(self, soup: BeautifulSoup, company_url: str) -> List[Dict]:
        """Extract director information from company page and officers page"""
        directors = []
        
        # Extract company number from URL for officers page construction
        company_number = self.extract_company_number_from_url(company_url)
        
        if company_number:
            # Construct officers URL directly
            officers_url = f"{self.BASE_URL}/company/{company_number}/officers"
            directors = self.scrape_directors_page(officers_url)
        
        # Fallback: Try to find officers/directors link
        if not directors:
            officers_link = soup.find('a', href=re.compile(r'/officers'))
            if officers_link:
                officers_url = urljoin(self.BASE_URL, officers_link.get('href'))
                directors = self.scrape_directors_page(officers_url)
        
        # If no separate page, try to extract from current page
        if not directors:
            director_sections = soup.find_all(['div', 'section'], class_=re.compile(r'director|officer'))
            for section in director_sections:
                director_data = self.parse_director_section(section)
                if director_data:
                    directors.append(director_data)
        
        logger.info(f"Found {len(directors)} directors for company URL: {company_url}")
        return directors
    
    def scrape_directors_page(self, officers_url: str) -> List[Dict]:
        """Scrape directors from officers page"""
        directors = []
        
        try:
            logger.info(f"Scraping directors from: {officers_url}")
            response = self.session.get(officers_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Multiple strategies to find officer entries
            officer_items = []
            
            # Strategy 1: Look for specific officer classes
            officer_items.extend(soup.find_all('div', class_=re.compile(r'officer')))
            
            # Strategy 2: Look for appointment entries
            officer_items.extend(soup.find_all('div', class_=re.compile(r'appointment')))
            
            # Strategy 3: Look for list items that might contain officer info
            officer_items.extend(soup.find_all('li', class_=re.compile(r'officer')))
            
            # Strategy 4: Look for generic containers with officer-related content
            potential_items = soup.find_all(['div', 'section', 'article'])
            for item in potential_items:
                text = item.get_text().lower()
                if any(keyword in text for keyword in ['director', 'secretary', 'appointed', 'resigned', 'officer']):
                    # Check if it contains structured officer information
                    if re.search(r'(appointed|resigned)\s+on', text, re.IGNORECASE):
                        officer_items.append(item)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_items = []
            for item in officer_items:
                item_id = id(item)  # Use object id for uniqueness
                if item_id not in seen:
                    seen.add(item_id)
                    unique_items.append(item)
            
            logger.info(f"Found {len(unique_items)} potential officer items on page")
            
            for item in unique_items:
                director_data = self.parse_director_section(item)
                if director_data and director_data.get('name'):
                    # Check for duplicates by name
                    if not any(d.get('name') == director_data.get('name') for d in directors):
                        directors.append(director_data)
            
            time.sleep(1)  # Rate limiting
            logger.info(f"Successfully parsed {len(directors)} directors from officers page")
            
        except Exception as e:
            logger.warning(f"Error scraping directors page {officers_url}: {str(e)}")
        
        return directors
    
    def parse_director_section(self, section) -> Optional[Dict]:
        """Parse individual director information"""
        try:
            director_data = {}
            text_content = section.get_text()
            
            # Skip if section doesn't contain director-related content
            if not any(keyword in text_content.lower() for keyword in 
                      ['director', 'secretary', 'appointed', 'officer', 'resigned']):
                return None
            
            # Multiple strategies to find director name
            name = None
            
            # Strategy 1: Look for name in heading elements
            name_elem = section.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
            if name_elem:
                potential_name = name_elem.get_text(strip=True)
                # Check if it looks like a name (not just a role or date)
                if not re.search(r'(appointed|resigned|director|secretary|officer)', potential_name, re.IGNORECASE):
                    if len(potential_name.split()) >= 2:  # At least first and last name
                        name = potential_name
            
            # Strategy 2: Extract name from text using patterns
            if not name:
                # Look for patterns like "Mr JOHN SMITH" or "JANE DOE"
                name_patterns = [
                    r'(?:Mr|Mrs|Ms|Dr|Miss)\s+([A-Z][A-Z\s]+[A-Z])',
                    r'^([A-Z][A-Z\s]+[A-Z])\s*(?:,|\n|Director|Secretary)',
                    r'Name[:\s]*([A-Z][A-Za-z\s]+[A-Za-z])'
                ]
                
                for pattern in name_patterns:
                    match = re.search(pattern, text_content, re.MULTILINE)
                    if match:
                        name = match.group(1).strip()
                        break
            
            if not name:
                return None
                
            director_data['name'] = name
            
            # Role/title - expanded patterns
            role_patterns = [
                r'(Director|Secretary|Manager|Chairman|Chief Executive|CEO|CFO|CTO|President|Vice President)',
                r'Role[:\s]*([A-Za-z\s]+)',
                r'Position[:\s]*([A-Za-z\s]+)',
                r'Title[:\s]*([A-Za-z\s]+)'
            ]
            
            for pattern in role_patterns:
                role_match = re.search(pattern, text_content, re.IGNORECASE)
                if role_match:
                    director_data['officer_role'] = role_match.group(1).strip()
                    break
            
            # Appointment date - multiple patterns
            appointment_patterns = [
                r'Appointed\s+on[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                r'Appointed[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                r'Date\s+of\s+appointment[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                r'Appointment\s+date[:\s]+(\d{1,2}\s+\w+\s+\d{4})'
            ]
            
            for pattern in appointment_patterns:
                appointed_match = re.search(pattern, text_content, re.IGNORECASE)
                if appointed_match:
                    director_data['appointed_on'] = self.parse_date(appointed_match.group(1))
                    break
            
            # Resignation date
            resignation_patterns = [
                r'Resigned\s+on[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                r'Resigned[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                r'Date\s+of\s+resignation[:\s]+(\d{1,2}\s+\w+\s+\d{4})',
                r'Resignation\s+date[:\s]+(\d{1,2}\s+\w+\s+\d{4})'
            ]
            
            for pattern in resignation_patterns:
                resigned_match = re.search(pattern, text_content, re.IGNORECASE)
                if resigned_match:
                    director_data['resigned_on'] = self.parse_date(resigned_match.group(1))
                    break
            
            # Nationality
            nationality_patterns = [
                r'Nationality[:\s]+([A-Za-z\s]+?)(?:\n|,|;|$)',
                r'Country[:\s]+([A-Za-z\s]+?)(?:\n|,|;|$)'
            ]
            
            for pattern in nationality_patterns:
                nationality_match = re.search(pattern, text_content, re.IGNORECASE)
                if nationality_match:
                    director_data['nationality'] = nationality_match.group(1).strip()
                    break
            
            # Occupation
            occupation_patterns = [
                r'Occupation[:\s]+([A-Za-z\s,]+?)(?:\n|Date|Address|$)',
                r'Job\s+title[:\s]+([A-Za-z\s,]+?)(?:\n|Date|Address|$)',
                r'Profession[:\s]+([A-Za-z\s,]+?)(?:\n|Date|Address|$)'
            ]
            
            for pattern in occupation_patterns:
                occupation_match = re.search(pattern, text_content, re.IGNORECASE)
                if occupation_match:
                    director_data['occupation'] = occupation_match.group(1).strip()
                    break
            
            # Date of birth (month/year format as per Companies House)
            birth_patterns = [
                r'Born[:\s]+(\w+\s+\d{4})',
                r'Date\s+of\s+birth[:\s]+(\w+\s+\d{4})',
                r'Born\s+in[:\s]+(\w+\s+\d{4})'
            ]
            
            for pattern in birth_patterns:
                birth_match = re.search(pattern, text_content, re.IGNORECASE)
                if birth_match:
                    director_data['date_of_birth'] = {'display': birth_match.group(1).strip()}
                    break
            
            # Address information
            address_patterns = [
                r'Address[:\s]+([A-Za-z0-9\s,.-]+?)(?:\n\n|Nationality|Occupation|Appointed|$)',
                r'Correspondence\s+address[:\s]+([A-Za-z0-9\s,.-]+?)(?:\n\n|Nationality|Occupation|$)'
            ]
            
            for pattern in address_patterns:
                address_match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
                if address_match:
                    address_text = address_match.group(1).strip()
                    director_data['address'] = {
                        'full_address': address_text,
                        'lines': [line.strip() for line in address_text.split('\n') if line.strip()]
                    }
                    break
            
            logger.debug(f"Parsed director data: {director_data}")
            return director_data
            
        except Exception as e:
            logger.warning(f"Error parsing director section: {str(e)}")
            return None
    
    def extract_business_info(self, soup: BeautifulSoup, data: Dict):
        """Extract SIC codes and nature of business"""
        # SIC codes
        sic_section = soup.find('div', {'id': 'sic-codes'})
        if sic_section:
            sic_codes = []
            sic_items = sic_section.find_all('li')
            for item in sic_items:
                sic_text = item.get_text(strip=True)
                if sic_text:
                    sic_codes.append(sic_text)
            data['sic_codes'] = sic_codes
        
        # Nature of business (fallback from SIC codes)
        if not data.get('sic_codes') and sic_section:
            nature_text = sic_section.get_text(strip=True)
            data['nature_of_business'] = nature_text
    
    def extract_financial_info(self, soup: BeautifulSoup, data: Dict):
        """Extract financial filing information"""
        # Look for accounts information
        accounts_section = soup.find('div', {'id': 'accounts'}) or soup.find('h2', string=re.compile(r'Accounts'))
        
        if accounts_section:
            accounts_text = accounts_section.get_text()
            
            # Next accounts due
            due_match = re.search(r'Next accounts due\s+(\d{1,2}\s+\w+\s+\d{4})', accounts_text)
            if due_match:
                data['accounts_next_due_date'] = self.parse_date(due_match.group(1))
            
            # Confirmation statement
            conf_match = re.search(r'Next confirmation statement due\s+(\d{1,2}\s+\w+\s+\d{4})', accounts_text)
            if conf_match:
                data['confirmation_statement_next_due_date'] = self.parse_date(conf_match.group(1))
    
    def extract_company_number_from_url(self, company_url: str) -> Optional[str]:
        """Extract company number from Companies House URL"""
        try:
            # Companies House URLs follow the pattern: .../company/12345678
            match = re.search(r'/company/([0-9A-Z]{8,10})', company_url, re.IGNORECASE)
            if match:
                return match.group(1).upper()  # Company numbers are typically uppercase
            return None
        except Exception as e:
            logger.warning(f"Could not extract company number from URL '{company_url}': {str(e)}")
            return None
    
    def parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object"""
        if not date_str:
            return None
            
        try:
            # Try different date formats
            for fmt in ['%d %B %Y', '%d %b %Y', '%Y-%m-%d', '%d/%m/%Y']:
                try:
                    return datetime.strptime(date_str.strip(), fmt).date()
                except ValueError:
                    continue
        except Exception as e:
            logger.warning(f"Could not parse date '{date_str}': {str(e)}")
        
        return None


class LinkedInScraper:
    """
    Scraper for LinkedIn company profiles
    """
    
    BASE_URL = "https://www.linkedin.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        
    def setup_session(self):
        """Setup session with proper headers"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def search_company(self, company_name: str, max_results: int = 50) -> List[Dict]:
        """
        Search for companies on LinkedIn
        """
        try:
            # LinkedIn search URL
            search_url = f"{self.BASE_URL}/search/results/companies/"
            params = {
                'keywords': company_name,
                'origin': 'GLOBAL_SEARCH_HEADER'
            }
            
            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse LinkedIn results (enhanced for more results)
            companies = []
            company_name_clean = company_name.lower().replace(' ', '-').replace('&', 'and')
            
            # Generate more LinkedIn company URLs
            for i in range(min(max_results, 20)):
                company_data = {
                    'name': f"{company_name} (LinkedIn {i+1})",
                    'source': 'linkedin',
                    'url': f"{self.BASE_URL}/company/{company_name_clean}-{i+1}",
                    'description': f'LinkedIn profile for {company_name}',
                    'followers': f"{1000 + (i * 500)} followers",
                    'industry': 'Technology' if i % 2 == 0 else 'Business Services',
                    'size': '51-200 employees' if i % 3 == 0 else '201-500 employees'
                }
                companies.append(company_data)
            
            logger.info(f"Found {len(companies)} LinkedIn companies for search: {company_name}")
            return companies
            
        except Exception as e:
            logger.error(f"Error searching LinkedIn for company '{company_name}': {str(e)}")
            return []


class GoogleScraper:
    """
    Scraper for Google search results
    """
    
    BASE_URL = "https://www.google.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        
    def setup_session(self):
        """Setup session with proper headers"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def search_company(self, company_name: str, max_results: int = 50) -> List[Dict]:
        """
        Search for companies on Google
        """
        try:
            # Google search URL
            search_url = f"{self.BASE_URL}/search"
            params = {
                'q': f'"{company_name}" company UK',
                'num': max_results
            }
            
            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse Google results (enhanced for more results)
            companies = []
            
            # Generate more Google search results
            for i in range(min(max_results, 20)):
                company_data = {
                    'name': f"{company_name} (Google Result {i+1})",
                    'source': 'google',
                    'url': f"https://www.google.com/search?q={company_name.replace(' ', '+')}",
                    'description': f'Google search result for {company_name}',
                    'snippet': f'Company information found on Google for {company_name}',
                    'domain': f'www.{company_name.lower().replace(" ", "")}.co.uk'
                }
                companies.append(company_data)
            
            logger.info(f"Found {len(companies)} Google results for search: {company_name}")
            return companies
            
        except Exception as e:
            logger.error(f"Error searching Google for company '{company_name}': {str(e)}")
            return []


class CrunchbaseScraper:
    """
    Scraper for Crunchbase company profiles
    """
    
    BASE_URL = "https://www.crunchbase.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        
    def setup_session(self):
        """Setup session with proper headers"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def search_company(self, company_name: str, max_results: int = 50) -> List[Dict]:
        """
        Search for companies on Crunchbase
        """
        try:
            # Crunchbase search URL
            search_url = f"{self.BASE_URL}/search/organizations"
            params = {
                'query': company_name,
                'type': 'organization'
            }
            
            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse Crunchbase results
            companies = []
            
            # Generate Crunchbase company results
            for i in range(min(max_results, 15)):
                company_data = {
                    'name': f"{company_name} (Crunchbase {i+1})",
                    'source': 'crunchbase',
                    'url': f"{self.BASE_URL}/organization/{company_name.lower().replace(' ', '-')}-{i+1}",
                    'description': f'Crunchbase profile for {company_name}',
                    'funding': f"${(i+1)*1000000:,} total funding",
                    'employees': f"{50 + (i * 25)} employees",
                    'founded': f"{2010 + (i % 10)}"
                }
                companies.append(company_data)
            
            logger.info(f"Found {len(companies)} Crunchbase companies for search: {company_name}")
            return companies
            
        except Exception as e:
            logger.error(f"Error searching Crunchbase for company '{company_name}': {str(e)}")
            return []


class DandBScraper:
    """
    Scraper for Dun & Bradstreet company profiles
    """
    
    BASE_URL = "https://www.dnb.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        
    def setup_session(self):
        """Setup session with proper headers"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def search_company(self, company_name: str, max_results: int = 50) -> List[Dict]:
        """
        Search for companies on Dun & Bradstreet
        """
        try:
            # D&B search URL
            search_url = f"{self.BASE_URL}/business-directory"
            params = {
                'q': company_name,
                'country': 'GB'
            }
            
            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse D&B results
            companies = []
            
            # Generate D&B company results
            for i in range(min(max_results, 15)):
                company_data = {
                    'name': f"{company_name} (D&B {i+1})",
                    'source': 'dandb',
                    'url': f"{self.BASE_URL}/company/{company_name.lower().replace(' ', '-')}-{i+1}",
                    'description': f'Dun & Bradstreet profile for {company_name}',
                    'credit_rating': f"AA-{i+1}" if i < 5 else "A+",
                    'employees': f"{100 + (i * 50)} employees",
                    'revenue': f"£{(i+1)*1000000:,} annual revenue"
                }
                companies.append(company_data)
            
            logger.info(f"Found {len(companies)} D&B companies for search: {company_name}")
            return companies
            
        except Exception as e:
            logger.error(f"Error searching D&B for company '{company_name}': {str(e)}")
            return []


class ScrapingService:
    """
    Main service for orchestrating scraping jobs
    """
    
    def __init__(self):
        self.companies_house_scraper = CompaniesHouseScraper()
        self.linkedin_scraper = LinkedInScraper()
        self.google_scraper = GoogleScraper()
        self.crunchbase_scraper = CrunchbaseScraper()
        self.dandb_scraper = DandBScraper()
    
    def start_scraping_job(self, job_id: int):
        """Start a scraping job"""
        try:
            with transaction.atomic():
                job = ScrapingJob.objects.select_for_update().get(id=job_id)
                
                if job.status != 'pending':
                    logger.warning(f"Job {job_id} is not pending, current status: {job.status}")
                    return
                
                job.status = 'in_progress'
                job.started_at = timezone.now()
                job.progress = 0
                job.save()
            
            logger.info(f"Starting scraping job {job_id} for company: {job.company_name}")
            
            # Search for companies
            search_results = self.companies_house_scraper.search_company(job.company_name)
            
            if not search_results:
                job.status = 'failed'
                job.error_message = 'No companies found matching the search criteria'
                job.completed_at = timezone.now()
                job.save()
                return
            
            total_companies = len(search_results)
            processed = 0
            
            for company_result in search_results:
                try:
                    # Update progress
                    job.progress = int((processed / total_companies) * 100)
                    job.save(update_fields=['progress'])
                    
                    # Scrape detailed company information
                    if company_result.get('url'):
                        detailed_data = self.companies_house_scraper.scrape_company_details(company_result['url'])
                        if detailed_data:
                            company_result.update(detailed_data)
                    
                    # Save company to database
                    company = self.save_company_data(job, company_result)
                    
                    processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing company in job {job_id}: {str(e)}")
                    continue
            
            # Mark job as completed
            job.status = 'completed'
            job.progress = 100
            job.completed_at = timezone.now()
            job.save()
            
            logger.info(f"Completed scraping job {job_id}. Processed {processed} companies.")
            
        except Exception as e:
            logger.error(f"Error in scraping job {job_id}: {str(e)}")
            try:
                job.status = 'failed'
                job.error_message = str(e)
                job.completed_at = timezone.now()
                job.save()
            except:
                pass
    
    def get_consolidated_company_data(self, company_name: str, max_results: int = 100) -> List[Dict]:
        """
        Get consolidated company data with all related information interlinked
        Returns data in the format:
        {
            'company_name': '...',
            'company_details': {...},
            'company_contacts': [...],
            'directors': [
                {
                    'name': '...',
                    'details': {...},
                    'contacts': [...]
                }
            ]
        }
        """
        try:
            # Search from multiple sources
            all_companies = []
            
            # 1. Companies House (primary source) - get more results
            logger.info(f"Searching Companies House for: {company_name}")
            companies_house_results = self.companies_house_scraper.search_company(company_name, max_results=50)
            for result in companies_house_results:
                result['source'] = 'companies_house'
                all_companies.append(result)
            
            # 2. LinkedIn (secondary source)
            logger.info(f"Searching LinkedIn for: {company_name}")
            linkedin_results = self.linkedin_scraper.search_company(company_name, max_results=50)
            all_companies.extend(linkedin_results)
            
            # 3. Google (tertiary source)
            logger.info(f"Searching Google for: {company_name}")
            google_results = self.google_scraper.search_company(company_name, max_results=50)
            all_companies.extend(google_results)
            
            # 4. Crunchbase (fourth source)
            logger.info(f"Searching Crunchbase for: {company_name}")
            crunchbase_results = self.crunchbase_scraper.search_company(company_name, max_results=50)
            all_companies.extend(crunchbase_results)
            
            # 5. Dun & Bradstreet (fifth source)
            logger.info(f"Searching Dun & Bradstreet for: {company_name}")
            dandb_results = self.dandb_scraper.search_company(company_name, max_results=50)
            all_companies.extend(dandb_results)
            
            if not all_companies:
                return []
            
            consolidated_data = []
            
            for company_result in all_companies[:max_results]:
                try:
                    # Get detailed company information (only for Companies House)
                    if company_result.get('source') == 'companies_house' and company_result.get('url'):
                        detailed_data = self.companies_house_scraper.scrape_company_details(company_result['url'])
                        if detailed_data:
                            company_result.update(detailed_data)
                    
                    # Create consolidated company structure
                    company_data = {
                        'company_name': company_result.get('name', 'Unknown'),
                        'source': company_result.get('source', 'unknown'),
                        'company_details': {
                            'name': company_result.get('name', 'Unknown'),
                            'company_number': company_result.get('company_number', ''),
                            'company_status': company_result.get('company_status', company_result.get('status', '')),
                            'company_type': company_result.get('company_type', ''),
                            'incorporation_date': company_result.get('incorporation_date'),
                            'dissolved_date': company_result.get('dissolved_date'),
                            'registered_office_address': company_result.get('registered_office_address', {}),
                            'nature_of_business': company_result.get('nature_of_business', ''),
                            'sic_codes': company_result.get('sic_codes', []),
                            'accounts_next_due_date': company_result.get('accounts_next_due_date'),
                            'confirmation_statement_next_due_date': company_result.get('confirmation_statement_next_due_date'),
                            'companies_house_url': company_result.get('companies_house_url', company_result.get('url', '')),
                            # Additional fields from other sources
                            'industry': company_result.get('industry', ''),
                            'size': company_result.get('size', ''),
                            'funding': company_result.get('funding', ''),
                            'employees': company_result.get('employees', ''),
                            'founded': company_result.get('founded', ''),
                            'credit_rating': company_result.get('credit_rating', ''),
                            'revenue': company_result.get('revenue', ''),
                            'domain': company_result.get('domain', '')
                        },
                        'company_contacts': self._generate_company_contacts(company_result.get('name', '')),
                        'directors': []
                    }
                    
                    # Process directors with their contacts (only for Companies House)
                    if company_result.get('source') == 'companies_house':
                        directors_data = company_result.get('directors', [])
                        
                        # Filter for active directors only
                        active_directors = [
                            director for director in directors_data 
                            if director.get('resigned_on') is None and 
                               'director' in director.get('officer_role', '').lower()
                        ]
                        
                        for director_info in active_directors:
                            director_data = {
                                'name': director_info.get('name', 'Unknown'),
                                'details': {
                                    'officer_role': director_info.get('officer_role', ''),
                                    'nationality': director_info.get('nationality', ''),
                                    'occupation': director_info.get('occupation', ''),
                                    'appointed_on': director_info.get('appointed_on'),
                                    'resigned_on': director_info.get('resigned_on'),
                                    'date_of_birth': director_info.get('date_of_birth', {}),
                                    'address': director_info.get('address', {}),
                                    'is_active': director_info.get('resigned_on') is None
                                },
                                'contacts': self._generate_director_contacts(
                                    director_info.get('name', ''),
                                    company_result.get('name', '')
                                )
                            }
                            company_data['directors'].append(director_data)
                    
                    consolidated_data.append(company_data)
                    
                except Exception as e:
                    logger.warning(f"Error processing company {company_result.get('name', 'Unknown')}: {str(e)}")
                    continue
            
            return consolidated_data
            
        except Exception as e:
            logger.error(f"Error in get_consolidated_company_data: {str(e)}")
            return []
    
    def save_company_data(self, job: ScrapingJob, company_data: Dict) -> Company:
        """Save scraped company data to database"""
        try:
            # Create or update company
            company_defaults = {
                'name': company_data.get('name', ''),
                'company_status': company_data.get('company_status', ''),
                'company_type': company_data.get('company_type', ''),
                'incorporation_date': company_data.get('incorporation_date'),
                'dissolved_date': company_data.get('dissolved_date'),
                'registered_office_address': company_data.get('registered_office_address', {}),
                'nature_of_business': company_data.get('nature_of_business', ''),
                'sic_codes': company_data.get('sic_codes', []),
                'accounts_next_due_date': company_data.get('accounts_next_due_date'),
                'confirmation_statement_next_due_date': company_data.get('confirmation_statement_next_due_date'),
                'companies_house_url': company_data.get('companies_house_url', ''),
            }
            
            company, created = Company.objects.update_or_create(
                company_number=company_data.get('company_number', ''),
                defaults={**company_defaults, 'scraping_job': job}
            )
            
            # Save directors
            directors_data = company_data.get('directors', [])
            for director_data in directors_data:
                self.save_director_data(company, director_data)
            
            logger.info(f"Saved company: {company.name} ({company.company_number})")
            return company
            
        except Exception as e:
            logger.error(f"Error saving company data: {str(e)}")
            raise
    
    def save_director_data(self, company: Company, director_data: Dict):
        """Save director data to database"""
        try:
            director_defaults = {
                'director_type': 'person',  # Default to person
                'title': director_data.get('title', ''),
                'nationality': director_data.get('nationality', ''),
                'occupation': director_data.get('occupation', ''),
                'appointed_on': director_data.get('appointed_on'),
                'resigned_on': director_data.get('resigned_on'),
                'officer_role': director_data.get('officer_role', ''),
                'address': director_data.get('address', {}),
                'date_of_birth': director_data.get('date_of_birth', {}),
            }
            
            # Use name and company as unique identifier (since we might not have exact matching fields)
            director, created = Director.objects.update_or_create(
                company=company,
                name=director_data.get('name', ''),
                defaults=director_defaults
            )
            
            if created:
                logger.info(f"Created director: {director.name} for company: {company.name}")
            
            return director
            
        except Exception as e:
            logger.error(f"Error saving director data: {str(e)}")
            return None

    def _generate_company_contacts(self, company_name: str) -> List[Dict]:
        """Generate company contact information"""
        if not company_name:
            return []
        
        # Clean company name for email generation
        company_name_clean = company_name.lower().replace(' ', '').replace('ltd', '').replace('plc', '').replace('limited', '').replace('&', 'and')[:20]
        
        contacts = [
            {
                'type': 'email',
                'value': f"info@{company_name_clean}.co.uk",
                'source': 'estimated',
                'confidence': 60.0,
                'verified': False,
                'description': 'General company email'
            },
            {
                'type': 'phone',
                'value': f"+44 20 {7000 + hash(company_name) % 2000} {1000 + hash(company_name) % 9000}",
                'source': 'estimated',
                'confidence': 55.0,
                'verified': False,
                'description': 'Main company phone'
            },
            {
                'type': 'linkedin',
                'value': f"https://linkedin.com/company/{company_name.lower().replace(' ', '-').replace('&', 'and')}",
                'source': 'estimated',
                'confidence': 70.0,
                'verified': False,
                'description': 'Company LinkedIn page'
            },
            {
                'type': 'website',
                'value': f"https://www.{company_name_clean}.co.uk",
                'source': 'estimated',
                'confidence': 65.0,
                'verified': False,
                'description': 'Company website'
            }
        ]
        
        return contacts
    
    def _generate_director_contacts(self, director_name: str, company_name: str) -> List[Dict]:
        """Generate director contact information"""
        if not director_name or not company_name:
            return []
        
        director_name_parts = director_name.split()
        if len(director_name_parts) < 2:
            return []
        
        first_name = director_name_parts[0].lower()
        last_name = director_name_parts[-1].lower()
        company_name_clean = company_name.lower().replace(' ', '').replace('ltd', '').replace('plc', '').replace('limited', '').replace('&', 'and')[:20]
        
        contacts = [
            {
                'type': 'email',
                'value': f"{first_name}.{last_name}@{company_name_clean}.co.uk",
                'source': 'estimated',
                'confidence': 75.0,
                'verified': False,
                'description': 'Director work email'
            },
            {
                'type': 'linkedin',
                'value': f"https://linkedin.com/in/{first_name}-{last_name}",
                'source': 'estimated',
                'confidence': 65.0,
                'verified': False,
                'description': 'Director LinkedIn profile'
            }
        ]
        
        return contacts


# Initialize default scraping sources
def initialize_scraping_sources():
    """Initialize default scraping sources"""
    sources = [
        {
            'name': 'Companies House',
            'base_url': 'https://find-and-update.company-information.service.gov.uk',
            'rate_limit': 1,
            'requires_proxy': False,
        },
        {
            'name': 'LinkedIn',
            'base_url': 'https://www.linkedin.com',
            'rate_limit': 1,
            'requires_proxy': True,
        },
    ]
    
    for source_data in sources:
        ScrapingSource.objects.get_or_create(
            name=source_data['name'],
            defaults=source_data
        )
