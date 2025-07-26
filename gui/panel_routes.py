# panel_routes.py - Refactored Routes panel with generic import/export

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional
import os

from services.event_broker import (event_aware, event_handler)
from services.routes_manager import RouteEvents


@event_aware()
class RoutesPanel:
    """Routes panel with generic import/export functionality"""

    def __init__(self, parent, routes_service, logger: Optional[Callable] = None):
        self.routes_service = routes_service
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="Routes")
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
        """Handle routes loaded event"""
        self.routes_loaded = True
        self.update_routes_info()
        self.log(f"Routes loaded: {data.get('route_count', 0)} routes via {data.get('importer', 'unknown')}")

    @event_handler(RouteEvents.ROUTES_CLEARED)
    def _on_routes_cleared(self):
        """Handle routes cleared event"""
        self.routes_loaded = False
        self.update_routes_info()
        self.log("Routes cleared")

    @event_handler(RouteEvents.ROUTES_EXPORTED)
    def _on_routes_exported(self, data: dict):
        """Handle routes exported event"""
        self.log(f"Routes exported via {data.get('exporter', 'unknown')}: {data.get('output_file', 'unknown')}")

    def _setup_widgets(self):
        """Setup routes control widgets"""

        # File management - Row 1
        file_frame = ttk.Frame(self.frame)
        file_frame.pack(fill=tk.X, pady=2)

        ttk.Button(file_frame, text="Load Routes",
                   command=self.load_routes).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="Clear Routes",
                   command=self.clear_routes).pack(side=tk.LEFT, padx=2)

        # Export controls - Row 2
        export_frame = ttk.Frame(self.frame)
        export_frame.pack(fill=tk.X, pady=2)

        ttk.Button(export_frame, text="Export Routes",
                   command=self.export_routes).pack(side=tk.LEFT, padx=2)

        # Export options
        self.export_transformed_var = tk.BooleanVar()
        ttk.Checkbutton(export_frame, text="Use transformed",
                        variable=self.export_transformed_var).pack(side=tk.LEFT, padx=5)

        # Routes info display
        self.routes_info_var = tk.StringVar(value="No routes loaded")
        self.routes_info_label = ttk.Label(self.frame, textvariable=self.routes_info_var,
                                           foreground="gray")
        self.routes_info_label.pack(pady=2)

    def load_routes(self):
        """Load routes using generic importer"""
        # Get file types from import manager
        file_types = self.routes_service.get_import_file_types()
        file_types.append(("All files", "*.*"))

        filename = filedialog.askopenfilename(
            title="Load Routes",
            filetypes=file_types
        )

        if filename:
            try:
                success = self.routes_service.load_routes_from_file(filename)

                if success:
                    self.routes_loaded = True
                    self.update_routes_info()
                    self.log(f"Loaded routes from: {filename}")
                else:
                    messagebox.showerror("Error", "Failed to load routes")

            except Exception as e:
                self.log(f"Failed to load routes: {e}", "error")
                messagebox.showerror("Error", f"Failed to load routes: {e}")

    def export_routes(self):
        """Export routes using generic exporter"""
        if not self.routes_loaded:
            messagebox.showwarning("Warning", "No routes loaded to export")
            return

        # Get available exporters
        exporters = self.routes_service.get_exporters()
        if not exporters:
            messagebox.showerror("Error", "No exporters available")
            return

        # Show exporter selection dialog
        selected_exporter = self._select_exporter(exporters)
        if not selected_exporter:
            return

        # Get filename with appropriate extension
        filename = filedialog.asksaveasfilename(
            title=f"Export Routes ({selected_exporter.name})",
            defaultextension=selected_exporter.default_extension,
            filetypes=[(selected_exporter.file_description,
                        " ".join([f"*{ext}" for ext in selected_exporter.file_extensions]))]
        )

        if filename:
            try:
                use_transformed = self.export_transformed_var.get()

                # Get export options
                export_options = self._get_export_options(selected_exporter)
                if export_options is None:
                    return

                success = self.routes_service.export_routes_to_file(
                    output_file=filename,
                    use_transformed=use_transformed,
                    exporter_name=selected_exporter.name,
                    **export_options
                )

                if success:
                    self.log(f"Exported routes to: {filename}")
                    messagebox.showinfo("Success", f"Routes exported successfully to:\n{filename}")
                else:
                    messagebox.showerror("Error", "Failed to export routes")

            except Exception as e:
                self.log(f"Failed to export routes: {e}", "error")
                messagebox.showerror("Error", f"Failed to export routes: {e}")

    def _select_exporter(self, exporters):
        """Show exporter selection dialog"""
        if len(exporters) == 1:
            return exporters[0]

        dialog = ExporterSelectionDialog(self.frame, exporters)
        return dialog.show()

    def _get_export_options(self, exporter):
        """Get export options for selected exporter"""
        default_options = exporter.get_export_options()

        if exporter.name == "SVG Exporter":
            dialog = SVGExportOptionsDialog(self.frame, default_options)
        elif exporter.name == "G-Code Exporter":
            dialog = GCodeExportOptionsDialog(self.frame, default_options)
        else:
            # Generic options dialog
            dialog = GenericExportOptionsDialog(self.frame, default_options)

        return dialog.show()

    def clear_routes(self):
        """Clear all routes"""
        self.routes_service.clear_routes()
        self.routes_loaded = False
        self.update_routes_info()
        self.log("Routes cleared")

    def update_routes_info(self):
        """Update routes information display"""
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

                self.routes_info_var.set(info_text)
                self.routes_info_label.config(foreground="green")
            else:
                self.routes_info_var.set("No routes loaded")
                self.routes_info_label.config(foreground="gray")

        except Exception as e:
            self.log(f"Error updating routes info: {e}", "error")
            self.routes_info_var.set("Error getting route info")
            self.routes_info_label.config(foreground="red")


