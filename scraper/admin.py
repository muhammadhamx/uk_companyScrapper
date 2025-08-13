from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ScrapingJob, Company, Director, CompanyContact, 
    ScrapingSource, ScrapingAttempt, ExportRequest
)


@admin.register(ScrapingJob)
class ScrapingJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'company_name', 'user', 'status', 'progress', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at', 'user']
    search_fields = ['company_name', 'user__username']
    readonly_fields = ['created_at', 'started_at', 'completed_at']
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'company_number', 'company_status', 'company_type', 'incorporation_date', 'created_at']
    list_filter = ['company_status', 'company_type', 'incorporation_date', 'created_at']
    search_fields = ['name', 'company_number', 'nature_of_business']
    readonly_fields = ['created_at', 'last_updated', 'companies_house_url']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'company_number', 'company_status', 'company_type')
        }),
        ('Dates', {
            'fields': ('incorporation_date', 'dissolved_date')
        }),
        ('Business Information', {
            'fields': ('nature_of_business', 'sic_codes')
        }),
        ('Address', {
            'fields': ('registered_office_address',)
        }),
        ('Financial', {
            'fields': ('accounts_next_due_date', 'confirmation_statement_next_due_date')
        }),
        ('Metadata', {
            'fields': ('scraping_job', 'companies_house_url', 'created_at', 'last_updated'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('scraping_job')


@admin.register(Director)
class DirectorAdmin(admin.ModelAdmin):
    list_display = ['name', 'company_name', 'officer_role', 'nationality', 'appointed_on', 'is_active']
    list_filter = ['director_type', 'nationality', 'officer_role', 'appointed_on', 'resigned_on']
    search_fields = ['name', 'company__name', 'occupation']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-appointed_on']
    
    def company_name(self, obj):
        return obj.company.name
    company_name.short_description = 'Company'
    
    def is_active(self, obj):
        return obj.is_active
    is_active.boolean = True
    is_active.short_description = 'Active'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company')


@admin.register(CompanyContact)
class CompanyContactAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'contact_type', 'contact_value', 'source', 'confidence_score', 'verified', 'found_at']
    list_filter = ['contact_type', 'source', 'verified', 'found_at']
    search_fields = ['company__name', 'contact_value']
    readonly_fields = ['found_at', 'last_verified']
    ordering = ['-confidence_score', '-found_at']
    
    def company_name(self, obj):
        return obj.company.name
    company_name.short_description = 'Company'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company')


@admin.register(ScrapingSource)
class ScrapingSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_url', 'is_active', 'rate_limit', 'success_rate', 'created_at']
    list_filter = ['is_active', 'requires_proxy', 'created_at']
    search_fields = ['name', 'base_url']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']


@admin.register(ScrapingAttempt)
class ScrapingAttemptAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'source_name', 'status', 'status_code', 'response_time', 'attempted_at']
    list_filter = ['status', 'source', 'attempted_at']
    search_fields = ['company_name', 'url']
    readonly_fields = ['attempted_at']
    ordering = ['-attempted_at']
    
    def source_name(self, obj):
        return obj.source.name
    source_name.short_description = 'Source'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('source', 'scraping_job')


@admin.register(ExportRequest)
class ExportRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'format', 'status', 'file_size_formatted', 'requested_at', 'completed_at']
    list_filter = ['format', 'status', 'requested_at']
    search_fields = ['user__username']
    readonly_fields = ['requested_at', 'completed_at', 'file_size']
    ordering = ['-requested_at']
    
    def file_size_formatted(self, obj):
        if obj.file_size:
            if obj.file_size > 1024 * 1024:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
            elif obj.file_size > 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size} bytes"
        return '-'
    file_size_formatted.short_description = 'File Size'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
