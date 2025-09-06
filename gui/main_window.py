"""
Complete Main Window - CORRECTED to use ORIGINAL code pattern exactly
TEMPORARILY: Using original MarkerDetectionOverlay to get camera working
"""

import time
import tkinter as tk
from tkinter import ttk
from typing import List

import numpy as np

from gui.camera_display import CameraDisplay
from gui.panel_camera import CameraPanel
from gui.panel_commands import GRBLCommandPanel
from gui.panel_debug import DebugPanel
from gui.panel_hardware import MachineConfigPanel
from gui.panel_jogger import JogPanel
from gui.panel_machine import MachinePanel
from gui.panel_machine_area import MachineAreaPanel
from gui.panel_registration import RegistrationPanel
from gui.panel_routes import RoutesPanel
from gui.window_machine_area import MachineAreaWindow
from services.camera_manager import CameraEvents
from services.event_broker import (event_aware, event_handler, EventBroker, EventPriority)
from services.events import ApplicationEvents
from services.grbl_controller import GRBLEvents
from services.overlays.marker_detection_overlay import MarkerDetectionOverlay
from services.registration_manager import RegistrationEvents
from gui.panel_transform import RouteTransformationPanel
from gui.panel_crosshair import CrosshairControlPanel


@event_aware()
class RegistrationGUI:
    """Main GUI window for GRBL Camera Registration application with Machine Area Visualization"""

    def __init__(self, root, grbl_controller, camera_manager, registration_manager, route_manager, hardware_service):
        self.machine_config_panel = None
        self.root = root
        self.root.title("GRBL Camera Registration with Machine Area Visualization")
        self.root.geometry("1600x900")

        # Initialize GUI state FIRST (before any event system setup)
        self.status_var = None
        self.camera_display = None
        self.marker_overlay = None
        self.routes_overlay = None
        self.routes_panel = None
        self.connection_panel = None
        self.machine_panel = None
        self.registration_panel = None
        self.calibration_panel = None
        self.debug_panel = None
        self.machine_area_panel = None
        self.route_transformation_panel = None
        self.crosshair_panel = None  # Crosshair control panel with auto-center

        # Machine area window (will be initialized later)
        self.machine_area_window = None
        self.machine_area_toggle_button = None

        # Set up event broker logging (using the decorator's broker)
        self.setup_event_logging()

        # Controllers and managers
        self.grbl_controller = grbl_controller
        self.camera_manager = camera_manager
        self.registration_manager = registration_manager
        self.route_manager = route_manager
        self.hardware_service = hardware_service

        self.setup_gui()

        # Setup machine area window AFTER GUI is ready
        self.root.after(100, self.setup_machine_area_window)

        # Start update timer for crosshair status
        self.start_update_timer()

    def setup_event_logging(self):
        """Setup event logging to debug panel"""
        # Get the event broker using the correct method
        broker = EventBroker.get_default()

        def log_to_debug(message, level="info"):
            """Route logs to debug panel if available"""
            if hasattr(self, 'debug_panel') and self.debug_panel:
                timestamp = time.strftime("%H:%M:%S")
                log_entry = f"[{timestamp}] {message}"
                self.debug_panel.log(log_entry, level)

        # Set the broker logger to our debug panel logger
        broker.set_logger(log_to_debug)

    def log(self, message: str, level: str = "info"):
        """Main logging method that routes to debug panel"""
        if hasattr(self, 'debug_panel') and self.debug_panel:
            timestamp = time.strftime("%H:%M:%S")
            log_entry = f"[GUI] {message}"
            self.debug_panel.log(log_entry, level)  # FIXED: correct method name
        else:
            print(f"[{level.upper()}] [GUI] {message}")

    # Event handlers using decorators - EXACTLY MATCHING ORIGINAL
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
            self.log("Work position: "+self.grbl_controller.get_work_position())
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

    @event_handler(GRBLEvents.POSITION_CHANGED)
    def _on_grbl_position_changed(self, position: List[float]):
        """Handle GRBL position changes"""
        # Update machine area window if visible - use event data instead of polling
        if hasattr(self, 'machine_area_window') and self.machine_area_window and self.machine_area_window.is_visible:
            try:
                # Directly update the machine area window position from event data
                self.machine_area_window.current_machine_position = np.array(position[:3])
                self.machine_area_window.schedule_update()
            except Exception as e:
                # Silently handle errors to avoid spam
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

        # Update machine area window
        if hasattr(self, 'machine_area_window') and self.machine_area_window and self.machine_area_window.is_visible:
            self.machine_area_window.update_calibration_points()
            self.machine_area_window.schedule_update()

    @event_handler(RegistrationEvents.COMPUTED)
    def _on_registration_computed(self, data: dict):
        """Handle registration computed event"""
        point_count = data.get('point_count', 0)
        error = data.get('error', 0.0)
        dimensions = data.get('dimensions', '2D')

        self.log(f"✅ {dimensions} Registration computed: {point_count} points, RMS error: {error:.3f}mm")

        # Update status bar
        self.status_var.set(f"{dimensions} Registration: {error:.3f}mm RMS")

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

        # Command frame (bottom of right panel)
        command_frame = ttk.Frame(right_panel)
        right_panel.add(command_frame, weight=0)

        # Machine area frame (in bottom container)
        machine_area_frame = ttk.Frame(right_panel)
        machine_area_frame.pack(fill=tk.X, pady=(0, 5))

        self.setup_control_panel(left_panel)
        self.setup_display_panel(display_frame)
        self.setup_debug_panel(debug_frame)
        self.setup_command_panel(command_frame)
        self.setup_machine_area_panel(machine_area_frame)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_control_panel(self, parent):
        """Setup the left control panel with all sub-panels - ORIGINAL CODE"""
        # Create scrollable frame for controls
        canvas = tk.Canvas(parent, width=450)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Mouse wheel support
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind('<Enter>', _bind_to_mousewheel)
        canvas.bind('<Leave>', _unbind_from_mousewheel)
        scrollable_frame.bind('<Enter>', _bind_to_mousewheel)
        scrollable_frame.bind('<Leave>', _unbind_from_mousewheel)

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.connection_panel = MachinePanel(scrollable_frame, self.grbl_controller)

        # CameraPanel handles all camera functionality
        self.calibration_panel = CameraPanel(scrollable_frame, self.camera_manager, self.hardware_service, self.log)

        # Create crosshair control panel with auto-center
        # Defer creation until marker overlay is ready in setup_display_panel
        self.root.after(200, self._create_crosshair_panel_deferred, scrollable_frame)

        self.machine_panel = JogPanel(scrollable_frame, self.grbl_controller)

        self.registration_panel = RegistrationPanel(
            scrollable_frame,
            self.registration_manager,
            self.grbl_controller,
            self.log
        )

        # Set up registration panel callbacks
        self.registration_panel.set_callbacks(
            self.capture_point,
            self.test_position,
            self.set_work_offset
        )

        self.machine_config_panel = MachineConfigPanel(
            scrollable_frame,
            self.grbl_controller,
            self.hardware_service,
            self.log
        )

        self.route_transformation_panel = RouteTransformationPanel(
            scrollable_frame,
            self.route_manager,
            self.registration_manager,
            self.log
        )

    def _create_crosshair_panel_deferred(self, parent):
        """Create enhanced crosshair panel with auto-center after marker overlay is ready"""
        if hasattr(self, 'marker_overlay') and self.marker_overlay:
            self.crosshair_panel = CrosshairControlPanel(
                parent,
                self.marker_overlay,
                self.log,
                self.grbl_controller,  # Pass GRBL controller for auto-center
                self.registration_manager  # Pass registration manager for coordinate transform
            )
            self.log("Enhanced crosshair control panel with auto-center created")
        else:
            self.log("Marker overlay not ready for crosshair panel", "warning")

    def setup_display_panel(self, parent):
        """Setup camera display panel with overlays - ENHANCED with crosshair"""
        # Create camera display
        self.camera_display = CameraDisplay(
            parent, self.camera_manager, logger=self.log
        )

        # Create ENHANCED marker detection overlay with crosshair functionality
        self.marker_overlay = MarkerDetectionOverlay(
            self.camera_manager, marker_length=15.0, logger=self.log
        )

        # Configure enhanced marker overlay settings
        self.marker_overlay.set_visibility(True)

        # Enable crosshair functionality
        if hasattr(self.marker_overlay, 'set_crosshair_visibility'):
            self.marker_overlay.set_crosshair_visibility(True)

        # Set pose callback for registration
        if hasattr(self.marker_overlay, 'set_pose_callback'):
            self.marker_overlay.set_pose_callback(self._on_marker_pose_detected)

        # Inject marker overlay
        self.camera_display.inject_overlay("markers", self.marker_overlay)

        # Create SVG routes panel now that overlays are ready
        control_parent = self.connection_panel.frame.master
        self.routes_panel = RoutesPanel(
            control_parent, self.route_manager, self.log
        )

        self.log("Enhanced camera display with crosshair functionality initialized")

    def setup_debug_panel(self, parent):
        """Setup debug panel using the dedicated DebugPanel class"""
        self.debug_panel = DebugPanel(parent)

    def setup_command_panel(self, command_frame):
        """Setup GRBL command panel"""
        try:
            self.command_panel = GRBLCommandPanel(
                command_frame,
                self.grbl_controller,
                self.log
            )
            self.log("GRBL command panel initialized")
        except Exception as e:
            self.log(f"Failed to create GRBL command panel: {e}", "error")

    def setup_machine_area_panel(self, machine_area_frame):
        """Setup machine area visualization control panel"""
        try:
            self.machine_area_panel = MachineAreaPanel(
                machine_area_frame,
                logger=self.log
            )
            # Set callbacks for machine area operations
            self.machine_area_panel.set_callbacks(
                self.toggle_machine_area_window,
                self.quick_setup_machine_area
            )
            self.log("Machine area control panel initialized")
        except Exception as e:
            self.log(f"Failed to create machine area panel: {e}", "error")

    def setup_machine_area_window(self):
        """Setup machine area visualization window"""
        try:
            # Create machine area window
            self.machine_area_window = MachineAreaWindow(
                self.root,
                self.grbl_controller,
                self.registration_manager,
                self.route_manager,
                self.hardware_service,
                self.camera_manager,
                self.log
            )

            # Link with control panel
            if self.machine_area_panel:
                self.machine_area_panel.set_machine_area_window(self.machine_area_window)

            # Add keyboard shortcuts
            self.setup_machine_area_shortcuts()

            self.log("Machine area visualization setup complete")
            self.log("Press F10 to toggle, F11 to center, F12 to clear trail")

        except Exception as e:
            self.log(f"Error setting up machine area window: {e}", "error")
            self.machine_area_window = None

    def setup_machine_area_shortcuts(self):
        """Setup keyboard shortcuts for machine area window"""
        if not self.machine_area_window:
            return

        self.root.bind('<F10>', lambda e: self.toggle_machine_area_window())
        self.root.bind('<F11>', lambda e: self.center_machine_area_view())
        self.root.bind('<F12>', lambda e: self.clear_machine_area_trail())

    def toggle_machine_area_window(self):
        """Toggle machine area window visibility"""
        if self.machine_area_window:
            self.machine_area_window.toggle_visibility()
            self.log("Machine area window toggled")

    def center_machine_area_view(self):
        """Center the machine area view"""
        if self.machine_area_window:
            self.machine_area_window.center_view()
            self.log("Machine area view centered")

    def clear_machine_area_trail(self):
        """Clear the machine area movement trail"""
        if self.machine_area_window:
            self.machine_area_window.clear_trail()
            self.log("Machine area trail cleared")

    def quick_setup_machine_area(self):
        """Quick setup for machine area visualization"""
        try:
            if self.machine_area_window:
                self.machine_area_window.quick_setup()
                self.log("Machine area quick setup completed")
            else:
                self.log("Machine area window not available", "warning")
        except Exception as e:
            self.log(f"Error in machine area quick setup: {e}", "error")

    # ORIGINAL CALLBACK METHODS
    def capture_point(self):
        """Capture calibration point callback - ORIGINAL"""
        try:
            # Get current machine position
            machine_pos = self.grbl_controller.get_position()  # FIXED: correct method name
            if machine_pos is None:
                self.log("Cannot capture point: machine position not available", "error")
                return

            # Get marker pose from overlay
            if not hasattr(self.marker_overlay, 'get_current_pose'):
                self.log("Cannot capture point: marker overlay not available", "error")
                return

            rvec, tvec, norm_pos = self.marker_overlay.get_current_pose()
            if tvec is None:
                self.log("Cannot capture point: no marker detected", "error")
                return

            # Add calibration point to registration manager
            success = self.registration_manager.add_calibration_point(
                np.array(machine_pos), tvec, norm_pos
            )

            if success:
                self.log(f"Calibration point captured at machine position: {machine_pos}")
            else:
                self.log("Failed to add calibration point", "error")

        except Exception as e:
            self.log(f"Error capturing calibration point: {e}", "error")

    def test_position(self):
        """Test position callback - ORIGINAL"""
        try:
            if not self.registration_manager.is_registered():
                self.log("Cannot test position: no registration computed", "error")
                return

            # Get current marker pose
            if not hasattr(self.marker_overlay, 'get_current_pose'):
                self.log("Cannot test position: marker overlay not available", "error")
                return

            rvec, tvec, norm_pos = self.marker_overlay.get_current_pose()
            if tvec is None:
                self.log("Cannot test position: no marker detected", "error")
                return

            # Transform camera position to machine coordinates
            predicted_pos = self.registration_manager.transform_point(tvec)
            actual_pos = self.grbl_controller.get_position()  # FIXED: correct method name

            if actual_pos is not None:
                error = np.linalg.norm(predicted_pos - np.array(actual_pos)[:2])
                self.log(f"Position test - Predicted: {predicted_pos}, Actual: {actual_pos[:2]}, Error: {error:.3f}mm")
            else:
                self.log(f"Position test - Predicted machine position: {predicted_pos}")

        except Exception as e:
            self.log(f"Error testing position: {e}", "error")

    def set_work_offset(self):
        """Set work offset callback - ORIGINAL"""
        try:
            if not self.registration_manager.is_registered():
                self.log("Cannot set work offset: no registration computed", "error")
                return

            if not self.grbl_controller.is_connected:
                self.log("Cannot set work offset: machine not connected", "error")
                return

            # Get current marker pose
            if not hasattr(self.marker_overlay, 'get_current_pose'):
                self.log("Cannot set work offset: marker overlay not available", "error")
                return

            rvec, tvec, norm_pos = self.marker_overlay.get_current_pose()
            if tvec is None:
                self.log("Cannot set work offset: no marker detected", "error")
                return

            # Transform to machine coordinates
            work_pos = self.registration_manager.transform_point(tvec)

            # Send G10 command to set work offset
            command = f"G10 L20 P1 X{work_pos[0]:.3f} Y{work_pos[1]:.3f}"
            self.grbl_controller.send_command(command)

            self.log(f"Work offset set to X{work_pos[0]:.3f} Y{work_pos[1]:.3f}")

        except Exception as e:
            self.log(f"Error setting work offset: {e}", "error")

    def _on_marker_pose_detected(self, rvec, tvec, norm_pos, marker_id):
        """Enhanced marker pose detection handler - called by marker overlay"""
        # This callback is used by the marker detection overlay
        # The actual capture logic is handled in the capture_point method
        pass

    def start_update_timer(self):
        """Start the periodic update timer for GUI updates"""
        def update_gui():
            try:
                # Update crosshair status display
                if hasattr(self, 'crosshair_panel') and self.crosshair_panel:
                    self.crosshair_panel.update_status_display()

            except Exception as e:
                self.log(f"Error in GUI update: {e}", "error")

            # Schedule next update
            if hasattr(self, '_gui_running') and self._gui_running:
                self.update_timer = self.root.after(500, update_gui)  # Update every 500ms

        # Start the update loop
        self._gui_running = True
        self.update_timer = self.root.after(1000, update_gui)  # Initial delay

    def stop_update_timer(self):
        """Stop the periodic update timer"""
        self._gui_running = False
        if hasattr(self, 'update_timer') and self.update_timer:
            self.root.after_cancel(self.update_timer)
            self.update_timer = None

    def start_camera_feed(self):
        """Start camera feed after connection - ORIGINAL"""
        if self.camera_display and self.camera_manager.is_connected:
            # Update marker length from calibration panel
            if hasattr(self.calibration_panel, 'get_marker_length'):
                marker_length = self.calibration_panel.get_marker_length()
                self.marker_overlay.set_marker_length(marker_length)

            self.camera_display.start_feed()

    def stop_camera_feed(self):
        """Stop camera feed - ORIGINAL"""
        if self.camera_display:
            self.camera_display.stop_feed()

    def on_closing(self):
        """Handle application closing"""
        try:
            # Stop update timer
            self.stop_update_timer()

            # Close machine area window
            if self.machine_area_window:
                self.machine_area_window.close()

            # Emit shutdown event
            self.emit(ApplicationEvents.SHUTDOWN)

        except Exception as e:
            self.log(f"Error during shutdown: {e}", "error")
        finally:
            self.root.quit()
            self.root.destroy()