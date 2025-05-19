

# In tracetype/urls.py
from django.contrib import admin
from django.urls import path, include
from dashboard import views as dashboard_views # Import your dashboard views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')), # For other dashboard views
    path('api/log/', dashboard_views.receive_keystrokes, name='global_api_receive_keystrokes'), # <--- NEW
    path('', lambda request: redirect('admin:index', permanent=False)),
]