# Updated panel_svg.py - Works with RoutesService

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional

from services.event_broker import (event_aware, event_handler, EventPriority)
from services.registration_manager import RegistrationEvents
from services.routes_manager import RouteEvents


@event_aware()
class SVGRoutesPanel:
    """SVG Routes panel that works with RoutesService"""

    def __init__(self, parent, routes_service, grbl_controller=None, logger: Optional[Callable] = None):
        self.routes_service = routes_service  # Changed from routes_overlay to routes_service
        self.grbl_controller = grbl_controller
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="SVG Routes")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # State tracking
        self.routes_loaded = False
        self.camera_connected = False
        self.registration_available = False

        self._setup_widgets()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    @event_handler(RegistrationEvents.COMPUTED, EventPriority.HIGH)
    def _on_registration_computed(self, computation_data: dict):
        """Handle registration computation events"""
        self.registration_available = True
        error = computation_data.get('error', 0.0)
        self.log(f"Registration computed - SVG routes can be transformed (error: {error:.4f})")

    @event_handler(RegistrationEvents.CLEARED)
    def _on_registration_cleared(self):
        """Handle registration cleared events"""
        self.registration_available = False
        self.log("Registration cleared")

    # Listen to routes service events
    @event_handler(RouteEvents.ROUTES_LOADED)
    def _on_routes_loaded(self, data: dict):
        """Handle routes loaded event from service"""
        self.routes_loaded = True
        self.update_svg_info()
        self.log(f"Routes loaded: {data.get('route_count', 0)} routes")

    @event_handler(RouteEvents.ROUTES_CLEARED)
    def _on_routes_cleared(self):
        """Handle routes cleared event from service"""
        self.routes_loaded = False
        self.update_svg_info()
        self.log("Routes cleared")

    def _setup_widgets(self):
        """Setup SVG routes control widgets"""

        # File management
        file_frame = ttk.Frame(self.frame)
        file_frame.pack(fill=tk.X, pady=2)

        ttk.Button(file_frame, text="Load SVG Routes",
                   command=self.load_svg_routes).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="Clear Routes",
                   command=self.clear_svg_routes).pack(side=tk.LEFT, padx=2)

        # Routes info display
        self.svg_info_var = tk.StringVar(value="No routes loaded")
        self.svg_info_label = ttk.Label(self.frame, textvariable=self.svg_info_var,
                                        foreground="gray")
        self.svg_info_label.pack(pady=2)

        # Export options
        export_frame = ttk.Frame(self.frame)
        export_frame.pack(fill=tk.X, pady=2)

        ttk.Button(export_frame, text="Export G-code",
                   command=self.export_gcode).pack(side=tk.LEFT, padx=2)

    def load_svg_routes(self):
        """Load SVG routes file"""
        filename = filedialog.askopenfilename(
            title="Load SVG Routes",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]
        )

        if filename:
            try:
                # Load routes into service
                success = self.routes_service.load_routes_from_svg(filename)

                if success:
                    # Update state and UI
                    self.routes_loaded = True
                    self.update_svg_info()
                    self.log(f"Loaded SVG routes from: {filename}")
                else:
                    messagebox.showerror("Error", "Failed to load SVG routes")

            except Exception as e:
                self.log(f"Failed to load SVG routes: {e}", "error")
                messagebox.showerror("Error", f"Failed to load SVG routes: {e}")

    def clear_svg_routes(self):
        """Clear all SVG routes"""
        self.routes_service.clear_routes()
        self.routes_loaded = False
        self.update_svg_info()
        self.log("SVG routes cleared")

    def export_gcode(self):
        """Export routes to G-code"""
        if not self.routes_loaded or not self.routes_service.is_loaded():
            messagebox.showwarning("Warning", "No routes loaded to export")
            return

        filename = filedialog.asksaveasfilename(
            title="Export G-code",
            defaultextension=".gcode",
            filetypes=[("G-code files", "*.gcode"), ("Text files", "*.txt"), ("All files", "*.*")]
        )

        if filename:
            try:
                # Get feed rate from user (simple dialog)
                feed_rate = self._get_feed_rate()
                if feed_rate is None:
                    return

                success = self.routes_service.export_routes_to_gcode(filename, feed_rate)

                if success:
                    messagebox.showinfo("Success", f"G-code exported to: {filename}")
                    self.log(f"G-code exported to: {filename}")
                else:
                    messagebox.showerror("Error", "Failed to export G-code")

            except Exception as e:
                self.log(f"Failed to export G-code: {e}", "error")
                messagebox.showerror("Error", f"Failed to export G-code: {e}")

    def _get_feed_rate(self) -> Optional[float]:
        """Get feed rate from user"""
        dialog = tk.Toplevel()
        dialog.title("Export Settings")
        dialog.geometry("300x150")
        dialog.transient()
        dialog.grab_set()

        result = {"feed_rate": None}

        # Feed rate input
        ttk.Label(dialog, text="Feed Rate (mm/min):").pack(pady=10)
        feed_var = tk.StringVar(value="1000")
        feed_entry = ttk.Entry(dialog, textvariable=feed_var)
        feed_entry.pack(pady=5)
        feed_entry.focus()

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        def on_ok():
            try:
                result["feed_rate"] = float(feed_var.get())
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Invalid feed rate")

        def on_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)

        # Handle Enter key
        feed_entry.bind('<Return>', lambda e: on_ok())

        dialog.wait_window()
        return result["feed_rate"]

    def update_svg_info(self):
        """Update SVG routes information display"""
        try:
            if self.routes_service.is_loaded():
                route_info = self.routes_service.get_route_info()

                info_text = f"{route_info['route_count']} routes loaded"

                if route_info['bounds']:
                    bounds = route_info['bounds']
                    width = bounds[2] - bounds[0]
                    height = bounds[3] - bounds[1]
                    info_text += f"\nSize: {width:.1f}×{height:.1f}mm"

                if route_info['total_length'] > 0:
                    info_text += f"\nLength: {route_info['total_length']:.1f}mm"

                if route_info['point_count'] > 0:
                    info_text += f"\nPoints: {route_info['point_count']}"

                self.svg_info_var.set(info_text)
                self.svg_info_label.config(foreground="green")
            else:
                self.svg_info_var.set("No routes loaded")
                self.svg_info_label.config(foreground="gray")

        except Exception as e:
            self.log(f"Error updating SVG info: {e}", "error")
            self.svg_info_var.set("Error getting route info")
            self.svg_info_label.config(foreground="red")

    def get_routes_count(self) -> int:
        """Get number of loaded routes"""
        try:
            return self.routes_service.get_routes_count() if self.routes_loaded else 0
        except Exception:
            return 0

    def refresh_display(self):
        """Refresh the display and information"""
        try:
            if self.routes_loaded:
                self.update_svg_info()
                self.log("SVG panel refreshed")

        except Exception as e:
            self.log(f"Error refreshing display: {e}", "error")

    def get_panel_status(self):
        """Get current panel status for external queries"""
        try:
            return {
                'routes_loaded': self.routes_loaded,
                'routes_count': self.get_routes_count(),
                'camera_connected': self.camera_connected,
                'registration_available': self.registration_available,
                'routes_service_status': self.routes_service.get_service_status() if self.routes_service else None
            }
        except Exception as e:
            self.log(f"Error getting panel status: {e}", "error")
            return {'error': str(e)}
