import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional


class SVGRoutesPanel:
    """SVG Routes AR overlay control panel with camera scale control"""

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

        # New AR-specific variables
        self.pixels_per_mm_var = tk.DoubleVar(value=10.0)
        self.auto_scale_var = tk.BooleanVar(value=True)

        # State
        self.routes_loaded = False

        self._setup_widgets()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

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

        for label, scale in quick_scales:
            btn = ttk.Button(
                quick_scale_frame,
                text=label,
                width=4,
                command=lambda s=scale: self.set_quick_scale(s)
            )
            btn.pack(side=tk.LEFT, padx=1)
            # Store reference to disable later
            if not hasattr(self, 'quick_scale_buttons'):
                self.quick_scale_buttons = []
            self.quick_scale_buttons.append(btn)

        # Camera position display
        self.camera_info_var = tk.StringVar(value="Camera: Not set")
        self.camera_info_label = ttk.Label(ar_frame, textvariable=self.camera_info_var,
                                           foreground="gray", font=("TkDefaultFont", 8))
        self.camera_info_label.pack(pady=1)

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

                self.log(f"Loaded SVG routes from: {filename}")

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

    def toggle_svg_visibility(self):
        """Toggle SVG routes overlay visibility"""
        visible = self.svg_visible_var.get()
        self.routes_overlay.set_visibility(visible)

        status = "visible" if visible else "hidden"
        self.log(f"SVG AR routes overlay {status}")

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
        if hasattr(self, 'quick_scale_buttons'):
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
                self.camera_info_label.config(foreground="blue")
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

        if hasattr(self, 'quick_scale_buttons'):
            for btn in self.quick_scale_buttons:
                btn.config(state='disabled')

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