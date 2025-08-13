# UK Company Scraper 

A powerful Django-based web application that scrapes and consolidates company information from multiple UK business data sources. Get comprehensive company details, director information, and contact data all in one place.

## What It Does

This application searches across multiple UK business databases and websites to provide you with:

- Company Information: Name, registration number, status, type, incorporation date, address
- Director Details: Active directors with their roles, appointment dates, and contact information
- Contact Data: Company emails, phone numbers, LinkedIn profiles, and websites
- Multi-Source Data: Combines information from Companies House, LinkedIn, Google, Crunchbase, and Dun & Bradstreet
- Export Functionality: Download results as CSV or Excel files

## Features

- Multi-Source Scraping: Searches 5 different data sources simultaneously
- Active Director Filtering: Only shows currently active directors (filters out resigned ones)
- Contact Generation: Estimates company and director contact information
- Export Options: Download data in CSV or Excel format
- Speed Optimized: Configurable limits for faster scraping
- Web Interface: Clean, responsive web UI for easy searching

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Git

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd uk_company_scrapper-main
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Database Setup

```bash
python manage.py migrate
```

### Step 5: Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### Step 6: Run the Application

```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

## How to Use

### Basic Usage

1. Open the Application: Navigate to `http://127.0.0.1:8000/` in your browser
2. Search for Companies: Enter a company name in the search box
3. View Results: Browse through the consolidated company information
4. Export Data: Click the "Export CSV" or "Export Excel" buttons to download results

### What You'll Get

For each company found, you'll see:
- Company Details: Registration info, status, address, industry
- Company Contacts: Email addresses, LinkedIn profiles
- Active Directors: Names, roles, appointment dates, contact information

## Customizing Limits

The application is designed for speed and efficiency. You can adjust various limits based on your needs:

### Company Search Limits

- Location: `scraper/services.py` (lines 865-890)

```python
# Current settings (optimized for speed):
companies_house_results = self.companies_house_scraper.search_company(company_name, max_results=15)
linkedin_results = self.linkedin_scraper.search_company(company_name, max_results=10)
google_results = self.google_scraper.search_company(company_name, max_results=10)
crunchbase_results = self.crunchbase_scraper.search_company(company_name, max_results=5)
dandb_results = self.dandb_scraper.search_company(company_name, max_results=10)
```

- To increase results: Change the `max_results` values (e.g., from 10 to 25)

### Total Results Limit

- Location: `scraper/views.py` (line 472)

```python
# Current setting:
consolidated_data = service.get_consolidated_company_data(company_name, max_results=50)
```

- To change: Modify the `max_results=50` value

### Director Limits

- Location: `scraper/services.py` (line 940)

```python
# Current setting:
limited_directors = active_directors[:3]  # Only first 3 directors per company
```

- To change: Modify the slice `[:3]` to `[:5]` for 5 directors, or `[:10]` for 10 directors

### Contact Generation Limits

- Location: `scraper/services.py` (lines 1046-1080)

```python
# Company contacts - currently generates 2 contacts (email + LinkedIn)
# Director contacts - currently generates 1 contact (email only)
```

- To add more contacts: Uncomment or add additional contact types in the contact generation functions

## Configuration Options

### Database Configuration

The application uses SQLite by default. For production, consider using PostgreSQL:

```python
# In settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db_name',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## Data Sources

The application scrapes data from:

1. Companies House - Official UK company registry
2. LinkedIn - Professional networking platform
3. Google Search - Web search results
4. Crunchbase - Business information platform
5. Dun & Bradstreet - Business data provider

## Important Notes

- Rate Limiting: Be mindful of the scraping limits to avoid being blocked by data sources
- Data Accuracy: Contact information is estimated and may not be 100% accurate
- Legal Compliance: Ensure you comply with the terms of service of data sources
- Performance: Higher limits will result in slower scraping times

## Troubleshooting

### Common Issues

1. Import Errors: Make sure your virtual environment is activated
2. Database Errors: Run `python manage.py migrate` to set up the database
3. Scraping Failures: Check your internet connection and the target websites' availability
4. Memory Issues: Reduce the search limits if you encounter memory problems


---

**Happy Scraping! 🚀**
