# main.py
"""
GRBL Camera Registration Application - Updated with Store System Integration
Main entry point with incremental store system adoption
Follows SOLID principles with dependency injection
"""

import tkinter as tk
import os
from pathlib import Path

# Core application imports
from gui.main_window import RegistrationGUI
from gui.panel_configuration import ConfigurationPanel

# Store system imports
from store.store import ApplicationStore
from store.middleware import DEFAULT_MIDDLEWARE

# Service imports (CameraManager is refactored, others remain event-based during transition)
from services.camera_manager import CameraManager  # ← Refactored version
from services.grbl_controller import GRBLController
from services.hardware_service import HardwareService, MachineOrigin
from services.registration_manager import RegistrationManager
from services.routes_manager import RouteManager
from services.configuration_service import ConfigurationService

# I/O imports
from services.io.format_gcode import GCodeExporter
from services.io.format_svg import SVGImporter, SVGExporter
from services.io.manager import ImportExportManager

# Configuration bridge imports
from services.configuration_bridge import initialize_camera_panel_with_config


def setup_default_directories():
    """Create default directories if they don't exist"""
    directories = [
        "config",
        "calibration",
        "routes",
        "registration",
        "tests"  # Add tests directory
    ]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)


def create_store() -> ApplicationStore:
    """Create and configure the application store"""
    store = ApplicationStore()

    # Add middleware for logging and debugging
    for middleware in DEFAULT_MIDDLEWARE:
        store.add_middleware(middleware)

    return store


def create_services(store: ApplicationStore):
    """
    Create all application services with proper dependency injection
    Only CameraManager uses store currently - others remain event-based during transition
    """

    # === STORE-INTEGRATED SERVICES ===

    # CameraManager uses store (refactored)
    camera_manager = CameraManager(store=store, enable_capture_thread=True)

    # === EVENT-BASED SERVICES (TO BE REFACTORED LATER) ===

    # GRBL Controller (event-based)
    grbl_controller = GRBLController()
    grbl_controller.enable_verbose_logging()

    # Hardware Service (event-based)
    hardware_service = HardwareService(
        machine_size=(450, 450, 80),  # Default values - will be updated by config
        camera_offset=(-45, 0, 0),  # Will be updated by config
        machine_origin=MachineOrigin.TOP_RIGHT,  # Will be updated by config
        homing_position=(-450, -450, 0)  # Will be updated by config
    )

    # Registration Manager (event-based)
    registration_manager = RegistrationManager()

    # Import/Export Manager
    format_manager = ImportExportManager()
    format_manager.register_importer(SVGImporter())
    format_manager.register_exporter(SVGExporter())
    format_manager.register_exporter(GCodeExporter())

    # Route Manager (event-based)
    route_manager = RouteManager(format_manager)

    # Configuration Service (event-based, but works with store-integrated camera_manager)
    configuration_service = ConfigurationService(
        hardware_service=hardware_service,
        camera_manager=camera_manager  # ← Passes refactored camera manager
    )

    return {
        'camera_manager': camera_manager,
        'grbl_controller': grbl_controller,
        'hardware_service': hardware_service,
        'registration_manager': registration_manager,
        'route_manager': route_manager,
        'configuration_service': configuration_service
    }


def load_default_configuration(configuration_service, store: ApplicationStore) -> bool:
    """Load default configuration if available"""
    default_config_path = "config/default_cnc_config.yaml"

    if os.path.exists(default_config_path):
        print(f"Loading default configuration from: {default_config_path}")
        success = configuration_service.load_and_apply_configuration(default_config_path)

        if success:
            print("Default configuration loaded successfully")

            # Additional store initialization based on configuration
            config = configuration_service.get_current_configuration()
            if config:
                # Could dispatch configuration-related actions to store here
                # store.dispatch(ConfigActions.loaded(config, default_config_path))
                pass

            return True
        else:
            print("Failed to load default configuration, using defaults")
    else:
        print(f"No default configuration found at {default_config_path}")
        print("You can create one using the Configuration panel")

    return False


