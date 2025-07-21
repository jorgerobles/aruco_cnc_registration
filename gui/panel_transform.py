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

        # Two transformation options
        transform_options_frame = ttk.Frame(self.frame)
        transform_options_frame.pack(fill=tk.X, padx=5, pady=5)

        self.apply_transform_btn = ttk.Button(
            transform_options_frame, text="Apply Registration Matrix",
            command=self.apply_registration_transformation
        )
        self.apply_transform_btn.pack(side=tk.LEFT, padx=(0,5))

        self.align_routes_btn = ttk.Button(
            transform_options_frame, text="Simple Alignment",
            command=self.apply_simple_alignment_transformation
        )
        self.align_routes_btn.pack(side=tk.LEFT, padx=(0,5))

        self.revert_transform_btn = ttk.Button(
            transform_options_frame, text="Revert to Original",
            command=self.revert_to_original
        )
        self.revert_transform_btn.pack(side=tk.LEFT)

        # Debug button
        debug_frame = ttk.Frame(self.frame)
        debug_frame.pack(fill=tk.X, padx=5, pady=2)

        self.debug_btn = ttk.Button(
            debug_frame, text="Debug Transformation Data",
            command=self.debug_transformation
        )
        self.debug_btn.pack(side=tk.LEFT)

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

        source = data.get('source', 'unknown')
        if source == 'simple_alignment_transformation':
            status_text = f"Simple alignment applied to {route_count} routes (centered on registration area)"
        elif source == 'registration_manager':
            status_text = f"Registration matrix applied to {route_count} routes (error: {reg_error:.3f}mm)"
        else:
            status_text = f"Transformation applied to {route_count} routes"

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

        # Debug button - enabled when registration is available
        self.debug_btn.config(
            state=tk.NORMAL if self.registration_available else tk.DISABLED
        )

        # Both transformation buttons - enabled when routes loaded and registration available
        transform_enabled = self.routes_loaded and self.registration_available and not self.transformation_applied

        self.apply_transform_btn.config(state=tk.NORMAL if transform_enabled else tk.DISABLED)
        self.align_routes_btn.config(state=tk.NORMAL if transform_enabled else tk.DISABLED)

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
        """Apply registration transformation matrix to loaded routes"""
        try:
            if not self.routes_loaded:
                messagebox.showwarning("No Routes", "No routes loaded to transform")
                return

            if not self.registration_available:
                messagebox.showwarning("No Registration", "No registration data available")
                return

            # Confirm action
            if not messagebox.askyesno("Apply Matrix Transformation",
                                     "Apply registration transformation matrix to routes?\n"
                                     "This uses the computed transformation matrix from calibration."):
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

    def apply_simple_alignment_transformation(self):
        """Apply simple alignment transformation to center routes on registration area"""
        try:
            if not self.routes_loaded:
                messagebox.showwarning("No Routes", "No routes loaded to transform")
                return

            if not self.registration_available:
                messagebox.showwarning("No Registration", "No registration data available")
                return

            # Confirm action
            if not messagebox.askyesno("Apply Simple Alignment",
                                     "Apply simple alignment transformation to routes?\n"
                                     "This will center the routes on the registration area."):
                return

            # Get current routes
            original_routes = self.route_manager.routes
            if not original_routes:
                messagebox.showerror("Error", "No route data available")
                return

            # Apply simple alignment transformation using transformer service
            transformed_routes = self.route_transformer.calculate_simple_alignment_transformation(
                original_routes, self.registration_manager
            )

            if transformed_routes is not None:
                # Update route manager with transformed routes
                self.route_manager.routes = transformed_routes
                self.route_manager.emit(RouteEvents.ROUTES_TRANSFORMED, {
                    'source': 'simple_alignment_transformation',
                    'route_count': len(transformed_routes)
                })

                self.log("Simple alignment transformation applied to routes successfully")
                messagebox.showinfo("Success", "Simple alignment transformation applied successfully!")

            else:
                messagebox.showerror("Transformation Failed", "Failed to apply simple alignment transformation")

        except Exception as e:
            error_msg = f"Failed to apply simple alignment transformation: {e}"
            self.log(error_msg, "error")
            messagebox.showerror("Error", error_msg)

    def debug_transformation(self):
        """Show debug information about transformation data"""
        try:
            if not self.registration_available:
                messagebox.showwarning("No Registration", "No registration data to debug")
                return

            # Get debug information
            debug_info = self.route_transformer.debug_transformation_data(self.registration_manager)

            # Create debug window
            debug_window = tk.Toplevel(self.frame)
            debug_window.title("Transformation Debug Info")
            debug_window.geometry("600x400")

            # Add scrollable text widget
            text_frame = ttk.Frame(debug_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            text_widget = tk.Text(text_frame, wrap=tk.WORD)
            scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)

            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Format debug information
            debug_text = "TRANSFORMATION DEBUG INFORMATION\n"
            debug_text += "=" * 50 + "\n\n"

            debug_text += f"Registration Status: {'REGISTERED' if debug_info['is_registered'] else 'NOT REGISTERED'}\n"
            debug_text += f"Calibration Points: {debug_info['point_count']}\n\n"

            if debug_info['is_registered']:
                debug_text += f"Registration Error: {debug_info['registration_error']:.4f} mm\n\n"

                debug_text += "TRANSFORMATION MATRIX:\n"
                if debug_info['transformation_matrix']:
                    matrix = debug_info['transformation_matrix']
                    for row in matrix:
                        debug_text += f"  [{', '.join(f'{val:8.4f}' for val in row)}]\n"
                debug_text += "\n"

                debug_text += "TRANSLATION VECTOR:\n"
                if debug_info['translation_vector']:
                    vector = debug_info['translation_vector']
                    debug_text += f"  [{', '.join(f'{val:8.4f}' for val in vector)}]\n\n"

                debug_text += "MACHINE POSITIONS (Registration Points):\n"
                for i, pos in enumerate(debug_info['machine_positions'], 1):
                    debug_text += f"  Point {i}: ({pos[0]:8.3f}, {pos[1]:8.3f}, {pos[2]:8.3f})\n"
                debug_text += "\n"

                debug_text += "CAMERA POSITIONS:\n"
                for i, pos in enumerate(debug_info['camera_positions'], 1):
                    debug_text += f"  Point {i}: ({pos[0]:8.3f}, {pos[1]:8.3f}, {pos[2]:8.3f})\n"
                debug_text += "\n"

                if 'machine_bounds' in debug_info:
                    mb = debug_info['machine_bounds']
                    debug_text += "MACHINE COORDINATE BOUNDS:\n"
                    debug_text += f"  X: {mb['x_min']:8.3f} to {mb['x_max']:8.3f} (center: {mb['center_x']:8.3f})\n"
                    debug_text += f"  Y: {mb['y_min']:8.3f} to {mb['y_max']:8.3f} (center: {mb['center_y']:8.3f})\n\n"

                if 'camera_bounds' in debug_info:
                    cb = debug_info['camera_bounds']
                    debug_text += "CAMERA COORDINATE BOUNDS:\n"
                    debug_text += f"  X: {cb['x_min']:8.3f} to {cb['x_max']:8.3f} (center: {cb['center_x']:8.3f})\n"
                    debug_text += f"  Y: {cb['y_min']:8.3f} to {cb['y_max']:8.3f} (center: {cb['center_y']:8.3f})\n\n"

                # Add simple alignment transformation analysis
                if 'alignment_analysis' in debug_info:
                    aa = debug_info['alignment_analysis']
                    debug_text += "SIMPLE ALIGNMENT ANALYSIS:\n"
                    debug_text += f"  Registration Center: ({aa['registration_center'][0]:8.3f}, {aa['registration_center'][1]:8.3f})\n"
                    rab = aa['registration_area_bounds']
                    debug_text += f"  Registration Area: {rab['width']:8.1f}×{rab['height']:8.1f}mm\n"
                    debug_text += f"  Registration Bounds: ({rab['x_min']:8.1f}, {rab['y_min']:8.1f}) to ({rab['x_max']:8.1f}, {rab['y_max']:8.1f})\n\n"

            # Add route information if available
            if hasattr(self, 'current_bounds') and self.current_bounds:
                debug_text += "CURRENT ROUTE BOUNDS:\n"
                rb = self.current_bounds
                debug_text += f"  X: {rb['x_min']:8.3f} to {rb['x_max']:8.3f} (center: {rb['center_x']:8.3f})\n"
                debug_text += f"  Y: {rb['y_min']:8.3f} to {rb['y_max']:8.3f} (center: {rb['center_y']:8.3f})\n"
                debug_text += f"  Size: {rb['width']:8.3f} × {rb['height']:8.3f} mm\n"

            text_widget.insert(tk.END, debug_text)
            text_widget.config(state=tk.DISABLED)

            self.log("Debug information displayed")

        except Exception as e:
            error_msg = f"Failed to show debug information: {e}"
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