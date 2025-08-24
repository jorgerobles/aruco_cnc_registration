# main.py
"""
GRBL Camera Registration Application - Updated with Configuration System
Main entry point for the application with YAML configuration support
"""

import tkinter as tk
import os
from pathlib import Path

from gui.main_window import RegistrationGUI
from gui.panel_configuration import ConfigurationPanel
from services.camera_manager import CameraManager
from services.grbl_controller import GRBLController
from services.hardware_service import HardwareService, MachineOrigin
from services.io.format_gcode import GCodeExporter
from services.io.format_svg import SVGImporter, SVGExporter
from services.io.manager import ImportExportManager
from services.registration_manager import RegistrationManager
from services.routes_manager import RouteManager
from services.configuration_service import ConfigurationService
from services.configuration_bridge import initialize_camera_panel_with_config


def setup_default_directories():
    """Create default directories if they don't exist"""
    directories = [
        "config",
        "calibration",
        "routes",
        "registration"
    ]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)


def main():
    """Main application entry point with configuration system"""
    root = tk.Tk()

    # Setup default directories
    setup_default_directories()

    # Create core services with default values
    # These will be updated by configuration if loaded
    grbl_controller = GRBLController()
    grbl_controller.enable_verbose_logging()

    hardware_service = HardwareService(
        machine_size=(450, 450, 80),  # Default values
        camera_offset=(-45, 0, 0),  # Will be updated by config
        machine_origin=MachineOrigin.TOP_RIGHT,  # Will be updated by config
        homing_position=(-450, -450, 0)  # Will be updated by config
    )

    camera_manager = CameraManager()

    # Create configuration service
    configuration_service = ConfigurationService(
        hardware_service=hardware_service,
        camera_manager=camera_manager
    )

    # Setup import/export manager
    format_manager = ImportExportManager()
    format_manager.register_importer(SVGImporter())
    format_manager.register_exporter(SVGExporter())
    format_manager.register_exporter(GCodeExporter())

    # Try to load default configuration
    default_config_path = "config/default.yaml"
    config_loaded = False

    if os.path.exists(default_config_path):
        print(f"Loading default configuration from: {default_config_path}")
        success = configuration_service.load_and_apply_configuration(default_config_path)
        if success:
            print("Default configuration loaded successfully")
            config_loaded = True
        else:
            print("Failed to load default configuration, using defaults")
    else:
        print(f"No default configuration found at {default_config_path}")
        print("You can create one using the Configuration panel")

    # Create main application
    app = RegistrationGUI(root,
                          registration_manager=RegistrationManager(),
                          camera_manager=camera_manager,
                          grbl_controller=grbl_controller,
                          route_manager=RouteManager(format_manager),
                          hardware_service=hardware_service
                          )

    # IMPORTANT: Initialize camera panel with current configuration after GUI is created
    # This ensures the camera ID field shows the correct value from configuration
    if config_loaded and hasattr(app, 'camera_panel'):
        # Use the utility function to sync camera panel with configuration
        initialize_camera_panel_with_config(app.camera_panel, configuration_service)
        print("Camera panel synchronized with configuration")

    # Alternative: If app doesn't expose camera_panel directly, we can wait and sync after GUI is ready
    if config_loaded:
        def sync_after_gui_ready():
            """Sync camera panel after GUI is fully initialized"""
            try:
                # Try to find camera panel in the app and sync it
                if hasattr(app, 'camera_panel'):
                    initialize_camera_panel_with_config(app.camera_panel, configuration_service)
                    print("Camera panel synchronized with configuration (delayed)")
            except Exception as e:
                print(f"Could not sync camera panel: {e}")

        # Schedule sync after GUI is ready
        root.after(500, sync_after_gui_ready)

    # Add configuration panel to the main window
    def open_configuration_window():
        """Open configuration window"""
        config_window = tk.Toplevel(root)
        config_window.title("Configuration Manager")
        config_window.geometry("600x500")

        config_panel = ConfigurationPanel(
            config_window,
            configuration_service,
            logger=lambda msg, level="info": print(f"[{level.upper()}] {msg}")
        )

        # Make configuration window modal
        config_window.transient(root)
        config_window.grab_set()

        # Center the window
        config_window.update_idletasks()
        x = (config_window.winfo_screenwidth() // 2) - (config_window.winfo_width() // 2)
        y = (config_window.winfo_screenheight() // 2) - (config_window.winfo_height() // 2)
        config_window.geometry(f"+{x}+{y}")

    # Add configuration menu to main window
    try:
        if hasattr(app, 'menubar'):
            # Add Configuration menu
            config_menu = tk.Menu(app.menubar, tearoff=0)
            config_menu.add_command(label="Open Configuration Manager", command=open_configuration_window)
            config_menu.add_separator()
            config_menu.add_command(label="Load Configuration...",
                                    command=lambda: load_config_dialog(configuration_service))
            config_menu.add_command(label="Save Configuration...",
                                    command=lambda: save_config_dialog(configuration_service))
            app.menubar.add_cascade(label="Configuration", menu=config_menu)
        else:
            # Add configuration button to main window if no menu bar
            config_button = tk.Button(root, text="Configuration", command=open_configuration_window)
            config_button.pack(side=tk.TOP, anchor=tk.NE, padx=5, pady=5)
    except:
        # Fallback: create configuration button
        config_button = tk.Button(root, text="Configuration", command=open_configuration_window)
        config_button.pack(side=tk.TOP, anchor=tk.NE, padx=5, pady=5)

    # Setup auto-connect based on configuration
    config = configuration_service.get_current_configuration()
    if config and config.application.auto_connect_camera:
        # Auto-connect camera after GUI is ready
        root.after(1000, lambda: camera_manager.connect())

    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

    # Add configuration panel to the main window
    # This would need to be integrated into the main GUI layout
    # For now, we'll add it as a separate window accessible from menu
    def open_configuration_window():
        """Open configuration window"""
        config_window = tk.Toplevel(root)
        config_window.title("Configuration Manager")
        config_window.geometry("600x500")

        config_panel = ConfigurationPanel(
            config_window,
            configuration_service,
            logger=lambda msg, level="info": print(f"[{level.upper()}] {msg}")
        )

        # Make configuration window modal
        config_window.transient(root)
        config_window.grab_set()

        # Center the window
        config_window.update_idletasks()
        x = (config_window.winfo_screenwidth() // 2) - (config_window.winfo_width() // 2)
        y = (config_window.winfo_screenheight() // 2) - (config_window.winfo_height() // 2)
        config_window.geometry(f"+{x}+{y}")

    # Add configuration menu to main window
    # This assumes the main window has a menu bar
    try:
        if hasattr(app, 'menubar'):
            # Add Configuration menu
            config_menu = tk.Menu(app.menubar, tearoff=0)
            config_menu.add_command(label="Open Configuration Manager", command=open_configuration_window)
            config_menu.add_separator()
            config_menu.add_command(label="Load Configuration...",
                                    command=lambda: load_config_dialog(configuration_service))
            config_menu.add_command(label="Save Configuration...",
                                    command=lambda: save_config_dialog(configuration_service))
            app.menubar.add_cascade(label="Configuration", menu=config_menu)
        else:
            # Add configuration button to main window if no menu bar
            config_button = tk.Button(root, text="Configuration", command=open_configuration_window)
            config_button.pack(side=tk.TOP, anchor=tk.NE, padx=5, pady=5)
    except:
        # Fallback: create configuration button
        config_button = tk.Button(root, text="Configuration", command=open_configuration_window)
        config_button.pack(side=tk.TOP, anchor=tk.NE, padx=5, pady=5)

    # Setup auto-connect based on configuration
    config = configuration_service.get_current_configuration()
    if config and config.application.auto_connect_camera:
        # Auto-connect camera after GUI is ready
        root.after(1000, lambda: camera_manager.connect())

    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


def load_config_dialog(configuration_service):
    """Simple configuration load dialog"""
    from tkinter import filedialog, messagebox

    file_path = filedialog.askopenfilename(
        title="Load Configuration",
        filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        initialdir="config"
    )

    if file_path:
        success = configuration_service.load_and_apply_configuration(file_path)
        if success:
            messagebox.showinfo("Success", "Configuration loaded successfully")
        else:
            messagebox.showerror("Error", "Failed to load configuration")


def save_config_dialog(configuration_service):
    """Simple configuration save dialog"""
    from tkinter import filedialog, messagebox

    file_path = filedialog.asksaveasfilename(
        title="Save Configuration",
        defaultextension=".yaml",
        filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
        initialdir="config"
    )

    if file_path:
        success = configuration_service.save_current_configuration(file_path)
        if success:
            messagebox.showinfo("Success", "Configuration saved successfully")
        else:
            messagebox.showerror("Error", "Failed to save configuration")


if __name__ == '__main__':
    main()