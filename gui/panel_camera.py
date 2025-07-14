"""
Enhanced Camera Panel with integrated FOV calculation using Camera Manager
Simplified version - FOV tab removed, Auto FOV button kept on camera tab
"""

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional

from services.camera_manager import CameraEvents
from services.event_broker import event_aware, event_handler, EventPriority


@event_aware()
class CameraPanel:
    """Enhanced camera panel with integrated FOV calculation using Camera Manager"""

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

        # FOV status variables (simplified)
        self.fov_status_var = tk.StringVar(value="No FOV data")

        # Setup UI with simplified structure
        self._setup_widgets()
        self._set_calibration_controls_enabled(False)

        self.log("Enhanced Camera Panel with FOV integration initialized", "info")

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
        """Setup UI with simplified tabbed interface"""
        # Create notebook for tabs (Camera and Offset only)
        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # Tab 1: Camera Connection & Calibration (with FOV button)
        camera_tab = ttk.Frame(notebook)
        notebook.add(camera_tab, text="Camera")
        self._setup_camera_tab(camera_tab)

        # Tab 2: Camera Offset
        offset_tab = ttk.Frame(notebook)
        notebook.add(offset_tab, text="Offset")
        self._setup_offset_tab(offset_tab)

    def _setup_camera_tab(self, parent):
        """Setup camera connection and calibration tab with FOV integration"""
        # Camera Connection Section
        conn_frame = ttk.LabelFrame(parent, text="Camera Connection")
        conn_frame.pack(fill=tk.X, pady=5, padx=5)

        # Camera ID and status row
        cam_row = ttk.Frame(conn_frame)
        cam_row.pack(fill=tk.X, pady=2, padx=3)

        ttk.Label(cam_row, text="Camera:").pack(side=tk.LEFT)
        ttk.Entry(cam_row, textvariable=self.camera_id_var, width=5).pack(side=tk.LEFT, padx=(2, 0))

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
        self.marker_length_entry = ttk.Entry(marker_row, textvariable=self.marker_length_var, width=6)
        self.marker_length_entry.pack(side=tk.LEFT, padx=(2, 0))
        ttk.Label(marker_row, text="mm").pack(side=tk.LEFT, padx=(1, 5))

        # Auto FOV calculation button (kept here as requested)
        ttk.Button(marker_row, text="Auto FOV", command=self.calculate_fov_auto, width=8).pack(side=tk.LEFT, padx=(5, 0))

        # Calibration status and buttons row
        calib_btn_row = ttk.Frame(calib_frame)
        calib_btn_row.pack(fill=tk.X, pady=2, padx=3)

        self.calib_status_label = ttk.Label(calib_btn_row, textvariable=self.calibration_file_var,
                                            foreground="red", font=("TkDefaultFont", 7))
        self.calib_status_label.pack(side=tk.LEFT, padx=(0, 5))

        self.load_calib_btn = ttk.Button(calib_btn_row, text="Load Calibration",
                                         command=self.load_calibration, width=14)
        self.load_calib_btn.pack(side=tk.LEFT, padx=(0, 2))

        self.info_btn = ttk.Button(calib_btn_row, text="Info",
                                   command=self._show_camera_info, width=6)
        self.info_btn.pack(side=tk.LEFT)

        # FOV Status Display (simplified, single line)
        fov_status_frame = ttk.Frame(calib_frame)
        fov_status_frame.pack(fill=tk.X, pady=2, padx=3)

        self.fov_status_label = ttk.Label(fov_status_frame, textvariable=self.fov_status_var,
                                          font=("TkDefaultFont", 8), foreground="blue")
        self.fov_status_label.pack(anchor=tk.W)

    def _setup_offset_tab(self, parent):
        """Setup camera offset configuration tab"""
        # Info label
        info_label = ttk.Label(parent,
                              text="Camera offset from machine spindle/tool position (mm)",
                              font=("TkDefaultFont", 8), foreground="gray")
        info_label.pack(pady=(10, 20))

        # Offset inputs
        offset_frame = ttk.Frame(parent)
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

    # FOV event handlers (simplified)
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
                fov = info.get('fov')

                log_msg = f"Camera: ID={info['camera_id']}, {info['width']}x{info['height']}, "
                log_msg += f"Cal={'Yes' if info['calibrated'] else 'No'}, "
                log_msg += f"Offset=[{offset['x']:.1f},{offset['y']:.1f},{offset['z']:.1f}]"

                if fov:
                    log_msg += f", FOV={fov['width_mm']:.1f}×{fov['height_mm']:.1f}mm"

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

    def _show_camera_info(self):
        """Show comprehensive camera information dialog"""
        try:
            if self.camera_manager.is_connected:
                info = self.camera_manager.get_camera_info()
                offset = self.hardware_service.get_camera_offset()
                fov = info.get('fov')

                info_text = f"""Camera ID: {info.get('camera_id', 'Unknown')}
Resolution: {info.get('width', '?')}x{info.get('height', '?')}
Calibrated: {'Yes' if info.get('calibrated', False) else 'No'}
Marker Size: {self.marker_length_var.get():.1f} mm

Camera Offset:
  X: {offset['x']:.2f} mm
  Y: {offset['y']:.2f} mm  
  Z: {offset['z']:.2f} mm"""

                if fov:
                    info_text += f"""

Field of View:
  Size: {fov['width_mm']:.1f} × {fov['height_mm']:.1f} mm
  Distance: {fov['distance_mm']:.1f} mm
  Resolution: {fov['pixels_per_mm']:.2f} px/mm
  Method: {fov.get('calculated_from', 'unknown')}"""
                else:
                    info_text += "\n\nField of View: Not calculated"

                info_text += f"\n\nStatus: {'Ready for precise positioning' if (info.get('calibrated', False) and fov) else 'Calculate FOV for precision'}"

                messagebox.showinfo("Camera Info", info_text)
            else:
                messagebox.showwarning("Camera Info", "Camera not connected")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

    # === CALIBRATION METHODS ===

    def load_calibration(self):
        """Load camera calibration"""
        try:
            file_path = filedialog.askopenfilename(
                title="Load Camera Calibration",
                filetypes=[("NumPy files", "*.npz"), ("All files", "*.*")]
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

    # === FOV CALCULATION METHODS (simplified) ===

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
            info_text = f"""FOV Calculated Successfully!

Field of View: {fov_data['width_mm']:.1f} × {fov_data['height_mm']:.1f} mm
Distance to marker: {fov_data['distance_mm']:.1f} mm
Pixels per mm: {fov_data['pixels_per_mm']:.2f}
Marker ID: {fov_data.get('marker_id', 'N/A')}

The camera manager will now use this FOV data for precise marker positioning."""

            messagebox.showinfo("FOV Calculation Complete", info_text)

        except Exception as e:
            self.log(f"FOV calculation error: {e}", "error")
            messagebox.showerror("Error", f"FOV calculation failed: {e}")

    # === UTILITY METHODS ===

    def get_marker_length(self) -> float:
        """Get current marker length setting"""
        return self.marker_length_var.get()

    def set_marker_length(self, length: float):
        """Set marker length"""
        self.marker_length_var.set(length)
        self._log_calibration_info()

    def is_camera_ready(self) -> bool:
        """Check if camera is connected"""
        return self.camera_manager.is_connected

    def is_calibrated(self) -> bool:
        """Check if camera is calibrated"""
        return self.camera_manager.is_calibrated() if self.camera_manager.is_connected else False

    def has_fov_data(self) -> bool:
        """Check if FOV data is available"""
        return self.camera_manager.get_current_fov() is not None

    def get_calibration_status(self) -> dict:
        """Get current calibration status including FOV"""
        offset = self.hardware_service.get_camera_offset()
        fov_data = self.camera_manager.get_current_fov()

        status = {
            'camera_connected': self.camera_manager.is_connected,
            'camera_calibrated': self.is_calibrated(),
            'marker_length': self.get_marker_length(),
            'camera_offset': offset,
            'has_fov_data': fov_data is not None,
            'controls_enabled': self.load_calib_btn['state'] == 'normal',
            'camera_id': self.camera_id_var.get()
        }

        if fov_data:
            status['fov_data'] = {
                'width_mm': fov_data['width_mm'],
                'height_mm': fov_data['height_mm'],
                'distance_mm': fov_data['distance_mm'],
                'pixels_per_mm': fov_data['pixels_per_mm']
            }

        return status

    def get_camera_fov(self) -> dict:
        """Get current camera FOV settings for backward compatibility"""
        fov_data = self.camera_manager.get_current_fov()

        if fov_data:
            return {
                'width_mm': fov_data['width_mm'],
                'height_mm': fov_data['height_mm'],
                'working_height_mm': fov_data['distance_mm']
            }
        else:
            # Return default values if no FOV data
            return {
                'width_mm': 100.0,
                'height_mm': 75.0,
                'working_height_mm': 50.0
            }

    def refresh_fov_display(self):
        """Refresh FOV display elements"""
        try:
            fov_data = self.camera_manager.get_current_fov()

            if fov_data:
                self.fov_status_var.set(f"FOV: {fov_data['width_mm']:.1f}×{fov_data['height_mm']:.1f}mm @ {fov_data['distance_mm']:.1f}mm")
            else:
                self.fov_status_var.set("No FOV data")

        except Exception as e:
            self.log(f"Error refreshing FOV display: {e}", "error")

    def validate_setup(self) -> dict:
        """Validate complete camera setup"""
        issues = []
        warnings = []

        # Check camera connection
        if not self.camera_manager.is_connected:
            issues.append("Camera not connected")

        # Check calibration
        if not self.is_calibrated():
            issues.append("Camera not calibrated")

        # Check FOV data
        if not self.has_fov_data():
            warnings.append("No FOV data - precision may be reduced")

        # Check marker size
        if self.get_marker_length() <= 0:
            issues.append("Invalid marker size")

        return {
            'valid': len(issues) == 0,
            'ready_for_precision': len(issues) == 0 and self.has_fov_data(),
            'issues': issues,
            'warnings': warnings,
            'summary': {
                'camera_connected': self.camera_manager.is_connected,
                'camera_calibrated': self.is_calibrated(),
                'has_fov_data': self.has_fov_data(),
                'marker_size': self.get_marker_length()
            }
        }