# gui/panel_camera.py
"""
Clean Store-Integrated Camera Panel
No backward compatibility - pure store integration
"""

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional

# Store integration imports
from store.store import ApplicationStore
from store.selectors import Selectors

# Event system imports (for configuration events only)
from services.event_broker import event_aware, event_handler, EventPriority
from services.configuration_service import ConfigurationServiceEvents
from services.configuration_manager import ConfigurationEvents


@event_aware()  # Keep decorator for configuration events
class CameraPanel:
    """
    Clean store-integrated camera panel
    Subscribes to store state changes for camera updates
    """

    def __init__(self, parent, camera_manager, hardware_service, store: ApplicationStore,
                 logger: Optional[Callable] = None):
        self.camera_manager = camera_manager
        self.hardware_service = hardware_service
        self.store = store
        self.logger = logger

        # Store subscription management
        self._store_unsubscribe = None
        self._previous_camera_state = None

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Camera & Hardware")
        self.frame.pack(fill=tk.X, pady=2, padx=5)

        # Camera variables
        self.camera_id_var = tk.StringVar(value="0")
        self.camera_status_var = tk.StringVar(value="Disconnected")
        self.calibration_file_var = tk.StringVar(value="No calibration")

        # Camera offset variables
        self.offset_x_var = tk.DoubleVar(value=0.0)
        self.offset_y_var = tk.DoubleVar(value=0.0)
        self.offset_z_var = tk.DoubleVar(value=0.0)

        # FOV status variables
        self.fov_status_var = tk.StringVar(value="No FOV data")

        # Setup UI
        self._setup_widgets()

        # Setup store integration
        self._setup_store_integration()

        self.log("Store-integrated Camera Panel initialized")

    def _setup_store_integration(self):
        """Setup store-based state management"""
        # Subscribe to store state changes
        self._store_unsubscribe = self.store.subscribe(self._on_store_state_change)

        # Initialize with current state
        current_state = self.store.get_state()
        self._update_ui_from_camera_state(current_state.camera)
        self._previous_camera_state = current_state.camera

    def _on_store_state_change(self, state):
        """Handle store state changes for camera updates"""
        camera_state = state.camera

        # Check for connection changes
        if (self._previous_camera_state is None or
                camera_state.connected != self._previous_camera_state.connected):
            self._update_connection_status(camera_state.connected)

        # Check for calibration changes
        if (self._previous_camera_state is None or
                camera_state.calibration_file != self._previous_camera_state.calibration_file):
            self._update_calibration_status(camera_state.calibration_file)

        # Check for new frames (for FOV updates)
        if (camera_state.current_frame is not None and
                camera_state.marker_detection is not None):
            self._update_fov_from_marker_data(camera_state.marker_detection)

        self._previous_camera_state = camera_state

    def _update_ui_from_camera_state(self, camera_state):
        """Update UI from camera state"""
        self._update_connection_status(camera_state.connected)
        self._update_calibration_status(camera_state.calibration_file)
        if camera_state.marker_detection:
            self._update_fov_from_marker_data(camera_state.marker_detection)

    def _update_connection_status(self, connected: bool):
        """Update UI connection status"""
        if connected:
            self.camera_status_var.set("Connected")
            self.connect_btn.config(state='disabled', text="Connected")
            self.disconnect_btn.config(state='normal')
        else:
            self.camera_status_var.set("Disconnected")
            self.connect_btn.config(state='normal', text="Connect")
            self.disconnect_btn.config(state='disabled')

    def _update_calibration_status(self, calibration_file: Optional[str]):
        """Update calibration status in UI"""
        if calibration_file:
            self.calibration_file_var.set(f"Loaded: {calibration_file}")
        else:
            self.calibration_file_var.set("No calibration")

    def _update_fov_from_marker_data(self, marker_data: dict):
        """Update FOV display from marker detection data"""
        if marker_data and marker_data.get('markers_detected', 0) > 0:
            # Calculate FOV if we have calibration
            if self.camera_manager.is_calibrated():
                fov_data = self.camera_manager.calculate_fov_from_marker(marker_data)
                if fov_data:
                    width = fov_data.get('width_mm', 0)
                    height = fov_data.get('height_mm', 0)
                    distance = fov_data.get('distance_mm', 0)
                    self.fov_status_var.set(f"FOV: {width:.1f}×{height:.1f}mm @ {distance:.1f}mm")
                    return

            # Fallback to basic marker info
            marker_count = marker_data.get('markers_detected', 0)
            self.fov_status_var.set(f"Markers detected: {marker_count}")
        else:
            self.fov_status_var.set("No markers detected")

    def _setup_widgets(self):
        """Create UI widgets"""
        # Camera Connection Section
        conn_frame = ttk.LabelFrame(self.frame, text="Camera Connection")
        conn_frame.pack(fill=tk.X, pady=2, padx=5)

        # Camera ID row
        id_frame = ttk.Frame(conn_frame)
        id_frame.pack(fill=tk.X, pady=2)

        ttk.Label(id_frame, text="Camera ID:").pack(side=tk.LEFT)
        ttk.Entry(id_frame, textvariable=self.camera_id_var, width=5).pack(side=tk.LEFT, padx=5)

        # Status display
        status_frame = ttk.Frame(conn_frame)
        status_frame.pack(fill=tk.X, pady=2)

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        ttk.Label(status_frame, textvariable=self.camera_status_var,
                  foreground="blue").pack(side=tk.LEFT, padx=5)

        # Connection buttons
        btn_frame = ttk.Frame(conn_frame)
        btn_frame.pack(fill=tk.X, pady=2)

        self.connect_btn = ttk.Button(btn_frame, text="Connect", command=self.connect_camera)
        self.connect_btn.pack(side=tk.LEFT, padx=2)

        self.disconnect_btn = ttk.Button(btn_frame, text="Disconnect",
                                         command=self.disconnect_camera, state='disabled')
        self.disconnect_btn.pack(side=tk.LEFT, padx=2)

        # Test button
        ttk.Button(btn_frame, text="Test", command=self._test_camera_quick).pack(side=tk.LEFT, padx=2)

        # Calibration Section
        calib_frame = ttk.LabelFrame(self.frame, text="Camera Calibration")
        calib_frame.pack(fill=tk.X, pady=2, padx=5)

        # Calibration status
        ttk.Label(calib_frame, textvariable=self.calibration_file_var).pack(pady=2)

        # Calibration buttons
        calib_btn_frame = ttk.Frame(calib_frame)
        calib_btn_frame.pack(fill=tk.X, pady=2)

        ttk.Button(calib_btn_frame, text="Load Calibration",
                   command=self.load_calibration).pack(side=tk.LEFT, padx=2)

        # FOV Section
        fov_frame = ttk.LabelFrame(self.frame, text="Field of View")
        fov_frame.pack(fill=tk.X, pady=2, padx=5)

        ttk.Label(fov_frame, textvariable=self.fov_status_var).pack(pady=2)

        # Camera Offset Section
        offset_frame = ttk.LabelFrame(self.frame, text="Camera Offset")
        offset_frame.pack(fill=tk.X, pady=2, padx=5)

        # Offset display
        offset_display_frame = ttk.Frame(offset_frame)
        offset_display_frame.pack(fill=tk.X, pady=2)

        self.offset_display = ttk.Label(
            offset_display_frame,
            text=f"X: {self.offset_x_var.get():.1f}, Y: {self.offset_y_var.get():.1f}, Z: {self.offset_z_var.get():.1f} mm"
        )
        self.offset_display.pack()

    def connect_camera(self):
        """Connect to camera using store-integrated manager"""
        try:
            camera_id = int(self.camera_id_var.get())

            # Update camera ID if changed
            if camera_id != self.camera_manager.camera_id:
                success = self.camera_manager.set_camera_id(camera_id)
                if not success:
                    self.log("Failed to set camera ID", "error")
                    return

            # Connect camera - returns result immediately
            success = self.camera_manager.connect()
            if not success:
                messagebox.showerror("Error", "Failed to connect to camera")
                self.log("Failed to connect to camera", "error")
            else:
                self.log(f"Camera {camera_id} connected successfully")

        except ValueError:
            messagebox.showerror("Error", "Invalid camera ID")
            self.log("Invalid camera ID", "error")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect: {e}")
            self.log(f"Camera connection error: {e}", "error")

    def disconnect_camera(self):
        """Disconnect camera using store-integrated manager"""
        try:
            success = self.camera_manager.disconnect()
            if not success:
                self.log("Failed to disconnect camera", "error")
            else:
                self.log("Camera disconnected successfully")

        except Exception as e:
            self.log(f"Camera disconnection error: {e}", "error")

    def load_calibration(self):
        """Load camera calibration file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Load Camera Calibration",
                filetypes=[("NumPy Archive", "*.npz"), ("All files", "*.*")],
                initialdir="calibration"
            )

            if file_path:
                success = self.camera_manager.load_calibration(file_path)
                if not success:
                    messagebox.showerror("Error", "Failed to load calibration file")
                    self.log("Failed to load calibration", "error")
                else:
                    self.log(f"Calibration loaded: {file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load calibration: {e}")
            self.log(f"Calibration load error: {e}", "error")

    def _test_camera_quick(self):
        """Quick camera test"""
        camera_id = int(self.camera_id_var.get())

        def test_thread():
            try:
                import cv2
                cap = cv2.VideoCapture(camera_id)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        h, w = frame.shape[:2]
                        self.log(f"Test: Camera {camera_id} working ({w}x{h})")
                    else:
                        self.log(f"Test: Camera {camera_id} opened but no frames", "error")
                    cap.release()
                else:
                    self.log(f"Test: Camera {camera_id} not available", "error")
            except Exception as e:
                self.log(f"Test error: {e}", "error")

        threading.Thread(target=test_thread, daemon=True).start()

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

    def update_from_configuration(self, config):
        """Update camera settings from configuration"""
        try:
            if config and config.camera:
                self.camera_id_var.set(str(config.camera.camera_id))

                # Update resolution if camera manager supports it
                if hasattr(self.camera_manager, 'set_resolution'):
                    self.camera_manager.set_resolution(
                        config.camera.resolution_width,
                        config.camera.resolution_height
                    )

                # Handle calibration file
                if config.camera.calibration_file:
                    self.calibration_file_var.set(config.camera.calibration_file)
                else:
                    self.calibration_file_var.set("No calibration")

                self.log(f"Camera panel updated from configuration: ID={config.camera.camera_id}")

        except Exception as e:
            self.log(f"Error updating from configuration: {e}", "error")

    def update_hardware_offset_from_configuration(self, config):
        """Update camera offset from hardware configuration"""
        try:
            if config and config.hardware:
                self.offset_x_var.set(config.hardware.camera_offset_x)
                self.offset_y_var.set(config.hardware.camera_offset_y)
                self.offset_z_var.set(config.hardware.camera_offset_z)

                # Update display
                self.offset_display.config(
                    text=f"X: {config.hardware.camera_offset_x:.1f}, "
                         f"Y: {config.hardware.camera_offset_y:.1f}, "
                         f"Z: {config.hardware.camera_offset_z:.1f} mm"
                )

                self.log(f"Camera offset updated: [{config.hardware.camera_offset_x:.1f}, "
                         f"{config.hardware.camera_offset_y:.1f}, {config.hardware.camera_offset_z:.1f}]")

        except Exception as e:
            self.log(f"Error updating camera offset: {e}", "error")

    def cleanup(self):
        """Cleanup resources when panel is destroyed"""
        if self._store_unsubscribe:
            self._store_unsubscribe()
            self._store_unsubscribe = None

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[CameraPanel] {message}", level)