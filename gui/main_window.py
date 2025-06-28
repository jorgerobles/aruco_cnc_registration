"""
Main Window (Fixed)
Main GUI window that uses the new overlay architecture
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import time
from typing import Optional

from services.camera_manager import CameraManager
from services.grbl_controller import GRBLController
from services.registration_manager import RegistrationManager
from gui.control_panels import ConnectionPanel, MachineControlPanel, RegistrationPanel, CalibrationPanel, SVGRoutesPanel
from gui.camera_display import CameraDisplay
from services.overlays.marker_detection_overlay import MarkerDetectionOverlay
from services.overlays.svg_routes_overlay import SVGRoutesOverlay
from services.event_broker import (event_aware, event_handler, EventBroker,
                         CameraEvents, GRBLEvents, RegistrationEvents, ApplicationEvents, EventPriority)


@event_aware()
class RegistrationGUI:
    """Main GUI window for GRBL Camera Registration application"""

    def __init__(self, root):
        self.root = root
        self.root.title("GRBL Camera Registration")
        self.root.geometry("1400x900")

        # Set up event broker logging (using the decorator's broker)
        self.setup_event_logging()

        # Controllers and managers
        self.grbl_controller = GRBLController()
        self.camera_manager = CameraManager()
        self.registration_manager = RegistrationManager()

        # GUI state
        self.debug_enabled = True

        # GUI components
        self.debug_text = None
        self.status_var = None
        self.camera_display = None
        self.marker_overlay = None
        self.routes_overlay = None
        self.svg_panel = None
        self.connection_panel = None
        self.machine_panel = None
        self.registration_panel = None
        self.calibration_panel = None

        self.setup_gui()

        # Emit startup event
        self.emit(ApplicationEvents.STARTUP)

    def setup_event_logging(self):
        """Set up event broker logging using the injected broker"""
        # Get the default broker and configure it
        broker = EventBroker.get_default()
        broker._enable_logging = True
        broker.set_logger(self._event_log)

    def _event_log(self, message: str, level: str = "info"):
        """Logger for event broker"""
        self.log(message, level)

    # Event handlers using decorators - automatically registered!
    @event_handler(CameraEvents.CONNECTED, EventPriority.HIGH)
    def _on_camera_connected(self, success: bool):
        """Handle camera connection event"""
        if success:
            self.log("Camera connected successfully", "info")
            self.status_var.set("Camera connected")

            # Start camera feed automatically
            self.start_camera_feed()

            # Enable camera-dependent controls
            if hasattr(self, 'calibration_panel'):
                self.calibration_panel.on_camera_connected()
            if hasattr(self, 'registration_panel'):
                self.registration_panel.on_camera_connected()

        else:
            self.log("Camera connection failed", "error")
            self.status_var.set("Camera connection failed")

            # Disable camera-dependent controls
            if hasattr(self, 'calibration_panel'):
                self.calibration_panel.on_camera_disconnected()
            if hasattr(self, 'registration_panel'):
                self.registration_panel.on_camera_disconnected()

    @event_handler(CameraEvents.DISCONNECTED, EventPriority.HIGH)
    def _on_camera_disconnected(self):
        """Handle camera disconnection event"""
        self.log("Camera disconnected", "info")
        self.status_var.set("Camera disconnected")

        # Stop camera feed
        if self.camera_display:
            self.camera_display.stop_feed()

        # Disable camera-dependent controls
        if hasattr(self, 'calibration_panel'):
            self.calibration_panel.on_camera_disconnected()
        if hasattr(self, 'registration_panel'):
            self.registration_panel.on_camera_disconnected()

    @event_handler(CameraEvents.ERROR)
    def _on_camera_error(self, error_message: str):
        """Handle camera error event"""
        self.log(f"Camera error: {error_message}", "error")

    @event_handler(CameraEvents.CALIBRATION_LOADED)
    def _on_camera_calibrated(self, file_path: str):
        """Handle camera calibration loaded event"""
        self.log(f"Camera calibration loaded: {file_path}", "info")
        self.status_var.set("Camera calibrated")

    @event_handler(GRBLEvents.CONNECTED, EventPriority.HIGH)
    def _on_grbl_connected(self, success: bool):
        """Handle GRBL connection event"""
        if success:
            self.log("GRBL connected successfully", "info")
            self.status_var.set("GRBL connected")
        else:
            self.log("GRBL connection failed", "error")
            self.status_var.set("GRBL connection failed")

    @event_handler(GRBLEvents.DISCONNECTED)
    def _on_grbl_disconnected(self):
        """Handle GRBL disconnection event"""
        self.log("GRBL disconnected", "info")
        self.status_var.set("GRBL disconnected")

    @event_handler(GRBLEvents.ERROR)
    def _on_grbl_error(self, error_message: str):
        """Handle GRBL error event"""
        self.log(f"GRBL error: {error_message}", "error")

    @event_handler(RegistrationEvents.POINT_ADDED, EventPriority.HIGH)
    def _on_registration_point_added(self, point_data: dict):
        """Handle new calibration point added"""
        point_index = point_data['point_index']
        total_points = point_data['total_points']
        machine_pos = point_data['machine_pos']

        self.log(f"Calibration point {point_index + 1} added at X{machine_pos[0]:.3f} Y{machine_pos[1]:.3f} Z{machine_pos[2]:.3f}")
        self.status_var.set(f"Calibration points: {total_points}")

        # Update registration panel display
        if hasattr(self, 'registration_panel'):
            self.registration_panel.update_point_list()

    @event_handler(RegistrationEvents.COMPUTED, EventPriority.HIGH)
    def _on_registration_computed(self, computation_data: dict):
        """Handle successful registration computation"""
        point_count = computation_data['point_count']
        error = computation_data['error']

        self.log(f"Registration computed successfully with {point_count} points. RMS error: {error:.4f}")
        self.status_var.set(f"Registration complete - Error: {error:.4f}")

        # Update UI to show registration is ready
        if hasattr(self, 'registration_panel'):
            self.registration_panel.on_registration_computed(error)

    @event_handler(RegistrationEvents.ERROR, EventPriority.HIGH)
    def _on_registration_error(self, error_message: str):
        """Handle registration errors"""
        self.log(f"Registration error: {error_message}", "error")

    def setup_gui(self):
        """Setup the main GUI layout"""
        # Create main paned window
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel for controls
        left_panel = ttk.Frame(main_paned)
        main_paned.add(left_panel, weight=0)

        # Right panel with vertical paned window for display and debug
        right_panel = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
        main_paned.add(right_panel, weight=1)

        # Display frame (top of right panel)
        display_frame = ttk.LabelFrame(right_panel, text="Camera View")
        right_panel.add(display_frame, weight=1)

        # Debug frame (bottom of right panel)
        debug_frame = ttk.LabelFrame(right_panel, text="Debug Console")
        right_panel.add(debug_frame, weight=0)

        self.setup_control_panel(left_panel)
        self.setup_display_panel(display_frame)
        self.setup_debug_panel(debug_frame)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_control_panel(self, parent):
        """Setup the left control panel with all sub-panels"""
        # Create scrollable frame for controls
        canvas = tk.Canvas(parent, width=300)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Create control panels
        self.connection_panel = ConnectionPanel(
            scrollable_frame, self.grbl_controller, self.camera_manager, self.log
        )

        self.setup_debug_controls(scrollable_frame)

        self.calibration_panel = CalibrationPanel(
            scrollable_frame, self.camera_manager, self.log
        )

        self.machine_panel = MachineControlPanel(
            scrollable_frame, self.grbl_controller, self.log
        )

        self.registration_panel = RegistrationPanel(
            scrollable_frame, self.registration_manager, self.log
        )

        # Set up registration panel callbacks
        self.registration_panel.set_callbacks(
            self.capture_point,
            self.test_position,
            self.set_work_offset
        )

        # SVG panel will be created in setup_display_panel after overlays are ready

    def setup_debug_controls(self, parent):
        """Setup debug controls section"""
        debug_ctrl_frame = ttk.LabelFrame(parent, text="Debug Controls")
        debug_ctrl_frame.pack(fill=tk.X, pady=5, padx=5)

        self.debug_var = tk.BooleanVar()
        ttk.Checkbutton(debug_ctrl_frame, text="Enable Debug",
                        variable=self.debug_var, command=self.toggle_debug).pack()

        ttk.Button(debug_ctrl_frame, text="Clear Debug", command=self.clear_debug).pack(pady=2)

        # Manual command entry
        ttk.Label(debug_ctrl_frame, text="Manual GRBL Command:").pack()
        self.manual_cmd_var = tk.StringVar()
        cmd_entry = ttk.Entry(debug_ctrl_frame, textvariable=self.manual_cmd_var, width=20)
        cmd_entry.pack()
        cmd_entry.bind('<Return>', self.send_manual_command)
        ttk.Button(debug_ctrl_frame, text="Send Command", command=self.send_manual_command).pack(pady=2)

        # Camera status display
        camera_status_frame = ttk.LabelFrame(debug_ctrl_frame, text="Camera Status")
        camera_status_frame.pack(fill=tk.X, pady=5)

        self.camera_status_var = tk.StringVar(value="Disconnected")
        ttk.Label(camera_status_frame, textvariable=self.camera_status_var).pack()

        ttk.Button(camera_status_frame, text="Refresh Camera Info",
                  command=self.update_camera_status).pack(pady=2)

        # Event broker status
        event_status_frame = ttk.LabelFrame(debug_ctrl_frame, text="Event System")
        event_status_frame.pack(fill=tk.X, pady=5)

        ttk.Button(event_status_frame, text="Show Event Stats",
                  command=self.show_event_stats).pack(pady=2)

    def setup_display_panel(self, parent):
        """Setup camera display panel with overlays"""
        # Create camera display without overlays
        self.camera_display = CameraDisplay(
            parent, self.camera_manager, logger=self.log
        )

        # Create and inject marker detection overlay
        self.marker_overlay = MarkerDetectionOverlay(
            self.camera_manager, marker_length=20.0, logger=self.log
        )
        self.camera_display.inject_overlay("markers", self.marker_overlay)

        # Create and inject routes overlay
        self.routes_overlay = SVGRoutesOverlay(
            registration_manager=self.registration_manager, logger=self.log
        )
        self.camera_display.inject_overlay("routes", self.routes_overlay)

        # Configure overlays
        self.marker_overlay.set_visibility(True)
        self.routes_overlay.set_visibility(False)  # Hidden by default

        # Create SVG routes panel now that overlays are ready
        # Get the parent frame from the control panel setup
        control_parent = self.connection_panel.frame.master
        self.svg_panel = SVGRoutesPanel(
            control_parent, self.routes_overlay, self.log
        )

    def setup_debug_panel(self, parent):
        """Setup debug console panel"""
        # Debug text area with scrollbar
        self.debug_text = scrolledtext.ScrolledText(parent, height=8, wrap=tk.WORD)
        self.debug_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure text tags for different message types
        self.debug_text.tag_configure("sent", foreground="blue")
        self.debug_text.tag_configure("received", foreground="green")
        self.debug_text.tag_configure("error", foreground="red")
        self.debug_text.tag_configure("info", foreground="gray")

    def log(self, message: str, level: str = "info"):
        """Log message to debug console"""
        if self.debug_enabled and self.debug_text:
            timestamp = time.strftime("%H:%M:%S")
            tag_map = {
                "info": "info",
                "error": "error",
                "sent": "sent",
                "received": "received"
            }
            tag = tag_map.get(level, "info")
            self.debug_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
            self.debug_text.see(tk.END)

    def toggle_debug(self):
        """Toggle debug mode on/off"""
        self.debug_enabled = self.debug_var.get()
        if self.debug_enabled:
            self.log("Debug mode enabled", "info")
        else:
            self.log("Debug mode disabled", "info")

    def clear_debug(self):
        """Clear debug console"""
        self.debug_text.delete(1.0, tk.END)

    def update_camera_status(self):
        """Update camera status display"""
        info = self.camera_manager.get_camera_info()
        if info['connected']:
            status = f"Connected (ID: {info['camera_id']}, {info['width']}x{info['height']}"
            if info['calibrated']:
                status += ", Calibrated"
            status += ")"
        else:
            status = f"Disconnected (ID: {info['camera_id']})"

        self.camera_status_var.set(status)

    def show_event_stats(self):
        """Show event broker statistics"""
        event_types = self._event_broker.list_event_types()
        stats = []
        for event_type in event_types:
            count = self._event_broker.get_subscriber_count(event_type)
            stats.append(f"{event_type}: {count} subscribers")

        if stats:
            self.log("Event Statistics:")
            for stat in stats:
                self.log(f"  {stat}")
        else:
            self.log("No active event subscriptions")

    def send_manual_command(self, event=None):
        """Send manual GRBL command"""
        command = self.manual_cmd_var.get().strip()
        if not command:
            return

        try:
            self.log(f"SENT: {command}", "sent")
            response = self.grbl_controller.send_command(command)
            for line in response:
                self.log(f"RECV: {line}", "received")
            self.manual_cmd_var.set("")  # Clear entry
        except Exception as e:
            self.log(f"ERROR: {e}", "error")

    def capture_point(self):
        """Capture calibration point (callback for registration panel)"""
        try:
            # Get machine position
            machine_pos = self.grbl_controller.get_position()
            self.log(f"Machine position: X{machine_pos[0]:.3f} Y{machine_pos[1]:.3f} Z{machine_pos[2]:.3f}")

            # Get marker position from marker overlay
            rvec, tvec, norm_pos = self.marker_overlay.get_current_pose()

            if tvec is None:
                self.log("No marker detected in current frame", "error")
                return

            # Add to registration manager
            self.registration_manager.add_calibration_point(machine_pos, tvec, norm_pos)

            # Update display
            self.registration_panel.add_point_to_list(machine_pos)

            point_count = self.registration_manager.get_calibration_points_count()
            self.status_var.set(f"Captured point {point_count}")
            self.log(f"Captured calibration point {point_count}")

        except Exception as e:
            self.log(f"Failed to capture point: {e}", "error")

    def test_position(self):
        """Test current position (callback for registration panel)"""
        try:
            if not self.registration_manager.is_registered():
                self.log("Registration not computed", "error")
                return

            # Get current marker pose from marker overlay
            rvec, tvec, norm_pos = self.marker_overlay.get_current_pose()

            if tvec is None:
                self.log("No marker detected", "error")
                return

            # Transform to machine coordinates
            machine_point = self.registration_manager.transform_point(tvec.flatten())

            self.log(f"Position test - Camera: {tvec.flatten()}, Predicted machine: X{machine_point[0]:.3f} Y{machine_point[1]:.3f} Z{machine_point[2]:.3f}")

        except Exception as e:
            self.log(f"Position test failed: {e}", "error")

    def set_work_offset(self):
        """Set work offset (callback for registration panel)"""
        try:
            if not self.registration_manager.is_registered():
                self.log("Registration not computed", "error")
                return

            # Get current marker pose from marker overlay
            rvec, tvec, norm_pos = self.marker_overlay.get_current_pose()

            if tvec is None:
                self.log("No marker detected", "error")
                return

            # Transform to machine coordinates
            machine_point = self.registration_manager.transform_point(tvec.flatten())

            # Set work offset
            response = self.grbl_controller.set_work_offset(machine_point, coordinate_system=1)
            for line in response:
                self.log(f"OFFSET: {line}", "received")

            self.status_var.set("Work offset set")
            self.log(f"Work offset set to: X{machine_point[0]:.3f} Y{machine_point[1]:.3f} Z{machine_point[2]:.3f}")

        except Exception as e:
            self.log(f"Failed to set work offset: {e}", "error")

    def start_camera_feed(self):
        """Start camera feed after connection"""
        if self.camera_display and self.camera_manager.is_connected:
            # Update marker length from calibration panel
            if hasattr(self.calibration_panel, 'get_marker_length'):
                marker_length = self.calibration_panel.get_marker_length()
                self.marker_overlay.set_marker_length(marker_length)

            self.camera_display.start_feed()
            self.log("Camera feed started", "info")
            self.update_camera_status()
        else:
            self.log("Cannot start camera feed - camera not connected", "error")

    def stop_camera_feed(self):
        """Stop camera feed"""
        if self.camera_display:
            self.camera_display.stop_feed()
            self.log("Camera feed stopped", "info")

    def on_closing(self):
        """Handle application closing"""
        self.log("Application closing", "info")

        # Emit shutdown event
        self.emit(ApplicationEvents.SHUTDOWN)

        # Stop camera feed
        self.stop_camera_feed()

        # Clean up event subscriptions
        self.cleanup_subscriptions()

        # Disconnect from devices
        self.camera_manager.disconnect()
        self.grbl_controller.disconnect()

        self.root.destroy()