# gui/panel_configuration.py
"""
Configuration Panel GUI
Provides interface for loading, saving, and editing YAML configurations
Follows SOLID principles with clean separation between UI and business logic
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable

from services.configuration_service import ConfigurationService, ConfigurationServiceEvents
from services.configuration_manager import ConfigurationEvents, ApplicationConfig
from services.hardware_service import MachineOrigin
from services.event_broker import event_aware, event_handler, EventPriority


@event_aware()
class ConfigurationPanel:
    """GUI panel for configuration management"""

    def __init__(self, parent, configuration_service: ConfigurationService, logger: Optional[Callable] = None):
        self.configuration_service = configuration_service
        self.logger = logger

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Configuration")
        self.frame.pack(fill=tk.X, pady=2, padx=5)

        # UI Variables
        self.current_file_var = tk.StringVar(value="No configuration loaded")
        self.auto_save_var = tk.BooleanVar(value=True)

        # Configuration editing variables
        self.setup_config_variables()

        # Setup UI
        self._create_widgets()

        # Initialize with current configuration if available
        self._initialize_with_current_config()

        self.log("Configuration Panel initialized")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(f"[ConfigPanel] {message}", level)

    def setup_config_variables(self):
        """Setup all configuration editing variables"""
        # Camera variables
        self.camera_id_var = tk.IntVar(value=0)
        self.resolution_width_var = tk.IntVar(value=640)
        self.resolution_height_var = tk.IntVar(value=480)
        self.calibration_file_var = tk.StringVar(value="")
        self.marker_length_var = tk.DoubleVar(value=15.0)

        # Hardware variables
        self.machine_size_x_var = tk.DoubleVar(value=450.0)
        self.machine_size_y_var = tk.DoubleVar(value=450.0)
        self.machine_size_z_var = tk.DoubleVar(value=80.0)

        self.camera_offset_x_var = tk.DoubleVar(value=-45.0)
        self.camera_offset_y_var = tk.DoubleVar(value=0.0)
        self.camera_offset_z_var = tk.DoubleVar(value=0.0)

        self.machine_origin_var = tk.StringVar(value="TOP_RIGHT")

        self.homing_x_var = tk.DoubleVar(value=-450.0)
        self.homing_y_var = tk.DoubleVar(value=-450.0)
        self.homing_z_var = tk.DoubleVar(value=0.0)

        # Application variables
        self.auto_connect_var = tk.BooleanVar(value=True)
        self.default_format_var = tk.StringVar(value="gcode")
        self.fov_samples_var = tk.IntVar(value=5)

    def _create_widgets(self):
        """Create all GUI widgets"""
        # File operations frame
        file_frame = ttk.Frame(self.frame)
        file_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(file_frame, text="Load Config", command=self.load_configuration).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="Save Config", command=self.save_configuration).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="Save As", command=self.save_configuration_as).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="New Default", command=self.create_default_configuration).pack(side=tk.LEFT, padx=2)

        # Current file status
        status_frame = ttk.Frame(self.frame)
        status_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(status_frame, text="Current:").pack(side=tk.LEFT)
        ttk.Label(status_frame, textvariable=self.current_file_var, foreground="blue").pack(side=tk.LEFT, padx=(5, 0))

        # Auto-save option
        ttk.Checkbutton(status_frame, text="Auto-save", variable=self.auto_save_var,
                        command=self.toggle_auto_save).pack(side=tk.RIGHT)

        # Configuration editing notebook
        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.X, padx=5, pady=5)

        # Camera tab
        self._create_camera_tab()

        # Hardware tab
        self._create_hardware_tab()

        # Application tab
        self._create_application_tab()

    def _create_camera_tab(self):
        """Create camera configuration tab"""
        camera_frame = ttk.Frame(self.notebook)
        self.notebook.add(camera_frame, text="Camera")

        # Camera ID and resolution
        basic_frame = ttk.LabelFrame(camera_frame, text="Basic Settings")
        basic_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(basic_frame, text="Camera ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(basic_frame, textvariable=self.camera_id_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(basic_frame, text="Resolution:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        res_frame = ttk.Frame(basic_frame)
        res_frame.grid(row=1, column=1, padx=5, pady=2)
        ttk.Entry(res_frame, textvariable=self.resolution_width_var, width=8).pack(side=tk.LEFT)
        ttk.Label(res_frame, text="x").pack(side=tk.LEFT, padx=2)
        ttk.Entry(res_frame, textvariable=self.resolution_height_var, width=8).pack(side=tk.LEFT)

        ttk.Label(basic_frame, text="Marker Length (mm):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(basic_frame, textvariable=self.marker_length_var, width=10).grid(row=2, column=1, padx=5, pady=2)

        # Calibration file
        calib_frame = ttk.LabelFrame(camera_frame, text="Calibration")
        calib_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(calib_frame, text="Calibration File:").pack(anchor=tk.W, padx=5, pady=2)
        file_frame = ttk.Frame(calib_frame)
        file_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Entry(file_frame, textvariable=self.calibration_file_var, state="readonly").pack(side=tk.LEFT, fill=tk.X,
                                                                                             expand=True)
        ttk.Button(file_frame, text="Browse", command=self.browse_calibration_file).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(file_frame, text="Clear", command=lambda: self.calibration_file_var.set("")).pack(side=tk.RIGHT)

        # Apply button
        ttk.Button(camera_frame, text="Apply Camera Settings", command=self.apply_camera_settings).pack(pady=5)

    def _create_hardware_tab(self):
        """Create hardware configuration tab"""
        hardware_frame = ttk.Frame(self.notebook)
        self.notebook.add(hardware_frame, text="Hardware")

        # Machine size
        size_frame = ttk.LabelFrame(hardware_frame, text="Machine Size (mm)")
        size_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(size_frame, text="X:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(size_frame, textvariable=self.machine_size_x_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(size_frame, text="Y:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(size_frame, textvariable=self.machine_size_y_var, width=10).grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(size_frame, text="Z:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(size_frame, textvariable=self.machine_size_z_var, width=10).grid(row=0, column=5, padx=5, pady=2)

        # Camera offset
        offset_frame = ttk.LabelFrame(hardware_frame, text="Camera Offset (mm)")
        offset_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(offset_frame, text="X:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(offset_frame, textvariable=self.camera_offset_x_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(offset_frame, text="Y:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(offset_frame, textvariable=self.camera_offset_y_var, width=10).grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(offset_frame, text="Z:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(offset_frame, textvariable=self.camera_offset_z_var, width=10).grid(row=0, column=5, padx=5, pady=2)

        # Machine origin
        origin_frame = ttk.LabelFrame(hardware_frame, text="Machine Origin")
        origin_frame.pack(fill=tk.X, padx=5, pady=2)

        origins = [origin.value for origin in MachineOrigin]
        ttk.Combobox(origin_frame, textvariable=self.machine_origin_var, values=origins,
                     state="readonly").pack(padx=5, pady=5)

        # Homing position
        homing_frame = ttk.LabelFrame(hardware_frame, text="Homing Position (mm)")
        homing_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(homing_frame, text="X:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(homing_frame, textvariable=self.homing_x_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(homing_frame, text="Y:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(homing_frame, textvariable=self.homing_y_var, width=10).grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(homing_frame, text="Z:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(homing_frame, textvariable=self.homing_z_var, width=10).grid(row=0, column=5, padx=5, pady=2)

        # Apply button
        ttk.Button(hardware_frame, text="Apply Hardware Settings", command=self.apply_hardware_settings).pack(pady=5)

    def _create_application_tab(self):
        """Create application configuration tab"""
        app_frame = ttk.Frame(self.notebook)
        self.notebook.add(app_frame, text="Application")

        # Connection settings
        conn_frame = ttk.LabelFrame(app_frame, text="Connection Settings")
        conn_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Checkbutton(conn_frame, text="Auto-connect camera on startup",
                        variable=self.auto_connect_var).pack(anchor=tk.W, padx=5, pady=2)

        # Export settings
        export_frame = ttk.LabelFrame(app_frame, text="Export Settings")
        export_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(export_frame, text="Default export format:").pack(anchor=tk.W, padx=5, pady=2)
        format_combo = ttk.Combobox(export_frame, textvariable=self.default_format_var,
                                    values=["gcode", "svg"], state="readonly")
        format_combo.pack(anchor=tk.W, padx=5, pady=2)

        # FOV calculation settings
        fov_frame = ttk.LabelFrame(app_frame, text="FOV Calculation")
        fov_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(fov_frame, text="Number of samples for averaging:").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Entry(fov_frame, textvariable=self.fov_samples_var, width=10).pack(anchor=tk.W, padx=5, pady=2)

        # Apply button
        ttk.Button(app_frame, text="Apply Application Settings", command=self.apply_application_settings).pack(pady=5)

    def load_configuration(self):
        """Load configuration from file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Load Configuration",
                filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
            )

            if file_path:
                success = self.configuration_service.load_and_apply_configuration(file_path)
                if success:
                    self.current_file_var.set(file_path)
                    # Force update the UI with loaded configuration
                    self._load_config_to_ui()
                    messagebox.showinfo("Success", "Configuration loaded successfully")
                    self.log(f"Configuration loaded from {file_path}")
                else:
                    messagebox.showerror("Error", "Failed to load configuration")

        except Exception as e:
            messagebox.showerror("Error", f"Load error: {e}")
            self.log(f"Load configuration error: {e}", "error")

    def save_configuration(self):
        """Save current configuration"""
        current_file = self.configuration_service.current_config_file
        if current_file:
            success = self.configuration_service.save_current_configuration(current_file)
            if success:
                messagebox.showinfo("Success", "Configuration saved successfully")
            else:
                messagebox.showerror("Error", "Failed to save configuration")
        else:
            self.save_configuration_as()

    def save_configuration_as(self):
        """Save configuration to new file"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Save Configuration As",
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
            )

            if file_path:
                success = self.configuration_service.save_current_configuration(file_path)
                if success:
                    self.current_file_var.set(file_path)
                    messagebox.showinfo("Success", "Configuration saved successfully")
                else:
                    messagebox.showerror("Error", "Failed to save configuration")

        except Exception as e:
            messagebox.showerror("Error", f"Save error: {e}")
            self.log(f"Save configuration error: {e}", "error")

    def create_default_configuration(self):
        """Create a new default configuration"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Create Default Configuration",
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
            )

            if file_path:
                success = self.configuration_service.create_default_configuration(file_path)
                if success:
                    self.current_file_var.set(file_path)
                    self._load_config_to_ui()
                    messagebox.showinfo("Success", "Default configuration created and loaded")
                else:
                    messagebox.showerror("Error", "Failed to create default configuration")

        except Exception as e:
            messagebox.showerror("Error", f"Create default error: {e}")
            self.log(f"Create default configuration error: {e}", "error")

    def browse_calibration_file(self):
        """Browse for camera calibration file"""
        file_path = filedialog.askopenfilename(
            title="Select Camera Calibration File",
            filetypes=[("NumPy files", "*.npz"), ("All files", "*.*")]
        )

        if file_path:
            self.calibration_file_var.set(file_path)

    def toggle_auto_save(self):
        """Toggle auto-save functionality"""
        self.configuration_service.set_auto_save(self.auto_save_var.get())
        self.log(f"Auto-save {'enabled' if self.auto_save_var.get() else 'disabled'}")

    def apply_camera_settings(self):
        """Apply camera settings to configuration service"""
        try:
            settings = {
                'camera_id': self.camera_id_var.get(),
                'resolution_width': self.resolution_width_var.get(),
                'resolution_height': self.resolution_height_var.get(),
                'calibration_file': self.calibration_file_var.get() if self.calibration_file_var.get() else None,
                'marker_length_mm': self.marker_length_var.get()
            }

            success = self.configuration_service.update_camera_settings(**settings)
            if success:
                messagebox.showinfo("Success", "Camera settings applied")
                self.log("Camera settings applied successfully")
            else:
                messagebox.showerror("Error", "Failed to apply camera settings")

        except Exception as e:
            messagebox.showerror("Error", f"Apply camera settings error: {e}")
            self.log(f"Apply camera settings error: {e}", "error")

    def apply_hardware_settings(self):
        """Apply hardware settings to configuration service"""
        try:
            settings = {
                'machine_size_x': self.machine_size_x_var.get(),
                'machine_size_y': self.machine_size_y_var.get(),
                'machine_size_z': self.machine_size_z_var.get(),
                'camera_offset_x': self.camera_offset_x_var.get(),
                'camera_offset_y': self.camera_offset_y_var.get(),
                'camera_offset_z': self.camera_offset_z_var.get(),
                'machine_origin': self.machine_origin_var.get(),
                'homing_position_x': self.homing_x_var.get(),
                'homing_position_y': self.homing_y_var.get(),
                'homing_position_z': self.homing_z_var.get()
            }

            success = self.configuration_service.update_hardware_settings(**settings)
            if success:
                messagebox.showinfo("Success", "Hardware settings applied")
                self.log("Hardware settings applied successfully")
            else:
                messagebox.showerror("Error", "Failed to apply hardware settings")

        except Exception as e:
            messagebox.showerror("Error", f"Apply hardware settings error: {e}")
            self.log(f"Apply hardware settings error: {e}", "error")

    def apply_application_settings(self):
        """Apply application settings to configuration service"""
        try:
            settings = {
                'auto_connect_camera': self.auto_connect_var.get(),
                'default_export_format': self.default_format_var.get(),
                'fov_calculation_samples': self.fov_samples_var.get()
            }

            success = self.configuration_service.update_application_settings(**settings)
            if success:
                messagebox.showinfo("Success", "Application settings applied")
                self.log("Application settings applied successfully")
            else:
                messagebox.showerror("Error", "Failed to apply application settings")

        except Exception as e:
            messagebox.showerror("Error", f"Apply application settings error: {e}")
            self.log(f"Apply application settings error: {e}", "error")

    def _load_config_to_ui(self):
        """Load current configuration values to UI"""
        config = self.configuration_service.get_current_configuration()
        if config is None:
            return

        try:
            # Camera settings
            self.camera_id_var.set(config.camera.camera_id)
            self.resolution_width_var.set(config.camera.resolution_width)
            self.resolution_height_var.set(config.camera.resolution_height)

            # Handle calibration file path properly
            calibration_file = config.camera.calibration_file
            if calibration_file:
                # Set the full path in the calibration file variable
                self.calibration_file_var.set(calibration_file)
                self.log(f"Loaded calibration file path: {calibration_file}")
            else:
                self.calibration_file_var.set("")
                self.log("No calibration file in configuration")

            self.marker_length_var.set(config.camera.marker_length_mm)

            # Hardware settings
            self.machine_size_x_var.set(config.hardware.machine_size_x)
            self.machine_size_y_var.set(config.hardware.machine_size_y)
            self.machine_size_z_var.set(config.hardware.machine_size_z)

            self.camera_offset_x_var.set(config.hardware.camera_offset_x)
            self.camera_offset_y_var.set(config.hardware.camera_offset_y)
            self.camera_offset_z_var.set(config.hardware.camera_offset_z)

            self.machine_origin_var.set(config.hardware.machine_origin)

            self.homing_x_var.set(config.hardware.homing_position_x)
            self.homing_y_var.set(config.hardware.homing_position_y)
            self.homing_z_var.set(config.hardware.homing_position_z)

            # Application settings
            self.auto_connect_var.set(config.application.auto_connect_camera)
            self.default_format_var.set(config.application.default_export_format)
            self.fov_samples_var.set(config.application.fov_calculation_samples)

            # Auto-save setting
            self.auto_save_var.set(self.configuration_service.auto_save_enabled)

        except Exception as e:
            self.log(f"Error loading config to UI: {e}", "error")

    def _initialize_with_current_config(self):
        """Initialize the panel with current configuration if available"""
        try:
            current_config = self.configuration_service.get_current_configuration()
            if current_config:
                self._load_config_to_ui()

                # Update current file display if we have a config file
                if self.configuration_service.current_config_file:
                    self.current_file_var.set(self.configuration_service.current_config_file)
                else:
                    self.current_file_var.set("Configuration loaded (no file)")

                self.log("Configuration panel initialized with current configuration")
            else:
                self.current_file_var.set("No configuration loaded")

        except Exception as e:
            self.log(f"Error initializing with current config: {e}", "error")
            self.current_file_var.set("Error loading current configuration")

    def _update_display(self):
        """Update display with current status"""
        if self.configuration_service.current_config_file:
            self.current_file_var.set(self.configuration_service.current_config_file)
        else:
            self.current_file_var.set("No configuration loaded")

    @event_handler(ConfigurationServiceEvents.APPLIED, EventPriority.NORMAL)
    def _on_configuration_applied(self, event_data):
        """Handle configuration applied event"""
        self.current_file_var.set(event_data['file_path'])
        self.log("Configuration applied successfully")

    @event_handler(ConfigurationServiceEvents.AUTO_SAVED, EventPriority.NORMAL)
    def _on_auto_saved(self, event_data):
        """Handle auto-save event"""
        self.log("Configuration auto-saved")

    @event_handler(ConfigurationEvents.ERROR, EventPriority.HIGH)
    def _on_configuration_error(self, error_message):
        """Handle configuration errors"""
        self.log(f"Configuration error: {error_message}", "error")
        messagebox.showerror("Configuration Error", error_message)