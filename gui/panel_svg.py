import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional

class SVGRoutesPanel:
    """SVG Routes overlay control panel"""

    def __init__(self, parent, routes_overlay, logger: Optional[Callable] = None):
        self.routes_overlay = routes_overlay
        self.logger = logger

        # Create frame
        self.frame = ttk.LabelFrame(parent, text="SVG Routes Overlay")
        self.frame.pack(fill=tk.X, pady=5, padx=5)

        # Variables
        self.svg_visible_var = tk.BooleanVar(value=False)
        self.svg_color_var = tk.StringVar(value="yellow")
        self.svg_thickness_var = tk.IntVar(value=2)
        self.svg_use_registration_var = tk.BooleanVar(value=True)
        self.svg_scale_var = tk.DoubleVar(value=1.0)
        self.svg_offset_x_var = tk.IntVar(value=0)
        self.svg_offset_y_var = tk.IntVar(value=0)

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
            text="Show Routes Overlay",
            variable=self.svg_visible_var,
            command=self.toggle_svg_visibility,
            state='disabled'  # Disabled until routes are loaded
        )
        self.svg_visibility_check.pack(pady=2)

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
            values=["yellow", "red", "green", "blue", "cyan", "magenta"],
            width=8,
            state='disabled'
        )
        self.svg_color_combo.pack(side=tk.LEFT, padx=2)
        self.svg_color_combo.bind('<<ComboboxSelected>>', self.change_svg_color)

        ttk.Label(style_frame, text="Thickness:").pack(side=tk.LEFT, padx=(10,0))
        self.svg_thickness_spin = tk.Spinbox(
            style_frame,
            from_=1, to=10,
            width=3,
            textvariable=self.svg_thickness_var,
            command=self.change_svg_thickness,
            state='disabled'
        )
        self.svg_thickness_spin.pack(side=tk.LEFT, padx=2)

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

        ttk.Label(offset_frame, text="Y:").pack(side=tk.LEFT, padx=(5,0))
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
        self.disable_svg_controls()
        self.log("SVG routes cleared")

    def toggle_svg_visibility(self):
        """Toggle SVG routes overlay visibility"""
        visible = self.svg_visible_var.get()
        self.routes_overlay.set_visibility(visible)

        status = "visible" if visible else "hidden"
        self.log(f"SVG routes overlay {status}")

    def change_svg_color(self, event=None):
        """Change SVG routes color"""
        color_name = self.svg_color_var.get()
        color_map = {
            "yellow": (255, 255, 0),
            "red": (0, 0, 255),
            "green": (0, 255, 0),
            "blue": (255, 0, 0),
            "cyan": (255, 255, 0),
            "magenta": (255, 0, 255)
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

    def toggle_svg_transform_mode(self):
        """Toggle between registration and manual transform mode"""
        try:
            use_registration = self.svg_use_registration_var.get()
            self.routes_overlay.set_use_registration_transform(use_registration)

            if use_registration:
                # Hide manual transform controls
                self.manual_transform_frame.pack_forget()
                self.log("SVG overlay using registration transform")
            else:
                # Show manual transform controls
                self.manual_transform_frame.pack(fill=tk.X, pady=2)
                # Apply current manual transform
                self.update_manual_transform()
                self.log("SVG overlay using manual transform")
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
                    info_text += f"\nBounds: ({bounds[0]:.1f}, {bounds[1]:.1f}) to ({bounds[2]:.1f}, {bounds[3]:.1f})"
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
            return float(marker_length_str)
        except ValueError:
            self.marker_length_var.set("20.0")
            if self.logger:
                self.log("Invalid marker length, using default 20.0mm", "error")
            return 20.0
        except Exception as e:
            self.marker_length_var.set("20.0")
            if self.logger:
                self.log(f"Error parsing marker length: {e}, using default 20.0mm", "error")
            return 20.0