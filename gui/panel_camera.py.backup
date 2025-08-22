# gui/panel_camera.py - Updated with configuration synchronization
"""
Enhanced Camera Panel with integrated FOV calculation using Camera Manager
Updated to synchronize with configuration system
"""

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional

from services.camera_manager import CameraEvents
from services.event_broker import event_aware, event_handler, EventPriority
from services.configuration_service import ConfigurationServiceEvents
from services.configuration_manager import ConfigurationEvents


@event_aware()
class CameraPanel:
    """Enhanced camera panel with configuration synchronization"""

    def __init__(self, parent, camera_manager, hardware_service, logger: Optional[Callable] = None, marker_length=15.0):
        self.camera_manager = camera_manager
        self.hardware_service = hardware_service
        self.logger = logger

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Camera & Hardware")
        self.frame.pack(fill=tk.X, pady=2, padx=5)

        # Camera variables
        self.camera_id_var = tk.StringVar(value="0")
        self.camera_status_var = tk.StringVar(value="Disconnected")
        self.marker_length_var = tk.DoubleVar(value=marker_length)
        self.calibration_file_var = tk.StringVar(value="No calibration")

        # Camera offset variables
        self.offset_x_var = tk.DoubleVar(value=0.0)
        self.offset_y_var = tk.DoubleVar(value=0.0)
        self.offset_z_var = tk.DoubleVar(value=0.0)

        # FOV status variables
        self.fov_status_var = tk.StringVar(value="No FOV data")

        # Setup UI
        self._setup_widgets()
        self._set_calibration_controls_enabled(False)

        self.log("Enhanced Camera Panel with configuration sync initialized", "info")

    def set_logger(self, logger: Callable):
        """Set logger after initialization"""
        self.logger = logger

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"CameraPanel: {message}", level)
        else:
            print(f"[{level.upper()}] CameraPanel: {message}")

    def _setup_widgets(self):
        """Setup UI with tabbed interface"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # Camera tab
        camera_tab = ttk.Frame(notebook)
        notebook.add(camera_tab, text="Camera")
        self._setup_camera_tab(camera_tab)

        # Offset tab
        offset_tab = ttk.Frame(notebook)
        notebook.add(offset_tab, text="Offset")
        self._setup_offset_tab(offset_tab)

    def _setup_camera_tab(self, parent):
        """Setup camera connection and calibration tab"""
        # Camera Connection Section
        conn_frame = ttk.LabelFrame(parent, text="Camera Connection")
        conn_frame.pack(fill=tk.X, pady=5, padx=5)

        # Camera ID and status row
        cam_row = ttk.Frame(conn_frame)
        cam_row.pack(fill=tk.X, pady=2, padx=3)

        ttk.Label(cam_row, text="Camera:").pack(side=tk.LEFT)
        
        # Camera ID entry - this is the field that needs to be updated
        self.camera_id_entry = ttk.Entry(cam_row, textvariable=self.camera_id_var, width=5)
        self.camera_id_entry.pack(side=tk.LEFT, padx=(2, 0))

        self.cam_status_label = ttk.Label(cam_row, textvariable=self.camera_status_var,
                                          foreground="red", font=("TkDefaultFont", 8))
        self.cam_status_label.pack(side=tk.LEFT, padx=(5, 0))

        # Connection buttons row
        btn_row = ttk.Frame(conn_frame)
        btn_row.pack(fill=tk.X, pady=2, padx=3)

        self.camera_connect_btn = ttk.Button(btn_row, text="Connect",
                                             command=self.connect_camera, width=8)
        self.camera_connect_btn.pack(side=tk.LEFT, padx=(0, 2))

        self.camera_disconnect_btn = ttk.Button(btn_row, text="Disconnect",
                                                command=self.disconnect_camera, width=8, state=tk.DISABLED)
        self.camera_disconnect_btn.pack(side=tk.LEFT, padx=(0, 2))

        ttk.Button(btn_row, text="🔍", command=self._diagnose_camera, width=3).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(btn_row, text="Test", command=self._test_camera_quick, width=6).pack(side=tk.LEFT)

        # Camera Calibration Section
        calib_frame = ttk.LabelFrame(parent, text="Camera Calibration")
        calib_frame.pack(fill=tk.X, pady=5, padx=5)

        # Marker size and calibration row
        marker_row = ttk.Frame(calib_frame)
        marker_row.pack(fill=tk.X, pady=2, padx=3)

        ttk.Label(marker_row, text="Marker Size:").pack(side=tk.LEFT)
        self.marker_length_entry = ttk.Entry(marker_row, textvariable=self.marker_length_var, width=8)
        self.marker_length_entry.pack(side=tk.LEFT, padx=(2, 0))
        ttk.Label(marker_row, text="mm").pack(side=tk.LEFT, padx=(2, 5))

        # Auto FOV button - integrated into camera tab
        ttk.Button(marker_row, text="Auto FOV", command=self.calculate_fov_auto, width=8).pack(side=tk.LEFT, padx=(5, 0))

        # Calibration file row
        calib_file_row = ttk.Frame(calib_frame)
        calib_file_row.pack(fill=tk.X, pady=2, padx=3)

        self.calib_status_label = ttk.Label(calib_file_row, textvariable=self.calibration_file_var,
                                           foreground="gray", font=("TkDefaultFont", 8))
        self.calib_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Calibration buttons row
        calib_btn_row = ttk.Frame(calib_frame)
        calib_btn_row.pack(fill=tk.X, pady=2, padx=3)

        self.load_calib_btn = ttk.Button(calib_btn_row, text="Load Calibration",
                                        command=self.load_calibration, width=12)
        self.load_calib_btn.pack(side=tk.LEFT, padx=(0, 2))

        self.info_btn = ttk.Button(calib_btn_row, text="Info", command=self._log_calibration_info, width=6)
        self.info_btn.pack(side=tk.LEFT)

        # FOV status row (simplified)
        fov_row = ttk.Frame(calib_frame)
        fov_row.pack(fill=tk.X, pady=(5, 2), padx=3)

        ttk.Label(fov_row, text="FOV:").pack(side=tk.LEFT)
        ttk.Label(fov_row, textvariable=self.fov_status_var, foreground="blue",
                 font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(5, 0))

    def _setup_offset_tab(self, parent):
        """Setup camera offset configuration tab"""
        # Offset input section
        offset_frame = ttk.LabelFrame(parent, text="Camera Offset from Spindle")
        offset_frame.pack(pady=10)

        # X offset
        ttk.Label(offset_frame, text="X Offset:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(offset_frame, textvariable=self.offset_x_var, width=10).grid(row=0, column=1, padx=(0, 2))
        ttk.Label(offset_frame, text="mm").grid(row=0, column=2, sticky=tk.W)

        # Y offset
        ttk.Label(offset_frame, text="Y Offset:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(offset_frame, textvariable=self.offset_y_var, width=10).grid(row=1, column=1, padx=(0, 2))
        ttk.Label(offset_frame, text="mm").grid(row=1, column=2, sticky=tk.W)

        # Z offset
        ttk.Label(offset_frame, text="Z Offset:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(offset_frame, textvariable=self.offset_z_var, width=10).grid(row=2, column=1, padx=(0, 2))
        ttk.Label(offset_frame, text="mm").grid(row=2, column=2, sticky=tk.W)

        # Buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="Apply Offset", command=self.apply_offset, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Reset", command=self.reset_offset, width=8).pack(side=tk.LEFT, padx=(0, 5))

        # Current offset display
        self.offset_display = ttk.Label(parent, text="Current: X0.0 Y0.0 Z0.0 mm",
                                       font=("TkDefaultFont", 8), foreground="blue")
        self.offset_display.pack(pady=(10, 0))

    def _set_calibration_controls_enabled(self, enabled: bool):
        """Enable or disable calibration controls"""
        state = tk.NORMAL if enabled else tk.DISABLED
        self.marker_length_entry.config(state=state)
        self.load_calib_btn.config(state=state)
        self.info_btn.config(state=state)

    # === CAMERA CONNECTION METHODS ===

    def connect_camera(self):
        """Connect to camera"""
        try:
            camera_id = int(self.camera_id_var.get())
            self.camera_manager.camera_id = camera_id
            self.camera_status_var.set("Connecting...")
            self.cam_status_label.config(foreground="orange")

            def connect_thread():
                try:
                    success = self.camera_manager.connect()
                    if not success:
                        self.frame.after(0, lambda: messagebox.showerror("Error", "Failed to connect to camera"))
                except Exception as e:
                    self.frame.after(0, lambda: messagebox.showerror("Error", f"Camera error: {e}"))

            threading.Thread(target=connect_thread, daemon=True).start()

        except ValueError:
            self.camera_status_var.set("Invalid ID")
            messagebox.showerror("Error", "Invalid camera ID")
        except Exception as e:
            self.camera_status_var.set("Error")
            messagebox.showerror("Error", f"Connection failed: {e}")

    def disconnect_camera(self):
        """Disconnect from camera"""
        try:
            self.camera_manager.disconnect()
        except Exception as e:
            self.log(f"Error disconnecting camera: {e}", "error")

    def _diagnose_camera(self):
        """Run camera diagnostics"""
        def diagnose():
            try:
                camera_id = int(self.camera_id_var.get())
                import cv2
                cap = cv2.VideoCapture(camera_id)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        h, w = frame.shape[:2]
                        self.log(f"✅ Camera {camera_id} OK - {w}x{h}")
                    else:
                        self.log(f"❌ Camera {camera_id} no frame", "error")
                    cap.release()
                else:
                    self.log(f"❌ Cannot open camera {camera_id}", "error")
            except Exception as e:
                self.log(f"❌ Camera test failed: {e}", "error")

        threading.Thread(target=diagnose, daemon=True).start()

    def _test_camera_quick(self):
        """Quick camera test including FOV info"""
        try:
            if self.camera_manager.is_connected:
                info = self.camera_manager.get_camera_info()
                offset = self.hardware_service.get_camera_offset()

                log_msg = f"Camera: ID={info['camera_id']}, {info['width']}x{info['height']}, "
                log_msg += f"Cal={'Yes' if info['calibrated'] else 'No'}, "
                log_msg += f"Offset=[{offset['x']:.1f},{offset['y']:.1f},{offset['z']:.1f}]"

                self.log(log_msg)
            else:
                camera_id = int(self.camera_id_var.get())
                def test():
                    try:
                        import cv2
                        cap = cv2.VideoCapture(camera_id)
                        if cap.isOpened():
                            ret, frame = cap.read()
                            if ret:
                                h, w = frame.shape[:2]
                                self.log(f"Test: Camera {camera_id} available ({w}x{h})")
                            cap.release()
                        else:
                            self.log(f"Test: Camera {camera_id} unavailable", "error")
                    except Exception as e:
                        self.log(f"Test failed: {e}", "error")
                threading.Thread(target=test, daemon=True).start()
        except Exception as e:
            self.log(f"Test error: {e}", "error")

    # === CALIBRATION METHODS ===

    def load_calibration(self):
        """Load camera calibration file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Load Camera Calibration",
                filetypes=[("NumPy Archive", "*.npz"), ("All files", "*.*")]
            )
            if file_path:
                success = self.camera_manager.load_calibration(file_path)
                if not success:
                    messagebox.showerror("Error", "Failed to load calibration")
        except Exception as e:
            messagebox.showerror("Error", f"Load error: {e}")

    def _log_calibration_info(self):
        """Log calibration info"""
        try:
            if self.camera_manager.is_connected:
                info = self.camera_manager.get_camera_info()
                offset = self.hardware_service.get_camera_offset()
                status = "Ready" if info.get('calibrated', False) else "Need calibration"
                self.log(f"Camera: {info.get('camera_id')} | {info.get('width')}x{info.get('height')} | "
                         f"Marker: {self.marker_length_var.get():.1f}mm | "
                         f"Offset: [{offset['x']:.1f},{offset['y']:.1f},{offset['z']:.1f}] | {status}")
        except Exception as e:
            self.log(f"Info error: {e}", "error")

    # === CAMERA OFFSET METHODS ===

    def apply_offset(self):
        """Apply camera offset"""
        try:
            x = float(self.offset_x_var.get())
            y = float(self.offset_y_var.get())
            z = float(self.offset_z_var.get())

            self.hardware_service.set_camera_offset(x, y, z)
            self.offset_display.config(text=f"Current: X{x:.1f} Y{y:.1f} Z{z:.1f} mm")
            self.log(f"Camera offset applied: X{x:.2f} Y{y:.2f} Z{z:.2f} mm")

        except ValueError:
            messagebox.showerror("Error", "Invalid offset values")
        except Exception as e:
            self.log(f"Error applying offset: {e}", "error")

    def reset_offset(self):
        """Reset camera offset to zero"""
        self.offset_x_var.set(0.0)
        self.offset_y_var.set(0.0)
        self.offset_z_var.set(0.0)
        self.apply_offset()

    # === FOV CALCULATION METHODS ===

    def calculate_fov_auto(self):
        """Calculate FOV automatically using camera manager"""
        try:
            if not self.camera_manager.is_connected:
                messagebox.showerror("Error", "Camera not connected")
                return

            if not self.camera_manager.is_calibrated():
                messagebox.showerror("Error", "Camera not calibrated - load calibration first")
                return

            marker_size_mm = self.marker_length_var.get()

            # Calculate FOV using camera manager
            fov_data = self.camera_manager.calculate_fov_from_current_frame(marker_size_mm)

            if fov_data is None:
                messagebox.showerror("Error", "No ArUco marker detected.\nPlace a marker in the camera view and try again.")
                return

            # Show results
            width_mm = fov_data['width_mm']
            height_mm = fov_data['height_mm']
            distance_mm = fov_data['distance_mm']
            
            info_text = f"""FOV Calculated Successfully!

Field of View: {width_mm:.1f} × {height_mm:.1f} mm
Camera Distance: {distance_mm:.1f} mm
Pixels per mm: {fov_data['pixels_per_mm']:.2f}
Resolution: {fov_data['frame_resolution'][0]}×{fov_data['frame_resolution'][1]}

This FOV data will be used for coordinate transformations."""

            messagebox.showinfo("FOV Calculation", info_text)
            self.log(f"FOV calculated: {width_mm:.1f}×{height_mm:.1f}mm @ {distance_mm:.1f}mm")

        except Exception as e:
            messagebox.showerror("Error", f"FOV calculation failed: {e}")
            self.log(f"FOV calculation error: {e}", "error")

    # === CONFIGURATION SYNC METHODS ===

    def update_from_configuration(self, config):
        """Update camera panel UI from configuration"""
        try:
            if config and config.camera:
                # Update camera connection settings
                self.camera_id_var.set(str(config.camera.camera_id))
                
                # Update marker length
                self.marker_length_var.set(config.camera.marker_length_mm)
                
                # Update calibration file if available
                if config.camera.calibration_file:
                    import os
                    if os.path.exists(config.camera.calibration_file):
                        filename = os.path.basename(config.camera.calibration_file)
                        if len(filename) > 20:
                            filename = filename[:17] + "..."
                        self.calibration_file_var.set(f"✓ {filename}")
                        self.calib_status_label.config(foreground="green")
                    else:
                        self.calibration_file_var.set("❌ File not found")
                        self.calib_status_label.config(foreground="red")
                else:
                    self.calibration_file_var.set("No calibration")
                    self.calib_status_label.config(foreground="gray")
                
                # Update camera manager with new camera ID (but don't auto-connect)
                self.camera_manager.camera_id = config.camera.camera_id
                
                # Update camera manager resolution
                self.camera_manager.resolution = (
                    config.camera.resolution_width, 
                    config.camera.resolution_height
                )
                
                self.log(f"Camera panel updated from configuration: ID={config.camera.camera_id}, "
                        f"Resolution={config.camera.resolution_width}x{config.camera.resolution_height}, "
                        f"Marker={config.camera.marker_length_mm}mm")
                
        except Exception as e:
            self.log(f"Error updating camera panel from configuration: {e}", "error")

    def update_hardware_offset_from_configuration(self, config):
        """Update camera offset UI from hardware configuration"""
        try:
            if config and config.hardware:
                self.offset_x_var.set(config.hardware.camera_offset_x)
                self.offset_y_var.set(config.hardware.camera_offset_y)
                self.offset_z_var.set(config.hardware.camera_offset_z)
                
                # Update the display
                self.offset_display.config(
                    text=f"Current: X{config.hardware.camera_offset_x:.1f} "
                         f"Y{config.hardware.camera_offset_y:.1f} "
                         f"Z{config.hardware.camera_offset_z:.1f} mm"
                )
                
                self.log(f"Camera offset updated from configuration: "
                        f"[{config.hardware.camera_offset_x:.1f}, "
                        f"{config.hardware.camera_offset_y:.1f}, "
                        f"{config.hardware.camera_offset_z:.1f}]")
                
        except Exception as e:
            self.log(f"Error updating camera offset from configuration: {e}", "error")

    # === EVENT HANDLERS ===

    @event_handler(CameraEvents.CONNECTED, EventPriority.HIGH)
    def on_camera_connected(self, success: bool):
        """Handle camera connection event"""
        if success:
            self.camera_status_var.set("Connected")
            self.cam_status_label.config(foreground="green")
            self.camera_connect_btn.config(state=tk.DISABLED)
            self.camera_disconnect_btn.config(state=tk.NORMAL)
            self._set_calibration_controls_enabled(True)

            # Update hardware service
            self.hardware_service.set_has_camera(True)
            self._log_calibration_info()
        else:
            self.camera_status_var.set("Failed")
            self.cam_status_label.config(foreground="red")
            self.camera_connect_btn.config(state=tk.NORMAL)
            self.camera_disconnect_btn.config(state=tk.DISABLED)
            self._set_calibration_controls_enabled(False)

    @event_handler(CameraEvents.DISCONNECTED, EventPriority.HIGH)
    def on_camera_disconnected(self):
        """Handle camera disconnection event"""
        self.camera_status_var.set("Disconnected")
        self.cam_status_label.config(foreground="red")
        self.camera_connect_btn.config(state=tk.NORMAL)
        self.camera_disconnect_btn.config(state=tk.DISABLED)
        self._set_calibration_controls_enabled(False)

        # Update hardware service
        self.hardware_service.set_has_camera(False)

        # Clear FOV data
        self.fov_status_var.set("No FOV data")

    @event_handler(CameraEvents.CALIBRATION_LOADED, EventPriority.NORMAL)
    def on_calibration_loaded(self, file_path: str):
        """Handle calibration loaded event"""
        filename = file_path.split('/')[-1]
        if len(filename) > 20:
            filename = filename[:17] + "..."
        self.calibration_file_var.set(f"✓ {filename}")
        self.calib_status_label.config(foreground="green")
        self._log_calibration_info()

    @event_handler(CameraEvents.ERROR, EventPriority.NORMAL)
    def on_camera_error(self, error_message: str):
        """Handle camera error events"""
        self.log(f"Camera error: {error_message}", "error")

    @event_handler(CameraEvents.FOV_CALCULATED, EventPriority.NORMAL)
    def on_fov_calculated(self, fov_data: dict):
        """Handle FOV calculation events"""
        width = fov_data.get('width_mm', 0)
        height = fov_data.get('height_mm', 0)
        distance = fov_data.get('distance_mm', 0)

        self.fov_status_var.set(f"FOV: {width:.1f}×{height:.1f}mm @ {distance:.1f}mm")
        self.log(f"FOV calculated: {width:.1f}×{height:.1f}mm @ {distance:.1f}mm")

    @event_handler(CameraEvents.FOV_UPDATED, EventPriority.NORMAL)
    def on_fov_updated(self, fov_data):
        """Handle FOV data updates"""
        if fov_data is None:
            self.fov_status_var.set("FOV data cleared")

    # === CONFIGURATION EVENT HANDLERS ===

    @event_handler(ConfigurationServiceEvents.APPLIED, EventPriority.NORMAL)
    def _on_configuration_applied(self, event_data):
        """Handle configuration applied event - update UI"""
        config = event_data.get('config')
        if config:
            self.update_from_configuration(config)
            self.update_hardware_offset_from_configuration(config)
            self.log("Camera panel synchronized with new configuration")

    @event_handler(ConfigurationEvents.LOADED, EventPriority.NORMAL) 
    def _on_configuration_loaded(self, event_data):
        """Handle configuration loaded event - update UI"""
        config = event_data.get('config')
        if config:
            self.update_from_configuration(config)
            self.update_hardware_offset_from_configuration(config)
            self.log("Camera panel synchronized with loaded configuration")