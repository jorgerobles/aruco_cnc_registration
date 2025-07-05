"""
Complete Main Window with Machine Area Integration
FIXED: Removed duplicate GRBL event logging - debug panel handles it directly
Clean separation of responsibilities between components
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
from gui.panel_jogger import JogPanel
from gui.panel_machine import MachinePanel
from gui.panel_machine_area import MachineAreaPanel
from gui.panel_registration import RegistrationPanel
from gui.panel_svg import SVGRoutesPanel
from gui.window_machine_area import MachineAreaWindow
from services.camera_manager import CameraEvents
from services.event_broker import (event_aware, event_handler, EventBroker, EventPriority)
from services.events import ApplicationEvents
from services.grbl_controller import GRBLEvents
from services.overlays.marker_detection_overlay import MarkerDetectionOverlay
from services.registration_manager import RegistrationEvents


@event_aware()
class RegistrationGUI:
    """Main GUI window for GRBL Camera Registration application with Machine Area Visualization"""

    def __init__(self, root, grbl_controller, camera_manager, registration_manager, route_manager, hardware_service):
        self.root = root
        self.root.title("GRBL Camera Registration with Machine Area Visualization")
        self.root.geometry("1600x900")

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
        self.machine_area_panel = None

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

        # Setup machine area window AFTER everything else is initialized
        self.setup_machine_area_window()

        # Emit startup event
        self.emit(ApplicationEvents.STARTUP)

    def setup_event_logging(self):
        """Set up event broker logging using the injected broker"""
        # Get the default broker and configure it
        broker = EventBroker.get_default()
        broker._enable_logging = True
        broker.set_logger(self._event_log)

    def setup_command_panel(self, parent):
        """Setup GRBL command panel"""
        try:
            self.command_panel = GRBLCommandPanel(parent, self.grbl_controller, self.log)
            self.log("GRBL Command Panel initialized")
        except Exception as e:
            self.log(f"Error setting up command panel: {e}", "error")
            self.command_panel = None

    def setup_machine_area_panel(self, parent):
        """Setup machine area control panel directly in layout"""
        try:
            # Create machine area panel
            self.machine_area_panel = MachineAreaPanel(parent, self.machine_area_window, self.log)

            # Set callbacks (machine_area_window might not exist yet, will be set later)
            self.machine_area_panel.set_callbacks(
                self.toggle_machine_area_window,
                self.set_machine_bounds_quick
            )

            self.log("Machine area panel initialized in main layout")

        except Exception as e:
            self.log(f"Error setting up machine area panel: {e}", "error")
            self.machine_area_panel = None

    def toggle_machine_area_window(self):
        """Toggle machine area window"""
        if hasattr(self, 'machine_area_window') and self.machine_area_window:
            if self.machine_area_window.is_visible:
                self.machine_area_window.hide_window()
                self.log("Machine area window hidden")
            else:
                self.machine_area_window.show_window()
                self.log("Machine area window shown")

            # Update panel button
            if self.machine_area_panel:
                self.machine_area_panel.update_toggle_button(self.machine_area_window.is_visible)

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

    # Event handlers using decorators - FIXED: Removed duplicate GRBL error handler
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

    # REMOVED: GRBLEvents.ERROR handler - debug panel handles this directly now
    # This was causing the duplicate logging issue

    @event_handler(GRBLEvents.STATUS_CHANGED)
    def _on_grbl_status_changed(self, status: str):
        """Handle GRBL status changes"""
        # Don't log status changes here to avoid spam - panels handle their own updates
        pass

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

    @event_handler(RegistrationEvents.COMPUTED, EventPriority.HIGH)
    def _on_registration_computed(self, computation_data: dict):
        """Handle successful registration computation"""
        point_count = computation_data['point_count']
        error = computation_data['error']

        self.log(f"Registration computed successfully with {point_count} points. RMS error: {error:.4f}")
        self.status_var.set(f"Registration complete - Error: {error:.4f}")

        # Update machine area window
        if hasattr(self, 'machine_area_window') and self.machine_area_window and self.machine_area_window.is_visible:
            self.machine_area_window.update_calibration_points()
            self.machine_area_window.schedule_update()

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

        # Command frame (bottom of right panel) - NEW
        command_frame = ttk.Frame(right_panel)
        right_panel.add(command_frame, weight=0)

        # Machine area frame (in bottom container) - NEW
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
        """Setup the left control panel with all sub-panels"""
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
        self.calibration_panel = CameraPanel(scrollable_frame, self.camera_manager, self.hardware_service)

        self.machine_panel = JogPanel(scrollable_frame, self.grbl_controller)

        self.registration_panel = RegistrationPanel(scrollable_frame, self.registration_manager)

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

        # # Create and inject routes overlay
        # self.routes_overlay = SVGRoutesOverlay(
        #     registration_manager=self.registration_manager, logger=self.log
        # )
        # self.camera_display.inject_overlay("routes", self.routes_overlay)

        # Configure overlays
        self.marker_overlay.set_visibility(True)
        # self.routes_overlay.set_visibility(False)  # Hidden by default

        # Create SVG routes panel now that overlays are ready
        # Get the parent frame from the control panel setup
        control_parent = self.connection_panel.frame.master
        self.svg_panel = SVGRoutesPanel(
            control_parent, self.route_manager, self.log
        )

    def setup_debug_panel(self, parent):
        """Setup debug panel using the dedicated DebugPanel class"""
        # Create the debug panel instance - Pass the main window's log method as logger
        self.debug_panel = DebugPanel(parent)

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

            # Add keyboard shortcuts
            self.setup_machine_area_shortcuts()

            self.log("Machine area visualization setup complete")
            self.log("Press F10 to toggle, F11 to center, F12 to clear trail")

        except Exception as e:
            self.log(f"Error setting up machine area window: {e}", "error")
            # Continue without machine area window - don't let this break the app
            self.machine_area_window = None

    def create_machine_area_control_window(self):
        """Create separate control window for machine area if debug panel integration fails"""
        try:
            # Create a small control window
            control_window = tk.Toplevel(self.root)
            control_window.title("Machine Area Controls")
            control_window.geometry("300x120")
            control_window.resizable(False, False)

            # Position relative to main window
            control_window.transient(self.root)

            # Main frame
            main_frame = tk.Frame(control_window, padx=10, pady=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Title
            title_label = tk.Label(main_frame, text="🗺️ Machine Area Visualization",
                                   font=('Arial', 10, 'bold'))
            title_label.pack(pady=(0, 5))

            # Button frame
            btn_frame = tk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=2)

            # Main toggle button
            self.machine_area_toggle_button = tk.Button(
                btn_frame,
                text="Show Machine Area",
                command=self.toggle_machine_area_window,
                bg='#4a90e2',
                fg='white',
                font=('Arial', 9, 'bold'),
                relief='raised'
            )
            self.machine_area_toggle_button.pack(side=tk.LEFT, padx=2)

            # Quick settings frame
            settings_frame = tk.Frame(btn_frame)
            settings_frame.pack(side=tk.RIGHT)

            # Machine size quick buttons
            for size in [200, 300, 400]:
                btn = tk.Button(
                    settings_frame,
                    text=f"{size}",
                    command=lambda s=size: self.set_machine_bounds_quick(s, s),
                    font=('Arial', 7),
                    relief='groove',
                    width=4
                )
                btn.pack(side=tk.LEFT, padx=1)

            # Info frame
            info_frame = tk.Frame(main_frame)
            info_frame.pack(fill=tk.X, pady=2)

            info_text = "F10: Toggle | F11: Center | F12: Clear Trail"
            tk.Label(info_frame, text=info_text, font=('Arial', 7), fg='gray').pack()

            # Store reference to prevent garbage collection
            self.machine_area_control_window = control_window

            self.log("Machine area control window created")

        except Exception as e:
            self.log(f"Error creating machine area control window: {e}", "error")

    def setup_machine_area_shortcuts(self):
        """Setup keyboard shortcuts"""

        def on_key_press(event):
            if event.keysym == 'F10':
                self.toggle_machine_area_window()
            elif event.keysym == 'F11' and hasattr(self, 'machine_area_window') and self.machine_area_window:
                if self.machine_area_window.is_visible:
                    self.machine_area_window.center_view()
                    self.log("Machine area view centered")
            elif event.keysym == 'F12' and hasattr(self, 'machine_area_window') and self.machine_area_window:
                if self.machine_area_window.is_visible:
                    self.machine_area_window.clear_movement_trail()
                    self.log("Movement trail cleared")

        self.root.bind('<KeyPress>', on_key_press)

    def toggle_machine_area_window(self):
        """Toggle machine area window"""
        if hasattr(self, 'machine_area_window') and self.machine_area_window:
            if self.machine_area_window.is_visible:
                self.machine_area_window.hide_window()
                if self.machine_area_toggle_button:
                    self.machine_area_toggle_button.config(
                        text="Show Machine Area",
                        bg='#4a90e2'
                    )
                self.log("Machine area window hidden")
            else:
                self.machine_area_window.show_window()
                if self.machine_area_toggle_button:
                    self.machine_area_toggle_button.config(
                        text="Hide Machine Area",
                        bg='#d0021b'
                    )
                self.log("Machine area window shown")

    def set_machine_bounds_quick(self, x_max: float, y_max: float):
        """Quick set machine bounds"""
        if hasattr(self, 'machine_area_window') and self.machine_area_window:
            self.machine_area_window.set_machine_bounds(x_max, y_max)
            self.log(f"Machine bounds set to {x_max}x{y_max}mm")

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

            # Update machine area window
            if hasattr(self,
                       'machine_area_window') and self.machine_area_window and self.machine_area_window.is_visible:
                self.machine_area_window.update_calibration_points()
                self.machine_area_window.schedule_update()

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

            # Update machine area window with camera position
            if hasattr(self,
                       'machine_area_window') and self.machine_area_window and self.machine_area_window.is_visible:
                self.machine_area_window.current_camera_position = (machine_point[0], machine_point[1])
                self.machine_area_window.update_camera_bounds()
                self.machine_area_window.schedule_update()

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

    def stop_camera_feed(self):
        """Stop camera feed"""
        if self.camera_display:
            self.camera_display.stop_feed()

    def load_svg_routes(self, svg_file_path: str):
        """Load SVG routes and update machine area visualization"""
        try:
            # Load routes into overlay
            if hasattr(self, 'routes_overlay') and self.routes_overlay:
                self.routes_overlay.load_routes_from_svg(svg_file_path)
                self.log(f"SVG routes loaded: {svg_file_path}")

                # Update machine area window
                if hasattr(self,
                           'machine_area_window') and self.machine_area_window and self.machine_area_window.is_visible:
                    self.machine_area_window.update_all_data()
                    self.machine_area_window.schedule_update()
                    self.log("Machine area window updated with new routes")

        except Exception as e:
            self.log(f"Error loading SVG routes: {e}", "error")

    def sync_camera_position_to_machine_area(self):
        """Synchronize current camera position to machine area window"""
        try:
            if not hasattr(self, 'machine_area_window') or not self.machine_area_window:
                return

            # Get current marker pose
            if hasattr(self, 'marker_overlay') and self.marker_overlay:
                rvec, tvec, norm_pos = self.marker_overlay.get_current_pose()

                if tvec is not None and self.registration_manager.is_registered():
                    # Transform to machine coordinates
                    machine_point = self.registration_manager.transform_point(tvec.flatten())

                    # Update machine area window
                    self.machine_area_window.current_camera_position = (machine_point[0], machine_point[1])
                    self.machine_area_window.update_camera_bounds()
                    self.machine_area_window.schedule_update()

                    self.log(
                        f"Camera position synced to machine area: ({machine_point[0]:.1f}, {machine_point[1]:.1f})")

        except Exception as e:
            self.log(f"Error syncing camera position: {e}", "error")

    def center_machine_area_on_current_position(self):
        """Center machine area view on current machine position"""
        if hasattr(self, 'machine_area_window') and self.machine_area_window and self.machine_area_window.is_visible:
            current_pos = self.grbl_controller.get_position()
            if current_pos:
                # Set machine bounds centered on current position
                margin = 100  # 100mm margin around current position
                x, y = current_pos[0], current_pos[1]

                self.machine_area_window.set_machine_bounds(
                    x + margin, y + margin, x - margin, y - margin
                )
                self.log(f"Machine area centered on current position: ({x:.1f}, {y:.1f})")

    def export_machine_area_data(self, filename: str = None):
        """Export machine area visualization data"""
        if not hasattr(self, 'machine_area_window') or not self.machine_area_window:
            self.log("Machine area window not available", "error")
            return

        try:
            if filename is None:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"machine_area_data_{timestamp}.json"

            import json

            # Collect data
            export_data = {
                'timestamp': time.time(),
                'machine_bounds': self.machine_area_window.machine_bounds,
                'current_machine_position': self.machine_area_window.current_machine_position.tolist(),
                'current_camera_position': self.machine_area_window.current_camera_position,
                'routes_bounds': self.machine_area_window.routes_bounds,
                'calibration_points': [(pos[0], pos[1]) for pos in self.machine_area_window.calibration_points],
                'movement_trail': [pos.tolist() for pos in self.machine_area_window.movement_trail],
                'window_status': self.machine_area_window.get_enhanced_status()
            }

            # Save to file
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)

            self.log(f"Machine area data exported to: {filename}")

        except Exception as e:
            self.log(f"Error exporting machine area data: {e}", "error")

    def import_machine_area_data(self, filename: str):
        """Import machine area visualization data"""
        if not hasattr(self, 'machine_area_window') or not self.machine_area_window:
            self.log("Machine area window not available", "error")
            return

        try:
            import json

            with open(filename, 'r') as f:
                import_data = json.load(f)

            # Restore data
            if 'machine_bounds' in import_data:
                bounds = import_data['machine_bounds']
                self.machine_area_window.set_machine_bounds(
                    bounds['x_max'], bounds['y_max'], bounds['x_min'], bounds['y_min']
                )

            if 'movement_trail' in import_data:
                trail_data = [np.array(pos) for pos in import_data['movement_trail']]
                self.machine_area_window.import_trail_data(trail_data)

            self.log(f"Machine area data imported from: {filename}")

        except Exception as e:
            self.log(f"Error importing machine area data: {e}", "error")

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
                },
                'machine_area': {
                    'available': hasattr(self, 'machine_area_window') and self.machine_area_window is not None,
                    'visible': False,
                    'bounds': None
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
                status['camera']['feed_active'] = hasattr(self.camera_display,
                                                          '_feed_running') and self.camera_display._feed_running

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

            # Get machine area status
            if hasattr(self, 'machine_area_window') and self.machine_area_window:
                try:
                    machine_area_status = self.machine_area_window.get_enhanced_status()
                    status['machine_area']['visible'] = machine_area_status['visible']
                    status['machine_area']['bounds'] = machine_area_status['machine_bounds']
                    status['machine_area']['trail_length'] = machine_area_status.get('movement_trail_length', 0)
                    status['machine_area']['routes_count'] = machine_area_status.get('actual_routes_count', 0)
                except:
                    pass

            return status

        except Exception as e:
            self.log(f"Error getting application status: {e}", "error")
            return {'error': str(e)}

    def get_comprehensive_status(self):
        """Get comprehensive application status including machine area"""
        base_status = self.get_application_status()

        # Add machine area detailed status
        if hasattr(self, 'machine_area_window') and self.machine_area_window:
            try:
                enhanced_status = self.machine_area_window.get_enhanced_status()
                base_status['machine_area_detailed'] = enhanced_status
            except Exception as e:
                self.log(f"Error getting enhanced machine area status: {e}", "error")

        return base_status

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

            # Refresh machine area window
            if hasattr(self, 'machine_area_window') and self.machine_area_window:
                self.machine_area_window.update_all_data()
                self.machine_area_window.schedule_update()

            self.log("All panels refreshed", "info")

        except Exception as e:
            self.log(f"Error refreshing panels: {e}", "error")

    def configure_grbl_logging(self, verbose: bool = False):
        """Configure GRBL logging levels"""
        if verbose:
            # Enable verbose logging for troubleshooting
            self.grbl_controller.enable_verbose_logging()
            self.log("GRBL verbose logging enabled", "info")
        else:
            # Use quiet logging (default)
            self.grbl_controller.enable_quiet_logging()
            self.log("GRBL quiet logging enabled", "info")

    def get_grbl_debug_settings(self):
        """Get current GRBL debug settings"""
        if self.grbl_controller:
            return self.grbl_controller.get_debug_settings()
        return {}

    def on_closing(self):
        """Handle application closing"""
        self.log("Application closing", "info")

        # Emit shutdown event
        self.emit(ApplicationEvents.SHUTDOWN)

        # Stop camera feed
        self.stop_camera_feed()

        # Clean up machine area window
        if hasattr(self, 'machine_area_window') and self.machine_area_window:
            self.machine_area_window.cleanup()
            self.log("Machine area window cleaned up")

        # Clean up command panel
        if hasattr(self, 'command_panel') and self.command_panel:
            self.command_panel.cleanup_subscriptions()
            self.log("Command panel cleaned up")

        if hasattr(self, 'machine_area_panel') and self.machine_area_panel:
            self.machine_area_panel.cleanup_subscriptions()
            self.log("Machine area panel cleaned up")

            # Clean up machine area window
        if hasattr(self, 'machine_area_control_window') and self.machine_area_window:
            self.machine_area_control_window.cleanup()
            self.log("Machine area window cleaned up")

        # Clean up event subscriptions
        self.cleanup_subscriptions()

        # Disconnect from devices
        self.camera_manager.disconnect()
        self.grbl_controller.disconnect()

        self.root.destroy()
