from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'jobs', views.ScrapingJobViewSet, basename='scrapingjob')
router.register(r'companies', views.CompanyViewSet, basename='company')
router.register(r'directors', views.DirectorViewSet, basename='director')
router.register(r'contacts', views.CompanyContactViewSet, basename='companycontact')
router.register(r'exports', views.ExportRequestViewSet, basename='exportrequest')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.search_companies, name='search_companies'),
    path('search-progress/', views.search_progress, name='search_progress'),
    path('export/', views.export_data, name='export_data'),
    path('api/', include(router.urls)),
    path('api/search/', views.CompanySearchView.as_view(), name='company-search'),
    path('api/dashboard/', views.DashboardView.as_view(), name='dashboard'),
]
