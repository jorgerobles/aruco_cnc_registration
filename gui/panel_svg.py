# panel_svg.py - Complete SVG Routes panel with export functionality

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional

from services.event_broker import (event_aware, event_handler)
from services.routes_manager import RouteEvents


@event_aware()
class SVGRoutesPanel:
    """SVG Routes panel with load/export functionality"""

    def __init__(self, parent, routes_service, logger: Optional[Callable] = None):
        self.routes_service = routes_service  # RouteManager with export capability
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="SVG Routes")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # State tracking
        self.routes_loaded = False

        self._setup_widgets()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    # Event handlers
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

    @event_handler(RouteEvents.ROUTES_EXPORTED)
    def _on_routes_exported(self, data: dict):
        """Handle routes exported event"""
        self.log(f"Routes exported to: {data.get('output_file', 'unknown')}")

    def _setup_widgets(self):
        """Setup SVG routes control widgets"""

        # File management - Row 1
        file_frame = ttk.Frame(self.frame)
        file_frame.pack(fill=tk.X, pady=2)

        ttk.Button(file_frame, text="Load SVG Routes",
                   command=self.load_svg_routes).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="Clear Routes",
                   command=self.clear_svg_routes).pack(side=tk.LEFT, padx=2)

        # Export controls - Row 2
        export_frame = ttk.Frame(self.frame)
        export_frame.pack(fill=tk.X, pady=2)

        ttk.Button(export_frame, text="Export SVG Routes",
                   command=self.export_svg_routes).pack(side=tk.LEFT, padx=2)

        # Export options
        self.export_transformed_var = tk.BooleanVar()
        ttk.Checkbutton(export_frame, text="Use transformed",
                        variable=self.export_transformed_var).pack(side=tk.LEFT, padx=5)

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
                success = self.routes_service.load_routes_from_svg(filename)

                if success:
                    self.routes_loaded = True
                    self.update_svg_info()
                    self.log(f"Loaded SVG routes from: {filename}")
                else:
                    messagebox.showerror("Error", "Failed to load SVG routes")

            except Exception as e:
                self.log(f"Failed to load SVG routes: {e}", "error")
                messagebox.showerror("Error", f"Failed to load SVG routes: {e}")

    def export_svg_routes(self):
        """Export current routes to SVG file"""
        if not self.routes_loaded:
            messagebox.showwarning("Warning", "No routes loaded to export")
            return

        # Get export filename
        filename = filedialog.asksaveasfilename(
            title="Export SVG Routes",
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]
        )

        if filename:
            try:
                # Check if we should use transformed routes
                use_transformed = self.export_transformed_var.get()

                # Show export options dialog
                export_options = self._get_export_options()
                if export_options is None:
                    return  # User cancelled

                success = self.routes_service.export_routes_to_svg(
                    output_file=filename,
                    use_transformed=use_transformed,
                    **export_options
                )

                if success:
                    self.log(f"Exported SVG routes to: {filename}")
                    messagebox.showinfo("Success", f"Routes exported successfully to:\n{filename}")
                else:
                    messagebox.showerror("Error", "Failed to export SVG routes")

            except Exception as e:
                self.log(f"Failed to export SVG routes: {e}", "error")
                messagebox.showerror("Error", f"Failed to export SVG routes: {e}")

    def _get_export_options(self) -> Optional[dict]:
        """Show export options dialog and return selected options"""
        dialog = ExportOptionsDialog(self.frame)
        return dialog.show()

    def clear_svg_routes(self):
        """Clear all SVG routes"""
        self.routes_service.clear_routes()
        self.routes_loaded = False
        self.update_svg_info()
        self.log("SVG routes cleared")

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


class ExportOptionsDialog:
    """Export options dialog for SVG export settings"""

    def __init__(self, parent):
        self.parent = parent
        self.result = None

    def show(self) -> Optional[dict]:
        """Show dialog and return options or None if cancelled"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("SVG Export Options")
        self.dialog.geometry("350x280")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()  # Modal dialog

        # Center on parent
        self.dialog.transient(self.parent)

        self._create_widgets()

        # Wait for dialog to close
        self.dialog.wait_window()

        return self.result

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Dimensions
        dim_frame = ttk.LabelFrame(main_frame, text="Dimensions (leave empty for auto)")
        dim_frame.pack(fill=tk.X, pady=5)

        ttk.Label(dim_frame, text="Width (mm):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.width_var = tk.StringVar()
        ttk.Entry(dim_frame, textvariable=self.width_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(dim_frame, text="Height (mm):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.height_var = tk.StringVar()
        ttk.Entry(dim_frame, textvariable=self.height_var, width=10).grid(row=1, column=1, padx=5, pady=2)

        # Style options
        style_frame = ttk.LabelFrame(main_frame, text="Style Options")
        style_frame.pack(fill=tk.X, pady=5)

        ttk.Label(style_frame, text="Margin (mm):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.margin_var = tk.StringVar(value="5.0")
        ttk.Entry(style_frame, textvariable=self.margin_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(style_frame, text="Stroke width:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.stroke_width_var = tk.StringVar(value="0.1")
        ttk.Entry(style_frame, textvariable=self.stroke_width_var, width=10).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(style_frame, text="Stroke color:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.stroke_color_var = tk.StringVar(value="black")
        color_combo = ttk.Combobox(style_frame, textvariable=self.stroke_color_var,
                                   values=["black", "red", "blue", "green", "purple"], width=8)
        color_combo.grid(row=2, column=1, padx=5, pady=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Export", command=self._on_export).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT)

    def _on_export(self):
        """Handle export button click"""
        try:
            options = {
                'margin_mm': float(self.margin_var.get() or 5.0),
                'stroke_width': float(self.stroke_width_var.get() or 0.1),
                'stroke_color': self.stroke_color_var.get() or 'black'
            }

            # Add dimensions if specified
            if self.width_var.get().strip():
                options['width_mm'] = float(self.width_var.get())
            if self.height_var.get().strip():
                options['height_mm'] = float(self.height_var.get())

            self.result = options
            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid numbers: {e}")

    def _on_cancel(self):
        """Handle cancel button click"""
        self.result = None
        self.dialog.destroy()