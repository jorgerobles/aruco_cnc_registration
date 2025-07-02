"""
Machine Area Visualization Window
Floating window that shows machine bounds, routes, and camera position in real-time
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
from typing import Optional, Tuple, List, Callable
import threading
import time

from services.event_broker import event_aware, event_handler, GRBLEvents, RegistrationEvents, CameraEvents


@event_aware()
class MachineAreaWindow:
    """Floating window displaying machine area, routes, and camera position"""

    def __init__(self, parent_window, grbl_controller, registration_manager, routes_overlay, logger: Optional[Callable] = None):
        self.parent_window = parent_window
        self.grbl_controller = grbl_controller
        self.registration_manager = registration_manager
        self.routes_overlay = routes_overlay
        self.logger = logger

        # Window state
        self.window = None
        self.canvas = None
        self.status_text = None  # Initialize status_text
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
        self.routes_bounds = None
        self.calibration_points = []

        # Display settings
        self.show_machine_bounds = True
        self.show_routes = True
        self.show_camera_position = True
        self.show_camera_bounds = True
        self.show_calibration_points = True
        self.show_grid = True
        self.show_coordinates = True

        # Colors (RGB values for tkinter)
        self.colors = {
            'background': '#2b2b2b',
            'machine_bounds': '#4a90e2',
            'routes': '#f5a623',
            'machine_position': '#d0021b',
            'camera_position': '#7ed321',
            'camera_bounds': '#50e3c2',
            'calibration_points': '#9013fe',
            'grid': '#404040',
            'text': '#ffffff'
        }

        # Update rate (slower to reduce GRBL communication load)
        self.update_rate_ms = 500  # Update every 500ms instead of 100ms

        self.log("Machine Area Visualization initialized")

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
            self.window.geometry(f"{self.canvas_width + 200}x{self.canvas_height + 100}")
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
        """Setup control widgets"""
        # Display toggles
        ttk.Label(parent, text="Show Elements:").pack(anchor=tk.W, pady=(5, 0))

        self.show_machine_bounds_var = tk.BooleanVar(value=self.show_machine_bounds)
        ttk.Checkbutton(parent, text="Machine Bounds", variable=self.show_machine_bounds_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_routes_var = tk.BooleanVar(value=self.show_routes)
        ttk.Checkbutton(parent, text="Routes", variable=self.show_routes_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_camera_position_var = tk.BooleanVar(value=self.show_camera_position)
        ttk.Checkbutton(parent, text="Camera Position", variable=self.show_camera_position_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_camera_bounds_var = tk.BooleanVar(value=self.show_camera_bounds)
        ttk.Checkbutton(parent, text="Camera FOV", variable=self.show_camera_bounds_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_calibration_points_var = tk.BooleanVar(value=self.show_calibration_points)
        ttk.Checkbutton(parent, text="Calibration Points", variable=self.show_calibration_points_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_grid_var = tk.BooleanVar(value=self.show_grid)
        ttk.Checkbutton(parent, text="Grid", variable=self.show_grid_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        # Separator
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Machine bounds configuration
        ttk.Label(parent, text="Machine Bounds (mm):").pack(anchor=tk.W, pady=(5, 0))

        bounds_frame = ttk.Frame(parent)
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
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        self.auto_update_var = tk.BooleanVar(value=self.auto_update)
        ttk.Checkbutton(parent, text="Auto Update", variable=self.auto_update_var,
                       command=self.on_auto_update_changed).pack(anchor=tk.W)

        ttk.Button(parent, text="Refresh Now", command=self.manual_update).pack(fill=tk.X, pady=2)
        ttk.Button(parent, text="Center View", command=self.center_view).pack(fill=tk.X, pady=2)

    def setup_status_display(self, parent):
        """Setup status display"""
        try:
            self.status_text = tk.Text(parent, height=4, wrap=tk.WORD, font=('Consolas', 8))
            self.status_text.pack(fill=tk.X)
        except Exception as e:
            self.log(f"Error setting up status display: {e}", "error")
            # Create a fallback status display
            self.status_text = None

    def on_display_option_changed(self):
        """Handle display option changes"""
        self.show_machine_bounds = self.show_machine_bounds_var.get()
        self.show_routes = self.show_routes_var.get()
        self.show_camera_position = self.show_camera_position_var.get()
        self.show_camera_bounds = self.show_camera_bounds_var.get()
        self.show_calibration_points = self.show_calibration_points_var.get()
        self.show_grid = self.show_grid_var.get()
        self.schedule_update()

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
            # Use cached position instead of requesting new one to avoid timeout
            if hasattr(self, 'current_machine_position'):
                # Only update display, don't fetch new data
                self.update_display()
            else:
                # If no cached position, do a full update but with error handling
                self.update_all_data()
                self.update_display()
        except Exception as e:
            self.log(f"Error in manual update: {e}", "warning")

    def center_view(self):
        """Center the view on the machine area"""
        self.calculate_scale_factor()
        self.schedule_update()

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

            # Update camera position from routes overlay
            if self.routes_overlay:
                try:
                    camera_info = self.routes_overlay.get_camera_info()
                    if camera_info and camera_info.get('camera_position'):
                        self.current_camera_position = camera_info['camera_position']

                        # Calculate camera field of view bounds
                        self.update_camera_bounds()
                except Exception as e:
                    # Silently handle camera info errors
                    pass

            # Update routes bounds
            if self.routes_overlay:
                try:
                    self.routes_bounds = self.routes_overlay.get_route_bounds()
                except Exception as e:
                    # Silently handle routes bounds errors
                    pass

            # Update calibration points
            self.update_calibration_points()

        except Exception as e:
            self.log(f"Error updating data: {e}", "error")

    def update_camera_bounds(self):
        """Update camera field of view bounds"""
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

            # Draw routes
            if self.show_routes and self.routes_bounds:
                self.draw_routes()

            # Draw camera field of view
            if self.show_camera_bounds and self.camera_view_bounds:
                self.draw_camera_bounds()

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

        x1, y1 = self.machine_to_canvas(self.routes_bounds[0], self.routes_bounds[1])
        x2, y2 = self.machine_to_canvas(self.routes_bounds[2], self.routes_bounds[3])

        # Draw routes bounding box
        self.canvas.create_rectangle(x1, y2, x2, y1, outline=self.colors['routes'], width=2, fill="", dash=(5, 5))

        # Add routes label
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        self.canvas.create_text(center_x, center_y, text="Routes", fill=self.colors['routes'], anchor=tk.CENTER)

    def draw_camera_bounds(self):
        """Draw camera field of view"""
        if not self.camera_view_bounds:
            return

        x1, y1 = self.machine_to_canvas(self.camera_view_bounds['x_min'], self.camera_view_bounds['y_min'])
        x2, y2 = self.machine_to_canvas(self.camera_view_bounds['x_max'], self.camera_view_bounds['y_max'])

        # Draw camera FOV rectangle
        self.canvas.create_rectangle(x1, y2, x2, y1, outline=self.colors['camera_bounds'], width=2,
                                   fill=self.colors['camera_bounds'], stipple="gray25")

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
                status_lines.append("Camera: Not available")

            # Routes status
            if self.routes_bounds:
                width = self.routes_bounds[2] - self.routes_bounds[0]
                height = self.routes_bounds[3] - self.routes_bounds[1]
                status_lines.append(f"Routes: {width:.1f}x{height:.1f}mm")
            else:
                status_lines.append("Routes: None loaded")

            # Calibration status
            status_lines.append(f"Calibration: {len(self.calibration_points)} points")

            # Scale info
            status_lines.append(f"Scale: {self.scale_factor:.2f} px/mm")

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

    def get_window_status(self) -> dict:
        """Get current window status"""
        return {
            'visible': self.is_visible,
            'auto_update': self.auto_update,
            'machine_bounds': self.machine_bounds.copy(),
            'current_machine_position': self.current_machine_position.tolist(),
            'current_camera_position': self.current_camera_position,
            'routes_bounds': self.routes_bounds,
            'calibration_points_count': len(self.calibration_points),
            'scale_factor': self.scale_factor
        }

    def cleanup(self):
        """Clean up resources"""
        self.stop_update_thread()
        if self.window:
            self.window.destroy()
        self.log("Machine area visualization cleaned up")


# Integration helper function for main window
def add_machine_area_window_to_main(main_window_class):
    """
    Helper function to add machine area window functionality to main window
    Call this to extend your existing main window with the machine area visualization
    """

    def __init_extension__(self, *args, **kwargs):
        # Call original init
        self._original_init(*args, **kwargs)

        # Add machine area window
        self.machine_area_window = MachineAreaWindow(
            self.root,
            self.grbl_controller,
            self.registration_manager,
            self.routes_overlay,
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


# Enhanced Machine Area Window with additional features
class EnhancedMachineAreaWindow(MachineAreaWindow):
    """Enhanced version with route visualization and real-time path tracking"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Enhanced features
        self.show_route_paths = True
        self.show_movement_trail = True
        self.movement_trail = []  # Store recent positions for trail
        self.max_trail_length = 50

        # Route visualization
        self.actual_routes = []  # Actual route paths from overlay
        self.route_colors = ['#f5a623', '#7ed321', '#d0021b', '#9013fe', '#50e3c2']

        # Animation
        self.animate_movement = True
        self.animation_steps = 5
        self.current_animation_step = 0

        # Enhanced controls variables (initialize these for the setup_controls method)
        self.show_route_paths_var = None
        self.show_movement_trail_var = None
        self.animate_movement_var = None
        self.trail_length_var = None

        self.log("Enhanced Machine Area Visualization initialized")

    def setup_controls(self, parent):
        """Setup enhanced controls"""
        # Display toggles
        ttk.Label(parent, text="Show Elements:").pack(anchor=tk.W, pady=(5, 0))

        self.show_machine_bounds_var = tk.BooleanVar(value=self.show_machine_bounds)
        ttk.Checkbutton(parent, text="Machine Bounds", variable=self.show_machine_bounds_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_routes_var = tk.BooleanVar(value=self.show_routes)
        ttk.Checkbutton(parent, text="Routes", variable=self.show_routes_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_camera_position_var = tk.BooleanVar(value=self.show_camera_position)
        ttk.Checkbutton(parent, text="Camera Position", variable=self.show_camera_position_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_camera_bounds_var = tk.BooleanVar(value=self.show_camera_bounds)
        ttk.Checkbutton(parent, text="Camera FOV", variable=self.show_camera_bounds_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_calibration_points_var = tk.BooleanVar(value=self.show_calibration_points)
        ttk.Checkbutton(parent, text="Calibration Points", variable=self.show_calibration_points_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        self.show_grid_var = tk.BooleanVar(value=self.show_grid)
        ttk.Checkbutton(parent, text="Grid", variable=self.show_grid_var,
                       command=self.on_display_option_changed).pack(anchor=tk.W)

        # Separator
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Machine bounds configuration
        ttk.Label(parent, text="Machine Bounds (mm):").pack(anchor=tk.W, pady=(5, 0))

        bounds_frame = ttk.Frame(parent)
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
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        self.auto_update_var = tk.BooleanVar(value=self.auto_update)
        ttk.Checkbutton(parent, text="Auto Update", variable=self.auto_update_var,
                       command=self.on_auto_update_changed).pack(anchor=tk.W)

        ttk.Button(parent, text="Refresh Now", command=self.manual_update).pack(fill=tk.X, pady=2)
        ttk.Button(parent, text="Center View", command=self.center_view).pack(fill=tk.X, pady=2)

        # Enhanced display options
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        ttk.Label(parent, text="Enhanced Features:").pack(anchor=tk.W)

        self.show_route_paths_var = tk.BooleanVar(value=self.show_route_paths)
        ttk.Checkbutton(parent, text="Route Paths", variable=self.show_route_paths_var,
                       command=self.on_enhanced_option_changed).pack(anchor=tk.W)

        self.show_movement_trail_var = tk.BooleanVar(value=self.show_movement_trail)
        ttk.Checkbutton(parent, text="Movement Trail", variable=self.show_movement_trail_var,
                       command=self.on_enhanced_option_changed).pack(anchor=tk.W)

        self.animate_movement_var = tk.BooleanVar(value=self.animate_movement)
        ttk.Checkbutton(parent, text="Animate Movement", variable=self.animate_movement_var,
                       command=self.on_enhanced_option_changed).pack(anchor=tk.W)

        # Trail controls
        trail_frame = ttk.Frame(parent)
        trail_frame.pack(fill=tk.X, pady=2)

        ttk.Label(trail_frame, text="Trail Length:").pack(side=tk.LEFT)
        self.trail_length_var = tk.StringVar(value=str(self.max_trail_length))
        trail_entry = ttk.Entry(trail_frame, textvariable=self.trail_length_var, width=6)
        trail_entry.pack(side=tk.RIGHT)
        trail_entry.bind('<Return>', self.on_trail_length_changed)

        ttk.Button(parent, text="Clear Trail", command=self.clear_movement_trail).pack(fill=tk.X, pady=2)

    def on_enhanced_option_changed(self):
        """Handle enhanced option changes"""
        self.show_route_paths = self.show_route_paths_var.get()
        self.show_movement_trail = self.show_movement_trail_var.get()
        self.animate_movement = self.animate_movement_var.get()
        self.schedule_update()

    def on_trail_length_changed(self, event=None):
        """Handle trail length changes"""
        try:
            new_length = int(self.trail_length_var.get())
            self.max_trail_length = max(10, min(new_length, 200))  # Limit between 10-200
            # Trim trail if needed
            if len(self.movement_trail) > self.max_trail_length:
                self.movement_trail = self.movement_trail[-self.max_trail_length:]
            self.log(f"Movement trail length set to {self.max_trail_length}")
        except ValueError:
            self.log("Invalid trail length value", "error")

    def clear_movement_trail(self):
        """Clear movement trail"""
        self.movement_trail = []
        self.schedule_update()
        self.log("Movement trail cleared")

    @event_handler(GRBLEvents.POSITION_CHANGED)
    def _on_position_changed_enhanced(self, position: List[float]):
        """Enhanced position change handler with trail tracking"""
        try:
            new_position = np.array(position[:3])

            # Add to movement trail
            if self.show_movement_trail:
                # Only add if position changed significantly (avoid noise)
                if (not self.movement_trail or
                    np.linalg.norm(new_position[:2] - np.array(self.movement_trail[-1])[:2]) > 0.1):

                    self.movement_trail.append(new_position.copy())

                    # Limit trail length
                    if len(self.movement_trail) > self.max_trail_length:
                        self.movement_trail = self.movement_trail[-self.max_trail_length:]

            self.current_machine_position = new_position

            if self.is_visible and self.auto_update:
                self.schedule_update()

        except Exception as e:
            # Silently handle position update errors to avoid spam
            pass

    def update_all_data(self):
        """Enhanced data update including actual routes"""
        super().update_all_data()

        # Update actual route paths from overlay
        try:
            if self.routes_overlay and hasattr(self.routes_overlay, 'routes'):
                self.actual_routes = self.routes_overlay.routes.copy() if self.routes_overlay.routes else []
        except Exception as e:
            self.log(f"Error updating route paths: {e}", "error")

    def update_display(self):
        """Enhanced display update"""
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
            if self.show_route_paths:
                self.draw_actual_routes()

            # Draw routes bounds (if not showing actual paths)
            if self.show_routes and self.routes_bounds and not self.show_route_paths:
                self.draw_routes()

            # Draw movement trail
            if self.show_movement_trail:
                self.draw_movement_trail()

            # Draw camera field of view
            if self.show_camera_bounds and self.camera_view_bounds:
                self.draw_camera_bounds()

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
            self.log(f"Error updating enhanced display: {e}", "error")

    def draw_actual_routes(self):
        """Draw actual route paths"""
        if not self.actual_routes:
            return

        try:
            for route_idx, route in enumerate(self.actual_routes):
                if len(route) < 2:
                    continue

                # Use different colors for different routes
                color = self.route_colors[route_idx % len(self.route_colors)]

                # Convert route points to canvas coordinates
                canvas_points = []
                for x, y in route:
                    canvas_x, canvas_y = self.machine_to_canvas(x, y)
                    canvas_points.extend([canvas_x, canvas_y])

                if len(canvas_points) >= 4:  # At least 2 points
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

        except Exception as e:
            self.log(f"Error drawing actual routes: {e}", "error")

    def draw_movement_trail(self):
        """Draw movement trail"""
        if len(self.movement_trail) < 2:
            return

        try:
            # Draw trail with fading effect
            for i in range(1, len(self.movement_trail)):
                prev_pos = self.movement_trail[i-1]
                curr_pos = self.movement_trail[i]

                # Calculate fade factor (newer positions are more opaque)
                fade_factor = i / len(self.movement_trail)

                # Convert to canvas coordinates
                x1, y1 = self.machine_to_canvas(prev_pos[0], prev_pos[1])
                x2, y2 = self.machine_to_canvas(curr_pos[0], curr_pos[1])

                # Create color with fade effect
                alpha = int(255 * fade_factor)
                # Use hex color with transparency simulation (lighter colors)
                gray_value = int(128 + 127 * fade_factor)
                color = f"#{gray_value:02x}{gray_value:02x}{gray_value:02x}"

                # Draw trail segment
                width = max(1, int(3 * fade_factor))
                self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)

        except Exception as e:
            self.log(f"Error drawing movement trail: {e}", "error")

    def draw_machine_position(self):
        """Enhanced machine position drawing with animation"""
        x, y = self.current_machine_position[0], self.current_machine_position[1]
        canvas_x, canvas_y = self.machine_to_canvas(x, y)

        # Draw machine position with animation
        if self.animate_movement:
            # Pulsing effect
            base_size = 6
            pulse_size = base_size + 2 * abs(np.sin(time.time() * 3))

            # Draw pulsing cross
            self.canvas.create_line(canvas_x - pulse_size, canvas_y, canvas_x + pulse_size, canvas_y,
                                   fill=self.colors['machine_position'], width=3)
            self.canvas.create_line(canvas_x, canvas_y - pulse_size, canvas_x, canvas_y + pulse_size,
                                   fill=self.colors['machine_position'], width=3)

            # Draw center dot
            self.canvas.create_oval(canvas_x - 2, canvas_y - 2, canvas_x + 2, canvas_y + 2,
                                   fill='white', outline=self.colors['machine_position'], width=1)
        else:
            # Static cross
            size = 6
            self.canvas.create_line(canvas_x - size, canvas_y, canvas_x + size, canvas_y,
                                   fill=self.colors['machine_position'], width=3)
            self.canvas.create_line(canvas_x, canvas_y - size, canvas_x, canvas_y + size,
                                   fill=self.colors['machine_position'], width=3)

        # Add position label
        self.canvas.create_text(canvas_x + 10, canvas_y - 10,
                               text=f"M({x:.1f},{y:.1f})",
                               fill=self.colors['machine_position'], anchor=tk.W)

    def update_status_display(self):
        """Update status text display"""
        # Check if status_text exists and is valid
        if not hasattr(self, 'status_text') or self.status_text is None:
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

                # Distance between machine and camera
                if self.current_camera_position:
                    dist = np.sqrt((pos[0] - cam_x)**2 + (pos[1] - cam_y)**2)
                    status_lines.append(f"M-C Distance: {dist:.1f}mm")
            else:
                status_lines.append("Camera: Not available")

            # Routes status
            if self.actual_routes:
                total_points = sum(len(route) for route in self.actual_routes)
                status_lines.append(f"Routes: {len(self.actual_routes)} paths, {total_points} points")
            elif self.routes_bounds:
                width = self.routes_bounds[2] - self.routes_bounds[0]
                height = self.routes_bounds[3] - self.routes_bounds[1]
                status_lines.append(f"Routes: {width:.1f}x{height:.1f}mm")
            else:
                status_lines.append("Routes: None loaded")

            # Trail status
            if self.show_movement_trail:
                status_lines.append(f"Trail: {len(self.movement_trail)}/{self.max_trail_length} points")

            # Calibration status
            status_lines.append(f"Calibration: {len(self.calibration_points)} points")

            # Scale info
            status_lines.append(f"Scale: {self.scale_factor:.2f} px/mm")

            # Update text widget if it exists
            if self.status_text and hasattr(self.status_text, 'delete'):
                self.status_text.delete(1.0, tk.END)
                self.status_text.insert(1.0, "\n".join(status_lines))

        except Exception as e:
            self.log(f"Error updating enhanced status display: {e}", "error")

    def export_trail_data(self) -> List[np.ndarray]:
        """Export movement trail data"""
        return [pos.copy() for pos in self.movement_trail]

    def import_trail_data(self, trail_data: List[np.ndarray]):
        """Import movement trail data"""
        self.movement_trail = [pos.copy() for pos in trail_data]
        self.schedule_update()
        self.log(f"Imported {len(trail_data)} trail points")

    def get_enhanced_status(self) -> dict:
        """Get enhanced window status"""
        base_status = super().get_window_status()
        enhanced_status = {
            'show_route_paths': self.show_route_paths,
            'show_movement_trail': self.show_movement_trail,
            'animate_movement': self.animate_movement,
            'movement_trail_length': len(self.movement_trail),
            'max_trail_length': self.max_trail_length,
            'actual_routes_count': len(self.actual_routes),
            'total_route_points': sum(len(route) for route in self.actual_routes) if self.actual_routes else 0
        }

        return {**base_status, **enhanced_status}