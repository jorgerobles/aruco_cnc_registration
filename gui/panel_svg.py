# Simplified panel_svg.py - Only route loading functionality

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional

from services.camera_manager import CameraEvents
from services.event_broker import (event_aware, event_handler, EventPriority)
from services.registration_manager import RegistrationEvents


@event_aware()
class SVGRoutesPanel:
    """Simplified SVG Routes panel with only loading functionality"""

    def __init__(self, parent, routes_overlay, grbl_controller=None, logger: Optional[Callable] = None):
        self.routes_overlay = routes_overlay
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

    # Event handlers using decorators
    @event_handler(CameraEvents.CONNECTED)
    def _on_camera_connected(self, success: bool):
        """Handle camera connection events"""
        self.camera_connected = success
        if success:
            self.log("Camera connected - SVG overlay available")

    @event_handler(CameraEvents.DISCONNECTED)
    def _on_camera_disconnected(self):
        """Handle camera disconnection events"""
        self.camera_connected = False
        self.log("Camera disconnected - SVG overlay unavailable")

    @event_handler(RegistrationEvents.COMPUTED, EventPriority.HIGH)
    def _on_registration_computed(self, computation_data: dict):
        """Handle registration computation events"""
        self.registration_available = True
        error = computation_data.get('error', 0.0)
        self.log(f"Registration computed - SVG overlay updated (error: {error:.4f})")

    @event_handler(RegistrationEvents.CLEARED)
    def _on_registration_cleared(self):
        """Handle registration cleared events"""
        self.registration_available = False
        self.log("Registration cleared")

    def _setup_widgets(self):
        """Setup simplified SVG routes control widgets"""

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

    def load_svg_routes(self):
        """Load SVG routes file"""
        filename = filedialog.askopenfilename(
            title="Load SVG Routes",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]
        )

        if filename:
            try:
                # Load routes into overlay
                self.routes_overlay.load_routes_from_svg(filename)

                # Update state and UI
                self.routes_loaded = True
                self.update_svg_info()

                self.log(f"Loaded SVG routes from: {filename}")

            except Exception as e:
                self.log(f"Failed to load SVG routes: {e}", "error")
                messagebox.showerror("Error", f"Failed to load SVG routes: {e}")

    def clear_svg_routes(self):
        """Clear all SVG routes"""
        self.routes_overlay.clear_routes()
        self.routes_loaded = False
        self.update_svg_info()
        self.log("SVG routes cleared")

    def update_svg_info(self):
        """Update SVG routes information display"""
        try:
            count = self.routes_overlay.get_routes_count()
            bounds = self.routes_overlay.get_route_bounds()

            if count > 0:
                info_text = f"{count} routes loaded"
                if bounds:
                    width = bounds[2] - bounds[0]
                    height = bounds[3] - bounds[1]
                    info_text += f"\nSize: {width:.1f}×{height:.1f}mm"

                    # Add total length if available
                    if hasattr(self.routes_overlay, 'get_total_route_length'):
                        total_length = self.routes_overlay.get_total_route_length()
                        info_text += f"\nLength: {total_length:.1f}mm"

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
            return self.routes_overlay.get_routes_count() if self.routes_loaded else 0
        except Exception:
            return 0

    def refresh_overlay(self):
        """Refresh the overlay display and information"""
        try:
            if self.routes_loaded:
                self.update_svg_info()

                # Refresh transformation if registration has changed
                if hasattr(self.routes_overlay, 'refresh_transformation'):
                    self.routes_overlay.refresh_transformation()

                self.log("SVG overlay refreshed")

        except Exception as e:
            self.log(f"Error refreshing overlay: {e}", "error")

    def get_panel_status(self):
        """Get current panel status for external queries"""
        try:
            return {
                'routes_loaded': self.routes_loaded,
                'routes_count': self.get_routes_count(),
                'camera_connected': self.camera_connected,
                'registration_available': self.registration_available
            }
        except Exception as e:
            self.log(f"Error getting panel status: {e}", "error")
            return {'error': str(e)}