from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    ScrapingJob, Company, Director, CompanyContact, 
    ScrapingSource, ScrapingAttempt, ExportRequest
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class DirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Director
        fields = [
            'id', 'name', 'director_type', 'title', 'date_of_birth', 
            'nationality', 'occupation', 'address', 'appointed_on', 
            'resigned_on', 'officer_role', 'email', 'phone', 
            'linkedin_url', 'is_active', 'created_at', 'updated_at'
        ]


class CompanyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyContact
        fields = [
            'id', 'contact_type', 'contact_value', 'source', 
            'confidence_score', 'verified', 'found_at', 
            'last_verified', 'notes'
        ]


class CompanySerializer(serializers.ModelSerializer):
    directors = DirectorSerializer(many=True, read_only=True)
    contacts = CompanyContactSerializer(many=True, read_only=True)
    
    class Meta:
        model = Company
        fields = [
            'id', 'name', 'company_number', 'company_status', 
            'company_type', 'incorporation_date', 'dissolved_date', 
            'registered_office_address', 'nature_of_business', 'sic_codes',
            'accounts_next_due_date', 'confirmation_statement_next_due_date',
            'companies_house_url', 'is_active', 'directors', 'contacts',
            'last_updated', 'created_at'
        ]


class CompanyListSerializer(serializers.ModelSerializer):
    """Lighter serializer for listing companies without nested data"""
    director_count = serializers.SerializerMethodField()
    contact_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Company
        fields = [
            'id', 'name', 'company_number', 'company_status', 
            'company_type', 'incorporation_date', 'is_active',
            'director_count', 'contact_count', 'created_at'
        ]
    
    def get_director_count(self, obj):
        return obj.directors.count()
    
    def get_contact_count(self, obj):
        return obj.contacts.count()


class ScrapingAttemptSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source.name', read_only=True)
    
    class Meta:
        model = ScrapingAttempt
        fields = [
            'id', 'source', 'source_name', 'company_name', 'url', 
            'status', 'status_code', 'response_time', 'data_found',
            'error_details', 'attempted_at', 'user_agent', 'ip_address'
        ]


class ScrapingJobSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    companies = CompanyListSerializer(many=True, read_only=True)
    attempts = ScrapingAttemptSerializer(many=True, read_only=True)
    
    class Meta:
        model = ScrapingJob
        fields = [
            'id', 'user', 'company_name', 'status', 'created_at', 
            'started_at', 'completed_at', 'error_message', 'progress',
            'companies', 'attempts'
        ]


class ScrapingJobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrapingJob
        fields = ['company_name']
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['user'] = request.user
        return super().create(validated_data)


class ScrapingSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrapingSource
        fields = [
            'id', 'name', 'base_url', 'is_active', 'rate_limit',
            'requires_proxy', 'success_rate', 'headers', 'cookies',
            'created_at', 'updated_at'
        ]


class ExportRequestSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    scraping_jobs = ScrapingJobSerializer(many=True, read_only=True)
    
    class Meta:
        model = ExportRequest
        fields = [
            'id', 'user', 'scraping_jobs', 'format', 'status',
            'include_directors', 'include_contacts', 'verified_contacts_only',
            'file_path', 'download_url', 'file_size', 'requested_at',
            'completed_at', 'expires_at', 'error_message'
        ]


class ExportRequestCreateSerializer(serializers.ModelSerializer):
    scraping_job_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        write_only=True
    )
    
    class Meta:
        model = ExportRequest
        fields = [
            'scraping_job_ids', 'format', 'include_directors', 
            'include_contacts', 'verified_contacts_only'
        ]
    
    def create(self, validated_data):
        request = self.context.get('request')
        scraping_job_ids = validated_data.pop('scraping_job_ids')
        validated_data['user'] = request.user
        
        export_request = super().create(validated_data)
        
        # Add scraping jobs
        scraping_jobs = ScrapingJob.objects.filter(
            id__in=scraping_job_ids,
            user=request.user
        )
        export_request.scraping_jobs.set(scraping_jobs)
        
        return export_request


class CompanySearchSerializer(serializers.Serializer):
    """Serializer for company search requests"""
    company_name = serializers.CharField(max_length=255)
    include_dissolved = serializers.BooleanField(default=False)
    max_results = serializers.IntegerField(default=10, min_value=1, max_value=50)


class ContactVerificationSerializer(serializers.Serializer):
    """Serializer for contact verification requests"""
    contact_id = serializers.IntegerField()
    verification_method = serializers.ChoiceField(
        choices=[('email', 'Email'), ('phone', 'Phone'), ('manual', 'Manual')]
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class BulkExportSerializer(serializers.Serializer):
    """Serializer for bulk export operations"""
    company_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    format = serializers.ChoiceField(
        choices=[('csv', 'CSV'), ('xlsx', 'Excel'), ('json', 'JSON')]
    )
    include_directors = serializers.BooleanField(default=True)
    include_contacts = serializers.BooleanField(default=True)
    verified_contacts_only = serializers.BooleanField(default=False)
