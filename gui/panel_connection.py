"""
Compact Connection Panel focused only on GRBL connections
Streamlined UI with test buttons removed for better space efficiency
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import time
from typing import Callable, Optional

from services.event_broker import (event_aware, event_handler, EventPriority,
                                   GRBLEvents)


@event_aware()
class ConnectionPanel:
    """Compact connection controls focused only on GRBL device connections"""

    def __init__(self, parent, grbl_controller, logger: Optional[Callable] = None):
        self.grbl_controller = grbl_controller
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="GRBL Connection")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Variables
        self.grbl_port_var = tk.StringVar(value="/dev/ttyUSB0")
        self.grbl_baudrate_var = tk.StringVar(value="115200")

        # Status variables
        self.grbl_status_var = tk.StringVar(value="Disconnected")

        self._setup_widgets()
        self._refresh_ports()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)
        print(f"[{level.upper()}] {message}")  # Also print to console

    # Event handlers using decorators
    @event_handler(GRBLEvents.CONNECTED, EventPriority.HIGH)
    def _on_grbl_connected(self, success: bool):
        """Handle GRBL connection status changes"""
        if success:
            self.grbl_status_var.set("Connected")
            self.grbl_connect_btn.config(state=tk.DISABLED)
            self.grbl_disconnect_btn.config(state=tk.NORMAL)
        else:
            self.grbl_status_var.set("Connection Failed")
            self.grbl_connect_btn.config(state=tk.NORMAL)
            self.grbl_disconnect_btn.config(state=tk.DISABLED)

    @event_handler(GRBLEvents.DISCONNECTED)
    def _on_grbl_disconnected(self):
        """Handle GRBL disconnection"""
        self.grbl_status_var.set("Disconnected")
        self.grbl_connect_btn.config(state=tk.NORMAL)
        self.grbl_disconnect_btn.config(state=tk.DISABLED)

    @event_handler(GRBLEvents.ERROR)
    def _on_grbl_error(self, error_message: str):
        """Handle GRBL errors/debug messages"""
        # Filter out debug messages from actual errors
        if "✅" in error_message or "Testing" in error_message:
            # Debug info - optionally show in a separate debug area
            pass
        else:
            # Actual error
            self.log(f"GRBL Error: {error_message}", "error")

    def _setup_widgets(self):
        """Setup GRBL connection control widgets"""

        # === GRBL Section ===
        grbl_frame = ttk.Frame(self.frame)
        grbl_frame.pack(fill=tk.X, pady=5, padx=5)

        # Port selection with refresh
        port_frame = ttk.Frame(grbl_frame)
        port_frame.pack(fill=tk.X, pady=2)

        ttk.Label(port_frame, text="Port:").pack(side=tk.LEFT)
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.grbl_port_var, width=15)
        self.port_combo.pack(side=tk.LEFT, padx=(5, 0))

        ttk.Button(port_frame, text="🔄", command=self._refresh_ports, width=3).pack(side=tk.LEFT, padx=(2, 0))
        ttk.Button(port_frame, text="🔍", command=self._diagnose_grbl, width=3).pack(side=tk.LEFT, padx=(2, 0))

        # Baudrate selection
        baud_frame = ttk.Frame(grbl_frame)
        baud_frame.pack(fill=tk.X, pady=2)

        ttk.Label(baud_frame, text="Baudrate:").pack(side=tk.LEFT)
        baud_combo = ttk.Combobox(baud_frame, textvariable=self.grbl_baudrate_var,
                                  values=["9600", "38400", "57600", "115200"], width=10)
        baud_combo.pack(side=tk.LEFT, padx=(5, 0))

        # Status and controls
        status_frame = ttk.Frame(grbl_frame)
        status_frame.pack(fill=tk.X, pady=2)

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        status_label = ttk.Label(status_frame, textvariable=self.grbl_status_var, foreground="red")
        status_label.pack(side=tk.LEFT, padx=(5, 0))

        # Connect/disconnect buttons
        button_frame = ttk.Frame(grbl_frame)
        button_frame.pack(fill=tk.X, pady=2)

        self.grbl_connect_btn = ttk.Button(button_frame, text="Connect GRBL", command=self.connect_grbl)
        self.grbl_connect_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.grbl_disconnect_btn = ttk.Button(button_frame, text="Disconnect", command=self.disconnect_grbl,
                                              state=tk.DISABLED)
        self.grbl_disconnect_btn.pack(side=tk.LEFT)

    def _refresh_ports(self):
        """Refresh available serial ports"""
        try:
            ports = serial.tools.list_ports.comports()
            port_list = [port.device for port in ports]

            self.port_combo['values'] = port_list

            if port_list:
                # If current selection is not in list, select first available
                if self.grbl_port_var.get() not in port_list:
                    self.grbl_port_var.set(port_list[0])
                self.log(f"Found {len(port_list)} serial ports: {', '.join(port_list)}")
            else:
                self.log("No serial ports found", "warning")

        except Exception as e:
            self.log(f"Error refreshing ports: {e}", "error")

    def _diagnose_grbl(self):
        """Run GRBL diagnostics in a separate thread"""

        def diagnose():
            port = self.grbl_port_var.get()
            baudrate = int(self.grbl_baudrate_var.get())

            self.log(f"Running GRBL diagnostics on {port}:{baudrate}")

            try:
                # Test 1: Check if port exists
                import os
                if not os.path.exists(port):
                    self.log(f"❌ Port {port} does not exist", "error")
                    return
                else:
                    self.log(f"✅ Port {port} exists")

                # Test 2: Check permissions
                if os.access(port, os.R_OK | os.W_OK):
                    self.log(f"✅ Port {port} has read/write permissions")
                else:
                    self.log(f"❌ Port {port} permission denied. Try: sudo usermod -a -G dialout $USER", "error")
                    return

                # Test 3: Test basic serial connection
                test_ser = serial.Serial(port, baudrate, timeout=2)
                time.sleep(2)  # Wait for device initialization

                self.log(f"✅ Basic serial connection successful")

                # Test 4: Try GRBL communication
                test_ser.write(b'?\r\n')
                time.sleep(0.5)

                if test_ser.in_waiting:
                    response = test_ser.read(test_ser.in_waiting).decode('utf-8', errors='ignore')
                    if '<' in response and '>' in response:
                        self.log(f"✅ GRBL status response received: {response.strip()}")
                    else:
                        self.log(f"⚠️  Device responded but not GRBL format: {response.strip()}", "warning")
                else:
                    self.log(f"⚠️  No response to status query", "warning")

                # Test settings command
                test_ser.write(b'$\r\n')
                time.sleep(0.5)

                if test_ser.in_waiting:
                    response = test_ser.read(test_ser.in_waiting).decode('utf-8', errors='ignore')
                    if '$' in response:
                        self.log(f"✅ GRBL settings response received")
                    else:
                        self.log(f"⚠️  Unexpected settings response: {response[:50]}...", "warning")

                test_ser.close()
                self.log("🎉 GRBL diagnostics completed successfully!")

            except serial.SerialException as e:
                self.log(f"❌ Serial connection failed: {e}", "error")
            except Exception as e:
                self.log(f"❌ Diagnostic error: {e}", "error")

        # Run in background thread
        threading.Thread(target=diagnose, daemon=True).start()

    def connect_grbl(self):
        """Connect to GRBL controller with better error handling"""
        port = self.grbl_port_var.get()
        baudrate = int(self.grbl_baudrate_var.get())

        self.log(f"Attempting to connect to GRBL on {port}:{baudrate}")
        self.grbl_status_var.set("Connecting...")

        # Disable connect button during connection attempt
        self.grbl_connect_btn.config(state=tk.DISABLED)

        def connect_thread():
            try:
                success = self.grbl_controller.connect(port, baudrate)

                # Update UI in main thread
                self.frame.after(0, lambda: self._grbl_connect_result(success))

            except Exception as e:
                self.frame.after(0, lambda: self._grbl_connect_error(str(e)))

        threading.Thread(target=connect_thread, daemon=True).start()

    def _grbl_connect_result(self, success):
        """Handle GRBL connection result in main thread"""
        if success:
            self.log("✅ GRBL connected successfully")
        else:
            self.log("❌ Failed to connect to GRBL", "error")
            self.grbl_status_var.set("Connection Failed")
            self.grbl_connect_btn.config(state=tk.NORMAL)
            messagebox.showerror("Connection Error", "Failed to connect to GRBL.\nCheck diagnostics for details.")

    def _grbl_connect_error(self, error_msg):
        """Handle GRBL connection error in main thread"""
        self.log(f"❌ GRBL connection error: {error_msg}", "error")
        self.grbl_status_var.set("Error")
        self.grbl_connect_btn.config(state=tk.NORMAL)
        messagebox.showerror("Connection Error", f"GRBL connection failed:\n{error_msg}")

    def disconnect_grbl(self):
        """Disconnect from GRBL"""
        try:
            self.grbl_controller.disconnect()
            self.log("GRBL disconnected")
        except Exception as e:
            self.log(f"Error disconnecting GRBL: {e}", "error")