def create_gui(root, services, store: ApplicationStore):
    """Create the main GUI with both store and event systems"""

    # Create main application GUI
    app = RegistrationGUI(
        root=root,
        registration_manager=services['registration_manager'],
        camera_manager=services['camera_manager'],  # ← Store-integrated version
        grbl_controller=services['grbl_controller'],
        route_manager=services['route_manager'],
        hardware_service=services['hardware_service'],
        store=store
    )

    # Add store access to GUI for store-integrated panels
    app.store = store  # Make store available to GUI components

    # Update camera panel to use store if it exists
    if hasattr(app, 'calibration_panel') and app.calibration_panel:
        # Replace the camera panel with store-integrated version
        parent = app.calibration_panel.frame.master
        app.calibration_panel.cleanup() if hasattr(app.calibration_panel, 'cleanup') else None

        # Import the updated camera panel
        from gui.panel_camera import CameraPanel

        app.calibration_panel = CameraPanel(
            parent,
            services['camera_manager'],
            services['hardware_service'],
            store,  # ← Pass store
            logger=print  # ← Pass logger
        )

    return app


def setup_configuration_menu(root, app, configuration_service):
    """Setup configuration management UI"""

    def open_configuration_window():
        """Open configuration management window"""
        config_window = tk.Toplevel(root)
        config_window.title("Configuration Manager")
        config_window.geometry("800x600")

        # Create configuration panel
        config_panel = ConfigurationPanel(
            parent=config_window,
            configuration_service=configuration_service,
            logger=print
        )

        # Center window relative to main window
        config_window.transient(root)
        config_window.grab_set()

        # Center on screen
        config_window.geometry(f"+{root.winfo_x() + 50}+{root.winfo_y() + 50}")

    def load_config_dialog():
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

    def save_config_dialog():
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

    # Add configuration menu to main window
    try:
        if hasattr(app, 'menubar'):
            # Add Configuration menu
            config_menu = tk.Menu(app.menubar, tearoff=0)
            config_menu.add_command(label="Open Configuration Manager", command=open_configuration_window)
            config_menu.add_separator()
            config_menu.add_command(label="Load Configuration...", command=load_config_dialog)
            config_menu.add_command(label="Save Configuration...", command=save_config_dialog)
            app.menubar.add_cascade(label="Configuration", menu=config_menu)
        else:
            # Add configuration button to main window if no menu bar
            config_button = tk.Button(root, text="Configuration", command=open_configuration_window)
            config_button.pack(side=tk.TOP, anchor=tk.NE, padx=5, pady=5)
    except:
        # Fallback: create configuration button
        config_button = tk.Button(root, text="Configuration", command=open_configuration_window)
        config_button.pack(side=tk.TOP, anchor=tk.NE, padx=5, pady=5)


def setup_auto_connect(services, config, store: ApplicationStore):
    """Setup auto-connect functionality"""

    if config and config.application.auto_connect_camera:
        # Auto-connect camera after GUI is ready
        def auto_connect():
            success = services['camera_manager'].connect()
            if success:
                print("Auto-connected to camera")
            else:
                print("Auto-connect to camera failed")

        # Delay auto-connect to ensure GUI is ready
        return auto_connect

    return None


def setup_store_debugging(store: ApplicationStore):
    """Setup store debugging and monitoring"""

    def log_state_changes(state):
        """Log significant state changes for debugging"""
        # Only log important state changes to avoid spam
        camera_state = state.camera
        machine_state = state.machine

        # Log connection changes
        if hasattr(log_state_changes, '_prev_camera_connected'):
            if camera_state.connected != log_state_changes._prev_camera_connected:
                print(f"[STORE] Camera connection: {camera_state.connected}")
        log_state_changes._prev_camera_connected = camera_state.connected

        if hasattr(log_state_changes, '_prev_machine_connected'):
            if machine_state.connected != log_state_changes._prev_machine_connected:
                print(f"[STORE] Machine connection: {machine_state.connected}")
        log_state_changes._prev_machine_connected = machine_state.connected

    # Subscribe to store changes for debugging
    store.subscribe(log_state_changes)


