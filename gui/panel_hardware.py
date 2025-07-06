"""
Compact Machine Configuration Panel
Modified to remove validation UI area and machine bounds panel - just show status
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Dict, Any
from services.event_broker import event_aware, event_handler, EventPriority
from services.grbl_controller import GRBLEvents
from services.hardware_service import HardwareEvents, MachineOrigin


@event_aware()
class MachineConfigPanel:
    """Compact machine configuration panel - status focused, minimal configuration"""

    def __init__(self, parent, grbl_controller, hardware_service, logger: Optional[Callable] = None):
        self.grbl_controller = grbl_controller
        self.hardware_service = hardware_service
        self.logger = logger

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Machine Configuration")
        self.frame.pack(fill=tk.X, pady=2, padx=5)

        # Status variables
        self.connection_status_var = tk.StringVar(value="Disconnected")
        self.machine_position_var = tk.StringVar(value="Position: Unknown")
        self.machine_status_var = tk.StringVar(value="Status: Unknown")

        # Configuration variables
        self.machine_size_x_var = tk.StringVar(value="450")
        self.machine_size_y_var = tk.StringVar(value="450")
        self.machine_size_z_var = tk.StringVar(value="80")
        self.machine_origin_var = tk.StringVar(value="bottom_left")

        self._setup_widgets()
        self._update_from_hardware_service()

        # Log initial configuration validation
        self._log_configuration_validation()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"MachineConfig: {message}", level)

    def _setup_widgets(self):
        """Setup compact configuration widgets"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # Tab 1: Status (real-time information)
        status_tab = ttk.Frame(notebook)
        notebook.add(status_tab, text="Status")
        self._setup_status_tab(status_tab)

        # Tab 2: Configuration (basic machine settings)
        config_tab = ttk.Frame(notebook)
        notebook.add(config_tab, text="Config")
        self._setup_config_tab(config_tab)

    def _setup_status_tab(self, parent):
        """Setup machine status display tab"""
        # Connection status
        conn_frame = ttk.Frame(parent)
        conn_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(conn_frame, text="Connection:", font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT)
        self.conn_status_label = ttk.Label(conn_frame, textvariable=self.connection_status_var,
                                          foreground="red", font=('TkDefaultFont', 9))
        self.conn_status_label.pack(side=tk.LEFT, padx=(5, 0))

        # Machine status
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=2, padx=5)

        self.status_label = ttk.Label(status_frame, textvariable=self.machine_status_var,
                                     font=('TkDefaultFont', 9))
        self.status_label.pack(side=tk.LEFT)

        # Position
        pos_frame = ttk.Frame(parent)
        pos_frame.pack(fill=tk.X, pady=2, padx=5)

        self.pos_label = ttk.Label(pos_frame, textvariable=self.machine_position_var,
                                  font=('TkDefaultFont', 9))
        self.pos_label.pack(side=tk.LEFT)

        # Separator
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Current machine info (read-only display)
        info_frame = ttk.LabelFrame(parent, text="Current Configuration")
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        # Machine size display
        size_display_frame = ttk.Frame(info_frame)
        size_display_frame.pack(fill=tk.X, pady=2, padx=5)

        ttk.Label(size_display_frame, text="Size:", font=('TkDefaultFont', 8, 'bold')).pack(side=tk.LEFT)
        self.size_display_label = ttk.Label(size_display_frame, text="450×450×80mm",
                                           font=('TkDefaultFont', 8), foreground="blue")
        self.size_display_label.pack(side=tk.LEFT, padx=(5, 0))

        # Origin display
        origin_display_frame = ttk.Frame(info_frame)
        origin_display_frame.pack(fill=tk.X, pady=2, padx=5)

        ttk.Label(origin_display_frame, text="Origin:", font=('TkDefaultFont', 8, 'bold')).pack(side=tk.LEFT)
        self.origin_display_label = ttk.Label(origin_display_frame, text="Bottom-Left (0,0)",
                                             font=('TkDefaultFont', 8), foreground="blue")
        self.origin_display_label.pack(side=tk.LEFT, padx=(5, 0))

        # Bounds display
        bounds_display_frame = ttk.Frame(info_frame)
        bounds_display_frame.pack(fill=tk.X, pady=2, padx=5)

        ttk.Label(bounds_display_frame, text="Bounds:", font=('TkDefaultFont', 8, 'bold')).pack(side=tk.LEFT)
        self.bounds_display_label = ttk.Label(bounds_display_frame, text="X(0,450) Y(0,450) Z(0,80)",
                                             font=('TkDefaultFont', 8), foreground="blue")
        self.bounds_display_label.pack(side=tk.LEFT, padx=(5, 0))

    def _setup_config_tab(self, parent):
        """Setup basic machine configuration tab"""
        # Machine size configuration
        size_frame = ttk.LabelFrame(parent, text="Machine Size (mm)")
        size_frame.pack(fill=tk.X, padx=5, pady=5)

        size_grid = ttk.Frame(size_frame)
        size_grid.pack(pady=5, padx=5)

        # X size
        ttk.Label(size_grid, text="X:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(size_grid, textvariable=self.machine_size_x_var, width=8).grid(row=0, column=1, padx=(0, 10))

        # Y size
        ttk.Label(size_grid, text="Y:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        ttk.Entry(size_grid, textvariable=self.machine_size_y_var, width=8).grid(row=0, column=3, padx=(0, 10))

        # Z size
        ttk.Label(size_grid, text="Z:").grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
        ttk.Entry(size_grid, textvariable=self.machine_size_z_var, width=8).grid(row=0, column=5)

        # Apply size button
        ttk.Button(size_frame, text="Apply Size", command=self._apply_machine_size).pack(pady=5)

        # Machine origin configuration
        origin_frame = ttk.LabelFrame(parent, text="Machine Origin")
        origin_frame.pack(fill=tk.X, padx=5, pady=5)

        origin_info = ttk.Label(origin_frame, text="Where is (0,0) located on your machine?",
                               font=('TkDefaultFont', 8), foreground="gray")
        origin_info.pack(pady=2)

        # Origin selection
        origin_select_frame = ttk.Frame(origin_frame)
        origin_select_frame.pack(pady=5)

        ttk.Label(origin_select_frame, text="Origin:").pack(side=tk.LEFT)
        origin_combo = ttk.Combobox(origin_select_frame, textvariable=self.machine_origin_var,
                                   values=["bottom_left", "bottom_right", "top_left", "top_right"],
                                   state="readonly", width=12)
        origin_combo.pack(side=tk.LEFT, padx=(5, 10))

        ttk.Button(origin_select_frame, text="Apply Origin", command=self._apply_machine_origin).pack(side=tk.LEFT)

        # Quick setup buttons
        quick_frame = ttk.LabelFrame(parent, text="Quick Setup")
        quick_frame.pack(fill=tk.X, padx=5, pady=5)

        quick_btn_frame = ttk.Frame(quick_frame)
        quick_btn_frame.pack(pady=5)

        # Common machine sizes
        common_sizes = [
            ("200×200×80", 200, 200, 80),
            ("300×300×80", 300, 300, 80),
            ("450×450×80", 450, 450, 80),
            ("600×400×80", 600, 400, 80)
        ]

        for i, (label, x, y, z) in enumerate(common_sizes):
            ttk.Button(quick_btn_frame, text=label,
                      command=lambda x=x, y=y, z=z: self._quick_setup_size(x, y, z),
                      width=12).grid(row=i//2, column=i%2, padx=2, pady=2)

    def _apply_machine_size(self):
        """Apply machine size configuration"""
        try:
            x = float(self.machine_size_x_var.get())
            y = float(self.machine_size_y_var.get())
            z = float(self.machine_size_z_var.get())

            if x <= 0 or y <= 0 or z <= 0:
                self.log("Machine size must be positive", "error")
                return

            self.hardware_service.set_machine_size(x, y, z)
            self.log(f"Machine size set to: {x}×{y}×{z}mm")

        except ValueError:
            self.log("Invalid machine size values", "error")

    def _apply_machine_origin(self):
        """Apply machine origin configuration"""
        try:
            origin_str = self.machine_origin_var.get()
            origin = MachineOrigin(origin_str)

            self.hardware_service.set_machine_origin(origin)
            self.log(f"Machine origin set to: {origin_str}")

        except ValueError as e:
            self.log(f"Invalid machine origin: {e}", "error")

    def _quick_setup_size(self, x: float, y: float, z: float):
        """Quick setup machine size"""
        self.machine_size_x_var.set(str(x))
        self.machine_size_y_var.set(str(y))
        self.machine_size_z_var.set(str(z))
        self._apply_machine_size()

    def _update_from_hardware_service(self):
        """Update UI from hardware service state"""
        try:
            # Update configuration variables
            size = self.hardware_service.get_machine_size()
            self.machine_size_x_var.set(str(size['x']))
            self.machine_size_y_var.set(str(size['y']))
            self.machine_size_z_var.set(str(size['z']))

            origin = self.hardware_service.get_machine_origin_name()
            self.machine_origin_var.set(origin)

            # Update status displays
            self._update_status_displays()

        except Exception as e:
            self.log(f"Error updating from hardware service: {e}", "error")

    def _update_status_displays(self):
        """Update status display labels"""
        try:
            # Machine size display
            size = self.hardware_service.get_machine_size()
            size_text = f"{size['x']}×{size['y']}×{size['z']}mm"
            self.size_display_label.config(text=size_text)

            # Origin display
            origin_desc = self.hardware_service.get_origin_description()
            self.origin_display_label.config(text=origin_desc)

            # Bounds display
            bounds = self.hardware_service.get_machine_bounds()
            bounds_text = f"X({bounds['x_min']:.0f},{bounds['x_max']:.0f}) Y({bounds['y_min']:.0f},{bounds['y_max']:.0f}) Z({bounds['z_min']:.0f},{bounds['z_max']:.0f})"
            self.bounds_display_label.config(text=bounds_text)

        except Exception as e:
            self.log(f"Error updating status displays: {e}", "error")

    def _log_configuration_validation(self):
        """Log configuration validation instead of showing UI"""
        try:
            validation = self.hardware_service.validate_configuration()

            if validation['valid']:
                self.log("✅ Machine configuration is valid", "info")
            else:
                self.log("❌ Machine configuration has issues:", "warning")
                for issue in validation['issues']:
                    self.log(f"  • {issue}", "warning")

            if validation['warnings']:
                self.log("⚠️ Configuration warnings:", "warning")
                for warning in validation['warnings']:
                    self.log(f"  • {warning}", "warning")

            # Log key configuration details
            config = validation['configuration']
            self.log(f"Machine: {config['machine_size']['x']}×{config['machine_size']['y']}×{config['machine_size']['z']}mm, Origin: {config['origin']}")

        except Exception as e:
            self.log(f"Configuration validation error: {e}", "error")

    # Event handlers
    @event_handler(GRBLEvents.CONNECTED, EventPriority.HIGH)
    def _on_grbl_connected(self, success: bool):
        """Handle GRBL connection events"""
        if success:
            self.connection_status_var.set("Connected")
            self.conn_status_label.config(foreground="green")
            self.log("GRBL connected", "info")
            # Re-validate configuration on connection
            self._log_configuration_validation()
        else:
            self.connection_status_var.set("Failed")
            self.conn_status_label.config(foreground="red")

    @event_handler(GRBLEvents.DISCONNECTED)
    def _on_grbl_disconnected(self):
        """Handle GRBL disconnection events"""
        self.connection_status_var.set("Disconnected")
        self.conn_status_label.config(foreground="red")
        self.machine_status_var.set("Status: Disconnected")
        self.machine_position_var.set("Position: Unknown")

    @event_handler(GRBLEvents.STATUS_CHANGED)
    def _on_grbl_status_changed(self, status: str):
        """Handle GRBL status changes"""
        self.machine_status_var.set(f"Status: {status}")

    @event_handler(GRBLEvents.POSITION_CHANGED)
    def _on_grbl_position_changed(self, position: list):
        """Handle GRBL position changes"""
        pos_str = f"Position: X{position[0]:.2f} Y{position[1]:.2f} Z{position[2]:.2f}"
        self.machine_position_var.set(pos_str)

    @event_handler(HardwareEvents.MACHINE_SIZE_UPDATED)
    def _on_machine_size_updated(self, data: dict):
        """Handle machine size updates"""
        self._update_status_displays()
        self._log_configuration_validation()

    @event_handler(HardwareEvents.MACHINE_ORIGIN_UPDATED)
    def _on_machine_origin_updated(self, data: dict):
        """Handle machine origin updates"""
        self._update_status_displays()
        self._log_configuration_validation()

    def get_panel_status(self) -> Dict[str, Any]:
        """Get current panel status"""
        return {
            'connection': self.connection_status_var.get(),
            'machine_status': self.machine_status_var.get(),
            'position': self.machine_position_var.get(),
            'machine_size': {
                'x': self.machine_size_x_var.get(),
                'y': self.machine_size_y_var.get(),
                'z': self.machine_size_z_var.get()
            },
            'origin': self.machine_origin_var.get(),
            'grbl_connected': self.grbl_controller.is_connected if self.grbl_controller else False,
            'config_valid': self.hardware_service.validate_configuration()['valid'] if self.hardware_service else False
        }

    def refresh_status(self):
        """Manually refresh all status information"""
        try:
            self._update_from_hardware_service()

            if self.grbl_controller and self.grbl_controller.is_connected:
                try:
                    position = self.grbl_controller.get_position()
                    status = self.grbl_controller.get_status()

                    self._on_grbl_position_changed(position)
                    self._on_grbl_status_changed(status)

                except Exception as e:
                    self.log(f"Error refreshing GRBL status: {e}", "warning")

            self.log("Panel status refreshed", "info")

        except Exception as e:
            self.log(f"Error refreshing panel: {e}", "error")