"""
Route Transformation Panel
GUI for applying rigid transformations to loaded SVG routes using registration data
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from services.event_broker import event_aware, event_handler, EventPriority
from services.routes_manager import RouteEvents
from services.registration_manager import RegistrationEvents
from services.route_transformer import RouteTransformer, RouteTransformerEvents


@event_aware()
class RouteTransformationPanel:
    """Panel for applying registration-based transformations to routes"""

    def __init__(self, parent, route_manager, registration_manager, logger: Optional[Callable] = None):
        self.route_manager = route_manager
        self.registration_manager = registration_manager
        self.route_transformer = RouteTransformer(logger)
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="Route Transformation")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # State tracking
        self.routes_loaded = False
        self.registration_available = False
        self.transformation_applied = False
        self.current_bounds = None
        self.transformed_bounds = None

        # Variables
        self.route_status_var = tk.StringVar(value="No routes loaded")
        self.registration_status_var = tk.StringVar(value="No registration")
        self.bounds_info_var = tk.StringVar(value="No bounds calculated")
        self.transformation_status_var = tk.StringVar(value="No transformation applied")

        self._setup_widgets()
        self._update_ui_state()

        # Initialize state from managers
        self._check_initial_state()

        self.log("Route Transformation Panel initialized")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[RouteTransformPanel] {message}", level)

    def _check_initial_state(self):
        """Check initial state of routes and registration"""
        # Check if routes are already loaded
        if hasattr(self.route_manager, 'is_loaded') and self.route_manager.is_loaded():
            self.routes_loaded = True
            route_info = self.route_manager.get_route_info()
            route_count = route_info.get('route_count', 0)
            self.route_status_var.set(f"{route_count} routes loaded")
            self.calculate_route_bounds()

        # Check if registration is available
        if self.registration_manager.is_registered():
            self.registration_available = True
            point_count = self.registration_manager.get_calibration_points_count()
            error = self.registration_manager.get_registration_error() or 0.0
            self.registration_status_var.set(f"Registered ({point_count} points, error: {error:.3f}mm)")

        self._update_ui_state()

    def _setup_widgets(self):
        """Setup the panel widgets"""

        # Status section
        status_frame = ttk.Frame(self.frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        # Routes status
        ttk.Label(status_frame, text="Routes:").grid(row=0, column=0, sticky=tk.W, padx=(0,5))
        self.routes_status_label = ttk.Label(status_frame, textvariable=self.route_status_var, foreground="gray")
        self.routes_status_label.grid(row=0, column=1, sticky=tk.W)

        # Registration status
        ttk.Label(status_frame, text="Registration:").grid(row=1, column=0, sticky=tk.W, padx=(0,5))
        self.reg_status_label = ttk.Label(status_frame, textvariable=self.registration_status_var, foreground="gray")
        self.reg_status_label.grid(row=1, column=1, sticky=tk.W)

        # Bounds info
        ttk.Label(status_frame, text="Bounds:").grid(row=2, column=0, sticky=tk.W, padx=(0,5))
        self.bounds_status_label = ttk.Label(status_frame, textvariable=self.bounds_info_var, foreground="gray")
        self.bounds_status_label.grid(row=2, column=1, sticky=tk.W)

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Action buttons
        button_frame = ttk.Frame(self.frame)
        button_frame.pack(fill=tk.X, padx=5)

        self.calculate_bounds_btn = ttk.Button(
            button_frame, text="Calculate Route Bounds",
            command=self.calculate_route_bounds
        )
        self.calculate_bounds_btn.pack(side=tk.LEFT, padx=(0,5))

        self.apply_transform_btn = ttk.Button(
            button_frame, text="Apply Registration Transform",
            command=self.apply_registration_transformation
        )
        self.apply_transform_btn.pack(side=tk.LEFT, padx=(0,5))

        self.revert_transform_btn = ttk.Button(
            button_frame, text="Revert to Original",
            command=self.revert_to_original
        )
        self.revert_transform_btn.pack(side=tk.LEFT)

        # Transformation status
        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        status_label = ttk.Label(self.frame, text="Transform Status:")
        status_label.pack(anchor=tk.W, padx=5)

        self.transform_status_label = ttk.Label(
            self.frame, textvariable=self.transformation_status_var,
            foreground="gray", wraplength=400
        )
        self.transform_status_label.pack(anchor=tk.W, padx=15)

    # Event handlers for route and registration state changes

    @event_handler(RouteEvents.ROUTES_LOADED, EventPriority.HIGH)
    def _on_routes_loaded(self, data: dict):
        """Handle routes loaded event"""
        self.routes_loaded = True
        self.transformation_applied = False
        route_count = data.get('route_count', 0)
        self.route_status_var.set(f"{route_count} routes loaded")
        self.routes_status_label.config(foreground="green")
        self.log(f"Routes loaded: {route_count} routes")
        self._update_ui_state()

        # Auto-calculate bounds when routes are loaded
        self.calculate_route_bounds()

    @event_handler(RouteEvents.ROUTES_CLEARED, EventPriority.HIGH)
    def _on_routes_cleared(self):
        """Handle routes cleared event"""
        self.routes_loaded = False
        self.transformation_applied = False
        self.current_bounds = None
        self.transformed_bounds = None
        self.route_status_var.set("No routes loaded")
        self.routes_status_label.config(foreground="gray")
        self.bounds_info_var.set("No bounds calculated")
        self.bounds_status_label.config(foreground="gray")
        self.transformation_status_var.set("No transformation applied")
        self.transform_status_label.config(foreground="gray")
        self.log("Routes cleared")
        self._update_ui_state()

    @event_handler(RegistrationEvents.COMPUTED, EventPriority.HIGH)
    def _on_registration_computed(self, data: dict):
        """Handle registration computed event"""
        self.registration_available = True
        error = data.get('error', 0.0)
        point_count = data.get('point_count', 0)
        self.registration_status_var.set(f"Registered ({point_count} points, error: {error:.3f}mm)")
        self.reg_status_label.config(foreground="green")
        self.log(f"Registration available: {point_count} points, error: {error:.3f}mm")
        self._update_ui_state()

    @event_handler(RegistrationEvents.CLEARED, EventPriority.HIGH)
    def _on_registration_cleared(self, data: dict):
        """Handle registration cleared event"""
        self.registration_available = False
        self.registration_status_var.set("No registration")
        self.reg_status_label.config(foreground="gray")
        self.log("Registration cleared")
        self._update_ui_state()

    @event_handler(RouteTransformerEvents.BOUNDS_CALCULATED)
    def _on_bounds_calculated(self, data: dict):
        """Handle bounds calculated event"""
        bounds = data['bounds']
        self.current_bounds = bounds

        bounds_text = (f"Size: {bounds['width']:.1f}×{bounds['height']:.1f}mm, "
                      f"Center: ({bounds['center_x']:.1f}, {bounds['center_y']:.1f})")
        self.bounds_info_var.set(bounds_text)
        self.bounds_status_label.config(foreground="blue")

        self.log(f"Route bounds calculated: {bounds_text}")

    @event_handler(RouteTransformerEvents.TRANSFORMATION_APPLIED)
    def _on_transformation_applied(self, data: dict):
        """Handle transformation applied event"""
        self.transformation_applied = True
        reg_error = data.get('registration_error', 0.0)
        route_count = data.get('route_count', 0)

        status_text = f"Registration transform applied to {route_count} routes (error: {reg_error:.3f}mm)"
        self.transformation_status_var.set(status_text)
        self.transform_status_label.config(foreground="green")

        # Store transformed bounds
        self.transformed_bounds = data.get('transformed_bounds')

        self.log(f"Transformation applied: {status_text}")
        self._update_ui_state()

    @event_handler(RouteTransformerEvents.ERROR)
    def _on_transformer_error(self, error_message: str):
        """Handle route transformer errors"""
        self.transformation_status_var.set(f"Error: {error_message}")
        self.transform_status_label.config(foreground="red")
        self.log(f"Route transformer error: {error_message}", "error")

    def _update_ui_state(self):
        """Update UI button states based on current state"""
        # Calculate bounds button - enabled when routes are loaded
        self.calculate_bounds_btn.config(
            state=tk.NORMAL if self.routes_loaded else tk.DISABLED
        )

        # Apply transform button - enabled when routes loaded and registration available
        self.apply_transform_btn.config(
            state=tk.NORMAL if (self.routes_loaded and self.registration_available and not self.transformation_applied) else tk.DISABLED
        )

        # Revert button - enabled when transformation has been applied
        self.revert_transform_btn.config(
            state=tk.NORMAL if self.transformation_applied else tk.DISABLED
        )

    def calculate_route_bounds(self):
        """Calculate and display route bounds"""
        try:
            if not self.routes_loaded:
                messagebox.showwarning("No Routes", "No routes loaded to calculate bounds for")
                return

            # Get routes from route manager
            if not hasattr(self.route_manager, 'routes') or not self.route_manager.routes:
                messagebox.showwarning("No Routes", "No route data available")
                return

            # Calculate bounds using transformer service
            bounds = self.route_transformer.calculate_route_bounds(self.route_manager.routes)

            if bounds:
                self.log(f"Route bounds: {bounds['width']:.1f}×{bounds['height']:.1f}mm at ({bounds['center_x']:.1f}, {bounds['center_y']:.1f})")
            else:
                messagebox.showerror("Calculation Error", "Failed to calculate route bounds")

        except Exception as e:
            error_msg = f"Failed to calculate route bounds: {e}"
            self.log(error_msg, "error")
            messagebox.showerror("Error", error_msg)

    def apply_registration_transformation(self):
        """Apply registration transformation to loaded routes"""
        try:
            if not self.routes_loaded:
                messagebox.showwarning("No Routes", "No routes loaded to transform")
                return

            if not self.registration_available:
                messagebox.showwarning("No Registration", "No registration data available")
                return

            # Confirm action
            if not messagebox.askyesno("Apply Transformation",
                                     "Apply registration transformation to routes?\n"
                                     "This will modify the route coordinates."):
                return

            # Get current routes
            original_routes = self.route_manager.routes
            if not original_routes:
                messagebox.showerror("Error", "No route data available")
                return

            # Apply transformation using transformer service
            transformed_routes = self.route_transformer.apply_registration_transformation(
                original_routes, self.registration_manager
            )

            if transformed_routes is not None:
                # Update route manager with transformed routes
                self.route_manager.routes = transformed_routes
                self.route_manager.emit(RouteEvents.ROUTES_TRANSFORMED, {
                    'source': 'registration_transformation',
                    'route_count': len(transformed_routes)
                })

                self.log("Registration transformation applied to routes successfully")
                messagebox.showinfo("Success", "Registration transformation applied successfully!")

            else:
                messagebox.showerror("Transformation Failed", "Failed to apply registration transformation")

        except Exception as e:
            error_msg = f"Failed to apply registration transformation: {e}"
            self.log(error_msg, "error")
            messagebox.showerror("Error", error_msg)

    def revert_to_original(self):
        """Revert routes to their original state"""
        try:
            if not self.transformation_applied:
                messagebox.showinfo("No Changes", "No transformation to revert")
                return

            # Confirm action
            if not messagebox.askyesno("Revert Transformation",
                                     "Revert routes to original coordinates?\n"
                                     "This will undo the transformation."):
                return

            # Reload routes from original file
            if hasattr(self.route_manager, 'current_file') and self.route_manager.current_file:
                success = self.route_manager.load_routes_from_svg(self.route_manager.current_file)
                if success:
                    self.transformation_applied = False
                    self.transformation_status_var.set("Reverted to original routes")
                    self.transform_status_label.config(foreground="blue")
                    self.log("Routes reverted to original state")
                    self._update_ui_state()
                    messagebox.showinfo("Success", "Routes reverted to original state")
                else:
                    messagebox.showerror("Error", "Failed to reload original routes")
            else:
                messagebox.showerror("Error", "No original route file available to revert to")

        except Exception as e:
            error_msg = f"Failed to revert routes: {e}"
            self.log(error_msg, "error")
            messagebox.showerror("Error", error_msg)