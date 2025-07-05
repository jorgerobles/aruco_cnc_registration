"""
Machine Area Control Panel - Extracted from main_window.py
Provides controls for machine area visualization window
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable

from services.event_broker import event_aware, event_handler, EventPriority
from services.grbl_controller import GRBLEvents


@event_aware()
class MachineAreaPanel:
    """
    Control panel for machine area visualization
    Provides toggle, quick setup, and status display
    """

    def __init__(self, parent, machine_area_window=None, logger=None):
        self.parent = parent
        self.machine_area_window = machine_area_window
        self.logger = logger or print

        # GUI elements
        self.frame = None
        self.toggle_button = None

        # Callbacks
        self.toggle_callback = None
        self.quick_setup_callback = None

        self.setup_gui()
        self.log("Machine Area Control Panel initialized")

    def log(self, message: str, level: str = "info"):
        """Log message via logger"""
        if self.logger:
            self.logger(f"[MachineArea] {message}", level)

    def set_machine_area_window(self, machine_area_window):
        """Set the machine area window reference"""
        self.machine_area_window = machine_area_window

    def set_callbacks(self, toggle_callback: Callable, quick_setup_callback: Callable):
        """Set callback functions"""
        self.toggle_callback = toggle_callback
        self.quick_setup_callback = quick_setup_callback

    def setup_gui(self):
        """Setup the control panel GUI"""
        # Main frame
        self.frame = ttk.LabelFrame(self.parent, text="🗺️ Machine Area Visualization")
        self.frame.pack(fill=tk.X, pady=5)

        # Button frame
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=2)

        # Main toggle button
        self.toggle_button = ttk.Button(
            btn_frame,
            text="Show Machine Area",
            command=self.toggle_machine_area,
            width=18
        )
        self.toggle_button.pack(side=tk.LEFT, padx=2)

        # Quick settings frame
        settings_frame = ttk.Frame(btn_frame)
        settings_frame.pack(side=tk.RIGHT)

        ttk.Label(settings_frame, text="Quick Setup:", font=('Arial', 8)).pack(side=tk.LEFT, padx=2)

        # Machine size quick buttons
        for size in [200, 300, 400]:
            btn = ttk.Button(
                settings_frame,
                text=f"{size}mm",
                command=lambda s=size: self.set_machine_bounds_quick(s, s),
                width=6
            )
            btn.pack(side=tk.LEFT, padx=1)

        # Info frame
        info_frame = ttk.Frame(self.frame)
        info_frame.pack(fill=tk.X, padx=5, pady=2)

        info_text = "F10: Toggle | F11: Center | F12: Clear Trail | Right-click: Context Menu"
        ttk.Label(info_frame, text=info_text, font=('Arial', 7), foreground='gray').pack()

    def toggle_machine_area(self):
        """Toggle machine area window"""
        if self.toggle_callback:
            self.toggle_callback()
        else:
            self.log("No toggle callback set", "warning")

    def set_machine_bounds_quick(self, x_max: float, y_max: float):
        """Quick set machine bounds"""
        if self.quick_setup_callback:
            self.quick_setup_callback(x_max, y_max)
        else:
            self.log("No quick setup callback set", "warning")

    def update_toggle_button(self, is_visible: bool):
        """Update toggle button text and appearance"""
        if self.toggle_button:
            if is_visible:
                self.toggle_button.config(text="Hide Machine Area")
            else:
                self.toggle_button.config(text="Show Machine Area")

    def update_machine_area_status(self):
        """Update panel based on machine area window status"""
        if self.machine_area_window:
            try:
                is_visible = getattr(self.machine_area_window, 'is_visible', False)
                self.update_toggle_button(is_visible)
            except Exception as e:
                self.log(f"Error updating status: {e}", "error")

    def get_panel_status(self):
        """Get current panel status"""
        return {
            'has_machine_area_window': self.machine_area_window is not None,
            'machine_area_visible': getattr(self.machine_area_window, 'is_visible',
                                            False) if self.machine_area_window else False,
            'toggle_button_text': self.toggle_button.cget('text') if self.toggle_button else None
        }

    @event_handler(GRBLEvents.CONNECTED, EventPriority.NORMAL)
    def _on_grbl_connected(self, success: bool):
        """Handle GRBL connection events"""
        # Could enable/disable certain features based on connection
        pass

    @event_handler(GRBLEvents.DISCONNECTED, EventPriority.NORMAL)
    def _on_grbl_disconnected(self):
        """Handle GRBL disconnection events"""
        # Could disable certain features when disconnected
        pass