def main():
    """Main application entry point with store system integration"""

    print("Starting GRBL Camera Registration Application with Store System...")

    # Setup Tkinter root
    root = tk.Tk()
    root.title("GRBL Camera Registration - Store Integration")
    root.geometry("1600x900")

    # Setup default directories
    setup_default_directories()

    # === INITIALIZE STORE SYSTEM ===
    print("Initializing store system...")
    store = create_store()

    # Setup store debugging (optional)
    if os.environ.get('DEBUG_STORE'):
        setup_store_debugging(store)

    # === CREATE SERVICES ===
    print("Creating services...")
    services = create_services(store)

    # === LOAD CONFIGURATION ===
    print("Loading configuration...")
    config_loaded = load_default_configuration(services['configuration_service'], store)
    config = services['configuration_service'].get_current_configuration() if config_loaded else None

    # === CREATE GUI ===
    print("Creating GUI...")
    app = create_gui(root, services, store)

    # === INITIALIZE CAMERA PANEL SYNCHRONIZATION ===
    if config_loaded and hasattr(app, 'camera_panel'):
        print("Synchronizing camera panel with configuration...")
        try:
            initialize_camera_panel_with_config(app.camera_panel, services['configuration_service'])
            print("Camera panel synchronized with configuration")
        except Exception as e:
            print(f"Failed to synchronize camera panel: {e}")

    # === SETUP CONFIGURATION MENU ===
    setup_configuration_menu(root, app, services['configuration_service'])

    # === SETUP AUTO-CONNECT ===
    auto_connect_func = setup_auto_connect(services, config, store)
    if auto_connect_func:
        root.after(1000, auto_connect_func)  # Delay auto-connect

    # === SETUP SHUTDOWN HANDLER ===
    def on_closing():
        """Handle application shutdown"""
        print("Shutting down application...")

        # Disconnect camera if connected
        if services['camera_manager'].is_connected:
            print("Disconnecting camera...")
            services['camera_manager'].disconnect()

        # Close GRBL connection if connected
        if hasattr(services['grbl_controller'], 'disconnect'):
            if services['grbl_controller'].is_connected:
                print("Disconnecting GRBL controller...")
                services['grbl_controller'].disconnect()

        # Call app's cleanup if available
        if hasattr(app, 'on_closing'):
            app.on_closing()

        print("Application shutdown complete")

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # === START APPLICATION ===
    print("Application started successfully")
    print("=" * 50)
    print("STORE INTEGRATION STATUS:")
    print("✓ CameraManager: Store-integrated")
    print("○ GRBLController: Event-based (to be refactored)")
    print("○ HardwareService: Event-based (to be refactored)")
    print("○ RegistrationManager: Event-based (to be refactored)")
    print("○ RouteManager: Event-based (to be refactored)")
    print("=" * 50)

    root.mainloop()


# === UTILITY FUNCTIONS FOR TESTING ===

def run_tests():
    """Run unit tests for the application"""
    import unittest
    import sys

    # Add project root to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


def create_default_config():
    """Create a default configuration file"""
    from services.configuration_service import ConfigurationService
    from services.hardware_service import HardwareService
    from services.camera_manager import CameraManager

    # Create minimal services for config creation
    store = create_store()
    camera_manager = CameraManager(store=store)
    hardware_service = HardwareService()

    config_service = ConfigurationService(
        hardware_service=hardware_service,
        camera_manager=camera_manager
    )

    default_path = "config/default_cnc_config.yaml"
    success = config_service.create_default_configuration(default_path)

    if success:
        print(f"Default configuration created: {default_path}")
    else:
        print("Failed to create default configuration")

    return success


if __name__ == '__main__':
    import sys

    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test':
            print("Running unit tests...")
            success = run_tests()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == '--create-config':
            print("Creating default configuration...")
            success = create_default_config()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == '--help':
            print("GRBL Camera Registration Application")
            print("Usage:")
            print("  python main.py           - Start application")
            print("  python main.py --test    - Run unit tests")
            print("  python main.py --create-config - Create default config")
            print("  python main.py --help    - Show this help")
            sys.exit(0)

    # Start main application
    main()