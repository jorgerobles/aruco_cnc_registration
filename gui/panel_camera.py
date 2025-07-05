"""
Enhanced Camera Panel with Camera Offset Configuration
Direct modification of existing panel_camera.py - KISS approach
"""

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional

from services.camera_manager import CameraEvents
from services.event_broker import event_aware, event_handler, EventPriority


@event_aware()
class CameraPanel:
    """Enhanced camera panel with offset configuration - KISS approach"""

    def __init__(self, parent, camera_manager, hardware_service, logger: Optional[Callable] = None):
        self.camera_manager = camera_manager
        self.hardware_service = hardware_service
        self.logger = logger

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Camera & Hardware")
        self.frame.pack(fill=tk.X, pady=2, padx=5)

        # Existing camera variables
        self.camera_id_var = tk.StringVar(value="0")
        self.camera_status_var = tk.StringVar(value="Disconnected")
        self.marker_length_var = tk.DoubleVar(value=20.0)
        self.calibration_file_var = tk.StringVar(value="No calibration")

        # NEW: Camera offset variables
        self.offset_x_var = tk.DoubleVar(value=0.0)
        self.offset_y_var = tk.DoubleVar(value=0.0)
        self.offset_z_var = tk.DoubleVar(value=0.0)

        # Setup UI with new offset tab
        self._setup_widgets()
        self._set_calibration_controls_enabled(False)

        self.log("Enhanced Camera Panel with offset initialized", "info")

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

        # Tab 1: Camera (existing functionality)
        camera_tab = ttk.Frame(notebook)
        notebook.add(camera_tab, text="Camera")
        self._setup_camera_tab(camera_tab)

        # Tab 2: NEW - Camera Offset
        offset_tab = ttk.Frame(notebook)
        notebook.add(offset_tab, text="Offset")
        self._setup_offset_tab(offset_tab)

    def _setup_camera_tab(self, parent):
        """Setup existing camera functionality"""
        # Camera Connection Row
        cam_frame = ttk.Frame(parent)
        cam_frame.pack(fill=tk.X, pady=1, padx=3)

        ttk.Label(cam_frame, text="Camera:").pack(side=tk.LEFT)
        ttk.Entry(cam_frame, textvariable=self.camera_id_var, width=5).pack(side=tk.LEFT, padx=(2, 0))

        self.cam_status_label = ttk.Label(cam_frame, textvariable=self.camera_status_var,
                                          foreground="red", font=("TkDefaultFont", 8))
        self.cam_status_label.pack(side=tk.LEFT, padx=(5, 0))

        self.camera_connect_btn = ttk.Button(cam_frame, text="Connect",
                                             command=self.connect_camera, width=8)
        self.camera_connect_btn.pack(side=tk.LEFT, padx=(0, 2))

        self.camera_disconnect_btn = ttk.Button(cam_frame, text="Disconnect",
                                                command=self.disconnect_camera, width=8, state=tk.DISABLED)
        self.camera_disconnect_btn.pack(side=tk.LEFT, padx=(0, 2))

        ttk.Button(cam_frame, text="🔍", command=self._diagnose_camera, width=3).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(cam_frame, text="Test", command=self._test_camera_quick, width=6).pack(side=tk.LEFT)

        # Calibration Row
        calib_frame = ttk.Frame(parent)
        calib_frame.pack(fill=tk.X, pady=1, padx=3)

        ttk.Label(calib_frame, text="Marker:").pack(side=tk.LEFT)
        self.marker_length_entry = ttk.Entry(calib_frame, textvariable=self.marker_length_var, width=6)
        self.marker_length_entry.pack(side=tk.LEFT, padx=(2, 0))
        ttk.Label(calib_frame, text="mm").pack(side=tk.LEFT, padx=(1, 5))

        self.calib_status_label = ttk.Label(calib_frame, textvariable=self.calibration_file_var,
                                            foreground="red", font=("TkDefaultFont", 7))
        self.calib_status_label.pack(side=tk.LEFT, padx=(5, 0))

        self.load_calib_btn = ttk.Button(calib_frame, text="Load Calibration",
                                         command=self.load_calibration, width=14)
        self.load_calib_btn.pack(side=tk.LEFT, padx=(0, 2))

        self.info_btn = ttk.Button(calib_frame, text="Info",
                                   command=self._show_camera_info, width=6)
        self.info_btn.pack(side=tk.LEFT)

    def _setup_offset_tab(self, parent):
        """NEW: Setup camera offset configuration"""
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

    # === EXISTING EVENT HANDLERS ===

    @event_handler(CameraEvents.CONNECTED, EventPriority.HIGH)
    def on_camera_connected(self, success: bool):
        """Handle camera connection event"""
        if success:
            self.camera_status_var.set("Connected")
            self.cam_status_label.config(foreground="green")
            self.camera_connect_btn.config(state=tk.DISABLED)
            self.camera_disconnect_btn.config(state=tk.NORMAL)
            self._set_calibration_controls_enabled(True)

            # NEW: Update hardware service
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

        # NEW: Update hardware service
        self.hardware_service.set_has_camera(False)

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

    # === EXISTING CAMERA METHODS ===

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
        """Quick camera test"""
        try:
            if self.camera_manager.is_connected:
                info = self.camera_manager.get_camera_info()
                offset = self.hardware_service.get_camera_offset()
                self.log(f"Camera: ID={info['camera_id']}, {info['width']}x{info['height']}, "
                         f"Cal={'Yes' if info['calibrated'] else 'No'}, "
                         f"Offset=[{offset['x']:.1f},{offset['y']:.1f},{offset['z']:.1f}]")
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
        """Show camera information dialog"""
        try:
            if self.camera_manager.is_connected:
                info = self.camera_manager.get_camera_info()
                offset = self.hardware_service.get_camera_offset()

                info_text = f"""Camera ID: {info.get('camera_id', 'Unknown')}
Resolution: {info.get('width', '?')}x{info.get('height', '?')}
Calibrated: {'Yes' if info.get('calibrated', False) else 'No'}
Marker: {self.marker_length_var.get():.1f} mm

Camera Offset:
  X: {offset['x']:.2f} mm
  Y: {offset['y']:.2f} mm  
  Z: {offset['z']:.2f} mm

Status: {'Ready' if info.get('calibrated', False) else 'Load calibration needed'}"""
                messagebox.showinfo("Camera Info", info_text)
            else:
                messagebox.showwarning("Camera Info", "Camera not connected")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

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

    # === NEW: CAMERA OFFSET METHODS ===

    def apply_offset(self):
        """Apply camera offset - send to hardware service which emits event"""
        try:
            x = float(self.offset_x_var.get())
            y = float(self.offset_y_var.get())
            z = float(self.offset_z_var.get())

            # Send to hardware service (which emits event)
            self.hardware_service.set_camera_offset(x, y, z)

            # Update display
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

    # === EXISTING UTILITY METHODS ===

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

    def get_calibration_status(self) -> dict:
        """Get current calibration status including offset"""
        offset = self.hardware_service.get_camera_offset()
        return {
            'camera_connected': self.camera_manager.is_connected,
            'camera_calibrated': self.is_calibrated(),
            'marker_length': self.get_marker_length(),
            'camera_offset': offset,
            'controls_enabled': self.load_calib_btn['state'] == 'normal',
            'camera_id': self.camera_id_var.get()
        }