# tracetype/tracetype/urls.py (The one next to settings.py - THIS IS YOUR MAIN PROJECT URLS)
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect # Import redirect

# You don't need to import dashboard_views here if 'api/log/' is handled within dashboard.urls

urlpatterns = [
    path('admin/', admin.site.urls),
    # This includes all URLs from dashboard/urls.py under the '/dashboard/' prefix
    # So, '/dashboard/api/log/' will be handled by this.
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    
    # Optional: Redirect the root URL to the admin or dashboard
    path('', lambda request: redirect('admin:index', permanent=False)),
    # Or to the dashboard home:
    # path('', lambda request: redirect('dashboard:home', permanent=False)),
]