"""
Enhanced Machine Area Visualization Window with Camera Frame Display
Shows camera frame bounds based on resolution and calibration
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
from typing import Optional, Tuple, List, Callable
import threading
import time

from services.camera_manager import CameraEvents
from services.event_broker import event_aware, event_handler

from services.grbl_controller import GRBLEvents
from services.registration_manager import RegistrationEvents


@event_aware()
class MachineAreaWindow:
    """Floating window displaying machine area, routes, camera position and frame bounds"""

    def __init__(self, parent_window, grbl_controller, registration_manager, routes_service, camera_manager=None, logger: Optional[Callable] = None):
        self.parent_window = parent_window
        self.grbl_controller = grbl_controller
        self.registration_manager = registration_manager
        self.routes_service = routes_service
        self.camera_manager = camera_manager  # Add camera manager
        self.logger = logger

        # Window state
        self.window = None
        self.canvas = None
        self.status_text = None
        self.is_visible = False
        self.auto_update = True
        self.update_thread = None
        self.update_running = False

        # Machine configuration (default values, should be configurable)
        self.machine_bounds = {
            'x_min': 0.0, 'x_max': 200.0,  # 200mm X travel
            'y_min': 0.0, 'y_max': 200.0,  # 200mm Y travel
            'z_min': 0.0, 'z_max': 50.0    # 50mm Z travel (for reference)
        }

        # Display configuration
        self.canvas_width = 400
        self.canvas_height = 400
        self.margin = 30
        self.scale_factor = 1.0  # pixels per mm (calculated dynamically)

        # Current positions and data
        self.current_machine_position = np.array([0.0, 0.0, 0.0])
        self.current_camera_position = None
        self.camera_view_bounds = None  # Camera field of view bounds
        self.camera_frame_bounds = None  # Camera frame bounds based on resolution
        self.routes_bounds = None
        self.calibration_points = []

        # Camera frame calculation parameters
        self.camera_height_mm = 100.0  # Height of camera above work surface (mm)
        self.pixels_per_mm = 5.0  # Camera resolution factor (pixels per mm) - adjustable
        self.camera_resolution = (640, 480)  # Default resolution

        # Display settings
        self.show_machine_bounds = True
        self.show_routes = True
        self.show_route_paths = True   # New: show actual route paths
        self.show_camera_position = True
        self.show_camera_bounds = True  # Legacy camera FOV
        self.show_camera_frame = True   # New: actual camera frame based on resolution
        self.show_calibration_points = True
        self.show_grid = True
        self.show_coordinates = True

        # Route visualization
        self.actual_routes = []  # Actual route paths from overlay
        self.route_colors = ['#f5a623', '#7ed321', '#d0021b', '#9013fe', '#50e3c2']

        # Colors (RGB values for tkinter)
        self.colors = {
            'background': '#2b2b2b',
            'machine_bounds': '#4a90e2',
            'routes': '#f5a623',
            'machine_position': '#d0021b',
            'camera_position': '#7ed321',
            'camera_bounds': '#50e3c2',      # Legacy FOV
            'camera_frame': '#ff6b35',       # New: actual camera frame
            'calibration_points': '#9013fe',
            'grid': '#404040',
            'text': '#ffffff'
        }

        # Update rate (slower to reduce GRBL communication load)
        self.update_rate_ms = 500  # Update every 500ms instead of 100ms

        self.log("Machine Area Visualization with Camera Frame initialized")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    # Event handlers for automatic updates
    @event_handler(GRBLEvents.POSITION_CHANGED)
    def _on_position_changed(self, position: List[float]):
        """Handle machine position changes"""
        try:
            self.current_machine_position = np.array(position[:3])  # Take X, Y, Z
            if self.is_visible and self.auto_update:
                self.schedule_update()
        except Exception as e:
            # Silently handle position update errors to avoid spam
            pass

    @event_handler(CameraEvents.CONNECTED)
    def _on_camera_connected(self, success: bool):
        """Handle camera connection events"""
        if success:
            self.update_camera_info()
            if self.is_visible and self.auto_update:
                self.schedule_update()

    @event_handler(CameraEvents.CALIBRATION_LOADED)
    def _on_camera_calibration_loaded(self, file_path: str):
        """Handle camera calibration loaded"""
        self.update_camera_info()
        if self.is_visible and self.auto_update:
            self.schedule_update()

    @event_handler(RegistrationEvents.POINT_ADDED)
    def _on_calibration_point_added(self, point_data: dict):
        """Handle new calibration point"""
        self.update_calibration_points()
        if self.is_visible and self.auto_update:
            self.schedule_update()

    @event_handler(RegistrationEvents.COMPUTED)
    def _on_registration_computed(self, computation_data: dict):
        """Handle registration computation"""
        self.update_calibration_points()
        if self.is_visible and self.auto_update:
            self.schedule_update()

    @event_handler(RegistrationEvents.CLEARED)
    def _on_calibration_cleared(self, data: dict):
        """Handle calibration points cleared"""
        self.update_calibration_points()
        if self.is_visible and self.auto_update:
            self.schedule_update()

    def show_window(self):
        """Show the machine area visualization window"""
        if self.window is not None:
            self.window.lift()
            self.window.focus_force()
            return

        self.create_window()
        self.is_visible = True
        self.start_update_thread()

        # Reset rate limiting timers when window is shown
        if hasattr(self, '_last_grbl_update'):
            delattr(self, '_last_grbl_update')
        if hasattr(self, '_last_grbl_error_time'):
            delattr(self, '_last_grbl_error_time')

        self.log("Machine area visualization window opened")

    def hide_window(self):
        """Hide the machine area visualization window"""
        if self.window is not None:
            self.stop_update_thread()
            self.window.destroy()
            self.window = None
            self.canvas = None
            self.is_visible = False
            self.log("Machine area visualization window closed")

    def create_window(self):
        """Create the visualization window"""
        try:
            self.window = tk.Toplevel(self.parent_window)
            self.window.title("Machine Area Visualization")
            self.window.geometry(f"{self.canvas_width + 250}x{self.canvas_height + 120}")  # Wider for new controls
            self.window.resizable(True, True)

            # Make window stay on top but not always
            self.window.attributes('-topmost', False)

            # Handle window closing
            self.window.protocol("WM_DELETE_WINDOW", self.hide_window)

            self.setup_window_layout()
            self.calculate_scale_factor()
            self.update_display()

        except Exception as e:
            self.log(f"Error creating machine area window: {e}", "error")
            self.window = None
            self.canvas = None
            self.status_text = None

    def setup_window_layout(self):
        """Setup the window layout with canvas and controls"""
        # Main frame
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Canvas frame (left side)
        canvas_frame = ttk.LabelFrame(main_frame, text="Machine Area View")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Create canvas
        self.canvas = tk.Canvas(
            canvas_frame,
            width=self.canvas_width,
            height=self.canvas_height,
            bg=self.colors['background']
        )
        self.canvas.pack(padx=5, pady=5)

        # Controls frame (right side)
        controls_frame = ttk.LabelFrame(main_frame, text="Display Options")
        controls_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        self.setup_controls(controls_frame)

        # Status frame (bottom)
        status_frame = ttk.Frame(self.window)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0, 5))

        self.setup_status_display(status_frame)

    def setup_controls(self, parent):
        """Setup control widgets including camera frame controls"""
        # Create scrollable frame for controls
        canvas_control = tk.Canvas(parent, width=230)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas_control.yview)
        scrollable_frame = ttk.Frame(canvas_control)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas_control.configure(scrollregion=canvas_control.bbox("all"))
        )

        canvas_control.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas_control.configure(yscrollcommand=scrollbar.set)

        canvas_control.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Display toggles
        ttk.Label(scrollable_frame, text="Show Elements:").pack(anchor=tk.W, pady=(5, 0))

        self.show_machine_bounds_var = tk.BooleanVar(value=self.show_machine_bounds)
        ttk.Checkbutton(scrollable_frame, text="Machine Bounds", variable=self.show_machine_bounds_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_routes_var = tk.BooleanVar(value=self.show_routes)
        ttk.Checkbutton(scrollable_frame, text="Routes Bounds", variable=self.show_routes_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_route_paths_var = tk.BooleanVar(value=self.show_route_paths)
        ttk.Checkbutton(scrollable_frame, text="Route Paths", variable=self.show_route_paths_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_camera_position_var = tk.BooleanVar(value=self.show_camera_position)
        ttk.Checkbutton(scrollable_frame, text="Camera Position", variable=self.show_camera_position_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_camera_bounds_var = tk.BooleanVar(value=self.show_camera_bounds)
        ttk.Checkbutton(scrollable_frame, text="Camera FOV (Legacy)", variable=self.show_camera_bounds_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_camera_frame_var = tk.BooleanVar(value=self.show_camera_frame)
        ttk.Checkbutton(scrollable_frame, text="Camera Frame", variable=self.show_camera_frame_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_calibration_points_var = tk.BooleanVar(value=self.show_calibration_points)
        ttk.Checkbutton(scrollable_frame, text="Calibration Points", variable=self.show_calibration_points_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_grid_var = tk.BooleanVar(value=self.show_grid)
        ttk.Checkbutton(scrollable_frame, text="Grid", variable=self.show_grid_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        # Separator
        ttk.Separator(scrollable_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Camera Frame Configuration
        ttk.Label(scrollable_frame, text="Camera Frame Config:").pack(anchor=tk.W, pady=(5, 0))

        camera_frame = ttk.Frame(scrollable_frame)
        camera_frame.pack(fill=tk.X, pady=2)

        ttk.Label(camera_frame, text="Height (mm):").grid(row=0, column=0, sticky=tk.W)
        self.camera_height_var = tk.StringVar(value=str(self.camera_height_mm))
        height_entry = ttk.Entry(camera_frame, textvariable=self.camera_height_var, width=8)
        height_entry.grid(row=0, column=1, padx=(5, 0))
        height_entry.bind('<Return>', self.on_camera_config_changed)

        ttk.Label(camera_frame, text="Pixels/mm:").grid(row=1, column=0, sticky=tk.W)
        self.pixels_per_mm_var = tk.StringVar(value=str(self.pixels_per_mm))
        pixels_entry = ttk.Entry(camera_frame, textvariable=self.pixels_per_mm_var, width=8)
        pixels_entry.grid(row=1, column=1, padx=(5, 0))
        pixels_entry.bind('<Return>', self.on_camera_config_changed)

        # Camera resolution display
        ttk.Label(camera_frame, text="Resolution:").grid(row=2, column=0, sticky=tk.W)
        self.resolution_label = ttk.Label(camera_frame, text="640x480")
        self.resolution_label.grid(row=2, column=1, padx=(5, 0), sticky=tk.W)

        ttk.Button(camera_frame, text="Update", command=self.on_camera_config_changed).grid(row=3, column=0, columnspan=2, pady=5)

        # Separator
        ttk.Separator(scrollable_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Machine bounds configuration
        ttk.Label(scrollable_frame, text="Machine Bounds (mm):").pack(anchor=tk.W, pady=(5, 0))

        bounds_frame = ttk.Frame(scrollable_frame)
        bounds_frame.pack(fill=tk.X, pady=2)

        ttk.Label(bounds_frame, text="X Max:").grid(row=0, column=0, sticky=tk.W)
        self.x_max_var = tk.StringVar(value=str(self.machine_bounds['x_max']))
        x_max_entry = ttk.Entry(bounds_frame, textvariable=self.x_max_var, width=8)
        x_max_entry.grid(row=0, column=1, padx=(5, 0))
        x_max_entry.bind('<Return>', self.on_bounds_changed)

        ttk.Label(bounds_frame, text="Y Max:").grid(row=1, column=0, sticky=tk.W)
        self.y_max_var = tk.StringVar(value=str(self.machine_bounds['y_max']))
        y_max_entry = ttk.Entry(bounds_frame, textvariable=self.y_max_var, width=8)
        y_max_entry.grid(row=1, column=1, padx=(5, 0))
        y_max_entry.bind('<Return>', self.on_bounds_changed)

        ttk.Button(bounds_frame, text="Update", command=self.on_bounds_changed).grid(row=2, column=0, columnspan=2, pady=5)

        # Update controls
        ttk.Separator(scrollable_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        self.auto_update_var = tk.BooleanVar(value=self.auto_update)
        ttk.Checkbutton(scrollable_frame, text="Auto Update", variable=self.auto_update_var,
                       command=self.on_auto_update_changed).pack(anchor=tk.W)

        ttk.Button(scrollable_frame, text="Refresh Now", command=self.manual_update).pack(fill=tk.X, pady=2)
        ttk.Button(scrollable_frame, text="Center View", command=self.center_view).pack(fill=tk.X, pady=2)
        ttk.Button(scrollable_frame, text="Update Camera Info", command=self.update_camera_info).pack(fill=tk.X, pady=2)
        ttk.Button(scrollable_frame, text="Debug: Show Data", command=self.debug_show_data).pack(fill=tk.X, pady=2)

    def debug_show_data(self):
        """Debug method to show current data state"""
        debug_info = []
        debug_info.append(f"Routes service: {self.routes_service is not None}")
        debug_info.append(f"Camera manager: {self.camera_manager is not None}")
        debug_info.append(f"Routes bounds: {self.routes_bounds}")
        debug_info.append(f"Actual routes count: {len(self.actual_routes) if self.actual_routes else 0}")
        debug_info.append(f"Camera position: {self.current_camera_position}")
        debug_info.append(f"Camera frame bounds: {self.camera_frame_bounds}")
        debug_info.append(f"Show routes: {self.show_routes}")
        debug_info.append(f"Show route paths: {self.show_route_paths}")
        debug_info.append(f"Show camera frame: {self.show_camera_frame}")

        # Enhanced debugging for routes service
        if self.routes_service:
            debug_info.append(f"Routes service type: {type(self.routes_service).__name__}")

            try:
                service_status = self.routes_service.get_service_status()
                debug_info.append(f"Service status: {service_status}")
            except Exception as e:
                debug_info.append(f"Error getting service status: {e}")

        if self.actual_routes:
            debug_info.append(f"First route sample: {self.actual_routes[0][:3] if len(self.actual_routes[0]) > 3 else self.actual_routes[0]}")

        debug_text = "\n".join(debug_info)
        self.log(f"DEBUG DATA STATE:\n{debug_text}", "info")

        # Also show in a popup
        import tkinter.messagebox as msgbox
        msgbox.showinfo("Debug Data State", debug_text)

    def setup_status_display(self, parent):
        """Setup status display"""
        try:
            self.status_text = tk.Text(parent, height=5, wrap=tk.WORD, font=('Consolas', 8))
            self.status_text.pack(fill=tk.X)
        except Exception as e:
            self.log(f"Error setting up status display: {e}", "error")
            # Create a fallback status display
            self.status_text = None

    def on_display_option_changed(self):
        """Handle display option changes"""
        self.show_machine_bounds = self.show_machine_bounds_var.get()
        self.show_routes = self.show_routes_var.get()
        self.show_route_paths = self.show_route_paths_var.get()
        self.show_camera_position = self.show_camera_position_var.get()
        self.show_camera_bounds = self.show_camera_bounds_var.get()
        self.show_camera_frame = self.show_camera_frame_var.get()
        self.show_calibration_points = self.show_calibration_points_var.get()
        self.show_grid = self.show_grid_var.get()
        self.schedule_update()

    def on_camera_config_changed(self, event=None):
        """Handle camera configuration changes"""
        try:
            self.camera_height_mm = float(self.camera_height_var.get())
            self.pixels_per_mm = float(self.pixels_per_mm_var.get())
            self.update_camera_frame_bounds()
            self.schedule_update()
            self.log(f"Camera config updated: Height={self.camera_height_mm}mm, Scale={self.pixels_per_mm}px/mm")
        except ValueError:
            self.log("Invalid camera configuration values", "error")

    def on_bounds_changed(self, event=None):
        """Handle machine bounds changes"""
        try:
            self.machine_bounds['x_max'] = float(self.x_max_var.get())
            self.machine_bounds['y_max'] = float(self.y_max_var.get())
            self.calculate_scale_factor()
            self.schedule_update()
            self.log(f"Machine bounds updated: X={self.machine_bounds['x_max']}, Y={self.machine_bounds['y_max']}")
        except ValueError:
            self.log("Invalid machine bounds values", "error")

    def on_auto_update_changed(self):
        """Handle auto update toggle"""
        self.auto_update = self.auto_update_var.get()
        if self.auto_update:
            self.start_update_thread()
        else:
            self.stop_update_thread()

    def manual_update(self):
        """Manually trigger update"""
        try:
            self.update_all_data()
            self.update_display()
        except Exception as e:
            self.log(f"Error in manual update: {e}", "warning")

    def center_view(self):
        """Center the view on the machine area"""
        self.calculate_scale_factor()
        self.schedule_update()

    def update_camera_info(self):
        """Update camera information from camera manager"""
        if not self.camera_manager:
            self.log("No camera manager available", "warning")
            return

        try:
            camera_info = self.camera_manager.get_camera_info()
            if camera_info.get('connected', False):
                # Update resolution from camera
                width = camera_info.get('width', 640)
                height = camera_info.get('height', 480)
                self.camera_resolution = (width, height)

                # Update resolution display
                if hasattr(self, 'resolution_label'):
                    self.resolution_label.config(text=f"{width}x{height}")

                self.log(f"Camera info updated: {width}x{height}, Connected: {camera_info.get('connected')}")
            else:
                self.log("Camera not connected", "warning")

            # Update camera frame bounds
            self.update_camera_frame_bounds()
            self.schedule_update()

        except Exception as e:
            self.log(f"Error updating camera info: {e}", "error")

    def calculate_scale_factor(self):
        """Calculate scale factor to fit machine bounds in canvas"""
        available_width = self.canvas_width - 2 * self.margin
        available_height = self.canvas_height - 2 * self.margin

        machine_width = self.machine_bounds['x_max'] - self.machine_bounds['x_min']
        machine_height = self.machine_bounds['y_max'] - self.machine_bounds['y_min']

        if machine_width <= 0 or machine_height <= 0:
            self.scale_factor = 1.0
            return

        scale_x = available_width / machine_width
        scale_y = available_height / machine_height

        # Use smaller scale to fit both dimensions
        self.scale_factor = min(scale_x, scale_y)

    def machine_to_canvas(self, x: float, y: float) -> Tuple[int, int]:
        """Convert machine coordinates to canvas coordinates"""
        # Machine coordinate (0,0) is at bottom-left, canvas (0,0) is at top-left
        canvas_x = self.margin + (x - self.machine_bounds['x_min']) * self.scale_factor
        canvas_y = self.canvas_height - self.margin - (y - self.machine_bounds['y_min']) * self.scale_factor

        return int(canvas_x), int(canvas_y)

    def start_update_thread(self):
        """Start the automatic update thread"""
        if self.update_thread is not None and self.update_thread.is_alive():
            return

        self.update_running = True
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def stop_update_thread(self):
        """Stop the automatic update thread"""
        self.update_running = False
        if self.update_thread is not None:
            self.update_thread.join(timeout=1.0)

    def update_loop(self):
        """Main update loop for automatic updates"""
        while self.update_running:
            try:
                if self.auto_update and self.is_visible:
                    self.update_all_data()
                    # Schedule GUI update on main thread
                    if self.window is not None:
                        self.window.after_idle(self.update_display)

                # Slower update rate to reduce GRBL communication load
                time.sleep(max(self.update_rate_ms / 1000.0, 0.2))  # Minimum 200ms between updates
            except Exception as e:
                self.log(f"Error in update loop: {e}", "error")
                time.sleep(1.0)  # Slow down on errors

    def schedule_update(self):
        """Schedule a display update on the main thread"""
        if self.window is not None:
            self.window.after_idle(self.update_display)

    def update_all_data(self):
        """Update all data from controllers and managers"""
        try:
            # Update machine position with error handling and rate limiting
            if self.grbl_controller and self.grbl_controller.is_connected:
                try:
                    # Add a simple rate limiting mechanism
                    current_time = time.time()
                    if not hasattr(self, '_last_grbl_update') or (current_time - self._last_grbl_update) > 0.5:  # Max 2Hz for GRBL updates
                        position = self.grbl_controller.get_position()
                        if position:
                            self.current_machine_position = np.array(position[:3])
                        self._last_grbl_update = current_time
                except Exception as e:
                    # Don't log every timeout error to avoid spam
                    if not hasattr(self, '_last_grbl_error_time') or (current_time - getattr(self, '_last_grbl_error_time', 0)) > 10.0:
                        self.log(f"GRBL communication error in machine area window: {e}", "warning")
                        self._last_grbl_error_time = current_time

            # Debug: Log routes service status
            if self.routes_service:
                self.log(f"Routes service available: {type(self.routes_service).__name__}", "debug")
            else:
                self.log("No routes service available", "debug")

            # Update camera position from routes service OR camera manager
            camera_position_updated = False

            # Try to get camera position from routes service first
            if self.routes_service:
                try:
                    camera_position = self.routes_service.get_camera_position()
                    if camera_position:
                        self.current_camera_position = camera_position
                        camera_position_updated = True
                        self.log(f"Camera position updated from routes service: {self.current_camera_position}", "debug")

                        # Calculate camera field of view bounds (legacy)
                        self.update_camera_bounds()

                        # Calculate camera frame bounds (new)
                        self.update_camera_frame_bounds()
                    else:
                        self.log("No camera position in routes service", "debug")

                except Exception as e:
                    self.log(f"Error getting camera position from routes service: {e}", "debug")

            # If no camera position from routes service, try to get it from camera manager
            if not camera_position_updated and self.camera_manager and self.camera_manager.is_connected:
                try:
                    # If we have a camera but no position from routes service,
                    # we could use the current machine position as camera position
                    # This assumes the camera moves with the machine
                    if hasattr(self, 'current_machine_position'):
                        self.current_camera_position = [
                            self.current_machine_position[0],
                            self.current_machine_position[1]
                        ]
                        camera_position_updated = True
                        self.log(f"Using machine position as camera position: {self.current_camera_position}", "debug")

                        # Calculate camera bounds
                        self.update_camera_bounds()
                        self.update_camera_frame_bounds()

                except Exception as e:
                    self.log(f"Error getting camera position from camera manager: {e}", "debug")

            # If still no camera position, clear camera bounds
            if not camera_position_updated:
                self.current_camera_position = None
                self.camera_view_bounds = None
                self.camera_frame_bounds = None
                self.log("No camera position available - cleared camera bounds", "debug")

            # Update routes bounds and actual routes from routes service
            if self.routes_service:
                try:
                    # Get route bounds
                    self.routes_bounds = self.routes_service.get_route_bounds()
                    self.log(f"Route bounds from service: {self.routes_bounds}", "debug")

                    # Get actual routes
                    self.actual_routes = self.routes_service.get_routes()
                    self.log(f"Routes from service: {len(self.actual_routes)} routes", "debug")

                    if self.actual_routes:
                        for i, route in enumerate(self.actual_routes[:3]):  # Log first 3 routes
                            if route and len(route) > 0:
                                self.log(f"Route {i}: {len(route)} points, first point: {route[0] if route else 'empty'}", "debug")
                            else:
                                self.log(f"Route {i}: empty or invalid", "debug")
                    else:
                        self.log("No routes found in service", "debug")

                except Exception as e:
                    self.log(f"Error getting routes data from service: {e}", "error")
                    self.routes_bounds = None
                    self.actual_routes = []
            else:
                self.routes_bounds = None
                self.actual_routes = []

            # Update calibration points
            self.update_calibration_points()

        except Exception as e:
            self.log(f"Error updating data: {e}", "error")

    def update_camera_bounds(self):
        """Update camera field of view bounds (legacy method)"""
        if not self.current_camera_position:
            self.camera_view_bounds = None
            return

        try:
            # Estimate camera field of view based on typical camera parameters
            # This is an approximation - in a real system you'd get this from camera calibration
            camera_fov_width = 50.0  # mm (adjust based on your camera/lens)
            camera_fov_height = 40.0  # mm (adjust based on your camera/lens)

            cam_x, cam_y = self.current_camera_position

            self.camera_view_bounds = {
                'x_min': cam_x - camera_fov_width / 2,
                'x_max': cam_x + camera_fov_width / 2,
                'y_min': cam_y - camera_fov_height / 2,
                'y_max': cam_y + camera_fov_height / 2
            }

        except Exception as e:
            self.log(f"Error updating camera bounds: {e}", "error")
            self.camera_view_bounds = None

    def update_camera_frame_bounds(self):
        """Update camera frame bounds based on resolution and scale"""
        if not self.current_camera_position:
            self.camera_frame_bounds = None
            return

        try:
            # Calculate frame size in mm based on resolution and pixels_per_mm
            frame_width_mm = self.camera_resolution[0] / self.pixels_per_mm
            frame_height_mm = self.camera_resolution[1] / self.pixels_per_mm

            cam_x, cam_y = self.current_camera_position

            # Camera frame centered on camera position
            self.camera_frame_bounds = {
                'x_min': cam_x - frame_width_mm / 2,
                'x_max': cam_x + frame_width_mm / 2,
                'y_min': cam_y - frame_height_mm / 2,
                'y_max': cam_y + frame_height_mm / 2,
                'width_mm': frame_width_mm,
                'height_mm': frame_height_mm
            }

            self.log(f"Camera frame: {frame_width_mm:.1f}x{frame_height_mm:.1f}mm at ({cam_x:.1f},{cam_y:.1f})", "debug")

        except Exception as e:
            self.log(f"Error updating camera frame bounds: {e}", "error")
            self.camera_frame_bounds = None

    def update_calibration_points(self):
        """Update calibration points from registration manager"""
        self.calibration_points = []

        try:
            if self.registration_manager:
                machine_positions = self.registration_manager.get_machine_positions()
                self.calibration_points = [(pos[0], pos[1]) for pos in machine_positions]
        except Exception as e:
            # Silently handle calibration point errors
            pass

    def update_display(self):
        """Update the canvas display"""
        if not self.canvas:
            return

        try:
            # Clear canvas
            self.canvas.delete("all")

            # Draw grid
            if self.show_grid:
                self.draw_grid()

            # Draw machine bounds
            if self.show_machine_bounds:
                self.draw_machine_bounds()

            # Draw actual route paths
            if self.show_route_paths and self.actual_routes:
                self.draw_actual_routes()

            # Draw routes bounds (if not showing actual paths or as fallback)
            if self.show_routes and self.routes_bounds and not (self.show_route_paths and self.actual_routes):
                self.draw_routes()

            # Draw camera field of view (legacy)
            if self.show_camera_bounds and self.camera_view_bounds:
                self.draw_camera_bounds()

            # Draw camera frame (new)
            if self.show_camera_frame and self.camera_frame_bounds:
                self.draw_camera_frame()

            # Draw calibration points
            if self.show_calibration_points:
                self.draw_calibration_points()

            # Draw current machine position
            self.draw_machine_position()

            # Draw current camera position
            if self.show_camera_position and self.current_camera_position:
                self.draw_camera_position()

            # Update status
            self.update_status_display()

        except Exception as e:
            self.log(f"Error updating display: {e}", "error")

    def draw_grid(self):
        """Draw coordinate grid"""
        grid_spacing = 20  # mm

        # Vertical lines
        x = self.machine_bounds['x_min']
        while x <= self.machine_bounds['x_max']:
            x1, y1 = self.machine_to_canvas(x, self.machine_bounds['y_min'])
            x2, y2 = self.machine_to_canvas(x, self.machine_bounds['y_max'])
            self.canvas.create_line(x1, y1, x2, y2, fill=self.colors['grid'], width=1)
            x += grid_spacing

        # Horizontal lines
        y = self.machine_bounds['y_min']
        while y <= self.machine_bounds['y_max']:
            x1, y1 = self.machine_to_canvas(self.machine_bounds['x_min'], y)
            x2, y2 = self.machine_to_canvas(self.machine_bounds['x_max'], y)
            self.canvas.create_line(x1, y1, x2, y2, fill=self.colors['grid'], width=1)
            y += grid_spacing

    def draw_machine_bounds(self):
        """Draw machine bounds rectangle"""
        x1, y1 = self.machine_to_canvas(self.machine_bounds['x_min'], self.machine_bounds['y_min'])
        x2, y2 = self.machine_to_canvas(self.machine_bounds['x_max'], self.machine_bounds['y_max'])

        self.canvas.create_rectangle(x1, y2, x2, y1, outline=self.colors['machine_bounds'], width=2, fill="")

        # Add coordinate labels
        self.canvas.create_text(x1 + 5, y1 - 5, text="(0,0)", fill=self.colors['text'], anchor=tk.SW)
        self.canvas.create_text(x2 - 5, y2 + 5, text=f"({self.machine_bounds['x_max']},{self.machine_bounds['y_max']})",
                               fill=self.colors['text'], anchor=tk.NE)

    def draw_routes(self):
        """Draw loaded routes"""
        if not self.routes_bounds:
            return

        try:
            # routes_bounds should be [x_min, y_min, x_max, y_max]
            if len(self.routes_bounds) >= 4:
                x1, y1 = self.machine_to_canvas(self.routes_bounds[0], self.routes_bounds[1])
                x2, y2 = self.machine_to_canvas(self.routes_bounds[2], self.routes_bounds[3])

                # Draw routes bounding box
                self.canvas.create_rectangle(x1, y2, x2, y1, outline=self.colors['routes'], width=2, fill="", dash=(5, 5))

                # Add routes label
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                self.canvas.create_text(center_x, center_y, text="Routes", fill=self.colors['routes'], anchor=tk.CENTER)
            else:
                self.log(f"Invalid routes_bounds format: {self.routes_bounds}", "warning")
        except Exception as e:
            self.log(f"Error drawing routes: {e}", "error")

    def draw_actual_routes(self):
        """Draw actual route paths"""
        if not self.actual_routes:
            self.log("No actual routes to draw", "debug")
            return

        self.log(f"Drawing {len(self.actual_routes)} routes", "debug")

        try:
            for route_idx, route in enumerate(self.actual_routes):
                if len(route) < 2:
                    self.log(f"Route {route_idx} has less than 2 points, skipping", "debug")
                    continue

                # Use different colors for different routes
                color = self.route_colors[route_idx % len(self.route_colors)]

                # Convert route points to canvas coordinates
                canvas_points = []
                for point in route:
                    # Handle different point formats
                    if len(point) >= 2:
                        x, y = point[0], point[1]
                        canvas_x, canvas_y = self.machine_to_canvas(x, y)
                        canvas_points.extend([canvas_x, canvas_y])

                if len(canvas_points) >= 4:  # At least 2 points
                    self.log(f"Drawing route {route_idx} with {len(canvas_points)//2} points in color {color}", "debug")

                    # Draw route as connected lines
                    self.canvas.create_line(*canvas_points, fill=color, width=2, smooth=True)

                    # Draw start point
                    if canvas_points:
                        start_x, start_y = canvas_points[0], canvas_points[1]
                        self.canvas.create_oval(start_x-3, start_y-3, start_x+3, start_y+3,
                                              fill='green', outline='white', width=1)

                    # Draw end point
                    if len(canvas_points) >= 4:
                        end_x, end_y = canvas_points[-2], canvas_points[-1]
                        self.canvas.create_rectangle(end_x-3, end_y-3, end_x+3, end_y+3,
                                                   fill='red', outline='white', width=1)

                    # Add route label
                    if len(canvas_points) >= 4:
                        mid_idx = len(canvas_points) // 4 * 2  # Roughly middle point
                        mid_x, mid_y = canvas_points[mid_idx], canvas_points[mid_idx + 1]
                        self.canvas.create_text(mid_x + 5, mid_y - 5, text=f"R{route_idx + 1}",
                                              fill=color, anchor=tk.W, font=('Arial', 8, 'bold'))
                else:
                    self.log(f"Route {route_idx} has insufficient canvas points: {len(canvas_points)}", "debug")

            self.log("Routes drawn successfully", "debug")

        except Exception as e:
            self.log(f"Error drawing actual routes: {e}", "error")

    def draw_camera_bounds(self):
        """Draw camera field of view (legacy)"""
        if not self.camera_view_bounds:
            return

        x1, y1 = self.machine_to_canvas(self.camera_view_bounds['x_min'], self.camera_view_bounds['y_min'])
        x2, y2 = self.machine_to_canvas(self.camera_view_bounds['x_max'], self.camera_view_bounds['y_max'])

        # Draw camera FOV rectangle
        self.canvas.create_rectangle(x1, y2, x2, y1, outline=self.colors['camera_bounds'], width=2,
                                   fill=self.colors['camera_bounds'], stipple="gray25")

    def draw_camera_frame(self):
        """Draw camera frame bounds based on resolution"""
        if not self.camera_frame_bounds:
            self.log("No camera frame bounds available", "debug")
            return

        try:
            self.log(f"Drawing camera frame: {self.camera_frame_bounds}", "debug")

            x1, y1 = self.machine_to_canvas(self.camera_frame_bounds['x_min'], self.camera_frame_bounds['y_min'])
            x2, y2 = self.machine_to_canvas(self.camera_frame_bounds['x_max'], self.camera_frame_bounds['y_max'])

            self.log(f"Canvas coordinates: ({x1},{y1}) to ({x2},{y2})", "debug")

            # Draw camera frame rectangle with distinct style
            self.canvas.create_rectangle(x1, y2, x2, y1, outline=self.colors['camera_frame'], width=3, fill="")

            # Draw corner markers for better visibility
            corner_size = 8
            # Top-left corner
            self.canvas.create_line(x1, y2, x1 + corner_size, y2, fill=self.colors['camera_frame'], width=3)
            self.canvas.create_line(x1, y2, x1, y2 + corner_size, fill=self.colors['camera_frame'], width=3)

            # Top-right corner
            self.canvas.create_line(x2, y2, x2 - corner_size, y2, fill=self.colors['camera_frame'], width=3)
            self.canvas.create_line(x2, y2, x2, y2 + corner_size, fill=self.colors['camera_frame'], width=3)

            # Bottom-left corner
            self.canvas.create_line(x1, y1, x1 + corner_size, y1, fill=self.colors['camera_frame'], width=3)
            self.canvas.create_line(x1, y1, x1, y1 - corner_size, fill=self.colors['camera_frame'], width=3)

            # Bottom-right corner
            self.canvas.create_line(x2, y1, x2 - corner_size, y1, fill=self.colors['camera_frame'], width=3)
            self.canvas.create_line(x2, y1, x2, y1 - corner_size, fill=self.colors['camera_frame'], width=3)

            # Add frame info label
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2

            frame_info = f"Frame: {self.camera_resolution[0]}x{self.camera_resolution[1]}\n"
            frame_info += f"{self.camera_frame_bounds['width_mm']:.1f}x{self.camera_frame_bounds['height_mm']:.1f}mm"

            # Create background for text
            self.canvas.create_rectangle(center_x - 40, center_y - 15, center_x + 40, center_y + 15,
                                       fill=self.colors['background'], outline=self.colors['camera_frame'], width=1)

            self.canvas.create_text(center_x, center_y, text=frame_info,
                                  fill=self.colors['camera_frame'], anchor=tk.CENTER, font=('Arial', 8))

            # Draw crosshairs at center
            crosshair_size = 5
            self.canvas.create_line(center_x - crosshair_size, center_y, center_x + crosshair_size, center_y,
                                   fill=self.colors['camera_frame'], width=1)
            self.canvas.create_line(center_x, center_y - crosshair_size, center_x, center_y + crosshair_size,
                                   fill=self.colors['camera_frame'], width=1)

            self.log("Camera frame drawn successfully", "debug")

        except Exception as e:
            self.log(f"Error drawing camera frame: {e}", "error")

    def draw_calibration_points(self):
        """Draw calibration points"""
        for i, (x, y) in enumerate(self.calibration_points):
            canvas_x, canvas_y = self.machine_to_canvas(x, y)

            # Draw point
            self.canvas.create_oval(canvas_x - 3, canvas_y - 3, canvas_x + 3, canvas_y + 3,
                                  fill=self.colors['calibration_points'], outline="white", width=1)

            # Add point number
            self.canvas.create_text(canvas_x + 8, canvas_y - 8, text=str(i + 1),
                                  fill=self.colors['calibration_points'], anchor=tk.W)

    def draw_machine_position(self):
        """Draw current machine position"""
        x, y = self.current_machine_position[0], self.current_machine_position[1]
        canvas_x, canvas_y = self.machine_to_canvas(x, y)

        # Draw machine position as cross
        size = 6
        self.canvas.create_line(canvas_x - size, canvas_y, canvas_x + size, canvas_y,
                               fill=self.colors['machine_position'], width=3)
        self.canvas.create_line(canvas_x, canvas_y - size, canvas_x, canvas_y + size,
                               fill=self.colors['machine_position'], width=3)

        # Add position label
        self.canvas.create_text(canvas_x + 10, canvas_y - 10,
                               text=f"M({x:.1f},{y:.1f})",
                               fill=self.colors['machine_position'], anchor=tk.W)

    def draw_camera_position(self):
        """Draw current camera position"""
        x, y = self.current_camera_position
        canvas_x, canvas_y = self.machine_to_canvas(x, y)

        # Draw camera position as circle
        radius = 5
        self.canvas.create_oval(canvas_x - radius, canvas_y - radius,
                               canvas_x + radius, canvas_y + radius,
                               fill=self.colors['camera_position'], outline="white", width=2)

        # Add position label
        self.canvas.create_text(canvas_x + 10, canvas_y + 10,
                               text=f"C({x:.1f},{y:.1f})",
                               fill=self.colors['camera_position'], anchor=tk.W)

    def update_status_display(self):
        """Update status text display"""
        if not self.status_text:
            return

        try:
            status_lines = []

            # Machine status
            pos = self.current_machine_position
            status_lines.append(f"Machine: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})")

            # Camera status
            if self.current_camera_position:
                cam_x, cam_y = self.current_camera_position
                status_lines.append(f"Camera: ({cam_x:.1f}, {cam_y:.1f})")
            else:
                # More detailed camera status
                if self.camera_manager:
                    if self.camera_manager.is_connected:
                        status_lines.append("Camera: Connected, no position from routes")
                    else:
                        status_lines.append("Camera: Manager available, not connected")
                else:
                    status_lines.append("Camera: No camera manager available")

            # Camera frame status
            if self.camera_frame_bounds:
                frame_w = self.camera_frame_bounds['width_mm']
                frame_h = self.camera_frame_bounds['height_mm']
                status_lines.append(f"Frame: {self.camera_resolution[0]}x{self.camera_resolution[1]} ({frame_w:.1f}x{frame_h:.1f}mm)")
            else:
                status_lines.append("Frame: Not calculated")

            # Camera configuration
            status_lines.append(f"Camera Config: {self.camera_height_mm}mm height, {self.pixels_per_mm}px/mm")

            # Routes status
            if self.actual_routes:
                total_points = sum(len(route) for route in self.actual_routes)
                status_lines.append(f"Routes: {len(self.actual_routes)} paths, {total_points} points")
            elif self.routes_bounds:
                try:
                    if len(self.routes_bounds) >= 4:
                        width = self.routes_bounds[2] - self.routes_bounds[0]
                        height = self.routes_bounds[3] - self.routes_bounds[1]
                        status_lines.append(f"Routes: {width:.1f}x{height:.1f}mm bounds")
                    else:
                        status_lines.append(f"Routes: Invalid bounds format ({len(self.routes_bounds)} values)")
                except Exception as e:
                    status_lines.append(f"Routes: Error processing bounds - {e}")
            else:
                status_lines.append("Routes: None loaded")

            # Calibration status
            status_lines.append(f"Calibration: {len(self.calibration_points)} points")

            # Scale info
            status_lines.append(f"Display Scale: {self.scale_factor:.2f} px/mm")

            # Update text widget
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, "\n".join(status_lines))

        except Exception as e:
            self.log(f"Error updating status display: {e}", "error")

    def set_machine_bounds(self, x_max: float, y_max: float, x_min: float = 0.0, y_min: float = 0.0):
        """Set machine bounds programmatically"""
        self.machine_bounds = {
            'x_min': x_min, 'x_max': x_max,
            'y_min': y_min, 'y_max': y_max
        }

        # Update GUI controls
        if hasattr(self, 'x_max_var'):
            self.x_max_var.set(str(x_max))
        if hasattr(self, 'y_max_var'):
            self.y_max_var.set(str(y_max))

        self.calculate_scale_factor()
        self.schedule_update()

    def set_camera_frame_config(self, height_mm: float, pixels_per_mm: float):
        """Set camera frame configuration programmatically"""
        self.camera_height_mm = height_mm
        self.pixels_per_mm = pixels_per_mm

        # Update GUI controls
        if hasattr(self, 'camera_height_var'):
            self.camera_height_var.set(str(height_mm))
        if hasattr(self, 'pixels_per_mm_var'):
            self.pixels_per_mm_var.set(str(pixels_per_mm))

        self.update_camera_frame_bounds()
        self.schedule_update()

    def get_camera_frame_info(self) -> dict:
        """Get camera frame information"""
        info = {
            'resolution': self.camera_resolution,
            'height_mm': self.camera_height_mm,
            'pixels_per_mm': self.pixels_per_mm,
            'frame_bounds': self.camera_frame_bounds,
            'camera_position': self.current_camera_position
        }

        if self.camera_frame_bounds:
            info.update({
                'frame_width_mm': self.camera_frame_bounds['width_mm'],
                'frame_height_mm': self.camera_frame_bounds['height_mm']
            })

        return info

    def get_window_status(self) -> dict:
        """Get current window status"""
        base_status = {
            'visible': self.is_visible,
            'auto_update': self.auto_update,
            'machine_bounds': self.machine_bounds.copy(),
            'current_machine_position': self.current_machine_position.tolist(),
            'current_camera_position': self.current_camera_position,
            'routes_bounds': self.routes_bounds,
            'calibration_points_count': len(self.calibration_points),
            'scale_factor': self.scale_factor
        }

        # Add camera frame specific info
        camera_frame_status = {
            'camera_resolution': self.camera_resolution,
            'camera_height_mm': self.camera_height_mm,
            'pixels_per_mm': self.pixels_per_mm,
            'camera_frame_bounds': self.camera_frame_bounds,
            'show_camera_frame': self.show_camera_frame
        }

        return {**base_status, **camera_frame_status}

    def cleanup(self):
        """Clean up resources"""
        self.stop_update_thread()
        if self.window:
            self.window.destroy()
        self.log("Machine area visualization with camera frame cleaned up")


# Integration helper function for main window
def add_machine_area_window_to_main(main_window_class):
    """
    Helper function to add machine area window functionality to main window
    Call this to extend your existing main window with the machine area visualization
    """

    def __init_extension__(self, *args, **kwargs):
        # Call original init
        self._original_init(*args, **kwargs)

        # Add machine area window with camera manager if available
        camera_manager = getattr(self, 'camera_manager', None)

        self.machine_area_window = MachineAreaWindow(
            self.root,
            self.grbl_controller,
            self.registration_manager,
            self.routes_service,  # Changed from routes_service to routes_service
            camera_manager,  # Pass camera manager
            self.log
        )

        # Add menu item or button to show machine area window
        self.add_machine_area_controls()

    def add_machine_area_controls(self):
        """Add controls to show/hide machine area window"""
        # Add to debug panel or create a button in main window
        if hasattr(self, 'debug_panel') and self.debug_panel:
            # Add button to debug panel
            machine_area_button = tk.Button(
                self.debug_panel.frame,
                text="Show Machine Area",
                command=self.toggle_machine_area_window
            )
            machine_area_button.pack(fill=tk.X, pady=2)

    def toggle_machine_area_window(self):
        """Toggle machine area window visibility"""
        if self.machine_area_window.is_visible:
            self.machine_area_window.hide_window()
        else:
            self.machine_area_window.show_window()

    def cleanup_extension(self):
        """Clean up machine area window"""
        if hasattr(self, 'machine_area_window'):
            self.machine_area_window.cleanup()

    # Store original methods
    main_window_class._original_init = main_window_class.__init__
    if hasattr(main_window_class, 'on_closing'):
        main_window_class._original_on_closing = main_window_class.on_closing

    # Replace methods
    main_window_class.__init__ = __init_extension__
    main_window_class.add_machine_area_controls = add_machine_area_controls
    main_window_class.toggle_machine_area_window = toggle_machine_area_window
    main_window_class.cleanup_extension = cleanup_extension

    # Extend on_closing if it exists
    if hasattr(main_window_class, 'on_closing'):
        def extended_on_closing(self):
            self.cleanup_extension()
            self._original_on_closing()
        main_window_class.on_closing = extended_on_closing
    else:
        main_window_class.on_closing = cleanup_extension

