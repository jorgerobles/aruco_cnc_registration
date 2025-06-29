"""
Fixed CalibrationPanel with proper event handling using @event_aware and @event_handler decorators
This will automatically enable/disable calibration controls when camera connects/disconnects
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from typing import Callable, Optional

# Import event system
from services.event_broker import event_aware, event_handler, CameraEvents, EventPriority


@event_aware()  # ← ESSENTIAL: Makes this class event-aware
class CalibrationPanel:
    """Camera calibration panel with automatic event handling"""

    def __init__(self, parent, camera_manager, logger: Optional[Callable] = None):
        self.camera_manager = camera_manager
        self.logger = logger

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Camera Calibration")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Variables for calibration settings
        self.marker_length_var = tk.DoubleVar(value=20.0)  # Default 20mm marker
        self.calibration_file_var = tk.StringVar(value="No calibration loaded")

        # Setup UI components
        self._setup_widgets()

        # Initially disable all controls (camera not connected)
        self._set_controls_enabled(False)

        self.log("CalibrationPanel initialized with event handlers", "info")

    def set_logger(self, logger: Callable):
        """Set logger after initialization to avoid circular dependency"""
        self.logger = logger

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"CalibrationPanel: {message}", level)
        else:
            print(f"[{level.upper()}] CalibrationPanel: {message}")

    def _setup_widgets(self):
        """Setup all calibration UI widgets"""

        # === Combined ArUco Marker & Calibration Section ===
        # Marker length setting
        length_frame = ttk.Frame(self.frame)
        length_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(length_frame, text="Marker Length (mm):").pack(side=tk.LEFT)
        self.marker_length_entry = ttk.Entry(length_frame, textvariable=self.marker_length_var, width=10)
        self.marker_length_entry.pack(side=tk.LEFT, padx=(5, 0))

        # Calibration file status
        status_frame = ttk.Frame(self.frame)
        status_frame.pack(fill=tk.X, pady=2, padx=5)

        ttk.Label(status_frame, text="Calibration:").pack(side=tk.LEFT)
        self.calib_status_label = ttk.Label(status_frame, textvariable=self.calibration_file_var,
                                           foreground="red", font=("TkDefaultFont", 8))
        self.calib_status_label.pack(side=tk.LEFT, padx=(5, 0))

        # Load calibration button
        self.load_calib_btn = ttk.Button(self.frame, text="Load Calibration",
                                        command=self.load_calibration)
        self.load_calib_btn.pack(pady=5)

    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable all calibration controls"""
        state = tk.NORMAL if enabled else tk.DISABLED

        # Marker settings
        self.marker_length_entry.config(state=state)

        # Calibration button
        self.load_calib_btn.config(state=state)

        self.log(f"Calibration controls {'enabled' if enabled else 'disabled'}", "info")

    # === EVENT HANDLERS ===
    # These methods are automatically registered as event handlers by the @event_handler decorator

    @event_handler(CameraEvents.CONNECTED, EventPriority.HIGH)
    def on_camera_connected(self, success: bool):
        """Handle camera connection event - enable calibration controls"""
        if success:
            self._set_controls_enabled(True)
            self._log_calibration_info()
            self.log("Camera connected - calibration controls enabled", "info")
        else:
            self._set_controls_enabled(False)
            self.log("Camera connection failed - calibration controls disabled", "error")

    @event_handler(CameraEvents.DISCONNECTED, EventPriority.HIGH)
    def on_camera_disconnected(self):
        """Handle camera disconnection event - disable calibration controls"""
        self._set_controls_enabled(False)
        self.log("Camera disconnected - calibration controls disabled", "info")

    @event_handler(CameraEvents.CALIBRATION_LOADED, EventPriority.NORMAL)
    def on_calibration_loaded(self, file_path: str):
        """Handle calibration loaded event"""
        self.calibration_file_var.set(f"Loaded: {file_path.split('/')[-1]}")
        self.calib_status_label.config(foreground="green")
        self._log_calibration_info()
        self._update_button_states()
        self.log(f"Calibration loaded: {file_path}", "info")

    @event_handler(CameraEvents.ERROR, EventPriority.NORMAL)
    def on_camera_error(self, error_message: str):
        """Handle camera error events"""
        self.log(f"Camera error: {error_message}", "error")

    # === CALIBRATION METHODS ===

    def load_calibration(self):
        """Load camera calibration from file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Load Camera Calibration",
                filetypes=[("NumPy files", "*.npz"), ("All files", "*.*")]
            )

            if file_path:
                success = self.camera_manager.load_calibration(file_path)
                if success:
                    # Event will be emitted by camera_manager
                    self.log(f"Successfully loaded calibration from {file_path}", "info")
                else:
                    self.log("Failed to load calibration file", "error")
                    messagebox.showerror("Error", "Failed to load calibration file")

        except Exception as e:
            self.log(f"Error loading calibration: {e}", "error")
            messagebox.showerror("Error", f"Error loading calibration:\n{e}")

    def _log_calibration_info(self):
        """Log calibration info instead of displaying in UI"""
        try:
            if self.camera_manager.is_connected:
                camera_info = self.camera_manager.get_camera_info()

                info_lines = [
                    f"Camera ID: {camera_info.get('camera_id', 'Unknown')}",
                    f"Resolution: {camera_info.get('width', '?')}x{camera_info.get('height', '?')}",
                    f"Calibrated: {'Yes' if camera_info.get('calibrated', False) else 'No'}",
                    f"Marker Length: {self.marker_length_var.get():.1f} mm"
                ]

                if camera_info.get('calibrated', False):
                    info_lines.append("✅ Ready for marker detection")
                else:
                    info_lines.append("⚠️  Load calibration for accurate measurements")

                # Log all info
                self.log("Camera Info: " + " | ".join(info_lines), "info")
            else:
                self.log("Camera not connected", "info")

        except Exception as e:
            self.log(f"Error logging calibration info: {e}", "error")

    def _update_button_states(self):
        """Update button states based on current calibration status"""
        try:
            is_connected = self.camera_manager.is_connected

            # Load button enabled if connected
            load_state = tk.NORMAL if is_connected else tk.DISABLED
            self.load_calib_btn.config(state=load_state)

        except Exception as e:
            self.log(f"Error updating button states: {e}", "error")

    # === UTILITY METHODS ===

    def get_marker_length(self) -> float:
        """Get current marker length setting"""
        return self.marker_length_var.get()

    def set_marker_length(self, length: float):
        """Set marker length"""
        self.marker_length_var.set(length)
        self._log_calibration_info()

    def is_ready(self) -> bool:
        """Check if calibration panel is ready (camera connected and optionally calibrated)"""
        return self.camera_manager.is_connected

    def get_calibration_status(self) -> dict:
        """Get current calibration status"""
        return {
            'camera_connected': self.camera_manager.is_connected,
            'camera_calibrated': self.camera_manager.is_calibrated(),
            'marker_length': self.get_marker_length(),
            'controls_enabled': self.load_calib_btn['state'] == 'normal'
        }