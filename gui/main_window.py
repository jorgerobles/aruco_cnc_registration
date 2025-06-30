"""
Updated Main Window using event-aware panels
Shows clean separation of concerns with event-driven architecture
"""

import time
import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import List  # Add this import for type hints

from gui.panel_connection import ConnectionPanel
from gui.panel_calibration import CalibrationPanel
from gui.panel_machine import MachineControlPanel
from gui.panel_registration import RegistrationPanel
from gui.panel_svg import SVGRoutesPanel
from gui.panel_debug import DebugPanel
from gui.camera_display import CameraDisplay
from services.camera_manager import CameraManager
from services.event_broker import (event_aware, event_handler, EventBroker,
                                   CameraEvents, GRBLEvents, RegistrationEvents, ApplicationEvents, EventPriority)
# Import the improved controller instead of the old one
from services.grbl_controller import GRBLController
from services.overlays.marker_detection_overlay import MarkerDetectionOverlay
from services.overlays.svg_routes_overlay import SVGRoutesOverlay
from services.registration_manager import RegistrationManager


@event_aware()
class RegistrationGUI:
    """Main GUI window for GRBL Camera Registration application"""

    def __init__(self, root):
        self.root = root
        self.root.title("GRBL Camera Registration")
        self.root.geometry("1400x900")

        # Initialize GUI state FIRST (before any event system setup)
        self.status_var = None
        self.camera_display = None
        self.marker_overlay = None
        self.routes_overlay = None
        self.svg_panel = None
        self.connection_panel = None
        self.machine_panel = None
        self.registration_panel = None
        self.calibration_panel = None
        self.debug_panel = None

        # Set up event broker logging (using the decorator's broker)
        self.setup_event_logging()

        # Controllers and managers - using the improved GRBL controller
        self.grbl_controller = GRBLController()  # <-- Changed to improved version
        self.camera_manager = CameraManager()
        self.registration_manager = RegistrationManager()

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
        """Logger for event broker - direct to debug panel to avoid circular dependency"""
        if self.debug_panel and self.debug_panel.is_ready():
            # Call debug panel's log method directly, not through self.log()
            self.debug_panel.log(message, level)
        else:
            print(f"[{level.upper()}] {message}")  # Fallback

    def log(self, message: str, level: str = "info"):
        """Main logging method - routes to debug panel"""
        if self.debug_panel and self.debug_panel.is_ready():
            self.debug_panel.log(message, level)
        else:
            print(f"[{level.upper()}] {message}")  # Fallback

    # Event handlers using decorators - automatically registered!
    @event_handler(CameraEvents.CONNECTED, EventPriority.HIGH)
    def _on_camera_connected(self, success: bool):
        """Handle camera connection event"""
        if success:
            self.log("Camera connected successfully", "info")
            self.status_var.set("Camera connected")

            # Start camera feed automatically
            self.start_camera_feed()

        else:
            self.log("Camera connection failed", "error")
            self.status_var.set("Camera connection failed")

    @event_handler(CameraEvents.DISCONNECTED, EventPriority.HIGH)
    def _on_camera_disconnected(self):
        """Handle camera disconnection event"""
        self.log("Camera disconnected", "info")
        self.status_var.set("Camera disconnected")

        # Stop camera feed
        if self.camera_display:
            self.camera_display.stop_feed()

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

            # Get connection info for debugging
            info = self.grbl_controller.get_connection_info()
            self.log(f"GRBL Info: {info['serial_port']}@{info['baudrate']}, Status: {info['current_status']}")
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
        # Use debug panel's GRBL event logger for proper filtering
        if self.debug_panel:
            self.debug_panel.log_grbl_event(error_message, "error")

    @event_handler(GRBLEvents.STATUS_CHANGED)
    def _on_grbl_status_changed(self, status: str):
        """Handle GRBL status changes"""
        # Don't log status changes here to avoid spam - panels handle their own updates
        pass

    @event_handler(GRBLEvents.POSITION_CHANGED)
    def _on_grbl_position_changed(self, position: List[float]):
        """Handle GRBL position changes"""
        # Don't log position changes here to avoid spam - panels handle their own updates
        pass

    @event_handler(RegistrationEvents.POINT_ADDED, EventPriority.HIGH)
    def _on_registration_point_added(self, point_data: dict):
        """Handle new calibration point added"""
        point_index = point_data['point_index']
        total_points = point_data['total_points']
        machine_pos = point_data['machine_pos']

        self.log(
            f"Calibration point {point_index + 1} added at X{machine_pos[0]:.3f} Y{machine_pos[1]:.3f} Z{machine_pos[2]:.3f}")
        self.status_var.set(f"Calibration points: {total_points}")

    @event_handler(RegistrationEvents.COMPUTED, EventPriority.HIGH)
    def _on_registration_computed(self, computation_data: dict):
        """Handle successful registration computation"""
        point_count = computation_data['point_count']
        error = computation_data['error']

        self.log(f"Registration computed successfully with {point_count} points. RMS error: {error:.4f}")
        self.status_var.set(f"Registration complete - Error: {error:.4f}")

    @event_handler(RegistrationEvents.ERROR, EventPriority.HIGH)
    def _on_registration_error(self, error_message: str):
        """Handle registration errors"""
        self.log(f"Registration error: {error_message}", "error")

    @event_handler(ApplicationEvents.STARTUP)
    def _on_app_startup(self):
        """Handle application startup event"""
        self.log("Application started successfully", "info")

    @event_handler(ApplicationEvents.SHUTDOWN)
    def _on_app_shutdown(self):
        """Handle application shutdown event"""
        self.log("Application shutdown initiated", "info")

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

        # Create control panels - Pass the main window's log method as logger
        # All panels are now event-aware and will auto-register their event handlers
        self.connection_panel = ConnectionPanel(
            scrollable_frame, self.grbl_controller, self.camera_manager, self.log
        )

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
        """Setup debug panel using the dedicated DebugPanel class"""
        # Create the debug panel instance - Pass the main window's log method as logger
        self.debug_panel = DebugPanel(
            parent, self.grbl_controller, self.camera_manager, self.log
        )

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

            # Add to registration manager - this will emit events automatically
            self.registration_manager.add_calibration_point(machine_pos, tvec, norm_pos)

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

            self.log(
                f"Position test - Camera: {tvec.flatten()}, Predicted machine: X{machine_point[0]:.3f} Y{machine_point[1]:.3f} Z{machine_point[2]:.3f}")

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
            # Update camera status in debug panel
            if self.debug_panel:
                self.debug_panel.update_camera_status()
        else:
            self.log("Cannot start camera feed - camera not connected", "error")

    def stop_camera_feed(self):
        """Stop camera feed"""
        if self.camera_display:
            self.camera_display.stop_feed()
            self.log("Camera feed stopped", "info")

    def get_application_status(self):
        """Get comprehensive application status for monitoring/debugging"""
        try:
            status = {
                'timestamp': time.time(),
                'grbl': {
                    'connected': self.grbl_controller.is_connected if self.grbl_controller else False,
                    'status': None,
                    'position': None
                },
                'camera': {
                    'connected': self.camera_manager.is_connected if self.camera_manager else False,
                    'feed_active': False
                },
                'registration': {
                    'points': 0,
                    'computed': False,
                    'error': None
                },
                'svg_routes': {
                    'loaded': False,
                    'visible': False,
                    'count': 0
                }
            }

            # Get GRBL status
            if self.grbl_controller and self.grbl_controller.is_connected:
                try:
                    status['grbl']['status'] = self.grbl_controller.get_status()
                    status['grbl']['position'] = self.grbl_controller.get_position()
                except:
                    pass

            # Get camera status
            if self.camera_display:
                status['camera']['feed_active'] = hasattr(self.camera_display, '_feed_running') and self.camera_display._feed_running

            # Get registration status
            if self.registration_manager:
                try:
                    status['registration']['points'] = self.registration_manager.get_calibration_points_count()
                    status['registration']['computed'] = self.registration_manager.is_registered()
                    if hasattr(self.registration_manager, 'get_registration_error'):
                        status['registration']['error'] = self.registration_manager.get_registration_error()
                except:
                    pass

            # Get SVG routes status
            if self.svg_panel:
                try:
                    panel_status = self.svg_panel.get_panel_status()
                    status['svg_routes']['loaded'] = panel_status.get('routes_loaded', False)
                    status['svg_routes']['visible'] = panel_status.get('routes_visible', False)
                    status['svg_routes']['count'] = panel_status.get('routes_count', 0)
                except:
                    pass

            return status

        except Exception as e:
            self.log(f"Error getting application status: {e}", "error")
            return {'error': str(e)}

    def refresh_all_panels(self):
        """Refresh all panels to ensure UI consistency"""
        try:
            self.log("Refreshing all panels...", "info")

            # Refresh registration panel
            if self.registration_panel:
                self.registration_panel.update_point_list()

            # Refresh SVG panel
            if self.svg_panel:
                self.svg_panel.refresh_overlay()

            # Update debug panel camera status
            if self.debug_panel:
                self.debug_panel.update_camera_status()

            self.log("All panels refreshed", "info")

        except Exception as e:
            self.log(f"Error refreshing panels: {e}", "error")

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