"""
Crosshair Control Panel
Simple control panel for managing crosshair overlay settings
Follows existing GUI panel pattern in the application
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable


class CrosshairControlPanel:
    """Simple control panel for crosshair overlay settings"""

    def __init__(self, parent, marker_overlay, logger: Optional[Callable] = None):
        self.marker_overlay = marker_overlay
        self.logger = logger

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="🎯 Crosshair Settings")
        self.frame.pack(fill=tk.X, pady=2, padx=5)

        # Variables
        self.crosshair_enabled_var = tk.BooleanVar(value=True)
        self.crosshair_size_var = tk.IntVar(value=20)

        self._create_widgets()
        self.log("Crosshair Control Panel initialized")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[Crosshair] {message}", level)

    def _create_widgets(self):
        """Create the control widgets"""
        # Main container
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill=tk.X, padx=5, pady=5)

        # Crosshair enable/disable
        enable_frame = ttk.Frame(main_frame)
        enable_frame.pack(fill=tk.X, pady=2)

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
        size_frame = ttk.Frame(main_frame)
        size_frame.pack(fill=tk.X, pady=2)

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

        # Info text
        info_text = "Crosshair helps center ArUco markers with camera"
        info_label = ttk.Label(main_frame, text=info_text,
                               font=('Arial', 8), foreground="gray")
        info_label.pack(pady=(5, 0))

        # Initialize status
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

    def update_status_display(self):
        """Update status display - call this periodically from main loop"""
        self._update_status()

    def get_settings(self) -> dict:
        """Get current crosshair settings"""
        return {
            'enabled': self.crosshair_enabled_var.get(),
            'size': self.crosshair_size_var.get()
        }

    def set_settings(self, settings: dict):
        """Apply crosshair settings"""
        if 'enabled' in settings:
            self.crosshair_enabled_var.set(settings['enabled'])
            self._on_crosshair_toggle()

        if 'size' in settings:
            self.crosshair_size_var.set(settings['size'])
            self._on_size_change(str(settings['size']))