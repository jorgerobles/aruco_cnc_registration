import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Callable, Optional

from services.event_broker import (event_aware, event_handler, EventPriority,
                                   CameraEvents, RegistrationEvents, GRBLEvents)


@event_aware()
class SVGRoutesPanel:
    """SVG Routes AR overlay control panel with camera scale control and debug features"""

    def __init__(self, parent, routes_overlay, logger: Optional[Callable] = None):
        self.routes_overlay = routes_overlay
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="SVG Routes AR Overlay")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Variables
        self.svg_visible_var = tk.BooleanVar(value=False)
        self.svg_color_var = tk.StringVar(value="yellow")
        self.svg_thickness_var = tk.IntVar(value=2)
        self.svg_use_registration_var = tk.BooleanVar(value=True)
        self.svg_scale_var = tk.DoubleVar(value=1.0)
        self.svg_offset_x_var = tk.IntVar(value=0)
        self.svg_offset_y_var = tk.IntVar(value=0)

        # AR-specific variables
        self.pixels_per_mm_var = tk.DoubleVar(value=10.0)
        self.auto_scale_var = tk.BooleanVar(value=True)

        # Debug variables
        self.show_debug_info_var = tk.BooleanVar(value=True)
        self.show_route_bounds_var = tk.BooleanVar(value=True)
        self.show_coordinate_grid_var = tk.BooleanVar(value=False)

        # State
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
        if success:
            self.camera_connected = True
            self.log("Camera connected - updating overlay camera info")
            self.update_camera_info()
        else:
            self.camera_connected = False

    @event_handler(CameraEvents.DISCONNECTED)
    def _on_camera_disconnected(self):
        """Handle camera disconnection events"""
        self.camera_connected = False
        self.log("Camera disconnected - overlay camera view unavailable")
        self.update_camera_info()

    @event_handler(RegistrationEvents.COMPUTED, EventPriority.HIGH)
    def _on_registration_computed(self, computation_data: dict):
        """Handle registration computation events"""
        self.registration_available = True
        error = computation_data.get('error', 0.0)
        self.log(f"Registration computed - SVG overlay can use registration transform (error: {error:.4f})")

        # If using registration transform, refresh the overlay
        if self.svg_use_registration_var.get() and self.routes_loaded:
            self.refresh_overlay()

    @event_handler(RegistrationEvents.CLEARED)
    def _on_registration_cleared(self):
        """Handle registration cleared events"""
        self.registration_available = False
        self.log("Registration cleared - SVG overlay will use manual transform")

        # Switch to manual transform mode if registration was being used
        if self.svg_use_registration_var.get():
            self.svg_use_registration_var.set(False)
            self.toggle_svg_transform_mode()

    @event_handler(RegistrationEvents.LOADED)
    def _on_registration_loaded(self, file_path: str):
        """Handle registration loaded events"""
        self.registration_available = True
        self.log(f"Registration loaded from {file_path} - SVG overlay can use registration transform")

        # Refresh overlay if using registration transform
        if self.svg_use_registration_var.get() and self.routes_loaded:
            self.refresh_overlay()

    @event_handler(RegistrationEvents.POINT_TRANSFORMED)
    def _on_point_transformed(self, transform_data: dict):
        """Handle point transformation events - update camera position"""
        if self.routes_loaded and self.camera_connected:
            try:
                # Get transformed point if available
                if 'machine_point' in transform_data:
                    machine_point = transform_data['machine_point']
                    self.update_camera_position(machine_point)
            except Exception as e:
                self.log(f"Error updating camera position from transform: {e}", "error")

    @event_handler(GRBLEvents.POSITION_CHANGED)
    def _on_grbl_position_changed(self, position: list):
        """Handle GRBL position changes to update camera view"""
        # Only update camera position occasionally to avoid spam
        if hasattr(self, '_last_camera_update'):
            import time
            now = time.time()
            if now - self._last_camera_update < 0.5:  # Update at most every 0.5 seconds
                return

        import time
        self._last_camera_update = time.time()

        if self.routes_loaded and self.registration_available:
            try:
                # Update camera position based on machine position
                self.update_camera_position(position[:2])  # Use X,Y only
            except Exception as e:
                self.log(f"Error updating camera position from GRBL: {e}", "error")

    def _setup_widgets(self):
        """Setup SVG routes control widgets"""
        # File management
        file_frame = ttk.Frame(self.frame)
        file_frame.pack(fill=tk.X, pady=2)

        ttk.Button(file_frame, text="Load SVG Routes",
                   command=self.load_svg_routes).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="Clear Routes",
                   command=self.clear_svg_routes).pack(side=tk.LEFT, padx=2)

        # Visibility toggle
        self.svg_visibility_check = ttk.Checkbutton(
            self.frame,
            text="Show AR Routes Overlay",
            variable=self.svg_visible_var,
            command=self.toggle_svg_visibility,
            state='disabled'  # Disabled until routes are loaded
        )
        self.svg_visibility_check.pack(pady=2)

        # AR Camera Scale Controls
        ar_frame = ttk.LabelFrame(self.frame, text="AR Camera View")
        ar_frame.pack(fill=tk.X, pady=2)

        # Auto-scale toggle
        self.auto_scale_check = ttk.Checkbutton(
            ar_frame,
            text="Auto-scale from SVG",
            variable=self.auto_scale_var,
            command=self.toggle_auto_scale,
            state='disabled'
        )
        self.auto_scale_check.pack(pady=1)

        # Manual scale control
        scale_control_frame = ttk.Frame(ar_frame)
        scale_control_frame.pack(fill=tk.X, pady=2)

        ttk.Label(scale_control_frame, text="Pixels per mm:").pack(side=tk.LEFT)
        self.pixels_per_mm_spin = tk.Spinbox(
            scale_control_frame,
            from_=0.5, to=100.0, increment=0.5,
            width=8,
            textvariable=self.pixels_per_mm_var,
            command=self.update_pixels_per_mm,
            state='disabled'
        )
        self.pixels_per_mm_spin.pack(side=tk.LEFT, padx=2)

        # Quick scale buttons
        quick_scale_frame = ttk.Frame(ar_frame)
        quick_scale_frame.pack(fill=tk.X, pady=1)

        ttk.Label(quick_scale_frame, text="Quick:").pack(side=tk.LEFT)

        quick_scales = [
            ("0.5x", 0.5),
            ("1x", 1.0),
            ("2x", 2.0),
            ("5x", 5.0),
            ("10x", 10.0),
            ("20x", 20.0)
        ]

        self.quick_scale_buttons = []
        for label, scale in quick_scales:
            btn = ttk.Button(
                quick_scale_frame,
                text=label,
                width=4,
                command=lambda s=scale: self.set_quick_scale(s)
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.quick_scale_buttons.append(btn)

        # Camera position display
        self.camera_info_var = tk.StringVar(value="Camera: Not set")
        self.camera_info_label = ttk.Label(ar_frame, textvariable=self.camera_info_var,
                                           foreground="gray", font=("TkDefaultFont", 8))
        self.camera_info_label.pack(pady=1)

        # Debug Controls
        debug_frame = ttk.LabelFrame(self.frame, text="Debug & Visualization")
        debug_frame.pack(fill=tk.X, pady=2)

        # Debug display options
        debug_options_frame = ttk.Frame(debug_frame)
        debug_options_frame.pack(fill=tk.X, pady=1)

        self.debug_info_check = ttk.Checkbutton(
            debug_options_frame,
            text="Show Debug Info",
            variable=self.show_debug_info_var,
            command=self.toggle_debug_info
        )
        self.debug_info_check.pack(side=tk.LEFT)

        self.route_bounds_check = ttk.Checkbutton(
            debug_options_frame,
            text="Route Bounds",
            variable=self.show_route_bounds_var,
            command=self.toggle_route_bounds
        )
        self.route_bounds_check.pack(side=tk.LEFT, padx=(10, 0))

        self.coordinate_grid_check = ttk.Checkbutton(
            debug_options_frame,
            text="Coordinate Grid",
            variable=self.show_coordinate_grid_var,
            command=self.toggle_coordinate_grid
        )
        self.coordinate_grid_check.pack(side=tk.LEFT, padx=(10, 0))

        # Debug action buttons
        debug_buttons_frame = ttk.Frame(debug_frame)
        debug_buttons_frame.pack(fill=tk.X, pady=2)

        ttk.Button(debug_buttons_frame, text="Print Route Summary",
                   command=self.print_route_summary).pack(side=tk.LEFT, padx=2)
        ttk.Button(debug_buttons_frame, text="Show Debug Window",
                   command=self.show_debug_window).pack(side=tk.LEFT, padx=2)
        ttk.Button(debug_buttons_frame, text="Export Debug Info",
                   command=self.export_debug_info).pack(side=tk.LEFT, padx=2)

        # Route configuration
        config_frame = ttk.LabelFrame(self.frame, text="Appearance")
        config_frame.pack(fill=tk.X, pady=2)

        # Color and thickness in one row
        style_frame = ttk.Frame(config_frame)
        style_frame.pack(fill=tk.X, pady=2)

        ttk.Label(style_frame, text="Color:").pack(side=tk.LEFT)
        self.svg_color_combo = ttk.Combobox(
            style_frame,
            textvariable=self.svg_color_var,
            values=["yellow", "red", "green", "blue", "cyan", "magenta", "white"],
            width=8,
            state='disabled'
        )
        self.svg_color_combo.pack(side=tk.LEFT, padx=2)
        self.svg_color_combo.bind('<<ComboboxSelected>>', self.change_svg_color)

        ttk.Label(style_frame, text="Thickness:").pack(side=tk.LEFT, padx=(10, 0))
        self.svg_thickness_spin = tk.Spinbox(
            style_frame,
            from_=1, to=10,
            width=3,
            textvariable=self.svg_thickness_var,
            command=self.change_svg_thickness,
            state='disabled'
        )
        self.svg_thickness_spin.pack(side=tk.LEFT, padx=2)

        # Display options
        display_options_frame = ttk.Frame(config_frame)
        display_options_frame.pack(fill=tk.X, pady=1)

        self.show_points_var = tk.BooleanVar(value=True)
        self.show_markers_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(
            display_options_frame,
            text="Points",
            variable=self.show_points_var,
            command=self.update_display_options
        ).pack(side=tk.LEFT)

        ttk.Checkbutton(
            display_options_frame,
            text="Start/End",
            variable=self.show_markers_var,
            command=self.update_display_options
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Transform controls
        transform_frame = ttk.LabelFrame(self.frame, text="Coordinate Transform")
        transform_frame.pack(fill=tk.X, pady=2)

        # Registration vs manual transform
        self.svg_registration_check = ttk.Checkbutton(
            transform_frame,
            text="Use Registration Transform",
            variable=self.svg_use_registration_var,
            command=self.toggle_svg_transform_mode,
            state='disabled'
        )
        self.svg_registration_check.pack()

        # Manual transform controls (initially hidden)
        self.manual_transform_frame = ttk.Frame(transform_frame)

        # Scale control
        scale_frame = ttk.Frame(self.manual_transform_frame)
        scale_frame.pack(fill=tk.X, pady=1)
        ttk.Label(scale_frame, text="Scale:").pack(side=tk.LEFT)
        self.svg_scale_spin = tk.Spinbox(
            scale_frame,
            from_=0.1, to=10.0, increment=0.1,
            width=6,
            textvariable=self.svg_scale_var,
            command=self.update_manual_transform
        )
        self.svg_scale_spin.pack(side=tk.LEFT, padx=2)

        # Offset controls
        offset_frame = ttk.Frame(self.manual_transform_frame)
        offset_frame.pack(fill=tk.X, pady=1)
        ttk.Label(offset_frame, text="Offset X:").pack(side=tk.LEFT)
        self.svg_offset_x_spin = tk.Spinbox(
            offset_frame,
            from_=-1000, to=1000, increment=10,
            width=6,
            textvariable=self.svg_offset_x_var,
            command=self.update_manual_transform
        )
        self.svg_offset_x_spin.pack(side=tk.LEFT, padx=2)

        ttk.Label(offset_frame, text="Y:").pack(side=tk.LEFT, padx=(5, 0))
        self.svg_offset_y_spin = tk.Spinbox(
            offset_frame,
            from_=-1000, to=1000, increment=10,
            width=6,
            textvariable=self.svg_offset_y_var,
            command=self.update_manual_transform
        )
        self.svg_offset_y_spin.pack(side=tk.LEFT, padx=2)

        # Routes info display
        self.svg_info_var = tk.StringVar(value="No routes loaded")
        self.svg_info_label = ttk.Label(self.frame, textvariable=self.svg_info_var,
                                        foreground="gray")
        self.svg_info_label.pack(pady=2)

        # Initialize UI state
        self.update_scale_controls()

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

                # Update pixels per mm from overlay's estimated value
                if hasattr(self.routes_overlay, 'camera_scale_factor'):
                    self.pixels_per_mm_var.set(self.routes_overlay.camera_scale_factor)

                # Update state and UI
                self.routes_loaded = True
                self.update_svg_info()
                self.update_camera_info()
                self.enable_svg_controls()

                # Auto-print route summary when debug is enabled
                if self.show_debug_info_var.get():
                    self.print_route_summary()

                self.log(f"Loaded SVG routes from: {filename}")

                # Emit event about routes being loaded
                if hasattr(self, 'emit'):
                    self.emit('svg.routes_loaded', filename)

            except Exception as e:
                self.log(f"Failed to load SVG routes: {e}", "error")
                messagebox.showerror("Error", f"Failed to load SVG routes: {e}")

    def clear_svg_routes(self):
        """Clear all SVG routes"""
        self.routes_overlay.clear_routes()
        self.routes_loaded = False
        self.update_svg_info()
        self.update_camera_info()
        self.disable_svg_controls()
        self.log("SVG routes cleared")

        # Emit event about routes being cleared
        if hasattr(self, 'emit'):
            self.emit('svg.routes_cleared')

    def toggle_svg_visibility(self):
        """Toggle SVG routes overlay visibility"""
        visible = self.svg_visible_var.get()
        self.routes_overlay.set_visibility(visible)

        status = "visible" if visible else "hidden"
        self.log(f"SVG AR routes overlay {status}")

        # Emit visibility change event
        if hasattr(self, 'emit'):
            self.emit('svg.visibility_changed', visible)

    def toggle_debug_info(self):
        """Toggle debug information display"""
        show_debug = self.show_debug_info_var.get()
        if hasattr(self.routes_overlay, 'enable_debug_display'):
            self.routes_overlay.enable_debug_display(show_debug)
        self.log(f"Debug info display {'enabled' if show_debug else 'disabled'}")

    def toggle_route_bounds(self):
        """Toggle route bounds display"""
        show_bounds = self.show_route_bounds_var.get()
        if hasattr(self.routes_overlay, 'enable_route_bounds_display'):
            self.routes_overlay.enable_route_bounds_display(show_bounds)
        self.log(f"Route bounds display {'enabled' if show_bounds else 'disabled'}")

    def toggle_coordinate_grid(self):
        """Toggle coordinate grid display"""
        show_grid = self.show_coordinate_grid_var.get()
        if hasattr(self.routes_overlay, 'enable_coordinate_grid'):
            self.routes_overlay.enable_coordinate_grid(show_grid)
        self.log(f"Coordinate grid {'enabled' if show_grid else 'disabled'}")

    def print_route_summary(self):
        """Print route summary to console/log"""
        if hasattr(self.routes_overlay, 'print_route_summary'):
            self.routes_overlay.print_route_summary()
        else:
            self.log("Route summary not available - overlay doesn't support debug info", "warning")

    def show_debug_window(self):
        """Show debug information in a separate window"""
        if not hasattr(self.routes_overlay, 'get_debug_info'):
            messagebox.showwarning("Debug Info", "Debug information not available")
            return

        debug_info = self.routes_overlay.get_debug_info()
        if not debug_info:
            messagebox.showinfo("Debug Info", "No debug information available")
            return

        # Create debug window
        debug_window = tk.Toplevel()
        debug_window.title("SVG Routes Debug Information")
        debug_window.geometry("600x500")

        # Create scrolled text widget
        text_widget = scrolledtext.ScrolledText(debug_window, wrap=tk.WORD, width=70, height=30)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Format and insert debug information
        debug_text = self._format_debug_info(debug_info)
        text_widget.insert(tk.END, debug_text)
        text_widget.config(state=tk.DISABLED)

        # Add close button
        close_button = ttk.Button(debug_window, text="Close", command=debug_window.destroy)
        close_button.pack(pady=(0, 10))

    def _format_debug_info(self, debug_info: dict) -> str:
        """Format debug information for display"""
        lines = []
        lines.append("=" * 60)
        lines.append("SVG ROUTES DEBUG INFORMATION")
        lines.append("=" * 60)
        lines.append("")

        # Basic information
        lines.append(f"File Path: {debug_info.get('file_path', 'N/A')}")
        lines.append(f"Transform Mode: {debug_info.get('transform_mode', 'N/A')}")
        lines.append(f"Route Count: {debug_info.get('route_count', 0)}")
        lines.append(f"Total Points: {debug_info.get('total_points', 0)}")
        lines.append(f"Total Length: {debug_info.get('total_length_mm', 0):.2f} mm")
        lines.append(f"Average Route Length: {debug_info.get('average_route_length_mm', 0):.2f} mm")
        lines.append(f"Average Points per Route: {debug_info.get('average_points_per_route', 0):.1f}")
        lines.append("")

        # Event system status
        lines.append("Event System Status:")
        lines.append(f"  Camera Connected: {self.camera_connected}")
        lines.append(f"  Registration Available: {self.registration_available}")
        lines.append(f"  Routes Loaded: {self.routes_loaded}")
        lines.append("")

        # SVG bounds
        if 'svg_bounds' in debug_info:
            svg = debug_info['svg_bounds']
            lines.append("SVG Coordinate Space:")
            lines.append(f"  Min X: {svg.get('min_x', 0):.2f}, Max X: {svg.get('max_x', 0):.2f}")
            lines.append(f"  Min Y: {svg.get('min_y', 0):.2f}, Max Y: {svg.get('max_y', 0):.2f}")
            lines.append(f"  Width: {svg.get('width', 0):.2f}, Height: {svg.get('height', 0):.2f}")
            lines.append(f"  Center: ({svg.get('center_x', 0):.2f}, {svg.get('center_y', 0):.2f})")
            lines.append("")

        # Machine bounds
        if 'machine_bounds' in debug_info:
            machine = debug_info['machine_bounds']
            lines.append("Machine Coordinate Space:")
            lines.append(f"  Min X: {machine.get('min_x', 0):.2f} mm, Max X: {machine.get('max_x', 0):.2f} mm")
            lines.append(f"  Min Y: {machine.get('min_y', 0):.2f} mm, Max Y: {machine.get('max_y', 0):.2f} mm")
            lines.append(f"  Width: {machine.get('width', 0):.2f} mm, Height: {machine.get('height', 0):.2f} mm")
            lines.append(f"  Center: ({machine.get('center_x', 0):.2f}, {machine.get('center_y', 0):.2f}) mm")
            lines.append("")

        # Camera information
        if 'current_camera_position' in debug_info:
            pos = debug_info['current_camera_position']
            if pos:
                lines.append(f"Camera Position: ({pos[0]:.2f}, {pos[1]:.2f}) mm")
            else:
                lines.append("Camera Position: Not set")

        if 'current_scale_factor' in debug_info:
            lines.append(f"Camera Scale Factor: {debug_info['current_scale_factor']:.2f} px/mm")
        lines.append("")

        # Registration information
        if 'registration_info' in debug_info:
            reg = debug_info['registration_info']
            if reg and reg.get('available'):
                lines.append("Registration Status:")
                lines.append(f"  Available: {reg.get('available', False)}")
                lines.append(f"  Registered: {reg.get('is_registered', False)}")
                lines.append(f"  Calibration Points: {reg.get('point_count', 0)}")
                if reg.get('registration_error') is not None:
                    lines.append(f"  Registration Error: {reg['registration_error']:.3f} mm")
                lines.append("")

        # Individual routes
        if 'individual_routes' in debug_info:
            lines.append("Individual Routes:")
            for route_info in debug_info['individual_routes']:
                lines.append(f"  Route {route_info['index']}:")
                lines.append(f"    Points: {route_info['point_count']}")
                lines.append(f"    Length: {route_info['length_mm']:.2f} mm")
                if route_info.get('start_point'):
                    start = route_info['start_point']
                    lines.append(f"    Start: ({start[0]:.2f}, {start[1]:.2f}) mm")
                if route_info.get('end_point'):
                    end = route_info['end_point']
                    lines.append(f"    End: ({end[0]:.2f}, {end[1]:.2f}) mm")
                lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def export_debug_info(self):
        """Export debug information to file"""
        if not hasattr(self.routes_overlay, 'get_debug_info'):
            messagebox.showwarning("Export Debug", "Debug information not available")
            return

        debug_info = self.routes_overlay.get_debug_info()
        if not debug_info:
            messagebox.showinfo("Export Debug", "No debug information available")
            return

        # Ask user for save location
        filename = filedialog.asksaveasfilename(
            title="Export Debug Information",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")]
        )

        if filename:
            try:
                if filename.lower().endswith('.json'):
                    # Export as JSON
                    import json
                    with open(filename, 'w') as f:
                        json.dump(debug_info, f, indent=2, default=str)
                else:
                    # Export as formatted text
                    debug_text = self._format_debug_info(debug_info)
                    with open(filename, 'w') as f:
                        f.write(debug_text)

                messagebox.showinfo("Export Debug", f"Debug information exported to:\n{filename}")
                self.log(f"Debug information exported to: {filename}")

            except Exception as e:
                self.log(f"Failed to export debug info: {e}", "error")
                messagebox.showerror("Export Error", f"Failed to export debug information:\n{e}")

    def toggle_auto_scale(self):
        """Toggle auto-scale mode"""
        auto_scale = self.auto_scale_var.get()
        self.update_scale_controls()

        if auto_scale and self.routes_loaded:
            # Reset to overlay's auto-estimated scale
            if hasattr(self.routes_overlay, 'camera_scale_factor'):
                self.pixels_per_mm_var.set(self.routes_overlay.camera_scale_factor)
                self.update_pixels_per_mm()

        self.log(f"Auto-scale mode: {'enabled' if auto_scale else 'disabled'}")

    def update_scale_controls(self):
        """Update the state of scale controls based on auto-scale setting"""
        auto_scale = self.auto_scale_var.get()

        # Enable/disable manual scale controls
        scale_state = 'disabled' if auto_scale else 'normal'
        self.pixels_per_mm_spin.config(state=scale_state)

        # Enable/disable quick scale buttons
        button_state = 'disabled' if auto_scale else 'normal'
        for btn in self.quick_scale_buttons:
            btn.config(state=button_state)

    def set_quick_scale(self, scale_factor: float):
        """Set a quick scale value"""
        try:
            # Get current scale and multiply by factor
            current_scale = self.pixels_per_mm_var.get()
            if current_scale == 0:
                current_scale = 10.0  # Default fallback

            new_scale = current_scale * scale_factor
            new_scale = max(0.5, min(new_scale, 100.0))  # Clamp to reasonable range

            self.pixels_per_mm_var.set(new_scale)
            self.update_pixels_per_mm()

            self.log(f"Quick scale {scale_factor}x applied: {new_scale:.1f} px/mm")
        except Exception as e:
            self.log(f"Error applying quick scale: {e}", "error")

    def update_pixels_per_mm(self):
        """Update the camera scale factor in the overlay"""
        try:
            pixels_per_mm = self.pixels_per_mm_var.get()

            # Validate range
            if pixels_per_mm < 0.1 or pixels_per_mm > 100.0:
                self.log("Pixels per mm must be between 0.1 and 100.0", "error")
                return

            # Update overlay
            if hasattr(self.routes_overlay, 'set_camera_scale_factor'):
                self.routes_overlay.set_camera_scale_factor(pixels_per_mm)
            else:
                # Fallback for older overlay versions
                self.routes_overlay.camera_scale_factor = pixels_per_mm

            self.log(f"Camera scale factor updated: {pixels_per_mm:.1f} px/mm")

            # Update camera info display
            self.update_camera_info()

        except Exception as e:
            self.log(f"Error updating pixels per mm: {e}", "error")

    def update_camera_info(self):
        """Update camera information display"""
        try:
            if hasattr(self.routes_overlay, 'get_camera_info'):
                camera_info = self.routes_overlay.get_camera_info()

                if camera_info['camera_position']:
                    pos_x, pos_y = camera_info['camera_position']
                    info_text = f"Cam: ({pos_x:.1f}, {pos_y:.1f}) @ {camera_info['camera_scale_factor']:.1f}px/mm"
                else:
                    info_text = f"Cam: Not set @ {camera_info['camera_scale_factor']:.1f}px/mm"

                self.camera_info_var.set(info_text)

                # Set color based on connection status
                if self.camera_connected:
                    self.camera_info_label.config(foreground="blue")
                else:
                    self.camera_info_label.config(foreground="gray")
            else:
                self.camera_info_var.set("Camera: Legacy mode")
                self.camera_info_label.config(foreground="gray")

        except Exception as e:
            self.log(f"Error updating camera info: {e}", "error")
            self.camera_info_var.set("Camera: Error")
            self.camera_info_label.config(foreground="red")

    def change_svg_color(self, event=None):
        """Change SVG routes color"""
        color_name = self.svg_color_var.get()
        color_map = {
            "yellow": (255, 255, 0),
            "red": (0, 0, 255),
            "green": (0, 255, 0),
            "blue": (255, 0, 0),
            "cyan": (255, 255, 0),
            "magenta": (255, 0, 255),
            "white": (255, 255, 255)
        }

        if color_name in color_map:
            try:
                self.routes_overlay.set_route_color(color_map[color_name])
                self.log(f"SVG route color changed to: {color_name}")
            except Exception as e:
                self.log(f"Error changing route color: {e}", "error")

    def change_svg_thickness(self):
        """Change SVG routes line thickness"""
        try:
            thickness = self.svg_thickness_var.get()
            self.routes_overlay.set_route_thickness(thickness)
            self.log(f"SVG route thickness changed to: {thickness}")
        except Exception as e:
            self.log(f"Error changing route thickness: {e}", "error")

    def update_display_options(self):
        """Update display options for routes"""
        try:
            show_points = self.show_points_var.get()
            show_markers = self.show_markers_var.get()

            if hasattr(self.routes_overlay, 'set_display_options'):
                self.routes_overlay.set_display_options(show_points, show_markers)
                self.log(f"Display options updated: points={show_points}, markers={show_markers}")
        except Exception as e:
            self.log(f"Error updating display options: {e}", "error")

    def toggle_svg_transform_mode(self):
        """Toggle between registration and manual transform mode"""
        try:
            use_registration = self.svg_use_registration_var.get()

            # Check if registration is available when trying to use it
            if use_registration and not self.registration_available:
                self.log("Registration transform not available - switching to manual", "warning")
                self.svg_use_registration_var.set(False)
                use_registration = False
                messagebox.showwarning("Registration Not Available",
                                       "Registration transform is not available.\nUsing manual transform instead.")

            self.routes_overlay.set_use_registration_transform(use_registration)

            if use_registration:
                # Hide manual transform controls
                self.manual_transform_frame.pack_forget()
                self.log("SVG AR overlay using registration transform")
            else:
                # Show manual transform controls
                self.manual_transform_frame.pack(fill=tk.X, pady=2)
                # Apply current manual transform
                self.update_manual_transform()
                self.log("SVG AR overlay using manual transform")
        except Exception as e:
            self.log(f"Error toggling transform mode: {e}", "error")

    def update_manual_transform(self):
        """Update manual transform parameters"""
        try:
            if not self.svg_use_registration_var.get():
                scale = self.svg_scale_var.get()
                offset_x = self.svg_offset_x_var.get()
                offset_y = self.svg_offset_y_var.get()

                self.routes_overlay.set_manual_transform(scale, (offset_x, offset_y))
                self.log(f"Manual transform: scale={scale:.1f}, offset=({offset_x}, {offset_y})")
        except Exception as e:
            self.log(f"Error updating manual transform: {e}", "error")

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

                # Add coordinate center information
                if hasattr(self.routes_overlay, 'get_debug_info'):
                    debug_info = self.routes_overlay.get_debug_info()
                    if debug_info and 'machine_bounds' in debug_info:
                        machine = debug_info['machine_bounds']
                        info_text += f"\nCenter: ({machine.get('center_x', 0):.1f}, {machine.get('center_y', 0):.1f})mm"

                self.svg_info_var.set(info_text)
                self.svg_info_label.config(foreground="green")
            else:
                self.svg_info_var.set("No routes loaded")
                self.svg_info_label.config(foreground="gray")
        except Exception as e:
            self.log(f"Error updating SVG info: {e}", "error")
            self.svg_info_var.set("Error getting route info")
            self.svg_info_label.config(foreground="red")

    def enable_svg_controls(self):
        """Enable SVG control widgets when routes are loaded"""
        self.svg_visibility_check.config(state='normal')
        self.svg_color_combo.config(state='readonly')
        self.svg_thickness_spin.config(state='normal')
        self.svg_registration_check.config(state='normal')

        # Enable AR controls
        self.auto_scale_check.config(state='normal')
        self.update_scale_controls()  # This will set the right state for scale controls

        # Enable debug controls
        self.debug_info_check.config(state='normal')
        self.route_bounds_check.config(state='normal')
        self.coordinate_grid_check.config(state='normal')

        # Enable manual transform controls if they exist
        if hasattr(self, 'svg_scale_spin'):
            self.svg_scale_spin.config(state='normal')
        if hasattr(self, 'svg_offset_x_spin'):
            self.svg_offset_x_spin.config(state='normal')
        if hasattr(self, 'svg_offset_y_spin'):
            self.svg_offset_y_spin.config(state='normal')

    def disable_svg_controls(self):
        """Disable SVG control widgets when no routes loaded"""
        self.svg_visible_var.set(False)
        self.routes_overlay.set_visibility(False)

        self.svg_visibility_check.config(state='disabled')
        self.svg_color_combo.config(state='disabled')
        self.svg_thickness_spin.config(state='disabled')
        self.svg_registration_check.config(state='disabled')

        # Disable AR controls
        self.auto_scale_check.config(state='disabled')
        self.pixels_per_mm_spin.config(state='disabled')

        for btn in self.quick_scale_buttons:
            btn.config(state='disabled')

        # Disable debug controls (but don't change their state)
        # Users should be able to toggle debug settings even without routes

        # Disable manual transform controls if they exist
        if hasattr(self, 'svg_scale_spin'):
            self.svg_scale_spin.config(state='disabled')
        if hasattr(self, 'svg_offset_x_spin'):
            self.svg_offset_x_spin.config(state='disabled')
        if hasattr(self, 'svg_offset_y_spin'):
            self.svg_offset_y_spin.config(state='disabled')

        # Hide manual transform controls
        self.manual_transform_frame.pack_forget()

    def get_routes_count(self) -> int:
        """Get number of loaded routes"""
        try:
            return self.routes_overlay.get_routes_count() if self.routes_loaded else 0
        except Exception:
            return 0

    def is_visible(self) -> bool:
        """Check if routes overlay is visible"""
        try:
            return self.svg_visible_var.get() and self.routes_loaded
        except Exception:
            return False

    def refresh_overlay(self):
        """Refresh the overlay display and information"""
        try:
            if self.routes_loaded:
                self.update_svg_info()
                self.update_camera_info()

                # Refresh transformation if registration has changed
                if hasattr(self.routes_overlay, 'refresh_transformation'):
                    self.routes_overlay.refresh_transformation()

                self.log("SVG overlay refreshed")

        except Exception as e:
            self.log(f"Error refreshing overlay: {e}", "error")

    def update_camera_position(self, camera_position=None):
        """Update camera position display (called from external camera system)"""
        try:
            if camera_position and hasattr(self.routes_overlay, 'update_camera_view'):
                import numpy as np
                if len(camera_position) >= 2:
                    # Convert to 3D if needed
                    if len(camera_position) == 2:
                        camera_pos_3d = np.array([camera_position[0], camera_position[1], 0.0])
                    else:
                        camera_pos_3d = np.array(camera_position[:3])

                    self.routes_overlay.update_camera_view(camera_pos_3d)
                    self.update_camera_info()

        except Exception as e:
            self.log(f"Error updating camera position: {e}", "error")

    def get_panel_status(self):
        """Get current panel status for external queries"""
        try:
            return {
                'routes_loaded': self.routes_loaded,
                'routes_visible': self.is_visible(),
                'routes_count': self.get_routes_count(),
                'camera_connected': self.camera_connected,
                'registration_available': self.registration_available,
                'using_registration_transform': self.svg_use_registration_var.get(),
                'auto_scale_enabled': self.auto_scale_var.get(),
                'pixels_per_mm': self.pixels_per_mm_var.get()
            }
        except Exception as e:
            self.log(f"Error getting panel status: {e}", "error")
            return {'error': str(e)}