class ExporterSelectionDialog:
    """Dialog for selecting exporter when multiple available"""

    def __init__(self, parent, exporters):
        self.parent = parent
        self.exporters = exporters
        self.result = None

    def show(self):
        """Show dialog and return selected exporter"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Select Export Format")
        self.dialog.geometry("300x200")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.transient(self.parent)

        self._create_widgets()
        self.dialog.wait_window()
        return self.result

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Select export format:").pack(pady=5)

        self.selected_var = tk.StringVar()
        for exporter in self.exporters:
            ttk.Radiobutton(main_frame, text=exporter.name,
                            variable=self.selected_var,
                            value=exporter.name).pack(anchor=tk.W, pady=2)

        # Set first as default
        if self.exporters:
            self.selected_var.set(self.exporters[0].name)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="OK", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT)

    def _on_ok(self):
        """Handle OK button"""
        selected_name = self.selected_var.get()
        self.result = next((e for e in self.exporters if e.name == selected_name), None)
        self.dialog.destroy()

    def _on_cancel(self):
        """Handle cancel button"""
        self.result = None
        self.dialog.destroy()


class SVGExportOptionsDialog:
    """SVG-specific export options dialog"""

    def __init__(self, parent, default_options):
        self.parent = parent
        self.default_options = default_options
        self.result = None

    def show(self):
        """Show dialog and return options"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("SVG Export Options")
        self.dialog.geometry("350x250")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.transient(self.parent)

        self._create_widgets()
        self.dialog.wait_window()
        return self.result

    def _create_widgets(self):
        """Create SVG options widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Dimensions
        dim_frame = ttk.LabelFrame(main_frame, text="Dimensions (auto if empty)")
        dim_frame.pack(fill=tk.X, pady=5)

        ttk.Label(dim_frame, text="Width (mm):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.width_var = tk.StringVar()
        ttk.Entry(dim_frame, textvariable=self.width_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(dim_frame, text="Height (mm):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.height_var = tk.StringVar()
        ttk.Entry(dim_frame, textvariable=self.height_var, width=10).grid(row=1, column=1, padx=5, pady=2)

        # Style
        style_frame = ttk.LabelFrame(main_frame, text="Style")
        style_frame.pack(fill=tk.X, pady=5)

        ttk.Label(style_frame, text="Margin (mm):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.margin_var = tk.StringVar(value=str(self.default_options.get('margin_mm', 5.0)))
        ttk.Entry(style_frame, textvariable=self.margin_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(style_frame, text="Stroke width:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.stroke_width_var = tk.StringVar(value=str(self.default_options.get('stroke_width', 0.1)))
        ttk.Entry(style_frame, textvariable=self.stroke_width_var, width=10).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(style_frame, text="Color:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.color_var = tk.StringVar(value=self.default_options.get('stroke_color', 'black'))
        ttk.Combobox(style_frame, textvariable=self.color_var,
                     values=["black", "red", "blue", "green"], width=8).grid(row=2, column=1, padx=5, pady=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Export", command=self._on_export).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT)

    def _on_export(self):
        """Handle export button"""
        try:
            options = {
                'margin_mm': float(self.margin_var.get() or 5.0),
                'stroke_width': float(self.stroke_width_var.get() or 0.1),
                'stroke_color': self.color_var.get() or 'black'
            }

            if self.width_var.get().strip():
                options['width_mm'] = float(self.width_var.get())
            if self.height_var.get().strip():
                options['height_mm'] = float(self.height_var.get())

            self.result = options
            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid numbers: {e}")

    def _on_cancel(self):
        """Handle cancel button"""
        self.result = None
        self.dialog.destroy()


class GCodeExportOptionsDialog:
    """G-code specific export options dialog"""

    def __init__(self, parent, default_options):
        self.parent = parent
        self.default_options = default_options
        self.result = None

    def show(self):
        """Show dialog and return options"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("G-Code Export Options")
        self.dialog.geometry("350x300")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        self.dialog.transient(self.parent)

        self._create_widgets()
        self.dialog.wait_window()
        return self.result

    def _create_widgets(self):
        """Create G-code options widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Motion parameters
        motion_frame = ttk.LabelFrame(main_frame, text="Motion Parameters")
        motion_frame.pack(fill=tk.X, pady=5)

        params = [
            ("Speed (mm/min):", "speed", 1500),
            ("Cut depth (mm):", "cut_depth", -1.0),
            ("Safety height (mm):", "safety_height", 5.0),
            ("Offset (mm):", "offset", 2.75),
            ("Angle threshold (°):", "angle_threshold", 30),
            ("Initial rotation (°):", "initial_rotation", 0)
        ]

        self.param_vars = {}
        for i, (label, key, default) in enumerate(params):
            ttk.Label(motion_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            var = tk.StringVar(value=str(self.default_options.get(key, default)))
            self.param_vars[key] = var
            ttk.Entry(motion_frame, textvariable=var, width=10).grid(row=i, column=1, padx=5, pady=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Export", command=self._on_export).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT)

    def _on_export(self):
        """Handle export button"""
        try:
            options = {}
            for key, var in self.param_vars.items():
                options[key] = float(var.get())

            self.result = options
            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid numbers: {e}")

    def _on_cancel(self):
        """Handle cancel button"""
        self.result = None
        self.dialog.destroy()


class GenericExportOptionsDialog:
    """Generic export options dialog for unknown exporters"""

    def __init__(self, parent, default_options):
        self.parent = parent
        self.default_options = default_options
        self.result = None

    def show(self):
        """Show dialog and return options"""
        # For now, just return default options
        # Could be expanded to show a generic key-value editor
        self.result = self.default_options.copy()
        return self.result