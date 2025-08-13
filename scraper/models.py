from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json


class ScrapingJob(models.Model):
    """Track scraping jobs and their status"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scraping_jobs')
    company_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    progress = models.IntegerField(default=0)  # 0-100
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Job {self.id}: {self.company_name} ({self.status})"


class Company(models.Model):
    """Store company information scraped from Companies House"""
    scraping_job = models.ForeignKey(ScrapingJob, on_delete=models.CASCADE, related_name='companies')
    name = models.CharField(max_length=500)
    company_number = models.CharField(max_length=20, unique=True)
    company_status = models.CharField(max_length=50, blank=True)
    company_type = models.CharField(max_length=100, blank=True)
    incorporation_date = models.DateField(null=True, blank=True)
    dissolved_date = models.DateField(null=True, blank=True)
    
    # Address information
    registered_office_address = models.JSONField(default=dict)
    
    # Company details
    nature_of_business = models.TextField(blank=True)
    sic_codes = models.JSONField(default=list)  # Standard Industrial Classification codes
    
    # Financial information
    accounts_next_due_date = models.DateField(null=True, blank=True)
    confirmation_statement_next_due_date = models.DateField(null=True, blank=True)
    
    # Metadata
    companies_house_url = models.URLField(max_length=500, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Companies'
    
    def __str__(self):
        return f"{self.name} ({self.company_number})"
    
    @property
    def is_active(self):
        return self.company_status.lower() == 'active'


class Director(models.Model):
    """Store director information"""
    DIRECTOR_TYPE_CHOICES = [
        ('person', 'Natural Person'),
        ('corporate', 'Corporate Entity'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='directors')
    name = models.CharField(max_length=255)
    director_type = models.CharField(max_length=20, choices=DIRECTOR_TYPE_CHOICES, default='person')
    title = models.CharField(max_length=100, blank=True)
    
    # Personal details (for natural persons)
    date_of_birth = models.JSONField(default=dict)  # month/year only as per Companies House
    nationality = models.CharField(max_length=100, blank=True)
    occupation = models.CharField(max_length=200, blank=True)
    
    # Address
    address = models.JSONField(default=dict)
    
    # Appointment details
    appointed_on = models.DateField(null=True, blank=True)
    resigned_on = models.DateField(null=True, blank=True)
    officer_role = models.CharField(max_length=100, blank=True)
    
    # Contact information (scraped from other sources)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    linkedin_url = models.URLField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-appointed_on']
    
    def __str__(self):
        return f"{self.name} - {self.company.name}"
    
    @property
    def is_active(self):
        return self.resigned_on is None


class CompanyContact(models.Model):
    """Store contact information found for companies"""
    SOURCE_CHOICES = [
        ('companies_house', 'Companies House'),
        ('website', 'Company Website'),
        ('linkedin', 'LinkedIn'),
        ('google', 'Google Search'),
        ('manual', 'Manual Entry'),
        ('other', 'Other'),
    ]
    
    CONTACT_RELATIONSHIP_CHOICES = [
        ('company', 'Company Contact'),
        ('director', 'Director Contact'),
        ('general', 'General Contact'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contacts')
    director = models.ForeignKey(Director, on_delete=models.CASCADE, related_name='contacts', null=True, blank=True)
    contact_type = models.CharField(max_length=50)  # email, phone, website, etc.
    contact_value = models.CharField(max_length=255)
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    relationship = models.CharField(max_length=20, choices=CONTACT_RELATIONSHIP_CHOICES, default='company')
    confidence_score = models.FloatField(default=0.0)  # 0.0 to 1.0
    verified = models.BooleanField(default=False)
    
    # Metadata
    found_at = models.DateTimeField(auto_now_add=True)
    last_verified = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-confidence_score', '-found_at']
        unique_together = ['company', 'contact_type', 'contact_value']
    
    def __str__(self):
        if self.director and self.relationship == 'director':
            return f"{self.director.name} ({self.company.name}) - {self.contact_type}: {self.contact_value}"
        return f"{self.company.name} - {self.contact_type}: {self.contact_value}"
    
    @property
    def display_name(self):
        """Get the display name for this contact"""
        if self.relationship == 'director' and self.director:
            return f"{self.director.name} (Director)"
        elif self.relationship == 'company':
            return f"{self.company.name} (Company)"
        else:
            return self.company.name


class ScrapingSource(models.Model):
    """Track different sources used for scraping"""
    name = models.CharField(max_length=100, unique=True)
    base_url = models.URLField()
    is_active = models.BooleanField(default=True)
    rate_limit = models.IntegerField(default=1)  # requests per second
    requires_proxy = models.BooleanField(default=False)
    success_rate = models.FloatField(default=0.0)
    
    # Configuration
    headers = models.JSONField(default=dict)
    cookies = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name


class ScrapingAttempt(models.Model):
    """Log individual scraping attempts"""
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('blocked', 'Blocked'),
        ('timeout', 'Timeout'),
        ('not_found', 'Not Found'),
    ]
    
    scraping_job = models.ForeignKey(ScrapingJob, on_delete=models.CASCADE, related_name='attempts')
    source = models.ForeignKey(ScrapingSource, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255)
    url = models.URLField(max_length=1000)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Response details
    status_code = models.IntegerField(null=True, blank=True)
    response_time = models.FloatField(null=True, blank=True)  # seconds
    data_found = models.JSONField(default=dict)
    error_details = models.TextField(blank=True)
    
    # Metadata
    attempted_at = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-attempted_at']
    
    def __str__(self):
        return f"{self.company_name} - {self.source.name} ({self.status})"


class ExportRequest(models.Model):
    """Track data export requests"""
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('json', 'JSON'),
        ('airtable', 'Airtable'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='export_requests')
    scraping_jobs = models.ManyToManyField(ScrapingJob, related_name='export_requests')
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Export configuration
    include_directors = models.BooleanField(default=True)
    include_contacts = models.BooleanField(default=True)
    verified_contacts_only = models.BooleanField(default=False)
    
    # File details
    file_path = models.CharField(max_length=500, blank=True)
    download_url = models.URLField(blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)  # bytes
    
    # Metadata
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Export {self.id} - {self.format.upper()} ({self.status})"
