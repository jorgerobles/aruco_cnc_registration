"""
Route Transformation Panel - Completely Rewritten
Clean implementation using intermediate RouteTransformationService
Follows SOLID principles with proper separation of concerns
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable

from services.event_broker import event_aware, event_handler, EventPriority
from services.routes_manager import RouteEvents
from services.registration_manager import RegistrationEvents
from services.route_transformation_service import RouteTransformationService, RouteTransformationEvents


@event_aware()
class RouteTransformationPanel:
    """
    GUI Panel for route transformations using intermediate service
    Handles only UI concerns and delegates business logic to service
    """

    def __init__(self, parent, route_manager, registration_manager, logger: Optional[Callable] = None):
        self.route_manager = route_manager
        self.registration_manager = registration_manager
        self.transformation_service = RouteTransformationService(route_manager, registration_manager, logger)
        self.logger = logger

        # UI State
        self.routes_available = False
        self.registration_available = False
        self.bounds_calculated = False
        self.transformation_applied = False

        # Current data
        self.current_bounds = None
        self.original_routes = None
        self.transformed_routes = None

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Route Transformation")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # UI Variables
        self.routes_status_var = tk.StringVar(value="No routes loaded")
        self.registration_status_var = tk.StringVar(value="No registration computed")
        self.bounds_status_var = tk.StringVar(value="No bounds calculated")
        self.transform_status_var = tk.StringVar(value="Ready for transformation")

        self._create_widgets()
        self._check_initial_state()
        self._update_ui_state()

        self.log("Route Transformation Panel initialized")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[TransformPanel] {message}", level)

    def _create_widgets(self):
        """Create all UI widgets"""
        # Status Section
        status_frame = ttk.LabelFrame(self.frame, text="Status")
        status_frame.pack(fill=tk.X, pady=5, padx=5)

        # Routes status
        ttk.Label(status_frame, text="Routes:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.routes_status_label = ttk.Label(status_frame, textvariable=self.routes_status_var, foreground="gray")
        self.routes_status_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        # Registration status
        ttk.Label(status_frame, text="Registration:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.registration_status_label = ttk.Label(status_frame, textvariable=self.registration_status_var, foreground="gray")
        self.registration_status_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        # Bounds status
        ttk.Label(status_frame, text="Bounds:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.bounds_status_label = ttk.Label(status_frame, textvariable=self.bounds_status_var, foreground="gray")
        self.bounds_status_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        # Transform status
        ttk.Label(status_frame, text="Transform:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.transform_status_label = ttk.Label(status_frame, textvariable=self.transform_status_var, foreground="blue")
        self.transform_status_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        # Actions Section
        actions_frame = ttk.LabelFrame(self.frame, text="Actions")
        actions_frame.pack(fill=tk.X, pady=5, padx=5)

        # Button row 1: Analysis
        btn_row1 = ttk.Frame(actions_frame)
        btn_row1.pack(fill=tk.X, pady=2)

        self.calculate_bounds_btn = ttk.Button(btn_row1, text="Calculate Bounds",
                                             command=self.calculate_bounds)
        self.calculate_bounds_btn.pack(side=tk.LEFT, padx=2)

        self.show_statistics_btn = ttk.Button(btn_row1, text="Show Statistics",
                                            command=self.show_statistics)
        self.show_statistics_btn.pack(side=tk.LEFT, padx=2)

        # Button row 2: Transformation
        btn_row2 = ttk.Frame(actions_frame)
        btn_row2.pack(fill=tk.X, pady=2)

        self.apply_registration_btn = ttk.Button(btn_row2, text="Apply Registration Transform",
                                               command=self.apply_registration_transformation)
        self.apply_registration_btn.pack(side=tk.LEFT, padx=2)

        self.manual_transform_btn = ttk.Button(btn_row2, text="Manual Transform",
                                             command=self.show_manual_transform_dialog)
        self.manual_transform_btn.pack(side=tk.LEFT, padx=2)

        # Button row 3: Utilities
        btn_row3 = ttk.Frame(actions_frame)
        btn_row3.pack(fill=tk.X, pady=2)

        self.revert_btn = ttk.Button(btn_row3, text="Revert Transform",
                                   command=self.revert_transformation)
        self.revert_btn.pack(side=tk.LEFT, padx=2)

        self.clear_btn = ttk.Button(btn_row3, text="Clear All",
                                  command=self.clear_all)
        self.clear_btn.pack(side=tk.LEFT, padx=2)

    def _check_initial_state(self):
        """Check initial state of routes and registration"""
        # Check routes
        if hasattr(self.route_manager, 'is_loaded') and self.route_manager.is_loaded():
            self.routes_available = True
            route_count = self.route_manager.get_routes_count()
            self.routes_status_var.set(f"{route_count} routes loaded")
            self.routes_status_label.config(foreground="green")
            self.log(f"Found {route_count} routes already loaded")

        # Check registration
        if hasattr(self.registration_manager, 'is_registered') and self.registration_manager.is_registered():
            self.registration_available = True
            point_count = self.registration_manager.get_calibration_points_count()
            error = self.registration_manager.get_registration_error() or 0.0
            self.registration_status_var.set(f"Registered ({point_count} points, error: {error:.3f}mm)")
            self.registration_status_label.config(foreground="green")
            self.log(f"Found registration with {point_count} points, error: {error:.3f}mm")

    # Event Handlers for Route Manager
    @event_handler(RouteEvents.ROUTES_LOADED, EventPriority.HIGH)
    def _on_routes_loaded(self, data: dict):
        """Handle routes loaded event"""
        self.routes_available = True
        self.transformation_applied = False
        self.bounds_calculated = False

        route_count = data.get('route_count', 0)
        self.routes_status_var.set(f"{route_count} routes loaded")
        self.routes_status_label.config(foreground="green")

        self.bounds_status_var.set("Bounds not calculated")
        self.bounds_status_label.config(foreground="gray")

        self.transform_status_var.set("Ready for transformation")
        self.transform_status_label.config(foreground="blue")

        self.log(f"Routes loaded: {route_count} routes")
        self._update_ui_state()

    @event_handler(RouteEvents.ROUTES_CLEARED, EventPriority.HIGH)
    def _on_routes_cleared(self):
        """Handle routes cleared event"""
        self.routes_available = False
        self.transformation_applied = False
        self.bounds_calculated = False
        self.current_bounds = None

        self.routes_status_var.set("No routes loaded")
        self.routes_status_label.config(foreground="gray")

        self.bounds_status_var.set("No bounds calculated")
        self.bounds_status_label.config(foreground="gray")

        self.transform_status_var.set("No routes to transform")
        self.transform_status_label.config(foreground="gray")

        self.log("Routes cleared")
        self._update_ui_state()

    # Event Handlers for Registration Manager
    @event_handler([RegistrationEvents.COMPUTED, RegistrationEvents.LOADED], EventPriority.HIGH)
    def _on_registration_computed(self, data: dict):
        """Handle registration computed event"""
        self.registration_available = True

        point_count = data.get('point_count', 0)
        error = data.get('error', 0.0)
        self.registration_status_var.set(f"Registered ({point_count} points, error: {error:.3f}mm)")
        self.registration_status_label.config(foreground="green")

        self.log(f"Registration computed: {point_count} points, error: {error:.3f}mm")
        self._update_ui_state()



    @event_handler(RegistrationEvents.CLEARED, EventPriority.HIGH)
    def _on_registration_cleared(self, data: dict):
        """Handle registration cleared event"""
        self.registration_available = False

        self.registration_status_var.set("No registration computed")
        self.registration_status_label.config(foreground="gray")

        self.log("Registration cleared")
        self._update_ui_state()

    # Event Handlers for Transformation Service
    @event_handler(RouteTransformationEvents.BOUNDS_CALCULATED, EventPriority.HIGH)
    def _on_bounds_calculated(self, data: dict):
        """Handle bounds calculated event"""
        self.bounds_calculated = True
        self.current_bounds = data['bounds']

        bounds = self.current_bounds
        bounds_text = (f"Size: {bounds['width']:.1f}×{bounds['height']:.1f}mm, "
                      f"Center: ({bounds['center_x']:.1f}, {bounds['center_y']:.1f})")

        self.bounds_status_var.set(bounds_text)
        self.bounds_status_label.config(foreground="blue")

        self.log(f"Bounds calculated: {bounds_text}")
        self._update_ui_state()

    @event_handler(RouteTransformationEvents.TRANSFORMATION_APPLIED, EventPriority.HIGH)
    def _on_transformation_applied(self, data: dict):
        """Handle transformation applied event"""
        self.transformation_applied = True

        source = data.get('source', 'unknown')
        route_count = data.get('route_count', 0)
        reg_error = data.get('registration_error', 0.0)

        if source == 'registration_transformation':
            status_text = f"Registration transform applied ({route_count} routes, error: {reg_error:.3f}mm)"
        elif source == 'manual_transformation':
            status_text = f"Manual transform applied ({route_count} routes)"
        else:
            status_text = f"Transform applied ({route_count} routes)"

        self.transform_status_var.set(status_text)
        self.transform_status_label.config(foreground="green")

        self.log(f"Transformation applied: {status_text}")
        self._update_ui_state()

    @event_handler(RouteTransformationEvents.ERROR, EventPriority.HIGH)
    def _on_transformation_error(self, error_message: str):
        """Handle transformation service errors"""
        self.transform_status_var.set(f"Error: {error_message}")
        self.transform_status_label.config(foreground="red")

        self.log(f"Transformation error: {error_message}", "error")
        messagebox.showerror("Transformation Error", error_message)

    def _update_ui_state(self):
        """Update button states based on current state"""
        # Calculate bounds - enabled when routes available
        self.calculate_bounds_btn.config(state=tk.NORMAL if self.routes_available else tk.DISABLED)

        # Show statistics - enabled when routes available
        self.show_statistics_btn.config(state=tk.NORMAL if self.routes_available else tk.DISABLED)

        # Registration transform - enabled when both routes and registration available, not already transformed
        reg_transform_enabled = (self.routes_available and
                                self.registration_available and
                                not self.transformation_applied)
        self.apply_registration_btn.config(state=tk.NORMAL if reg_transform_enabled else tk.DISABLED)

        # Manual transform - enabled when routes available, not already transformed
        manual_transform_enabled = self.routes_available and not self.transformation_applied
        self.manual_transform_btn.config(state=tk.NORMAL if manual_transform_enabled else tk.DISABLED)

        # Revert - enabled when transformation applied
        self.revert_btn.config(state=tk.NORMAL if self.transformation_applied else tk.DISABLED)

        # Clear - always enabled
        self.clear_btn.config(state=tk.NORMAL)

    # Action Methods
    def calculate_bounds(self):
        """Calculate and display route bounds"""
        try:
            if not self.routes_available:
                messagebox.showwarning("No Routes", "No routes loaded to calculate bounds for")
                return

            routes = self.route_manager.get_routes()
            if not routes:
                messagebox.showerror("No Data", "No route data available")
                return

            # Use service to calculate bounds (will emit event)
            bounds = self.transformation_service.calculate_route_bounds(routes)

            if not bounds:
                messagebox.showerror("Calculation Failed", "Could not calculate route bounds")

        except Exception as e:
            error_msg = f"Failed to calculate bounds: {e}"
            self.log(error_msg, "error")
            messagebox.showerror("Error", error_msg)

    def show_statistics(self):
        """Show detailed route statistics"""
        try:
            if not self.routes_available:
                messagebox.showwarning("No Routes", "No routes loaded")
                return

            routes = self.route_manager.get_routes()
            if not routes:
                messagebox.showerror("No Data", "No route data available")
                return

            # Get statistics from service
            stats = self.transformation_service.get_route_statistics(routes)

            if 'error' in stats:
                messagebox.showerror("Statistics Error", stats['error'])
                return

            # Format statistics message
            stats_msg = (
                f"Route Statistics:\n\n"
                f"• Routes: {stats['route_count']}\n"
                f"• Total Points: {stats['total_points']}\n"
                f"• Total Length: {stats['total_length']:.2f}mm\n"
                f"• Average Route Length: {stats['average_route_length']:.2f}mm\n"
            )

            if stats['bounds']:
                bounds = stats['bounds']
                stats_msg += (
                    f"\nBounds:\n"
                    f"• Size: {bounds['width']:.1f} × {bounds['height']:.1f}mm\n"
                    f"• Center: ({bounds['center_x']:.1f}, {bounds['center_y']:.1f})\n"
                    f"• Range: X[{bounds['x_min']:.1f}, {bounds['x_max']:.1f}] "
                    f"Y[{bounds['y_min']:.1f}, {bounds['y_max']:.1f}]"
                )

            messagebox.showinfo("Route Statistics", stats_msg)

        except Exception as e:
            error_msg = f"Failed to get statistics: {e}"
            self.log(error_msg, "error")
            messagebox.showerror("Error", error_msg)

    def apply_registration_transformation(self):
        """Apply registration-based transformation"""
        try:
            if not self.routes_available:
                messagebox.showwarning("No Routes", "No routes loaded to transform")
                return

            if not self.registration_available:
                messagebox.showwarning("No Registration", "No registration computed")
                return

            # Confirm transformation
            if not messagebox.askyesno("Apply Registration Transform",
                                     "Apply registration-based transformation to routes?\n"
                                     "This will transform routes using the computed camera-to-machine registration."):
                return

            # Store original routes for potential revert
            self.original_routes = self.route_manager.get_routes()

            # Apply transformation using service
            transformed_routes = self.transformation_service.apply_registration_transformation(
                self.original_routes, self.registration_manager)

            if transformed_routes:
                # Update route manager with transformed routes
                self.route_manager.routes = transformed_routes
                self.transformed_routes = transformed_routes

                # Emit routes transformed event
                self.route_manager.emit(RouteEvents.ROUTES_TRANSFORMED, {
                    'source': 'registration_transformation',
                    'route_count': len(transformed_routes)
                })

                messagebox.showinfo("Success", "Registration transformation applied successfully!")
            else:
                messagebox.showerror("Transformation Failed", "Could not apply registration transformation")

        except Exception as e:
            error_msg = f"Failed to apply registration transformation: {e}"
            self.log(error_msg, "error")
            messagebox.showerror("Error", error_msg)

    def show_manual_transform_dialog(self):
        """Show dialog for manual transformation with 3 destination points"""
        try:
            if not self.routes_available:
                messagebox.showwarning("No Routes", "No routes loaded to transform")
                return

            # Create dialog
            dialog = tk.Toplevel(self.frame)
            dialog.title("Manual Transformation")
            dialog.geometry("400x250")
            dialog.transient(self.frame.winfo_toplevel())
            dialog.grab_set()

            # Instructions
            ttk.Label(dialog, text="Enter 3 destination points for transformation:",
                     font=('Arial', 10, 'bold')).pack(pady=10)

            ttk.Label(dialog, text="Points should form a triangle in machine coordinates (mm)",
                     font=('Arial', 9)).pack(pady=5)

            # Point entry frame
            points_frame = ttk.Frame(dialog)
            points_frame.pack(pady=10)

            # Create entry fields for 3 points
            point_vars = []
            for i in range(3):
                row_frame = ttk.Frame(points_frame)
                row_frame.pack(pady=2)

                ttk.Label(row_frame, text=f"Point {i+1}:", width=8).pack(side=tk.LEFT)

                x_var = tk.StringVar(value="0.0")
                y_var = tk.StringVar(value="0.0")

                ttk.Label(row_frame, text="X:").pack(side=tk.LEFT, padx=(5, 2))
                ttk.Entry(row_frame, textvariable=x_var, width=8).pack(side=tk.LEFT, padx=2)

                ttk.Label(row_frame, text="Y:").pack(side=tk.LEFT, padx=(5, 2))
                ttk.Entry(row_frame, textvariable=y_var, width=8).pack(side=tk.LEFT, padx=2)

                point_vars.append((x_var, y_var))

            # Buttons
            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(pady=20)

            def apply_manual_transform():
                try:
                    # Parse destination points
                    destination_points = []
                    for i, (x_var, y_var) in enumerate(point_vars):
                        try:
                            x = float(x_var.get())
                            y = float(y_var.get())
                            destination_points.append((x, y))
                        except ValueError:
                            messagebox.showerror("Invalid Input", f"Invalid coordinates for point {i+1}")
                            return

                    # Store original routes
                    self.original_routes = self.route_manager.get_routes()

                    # Apply transformation
                    transformed_routes = self.transformation_service.apply_manual_transformation(
                        self.original_routes, destination_points)

                    if transformed_routes:
                        # Update route manager
                        self.route_manager.routes = transformed_routes
                        self.transformed_routes = transformed_routes

                        # Emit event
                        self.route_manager.emit(RouteEvents.ROUTES_TRANSFORMED, {
                            'source': 'manual_transformation',
                            'route_count': len(transformed_routes)
                        })

                        dialog.destroy()
                        messagebox.showinfo("Success", "Manual transformation applied successfully!")
                    else:
                        messagebox.showerror("Transformation Failed", "Could not apply manual transformation")

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to apply transformation: {e}")

            ttk.Button(btn_frame, text="Apply", command=apply_manual_transform).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            error_msg = f"Failed to show manual transform dialog: {e}"
            self.log(error_msg, "error")
            messagebox.showerror("Error", error_msg)

    def revert_transformation(self):
        """Revert to original routes before transformation"""
        try:
            if not self.transformation_applied:
                messagebox.showinfo("No Transformation", "No transformation has been applied")
                return

            if not self.original_routes:
                messagebox.showerror("Cannot Revert", "Original routes not available")
                return

            # Confirm revert
            if not messagebox.askyesno("Revert Transformation",
                                     "Revert to original routes before transformation?"):
                return

            # Restore original routes
            self.route_manager.routes = self.original_routes
            self.transformation_applied = False
            self.transformed_routes = None

            # Update UI
            self.transform_status_var.set("Transformation reverted")
            self.transform_status_label.config(foreground="blue")

            # Emit event
            self.route_manager.emit(RouteEvents.ROUTES_TRANSFORMED, {
                'source': 'revert_transformation',
                'route_count': len(self.original_routes)
            })

            self.log("Transformation reverted to original routes")
            self._update_ui_state()
            messagebox.showinfo("Success", "Routes reverted to original state")

        except Exception as e:
            error_msg = f"Failed to revert transformation: {e}"
            self.log(error_msg, "error")
            messagebox.showerror("Error", error_msg)

    def clear_all(self):
        """Clear all transformation data"""
        try:
            if not messagebox.askyesno("Clear All",
                                     "Clear all transformation data?\n"
                                     "This will reset the transformation state but keep loaded routes."):
                return

            # Reset transformation state
            self.transformation_applied = False
            self.bounds_calculated = False
            self.current_bounds = None
            self.original_routes = None
            self.transformed_routes = None

            # Update UI
            self.bounds_status_var.set("Bounds not calculated")
            self.bounds_status_label.config(foreground="gray")

            self.transform_status_var.set("Ready for transformation")
            self.transform_status_label.config(foreground="blue")

            self.log("Transformation state cleared")
            self._update_ui_state()
            messagebox.showinfo("Success", "Transformation state cleared")

        except Exception as e:
            error_msg = f"Failed to clear transformation state: {e}"
            self.log(error_msg, "error")
            messagebox.showerror("Error", error_msg)