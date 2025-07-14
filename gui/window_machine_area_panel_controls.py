"""
Machine Area Controls Panel Component
Handles all control widgets and settings for the machine area visualization
Updated to remove manual FOV controls and use only camera manager data
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Dict, Any


class MachineAreaControls:
    """Controls panel for machine area visualization settings"""

    def __init__(self, parent, logger: Optional[Callable] = None):
        self.parent = parent
        self.logger = logger

        # Callbacks for various actions
        self.callbacks = {}

        # Display option variables
        self.show_machine_bounds_var = tk.BooleanVar(value=True)
        self.show_routes_var = tk.BooleanVar(value=True)
        self.show_route_paths_var = tk.BooleanVar(value=True)
        self.show_camera_position_var = tk.BooleanVar(value=True)
        self.show_camera_bounds_var = tk.BooleanVar(value=True)
        self.show_camera_frame_var = tk.BooleanVar(value=True)
        self.show_calibration_points_var = tk.BooleanVar(value=True)
        self.show_grid_var = tk.BooleanVar(value=True)

        # Machine bounds variables
        self.x_max_var = tk.StringVar(value="400")
        self.y_max_var = tk.StringVar(value="400")

        # Auto update variable
        self.auto_update_var = tk.BooleanVar(value=True)

        # Debug variable
        self.debug_enabled_var = tk.BooleanVar(value=False)

        # Status labels
        self.zoom_label = None
        self.resolution_label = None
        self.fov_status_label = None
        self.camera_status_label = None

        # Setup the controls
        self.setup_controls()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def set_callback(self, name: str, callback: Callable):
        """Set a callback for a specific action"""
        self.callbacks[name] = callback

    def _call_callback(self, name: str, *args, **kwargs):
        """Call a callback if it exists"""
        if name in self.callbacks:
            try:
                self.callbacks[name](*args, **kwargs)
            except Exception as e:
                self.log(f"Error in callback {name}: {e}", "error")

    def setup_controls(self):
        """Setup all control widgets"""
        # Create scrollable frame for controls
        canvas_control = tk.Canvas(self.parent, width=250)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas_control.yview)
        scrollable_frame = ttk.Frame(canvas_control)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas_control.configure(scrollregion=canvas_control.bbox("all"))
        )

        canvas_control.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas_control.configure(yscrollcommand=scrollbar.set)

        canvas_control.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Setup individual control sections
        self.setup_display_options(scrollable_frame)
        self.setup_view_controls(scrollable_frame)
        self.setup_camera_status(scrollable_frame)
        self.setup_machine_bounds(scrollable_frame)
        self.setup_update_controls(scrollable_frame)
        self.setup_debug_controls(scrollable_frame)

    def setup_display_options(self, parent):
        """Setup display toggle options"""
        ttk.Label(parent, text="Show Elements:").pack(anchor=tk.W, pady=(5, 0))

        options = [
            ("Machine Bounds", self.show_machine_bounds_var),
            ("Routes Bounds", self.show_routes_var),
            ("Route Paths", self.show_route_paths_var),
            ("Camera Position", self.show_camera_position_var),
            ("Camera FOV (Legacy)", self.show_camera_bounds_var),
            ("Camera Frame", self.show_camera_frame_var),
            ("Calibration Points", self.show_calibration_points_var),
            ("Grid", self.show_grid_var)
        ]

        for text, var in options:
            ttk.Checkbutton(parent, text=text, variable=var,
                            command=self.on_display_option_changed).pack(anchor=tk.W)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

    def setup_view_controls(self, parent):
        """Setup zoom and pan controls"""
        ttk.Label(parent, text="View Controls:").pack(anchor=tk.W, pady=(5, 0))

        zoom_frame = ttk.Frame(parent)
        zoom_frame.pack(fill=tk.X, pady=2)

        ttk.Button(zoom_frame, text="Zoom In", command=self.zoom_in, width=8).pack(side=tk.LEFT, padx=1)
        ttk.Button(zoom_frame, text="Zoom Out", command=self.zoom_out, width=8).pack(side=tk.LEFT, padx=1)

        zoom_frame2 = ttk.Frame(parent)
        zoom_frame2.pack(fill=tk.X, pady=2)

        ttk.Button(zoom_frame2, text="Reset View", command=self.reset_view, width=8).pack(side=tk.LEFT, padx=1)
        ttk.Button(zoom_frame2, text="Fit All", command=self.zoom_to_fit, width=8).pack(side=tk.LEFT, padx=1)

        # Zoom level display
        self.zoom_label = ttk.Label(parent, text="Zoom: 100%", font=("TkDefaultFont", 8))
        self.zoom_label.pack(anchor=tk.W, pady=2)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

    def setup_camera_status(self, parent):
        """Setup camera status display (read-only)"""
        ttk.Label(parent, text="Camera Status:").pack(anchor=tk.W, pady=(5, 0))

        # Camera connection status
        self.camera_status_label = ttk.Label(parent, text="Status: Disconnected",
                                           font=("TkDefaultFont", 8))
        self.camera_status_label.pack(anchor=tk.W, pady=2)

        # Resolution display
        resolution_frame = ttk.Frame(parent)
        resolution_frame.pack(fill=tk.X, pady=2)
        ttk.Label(resolution_frame, text="Resolution:").pack(side=tk.LEFT)
        self.resolution_label = ttk.Label(resolution_frame, text="640x480",
                                        font=("TkDefaultFont", 8))
        self.resolution_label.pack(side=tk.LEFT, padx=(5, 0))

        # FOV status display
        self.fov_status_label = ttk.Label(parent, text="FOV: No data",
                                        font=("TkDefaultFont", 8))
        self.fov_status_label.pack(anchor=tk.W, pady=2)

        # Camera control buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Update Camera Info",
                  command=self.update_camera_info).pack(fill=tk.X, pady=1)
        ttk.Button(button_frame, text="Calculate FOV",
                  command=self.calculate_fov).pack(fill=tk.X, pady=1)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

    def setup_machine_bounds(self, parent):
        """Setup machine bounds configuration"""
        ttk.Label(parent, text="Machine Bounds (mm):").pack(anchor=tk.W, pady=(5, 0))

        bounds_frame = ttk.Frame(parent)
        bounds_frame.pack(fill=tk.X, pady=2)

        ttk.Label(bounds_frame, text="X Max:").grid(row=0, column=0, sticky=tk.W)
        x_max_entry = ttk.Entry(bounds_frame, textvariable=self.x_max_var, width=8)
        x_max_entry.grid(row=0, column=1, padx=(5, 0))
        x_max_entry.bind('<Return>', self.on_bounds_changed)

        ttk.Label(bounds_frame, text="Y Max:").grid(row=1, column=0, sticky=tk.W)
        y_max_entry = ttk.Entry(bounds_frame, textvariable=self.y_max_var, width=8)
        y_max_entry.grid(row=1, column=1, padx=(5, 0))
        y_max_entry.bind('<Return>', self.on_bounds_changed)

        ttk.Button(bounds_frame, text="Update", command=self.on_bounds_changed).grid(
            row=2, column=0, columnspan=2, pady=5)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

    def setup_update_controls(self, parent):
        """Setup update and refresh controls"""
        ttk.Checkbutton(parent, text="Auto Update", variable=self.auto_update_var,
                        command=self.on_auto_update_changed).pack(anchor=tk.W)

        ttk.Button(parent, text="Refresh Now", command=self.manual_update).pack(fill=tk.X, pady=2)
        ttk.Button(parent, text="Center View", command=self.center_view).pack(fill=tk.X, pady=2)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

    def setup_debug_controls(self, parent):
        """Setup debug controls"""
        ttk.Checkbutton(parent, text="Enable Debug Logging",
                        variable=self.debug_enabled_var).pack(anchor=tk.W, pady=2)
        ttk.Button(parent, text="Debug: Show Data", command=self.debug_show_data).pack(fill=tk.X, pady=2)

    # Event handlers
    def on_display_option_changed(self):
        """Handle display option changes"""
        self._call_callback('display_changed', self.get_display_options())

    def zoom_in(self):
        """Zoom in"""
        self._call_callback('zoom_in')

    def zoom_out(self):
        """Zoom out"""
        self._call_callback('zoom_out')

    def reset_view(self):
        """Reset view"""
        self._call_callback('reset_view')

    def zoom_to_fit(self):
        """Zoom to fit"""
        self._call_callback('zoom_to_fit')

    def on_bounds_changed(self, event=None):
        """Handle machine bounds changes"""
        try:
            x_max = float(self.x_max_var.get())
            y_max = float(self.y_max_var.get())

            self._call_callback('bounds_changed', {
                'x_max': x_max,
                'y_max': y_max
            })

        except ValueError:
            self.log("Invalid machine bounds values", "error")

    def on_auto_update_changed(self):
        """Handle auto update toggle"""
        self._call_callback('auto_update_changed', self.auto_update_var.get())

    def manual_update(self):
        """Manual update"""
        self._call_callback('manual_update')

    def center_view(self):
        """Center view"""
        self._call_callback('center_view')

    def update_camera_info(self):
        """Update camera info"""
        self._call_callback('update_camera_info')

    def calculate_fov(self):
        """Trigger FOV calculation"""
        self._call_callback('calculate_fov')

    def debug_show_data(self):
        """Debug show data"""
        if self.debug_enabled_var.get():
            self._call_callback('debug_show_data')

    # Getters for current settings
    def get_display_options(self) -> Dict[str, bool]:
        """Get current display options"""
        return {
            'show_machine_bounds': self.show_machine_bounds_var.get(),
            'show_routes': self.show_routes_var.get(),
            'show_route_paths': self.show_route_paths_var.get(),
            'show_camera_position': self.show_camera_position_var.get(),
            'show_camera_bounds': self.show_camera_bounds_var.get(),
            'show_camera_frame': self.show_camera_frame_var.get(),
            'show_calibration_points': self.show_calibration_points_var.get(),
            'show_grid': self.show_grid_var.get()
        }

    def get_machine_bounds(self) -> Dict[str, float]:
        """Get current machine bounds"""
        try:
            return {
                'x_max': float(self.x_max_var.get()),
                'y_max': float(self.y_max_var.get())
            }
        except ValueError:
            return {'x_max': 400.0, 'y_max': 400.0}

    def is_auto_update_enabled(self) -> bool:
        """Check if auto update is enabled"""
        return self.auto_update_var.get()

    def is_debug_enabled(self) -> bool:
        """Check if debug is enabled"""
        return self.debug_enabled_var.get()

    # Setters for updating from external sources
    def update_zoom_display(self, zoom_factor: float):
        """Update zoom level display"""
        if self.zoom_label:
            self.zoom_label.config(text=f"Zoom: {zoom_factor * 100:.0f}%")

    def update_resolution_display(self, width: int, height: int):
        """Update resolution display"""
        if self.resolution_label:
            self.resolution_label.config(text=f"{width}x{height}")

    def update_camera_status(self, connected: bool, calibrated: bool = False):
        """Update camera status display"""
        if self.camera_status_label:
            if connected:
                cal_text = " | Calibrated" if calibrated else " | Not calibrated"
                self.camera_status_label.config(text=f"Status: Connected{cal_text}")
            else:
                self.camera_status_label.config(text="Status: Disconnected")

    def update_fov_status(self, fov_data: Optional[Dict[str, Any]]):
        """Update FOV status display with camera manager data"""
        if not self.fov_status_label:
            return

        if fov_data is None:
            self.fov_status_label.config(text="FOV: No data")
            return

        try:
            width_mm = fov_data.get('width_mm', 0)
            height_mm = fov_data.get('height_mm', 0)
            pixels_per_mm = fov_data.get('pixels_per_mm', 0)
            source = fov_data.get('calculated_from', 'unknown')

            # Create status text based on data source
            if source == 'aruco_detection':
                status_text = f"FOV: {width_mm:.1f}×{height_mm:.1f}mm ({pixels_per_mm:.2f}px/mm) [ArUco]"
            elif source == 'averaged_aruco_detection':
                num_samples = fov_data.get('num_samples', 0)
                status_text = f"FOV: {width_mm:.1f}×{height_mm:.1f}mm ({pixels_per_mm:.2f}px/mm) [Avg:{num_samples}]"
            else:
                status_text = f"FOV: {width_mm:.1f}×{height_mm:.1f}mm ({pixels_per_mm:.2f}px/mm) [Calc]"

            self.fov_status_label.config(text=status_text)

        except Exception as e:
            self.log(f"Error updating FOV status: {e}", "error")
            self.fov_status_label.config(text="FOV: Error displaying data")

    def set_machine_bounds(self, x_max: float, y_max: float):
        """Set machine bounds values"""
        self.x_max_var.set(str(x_max))
        self.y_max_var.set(str(y_max))

    def set_auto_update(self, enabled: bool):
        """Set auto update state"""
        self.auto_update_var.set(enabled)

    def set_display_option(self, option: str, value: bool):
        """Set a specific display option"""
        option_map = {
            'show_machine_bounds': self.show_machine_bounds_var,
            'show_routes': self.show_routes_var,
            'show_route_paths': self.show_route_paths_var,
            'show_camera_position': self.show_camera_position_var,
            'show_camera_bounds': self.show_camera_bounds_var,
            'show_camera_frame': self.show_camera_frame_var,
            'show_calibration_points': self.show_calibration_points_var,
            'show_grid': self.show_grid_var
        }

        if option in option_map:
            option_map[option].set(value)

    # REMOVED METHODS (no longer needed):
    # - get_camera_config()
    # - set_camera_config()
    # - on_camera_config_changed()
    # - setup_camera_config()
    # All manual FOV configuration has been removed