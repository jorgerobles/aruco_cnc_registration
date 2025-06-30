"""
Updated Connection Panel with event awareness
Focuses only on device connections and diagnostics without adding new features
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import threading
import time
from typing import Callable, Optional

from services.event_broker import (event_aware, event_handler, EventPriority,
                                   CameraEvents, GRBLEvents)


@event_aware()
class ConnectionPanel:
    """Connection controls focused on device connections and diagnostics"""

    def __init__(self, parent, grbl_controller, camera_manager, logger: Optional[Callable] = None):
        self.grbl_controller = grbl_controller
        self.camera_manager = camera_manager
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="Device Connections")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Variables
        self.grbl_port_var = tk.StringVar(value="/dev/ttyUSB0")
        self.grbl_baudrate_var = tk.StringVar(value="115200")
        self.camera_id_var = tk.StringVar(value="0")

        # Status variables
        self.grbl_status_var = tk.StringVar(value="Disconnected")
        self.camera_status_var = tk.StringVar(value="Disconnected")

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

    @event_handler(CameraEvents.CONNECTED, EventPriority.HIGH)
    def _on_camera_connected(self, success: bool):
        """Handle camera connection status changes"""
        if success:
            self.camera_status_var.set("Connected")
            self.camera_connect_btn.config(state=tk.DISABLED)
            self.camera_disconnect_btn.config(state=tk.NORMAL)
        else:
            self.camera_status_var.set("Connection Failed")
            self.camera_connect_btn.config(state=tk.NORMAL)
            self.camera_disconnect_btn.config(state=tk.DISABLED)

    @event_handler(CameraEvents.DISCONNECTED)
    def _on_camera_disconnected(self):
        """Handle camera disconnection"""
        self.camera_status_var.set("Disconnected")
        self.camera_connect_btn.config(state=tk.NORMAL)
        self.camera_disconnect_btn.config(state=tk.DISABLED)

    @event_handler(CameraEvents.ERROR)
    def _on_camera_error(self, error_message: str):
        """Handle camera errors"""
        self.log(f"Camera Error: {error_message}", "error")

    def _setup_widgets(self):
        """Setup connection control widgets with diagnostics"""

        # === GRBL Section ===
        grbl_frame = ttk.LabelFrame(self.frame, text="GRBL Controller")
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

        # === Camera Section ===
        camera_frame = ttk.LabelFrame(self.frame, text="Camera")
        camera_frame.pack(fill=tk.X, pady=5, padx=5)

        # Camera ID
        cam_id_frame = ttk.Frame(camera_frame)
        cam_id_frame.pack(fill=tk.X, pady=2)

        ttk.Label(cam_id_frame, text="Camera ID:").pack(side=tk.LEFT)
        ttk.Entry(cam_id_frame, textvariable=self.camera_id_var, width=10).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(cam_id_frame, text="🔍", command=self._diagnose_camera, width=3).pack(side=tk.LEFT, padx=(5, 0))

        # Camera status
        cam_status_frame = ttk.Frame(camera_frame)
        cam_status_frame.pack(fill=tk.X, pady=2)

        ttk.Label(cam_status_frame, text="Status:").pack(side=tk.LEFT)
        cam_status_label = ttk.Label(cam_status_frame, textvariable=self.camera_status_var, foreground="red")
        cam_status_label.pack(side=tk.LEFT, padx=(5, 0))

        # Camera buttons
        cam_button_frame = ttk.Frame(camera_frame)
        cam_button_frame.pack(fill=tk.X, pady=2)

        self.camera_connect_btn = ttk.Button(cam_button_frame, text="Connect Camera", command=self.connect_camera)
        self.camera_connect_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.camera_disconnect_btn = ttk.Button(cam_button_frame, text="Disconnect", command=self.disconnect_camera,
                                                state=tk.DISABLED)
        self.camera_disconnect_btn.pack(side=tk.LEFT)

        # === Quick Test Section ===
        quick_frame = ttk.LabelFrame(self.frame, text="Quick Tests")
        quick_frame.pack(fill=tk.X, pady=5, padx=5)

        # Test buttons in a grid
        test_grid = ttk.Frame(quick_frame)
        test_grid.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(test_grid, text="Test GRBL Comm",
                  command=self._test_grbl_quick, width=15).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(test_grid, text="Get Position",
                  command=self._get_grbl_position, width=15).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(test_grid, text="Test Camera",
                  command=self._test_camera_quick, width=15).grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(test_grid, text="Get Status",
                  command=self._get_detailed_status, width=15).grid(row=1, column=1, padx=2, pady=2, sticky="ew")

        # Configure grid weights
        test_grid.columnconfigure(0, weight=1)
        test_grid.columnconfigure(1, weight=1)

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

            # Use the same test logic as the improved controller
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

    def _diagnose_camera(self):
        """Run camera diagnostics"""
        try:
            camera_id = int(self.camera_id_var.get())
            self.log(f"Testing camera {camera_id}...")

            import cv2
            cap = cv2.VideoCapture(camera_id)

            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    height, width = frame.shape[:2]
                    self.log(f"✅ Camera {camera_id} working - Resolution: {width}x{height}")
                else:
                    self.log(f"❌ Camera {camera_id} opened but no frame received", "error")
                cap.release()
            else:
                self.log(f"❌ Cannot open camera {camera_id}", "error")

        except ValueError:
            self.log("❌ Invalid camera ID", "error")
        except ImportError:
            self.log("❌ OpenCV not available for camera testing", "error")
        except Exception as e:
            self.log(f"❌ Camera diagnostic error: {e}", "error")

    def _test_grbl_quick(self):
        """Quick GRBL communication test"""
        if self.grbl_controller.is_connected:
            try:
                status = self.grbl_controller.get_status()
                position = self.grbl_controller.get_position()
                self.log(f"GRBL Status: {status}")
                self.log(f"Position: X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}")
            except Exception as e:
                self.log(f"GRBL test failed: {e}", "error")
        else:
            self.log("GRBL not connected", "warning")

    def _get_grbl_position(self):
        """Get and display current GRBL position"""
        if self.grbl_controller.is_connected:
            try:
                position = self.grbl_controller.get_position()
                self.log(f"Current Position: X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}")

                # Also get connection info if available (improved controller)
                if hasattr(self.grbl_controller, 'get_connection_info'):
                    info = self.grbl_controller.get_connection_info()
                    self.log(f"GRBL Info: Status={info['current_status']}, Detected={info['grbl_detected']}")

            except Exception as e:
                self.log(f"Failed to get position: {e}", "error")
        else:
            self.log("GRBL not connected", "warning")

    def _test_camera_quick(self):
        """Quick camera test"""
        try:
            camera_id = int(self.camera_id_var.get())

            if self.camera_manager.is_connected:
                info = self.camera_manager.get_camera_info()
                self.log(f"Camera test: Connected, ID={info['camera_id']}, "
                        f"Resolution={info['width']}x{info['height']}, "
                        f"Calibrated={info['calibrated']}")
            else:
                # Try a quick connection test
                import cv2
                cap = cv2.VideoCapture(camera_id)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        height, width = frame.shape[:2]
                        self.log(f"Camera test: ID {camera_id} available, Resolution: {width}x{height}")
                    else:
                        self.log(f"Camera test: ID {camera_id} opened but no frame", "warning")
                    cap.release()
                else:
                    self.log(f"Camera test: Cannot open camera ID {camera_id}", "error")

        except Exception as e:
            self.log(f"Camera test failed: {e}", "error")

    def _get_detailed_status(self):
        """Get detailed status from both devices"""
        self.log("=== Detailed Status Report ===")

        # GRBL Status
        if self.grbl_controller.is_connected:
            try:
                status = self.grbl_controller.get_status()
                position = self.grbl_controller.get_position()
                info = self.grbl_controller.get_connection_info()

                self.log(f"GRBL: Connected to {info['serial_port']}@{info['baudrate']}")
                self.log(f"GRBL: Status={status}, Position=X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}")
                self.log(f"GRBL: Detected={info['grbl_detected']}")
            except Exception as e:
                self.log(f"GRBL status error: {e}", "error")
        else:
            self.log("GRBL: Disconnected")

        # Camera Status
        if self.camera_manager.is_connected:
            try:
                info = self.camera_manager.get_camera_info()
                self.log(f"Camera: Connected ID={info['camera_id']}, "
                        f"Resolution={info['width']}x{info['height']}, "
                        f"Calibrated={info['calibrated']}")
            except Exception as e:
                self.log(f"Camera status error: {e}", "error")
        else:
            self.log("Camera: Disconnected")

        self.log("=== End Status Report ===")

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

    def connect_camera(self):
        """Connect to camera with error handling"""
        try:
            camera_id = int(self.camera_id_var.get())
            self.camera_manager.camera_id = camera_id
            self.log(f"Attempting to connect to camera {camera_id}")
            self.camera_status_var.set("Connecting...")

            if self.camera_manager.connect():
                self.log("✅ Camera connected successfully")
                return True
            else:
                self.log("❌ Failed to connect to camera", "error")
                self.camera_status_var.set("Connection Failed")
                messagebox.showerror("Error", "Failed to connect to camera")
                return False

        except ValueError:
            self.log("❌ Invalid camera ID format", "error")
            self.camera_status_var.set("Invalid ID")
            messagebox.showerror("Error", "Invalid camera ID")
            return False
        except Exception as e:
            self.log(f"❌ Camera connection error: {e}", "error")
            self.camera_status_var.set("Error")
            messagebox.showerror("Error", f"Failed to connect to camera: {e}")
            return False

    def disconnect_camera(self):
        """Disconnect from camera"""
        try:
            self.camera_manager.disconnect()
            self.log("Camera disconnected")
        except Exception as e:
            self.log(f"Error disconnecting camera: {e}", "error")