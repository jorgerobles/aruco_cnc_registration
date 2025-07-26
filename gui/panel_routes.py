# gui/panel_routes.py (Updated sections)
"""
Routes Panel with Dynamic Form Generation
Replaces hardcoded export dialogs with JSON-driven forms
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional

from gui.dynamic_form_generator import DynamicFormGenerator
from services.event_broker import event_aware, event_handler, EventPriority
from services.routes_manager import RouteEvents


@event_aware()
class RoutesPanel:
    """Routes management panel with dynamic export forms"""

    def __init__(self, parent, routes_service, logger: Optional[Callable] = None):
        self.routes_service = routes_service
        self.logger = logger
        self.routes_loaded = False

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Routes")
        self.frame.pack(fill=tk.X, pady=2, padx=5)

        # UI Variables
        self.routes_info_var = tk.StringVar(value="No routes loaded")
        self.export_transformed_var = tk.BooleanVar(value=True)
        self.selected_exporter_var = tk.StringVar()

        self._setup_widgets()
        self._check_initial_state()
        self._update_exporter_dropdown()

    def log(self, message: str, level: str = "info"):
        """Log message if logger available"""
        if self.logger:
            self.logger(message, level)

    def _setup_widgets(self):
        """Create UI widgets"""
        # Routes info display
        info_frame = ttk.Frame(self.frame)
        info_frame.pack(fill=tk.X, padx=5, pady=2)

        self.routes_info_label = ttk.Label(info_frame, textvariable=self.routes_info_var)
        self.routes_info_label.pack(side=tk.LEFT)

        # Control buttons
        controls_frame = ttk.Frame(self.frame)
        controls_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(controls_frame, text="Load Routes", command=self.load_routes).pack(side=tk.LEFT, padx=2)
        ttk.Button(controls_frame, text="Export Routes", command=self.export_routes).pack(side=tk.LEFT, padx=2)
        ttk.Button(controls_frame, text="Clear", command=self.clear_routes).pack(side=tk.LEFT, padx=2)

        # Export configuration
        export_frame = ttk.Frame(self.frame)
        export_frame.pack(fill=tk.X, padx=5, pady=2)

        # Exporter selection
        ttk.Label(export_frame, text="Format:").pack(side=tk.LEFT, padx=2)
        self.exporter_combo = ttk.Combobox(
            export_frame,
            textvariable=self.selected_exporter_var,
            state='readonly',
            width=15
        )
        self.exporter_combo.pack(side=tk.LEFT, padx=2)

        # Export options
        ttk.Checkbutton(
            export_frame,
            text="Use transformed coordinates",
            variable=self.export_transformed_var
        ).pack(side=tk.LEFT, padx=10)

    def _update_exporter_dropdown(self):
        """Update exporter dropdown with available exporters"""
        exporters = self.routes_service.get_exporters()
        exporter_names = [exporter.name for exporter in exporters]

        self.exporter_combo['values'] = exporter_names

        # Set default selection
        if exporter_names:
            self.selected_exporter_var.set(exporter_names[0])

    def _get_selected_exporter(self):
        """Get currently selected exporter"""
        selected_name = self.selected_exporter_var.get()
        if not selected_name:
            return None

        exporters = self.routes_service.get_exporters()
        return next((e for e in exporters if e.name == selected_name), None)

    # Event handlers
    @event_handler(RouteEvents.ROUTES_LOADED, EventPriority.NORMAL)
    def _on_routes_loaded(self, event_data):
        """Handle routes loaded event"""
        self.routes_loaded = True
        self.update_routes_info()

    @event_handler(RouteEvents.ROUTES_CLEARED)
    def _on_routes_cleared(self, event_data):
        """Handle routes cleared event"""
        self.routes_loaded = False
        self.update_routes_info()

    def load_routes(self):
        """Load routes from file"""
        # Get available file types from importers
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

    def _check_initial_state(self):
        """Check if routes are already loaded"""
        if self.routes_service.is_loaded():
            self.routes_loaded = True
            self.update_routes_info()

    def export_routes(self):
        """Export routes using dynamic form generator"""
        if not self.routes_loaded:
            messagebox.showwarning("Warning", "No routes loaded to export")
            return

        # Get selected exporter from dropdown
        selected_exporter = self._get_selected_exporter()
        if not selected_exporter:
            messagebox.showerror("Error", "No exporter selected")
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

                # Get export options using dynamic form
                export_options = self._get_export_options_dynamic(selected_exporter)
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

    def _get_export_options_dynamic(self, exporter):
        """Get export options using dynamic form generator"""
        default_options = exporter.get_export_options()

        # Get form schema from exporter
        schema = exporter.get_form_schema()

        # Fallback to generic schema if exporter doesn't provide one
        if schema is None:
            from gui.dynamic_form_generator import create_generic_schema
            schema = create_generic_schema(default_options)

        # Create and show dynamic form
        form_generator = DynamicFormGenerator(
            parent=self.frame,
            title=f"{exporter.name} Options",
            form_schema=schema,
            default_values=default_options
        )

        return form_generator.show()

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