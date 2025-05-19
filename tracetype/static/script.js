document.addEventListener('DOMContentLoaded', function() {
    // Page management
    const pages = {
        // login: document.getElementById('login-page'), // We'll manage login via Django session for now
        dashboard: document.getElementById('dashboard-page'),
        logs: document.getElementById('logs-page')
    };
    const devicesGrid = document.getElementById('devices-grid');
    const logsTerminal = document.getElementById('logs-terminal');
    const logsPageDeviceName = document.getElementById('logs-page-device-name');

    // Modals
    const renameDeviceModal = document.getElementById('rename-device-modal');
    const renameDeviceForm = document.getElementById('rename-device-form');
    const cancelRenameDeviceBtn = document.getElementById('cancel-rename-device');
    const renameDeviceIdInput = document.getElementById('rename-device-id');
    const newDeviceDisplayNameInput = document.getElementById('new-device-display-name');

    const deleteModal = document.getElementById('delete-modal');
    const cancelDeleteBtn = document.getElementById('cancel-delete');
    const confirmDeleteBtn = document.getElementById('confirm-delete');
    let deviceToDeleteId = null;

    // Buttons
    const refreshDevicesBtn = document.getElementById('refresh-devices-btn');
    const backToDashboardBtn = document.getElementById('back-to-dashboard-btn');


    function showPage(pageId) {
        Object.values(pages).forEach(page => page.classList.add('hidden'));
        if (pages[pageId]) {
            pages[pageId].classList.remove('hidden');
        } else {
            console.error("Page not found:", pageId);
        }
    }

    // Function to get CSRF token (Django specific)
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    // Fetch and render monitored devices
    async function fetchAndRenderDevices() {
        try {
            // Correct API endpoint for listing devices
            const response = await fetch('/dashboard/api/devices/');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const devices = await response.json();
            devicesGrid.innerHTML = ''; // Clear existing cards

            if (devices.length === 0) {
                devicesGrid.innerHTML = '<p>No monitored devices found.</p>';
                return;
            }

            devices.forEach(device => {
                const card = document.createElement('div');
                card.classList.add('user-card'); // Keeping class name for CSS compatibility
                card.innerHTML = `
                    <button class="menu-dots" data-device-id="${device.id}" data-device-name="${escapeHtml(device.display_name)}">⋮</button>
                    <div class="dropdown-menu hidden">
                        <button class="rename-action" data-device-id="${device.id}" data-current-name="${escapeHtml(device.display_name)}">Rename</button>
                        <button class="delete-action" data-device-id="${device.id}" data-device-name="${escapeHtml(device.display_name)}">Delete Device</button>
                    </div>
                    <h3>${escapeHtml(device.display_name)}</h3>
                    <div class="user-info">
                        <p>ID: ${device.id}</p>
                        <p>Hostname: ${escapeHtml(device.hostname)}</p>
                        <p>Last Seen: ${device.last_seen ? new Date(device.last_seen).toLocaleString() : 'Never'}</p>
                        <p>Status: ${device.is_active ? 'Active' : 'Inactive'}</p>
                    </div>
                    <button class="view-logs-btn" data-device-id="${device.id}" data-device-name="${escapeHtml(device.display_name)}">Access Logs</button>
                `;
                devicesGrid.appendChild(card);
            });

            // Add event listeners for new elements
            addCardEventListeners();

        } catch (error) {
            console.error('Error fetching devices:', error);
            devicesGrid.innerHTML = '<p>Failed to load devices. Please try refreshing.</p>';
        }
    }

    function addCardEventListeners() {
        // Dropdown menu behavior
        document.querySelectorAll('.menu-dots').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const dropdown = button.nextElementSibling;
                // Close other open dropdowns
                document.querySelectorAll('.dropdown-menu').forEach(menu => {
                    if (menu !== dropdown) menu.classList.add('hidden');
                });
                dropdown.classList.toggle('hidden');
            });
        });

        // View logs button
        document.querySelectorAll('.view-logs-btn').forEach(button => {
            button.addEventListener('click', () => {
                const deviceId = button.dataset.deviceId;
                const deviceName = button.dataset.deviceName;
                fetchAndRenderLogs(deviceId, deviceName);
            });
        });

        // Rename action button
        document.querySelectorAll('.rename-action').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent card click if any
                const deviceId = button.dataset.deviceId;
                const currentName = button.dataset.currentName;
                openRenameModal(deviceId, currentName);
                button.closest('.dropdown-menu').classList.add('hidden'); // Close dropdown
            });
        });

        // Delete action button
        document.querySelectorAll('.delete-action').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const deviceId = button.dataset.deviceId;
                const deviceName = button.dataset.deviceName; // For confirmation message
                openDeleteModal(deviceId, deviceName);
                button.closest('.dropdown-menu').classList.add('hidden'); // Close dropdown
            });
        });
    }
    
    // Hide dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.matches('.menu-dots')) {
            document.querySelectorAll('.dropdown-menu').forEach(menu => {
                menu.classList.add('hidden');
            });
        }
    });


    // Rename Device Modal Logic
    function openRenameModal(deviceId, currentName) {
        renameDeviceIdInput.value = deviceId;
        newDeviceDisplayNameInput.value = currentName; // Pre-fill with current name
        renameDeviceModal.classList.remove('hidden');
    }

    cancelRenameDeviceBtn.addEventListener('click', () => {
        renameDeviceModal.classList.add('hidden');
        renameDeviceForm.reset();
    });

    renameDeviceForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const deviceId = renameDeviceIdInput.value;
        const newName = newDeviceDisplayNameInput.value.trim();

        if (!newName) {
            alert("Display name cannot be empty.");
            return;
        }

        try {
            // Correct API endpoint for renaming
            const response = await fetch(`/dashboard/api/devices/${deviceId}/rename/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken // Add CSRF token
                },
                body: JSON.stringify({ new_display_name: newName })
            });
            if (response.ok) {
                await response.json(); // Consume JSON response
                fetchAndRenderDevices(); // Refresh device list
                renameDeviceModal.classList.add('hidden');
                renameDeviceForm.reset();
            } else {
                const errorData = await response.json();
                alert(`Failed to rename device: ${errorData.message || response.statusText}`);
            }
        } catch (error) {
            console.error('Error renaming device:', error);
            alert('An error occurred while renaming the device.');
        }
    });


    // Delete Device Modal Logic
    function openDeleteModal(deviceId, deviceName) {
        deviceToDeleteId = deviceId;
        // Update modal text if you have a placeholder for device name
        deleteModal.querySelector('p').textContent = `Are you sure you want to delete "${escapeHtml(deviceName)}" and all its logs?`;
        deleteModal.classList.remove('hidden');
    }

    cancelDeleteBtn.addEventListener('click', () => {
        deleteModal.classList.add('hidden');
        deviceToDeleteId = null;
    });

    confirmDeleteBtn.addEventListener('click', async () => {
        if (deviceToDeleteId !== null) {
            try {
                // Correct API endpoint for deleting
                const response = await fetch(`/dashboard/api/devices/${deviceToDeleteId}/delete/`, {
                    method: 'POST', // Or 'DELETE', ensure view supports it. POST is simpler with CSRF.
                    headers: {
                        'X-CSRFToken': csrftoken // Add CSRF token
                    }
                });
                if (response.ok) {
                    await response.json(); // Consume JSON response
                    fetchAndRenderDevices(); // Refresh device list
                    deleteModal.classList.add('hidden');
                    deviceToDeleteId = null;
                } else {
                    const errorData = await response.json();
                    alert(`Failed to delete device: ${errorData.message || response.statusText}`);
                }
            } catch (error) {
                console.error('Error deleting device:', error);
                alert('An error occurred while deleting the device.');
            }
        }
    });

    // Fetch and render logs for a specific device
    async function fetchAndRenderLogs(deviceId, deviceName) {
        showPage('logs');
        logsPageDeviceName.textContent = `Logs for ${escapeHtml(deviceName)}`;
        logsTerminal.innerHTML = '<p>Loading logs...</p>';

        try {
            // Correct API endpoint for device logs
            const response = await fetch(`/dashboard/api/devices/${deviceId}/logs/`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json(); // Expects { device_name: "...", logs: [...] }
            
            if (data.logs && data.logs.length > 0) {
                logsTerminal.innerHTML = data.logs.map(log => `
                    <div class="log-entry">
                        <span class="log-timestamp">[${new Date(log.server_timestamp).toLocaleString()}]</span>
                        <pre class="log-content">${escapeHtml(log.decrypted_content)}</pre> <!-- Use <pre> for formatting -->
                    </div>
                `).join('');
            } else {
                logsTerminal.innerHTML = '<p>No logs found for this device.</p>';
            }
        } catch (error) {
            console.error('Error fetching logs:', error);
            logsTerminal.innerHTML = '<p>Failed to load logs. Please try again.</p>';
        }
    }
    
    // Basic HTML escaping function
    function escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') return '';
        return unsafe
             .replace(/&/g, "&")
             .replace(/</g, "<")
             .replace(/>/g, ">")
             .replace(/'/g, "'");
    }


    // Navigation and Initial Load
    if (refreshDevicesBtn) {
        refreshDevicesBtn.addEventListener('click', fetchAndRenderDevices);
    }
    if (backToDashboardBtn) {
        backToDashboardBtn.addEventListener('click', () => {
            showPage('dashboard');
            fetchAndRenderDevices(); // Optionally refresh when going back
        });
    }
    
    // Initial setup:
    // We assume the user is already authenticated by Django to see this page.
    // So, directly show the dashboard.
    showPage('dashboard');
    fetchAndRenderDevices(); // Load devices when the dashboard page is shown

});