"""
Crosshair Control Panel with Auto-Center Feature
Simple control panel for managing crosshair overlay settings
Follows existing GUI panel pattern in the application
Auto-center button moves machine to center camera (crosshair) on detected marker
This is a utility to help with marker alignment and registration setup
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable


class CrosshairControlPanel:
    """Enhanced control panel for crosshair overlay settings with auto-center functionality

    Auto-center moves the machine to position the camera (crosshair) centered on detected marker.
    This is a utility for alignment and registration setup - no registration required.
    """

    def __init__(self, parent, marker_overlay, logger: Optional[Callable] = None,
                 grbl_controller=None, registration_manager=None):
        self.marker_overlay = marker_overlay
        self.logger = logger
        self.grbl_controller = grbl_controller
        self.registration_manager = registration_manager  # Keep for future features

        # Auto-center settings
        self.pixels_per_mm = 10.0  # Default scaling factor - can be made configurable

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="🎯 Crosshair & Auto-Center")
        self.frame.pack(fill=tk.X, pady=2, padx=5)

        # Variables
        self.crosshair_enabled_var = tk.BooleanVar(value=True)
        self.crosshair_size_var = tk.IntVar(value=20)
        self.pixels_per_mm_var = tk.DoubleVar(value=self.pixels_per_mm)

        self._create_widgets()
        self.log("Crosshair Control Panel with Auto-Center initialized")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[Crosshair] {message}", level)

    def set_controllers(self, grbl_controller, registration_manager=None):
        """Set GRBL controller and optionally registration manager after initialization"""
        self.grbl_controller = grbl_controller
        if registration_manager:
            self.registration_manager = registration_manager
        self._update_auto_center_button_state()

    def set_pixels_per_mm(self, pixels_per_mm: float):
        """Set the pixels-per-mm scaling factor for auto-center"""
        self.pixels_per_mm = max(0.1, pixels_per_mm)  # Prevent division by zero
        self.log(f"Pixels per mm set to: {pixels_per_mm:.2f}")

    def get_pixels_per_mm(self) -> float:
        """Get current pixels-per-mm scaling factor"""
        return self.pixels_per_mm

    def _create_widgets(self):
        """Create the control widgets"""
        # Main container
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill=tk.X, padx=5, pady=5)

        # Crosshair controls section
        crosshair_frame = ttk.LabelFrame(main_frame, text="Crosshair Display")
        crosshair_frame.pack(fill=tk.X, pady=2)

        # Crosshair enable/disable
        enable_frame = ttk.Frame(crosshair_frame)
        enable_frame.pack(fill=tk.X, pady=2, padx=3)

        self.enable_checkbox = ttk.Checkbutton(
            enable_frame,
            text="Show Crosshair",
            variable=self.crosshair_enabled_var,
            command=self._on_crosshair_toggle
        )
        self.enable_checkbox.pack(side=tk.LEFT)

        # Status label
        self.status_label = ttk.Label(enable_frame, text="", foreground="green")
        self.status_label.pack(side=tk.RIGHT)

        # Size control
        size_frame = ttk.Frame(crosshair_frame)
        size_frame.pack(fill=tk.X, pady=2, padx=3)

        ttk.Label(size_frame, text="Size:").pack(side=tk.LEFT)

        self.size_scale = ttk.Scale(
            size_frame,
            from_=5, to=50,
            orient=tk.HORIZONTAL,
            variable=self.crosshair_size_var,
            command=self._on_size_change
        )
        self.size_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        self.size_label = ttk.Label(size_frame, text="20")
        self.size_label.pack(side=tk.RIGHT)

        # NEW: Auto-Center section
        center_frame = ttk.LabelFrame(main_frame, text="Auto-Center")
        center_frame.pack(fill=tk.X, pady=(5, 2))

        # Auto-center button and info
        center_button_frame = ttk.Frame(center_frame)
        center_button_frame.pack(fill=tk.X, pady=2, padx=3)

        self.auto_center_btn = ttk.Button(
            center_button_frame,
            text="🎯 Center Camera",
            command=self._on_auto_center,
            width=15
        )
        self.auto_center_btn.pack(side=tk.LEFT)

        # Auto-center status
        self.center_status_label = ttk.Label(
            center_button_frame,
            text="Ready",
            foreground="gray",
            font=('Arial', 8)
        )
        self.center_status_label.pack(side=tk.LEFT, padx=(5, 0))

        # Pixels per mm setting
        ppm_frame = ttk.Frame(center_frame)
        ppm_frame.pack(fill=tk.X, pady=2, padx=3)

        ttk.Label(ppm_frame, text="Scale:", font=('Arial', 8)).pack(side=tk.LEFT)

        self.ppm_entry = ttk.Entry(
            ppm_frame,
            textvariable=self.pixels_per_mm_var,
            width=8,
            font=('Arial', 8)
        )
        self.ppm_entry.pack(side=tk.LEFT, padx=(2, 2))
        self.ppm_entry.bind('<Return>', self._on_ppm_change)
        self.ppm_entry.bind('<FocusOut>', self._on_ppm_change)

        ttk.Label(ppm_frame, text="px/mm", font=('Arial', 8)).pack(side=tk.LEFT)

        # Requirements info
        requirements_text = "Requires: Marker detected, GRBL connected"
        requirements_label = ttk.Label(
            center_frame,
            text=requirements_text,
            font=('Arial', 7),
            foreground="gray"
        )
        requirements_label.pack(pady=(0, 2))

        # General info text
        info_text = "Crosshair helps center markers • Auto-center moves machine to align camera"
        info_label = ttk.Label(main_frame, text=info_text,
                              font=('Arial', 8), foreground="gray")
        info_label.pack(pady=(5, 0))

        # Initialize button state
        self._update_auto_center_button_state()
        self._update_status()

    def _on_crosshair_toggle(self):
        """Handle crosshair enable/disable"""
        enabled = self.crosshair_enabled_var.get()

        if self.marker_overlay:
            self.marker_overlay.set_crosshair_visibility(enabled)

        self.log(f"Crosshair {'enabled' if enabled else 'disabled'}")
        self._update_status()

    def _on_size_change(self, value):
        """Handle crosshair size change"""
        size = int(float(value))
        self.size_label.config(text=str(size))

        if self.marker_overlay:
            self.marker_overlay.set_crosshair_size(size)

        self.log(f"Crosshair size changed to {size}")

    def _on_ppm_change(self, event=None):
        """Handle pixels per mm change"""
        try:
            new_ppm = self.pixels_per_mm_var.get()
            if new_ppm > 0:
                self.pixels_per_mm = new_ppm
                self.log(f"Pixels per mm changed to {new_ppm:.2f}")
            else:
                # Reset to previous valid value
                self.pixels_per_mm_var.set(self.pixels_per_mm)
                self.log("Invalid pixels per mm value, reset to previous", "warning")
        except tk.TclError:
            # Reset to previous valid value if invalid input
            self.pixels_per_mm_var.set(self.pixels_per_mm)
            self.log("Invalid pixels per mm input, reset to previous", "warning")

    def _on_auto_center(self):
        """Handle auto-center button click - centers camera on detected marker"""
        try:
            # Check all requirements
            error_msg = self._check_auto_center_requirements()
            if error_msg:
                messagebox.showerror("Auto-Center Error", error_msg)
                self.log(f"Auto-center failed: {error_msg}", "error")
                return

            # Get marker center position in pixels
            if not hasattr(self.marker_overlay, 'get_centering_status'):
                messagebox.showerror("Auto-Center Error", "Marker overlay doesn't support centering")
                return

            centering_status = self.marker_overlay.get_centering_status()
            if not centering_status or centering_status.get('offset') is None:
                messagebox.showerror("Auto-Center Error", "Cannot get marker offset")
                return

            # Get pixel offset from crosshair center
            offset_pixels = centering_status['offset']  # (x, y) offset in pixels
            offset_x_px, offset_y_px = offset_pixels

            # Convert pixel offset to machine movement (mm)
            # Note: Camera X maps to machine X, Camera Y maps to machine -Y (inverted)
            move_x_mm = offset_x_px / self.pixels_per_mm
            move_y_mm = -offset_y_px / self.pixels_per_mm  # Invert Y axis

            # Show confirmation dialog
            confirm_msg = (f"Center camera on marker?\n\n"
                          f"Move machine: X{move_x_mm:+.3f}mm, Y{move_y_mm:+.3f}mm\n"
                          f"(Pixel offset: {offset_x_px:+.0f}, {offset_y_px:+.0f})\n\n"
                          f"This will send relative movement commands to GRBL.")

            if not messagebox.askyesno("Confirm Auto-Center", confirm_msg):
                self.log("Auto-center cancelled by user")
                return

            # Update status
            self.center_status_label.config(text="Centering...", foreground="orange")
            self.auto_center_btn.config(state='disabled')

            # Send relative move command
            success = self._execute_auto_center_move(move_x_mm, move_y_mm)

            if success:
                self.center_status_label.config(text="✅ Centered", foreground="green")
                self.log(f"Auto-center successful: moved X{move_x_mm:+.3f}mm, Y{move_y_mm:+.3f}mm")

                # Reset status after 3 seconds
                self.frame.after(3000, lambda: self._reset_center_status())
            else:
                self.center_status_label.config(text="❌ Failed", foreground="red")
                self.log("Auto-center move command failed", "error")
                messagebox.showerror("Auto-Center Error", "Failed to execute move command")

                # Reset status after 3 seconds
                self.frame.after(3000, lambda: self._reset_center_status())

        except Exception as e:
            self.center_status_label.config(text="❌ Error", foreground="red")
            self.log(f"Auto-center error: {e}", "error")
            messagebox.showerror("Auto-Center Error", f"Unexpected error: {str(e)}")

            # Reset status after 3 seconds
            self.frame.after(3000, lambda: self._reset_center_status())

        finally:
            # Re-enable button
            self.frame.after(1000, lambda: self.auto_center_btn.config(state='normal'))

    def _check_auto_center_requirements(self) -> Optional[str]:
        """Check if auto-center requirements are met. Returns error message if not."""
        # Check marker detection
        if not self.marker_overlay or not self.marker_overlay.is_marker_detected():
            return "No ArUco marker detected"

        # Check GRBL connection (only need this to move machine)
        if not self.grbl_controller or not self.grbl_controller.is_connected:
            return "GRBL not connected"

        return None  # All requirements met (registration NOT needed for centering)

    def _execute_auto_center_move(self, move_x_mm: float, move_y_mm: float) -> bool:
        """Execute the auto-center relative move command"""
        try:
            # Use relative jogging for small centering movements
            feed_rate = 1000  # mm/min - adjust as needed

            # Check if we have jog_relative method (preferred for small moves)
            if hasattr(self.grbl_controller, 'jog_relative'):
                success = self.grbl_controller.jog_relative(
                    move_x_mm, move_y_mm, 0, feed_rate
                )
            else:
                # Fallback: get current position and move to new position
                current_pos = self.grbl_controller.get_position()
                if current_pos is None:
                    self.log("Cannot get current position for auto-center", "error")
                    return False

                new_x = current_pos[0] + move_x_mm
                new_y = current_pos[1] + move_y_mm
                success = self.grbl_controller.move_to(new_x, new_y, None, feed_rate)

            return success
        except Exception as e:
            self.log(f"Move command failed: {e}", "error")
            return False

    def _reset_center_status(self):
        """Reset center status to default"""
        self.center_status_label.config(text="Ready", foreground="gray")
        self._update_auto_center_button_state()

    def _update_auto_center_button_state(self):
        """Update auto-center button state based on requirements"""
        try:
            error_msg = self._check_auto_center_requirements()

            if error_msg:
                self.auto_center_btn.config(state='disabled')
                self.center_status_label.config(text="Not ready", foreground="gray")
            else:
                self.auto_center_btn.config(state='normal')
                if self.center_status_label.cget('text') in ['Ready', 'Not ready']:
                    self.center_status_label.config(text="Ready", foreground="green")
        except:
            # If any error in checking requirements, disable button
            self.auto_center_btn.config(state='disabled')

    def _update_status(self):
        """Update status display"""
        if self.crosshair_enabled_var.get():
            if self.marker_overlay and self.marker_overlay.is_marker_detected():
                centering_status = self.marker_overlay.get_centering_status()
                status_text = centering_status.get('status', 'Unknown')
                color = {
                    'CENTERED': 'green',
                    'CLOSE': 'orange',
                    'ADJUST POSITION': 'red'
                }.get(status_text, 'gray')
                self.status_label.config(text=status_text, foreground=color)
            else:
                self.status_label.config(text="No marker", foreground="gray")
        else:
            self.status_label.config(text="Disabled", foreground="gray")

        # Update auto-center button state
        self._update_auto_center_button_state()

    def update_status_display(self):
        """Update status display - call this periodically from main loop"""
        self._update_status()

    def get_settings(self) -> dict:
        """Get current crosshair settings"""
        return {
            'enabled': self.crosshair_enabled_var.get(),
            'size': self.crosshair_size_var.get(),
            'pixels_per_mm': self.pixels_per_mm
        }

    def set_settings(self, settings: dict):
        """Apply crosshair settings"""
        if 'enabled' in settings:
            self.crosshair_enabled_var.set(settings['enabled'])
            self._on_crosshair_toggle()

        if 'size' in settings:
            self.crosshair_size_var.set(settings['size'])
            self._on_size_change(str(settings['size']))

        if 'pixels_per_mm' in settings:
            self.pixels_per_mm = settings['pixels_per_mm']
            self.pixels_per_mm_var.set(self.pixels_per_mm)