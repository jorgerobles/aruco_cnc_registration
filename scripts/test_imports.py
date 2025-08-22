#!/usr/bin/env python3
# test_imports.py
"""
Test script to check all imports required for the main application
Helps identify missing dependencies or import issues
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def test_store_imports():
    """Test store system imports"""
    print("Testing store system imports...")

    try:
        from store.store import ApplicationStore
        print("✓ store.store.ApplicationStore")
    except ImportError as e:
        print(f"❌ store.store.ApplicationStore: {e}")
        return False

    try:
        from store.actions import CameraActions, ActionType
        print("✓ store.actions")
    except ImportError as e:
        print(f"❌ store.actions: {e}")
        return False

    try:
        from store.state import ApplicationState, CameraState
        print("✓ store.state")
    except ImportError as e:
        print(f"❌ store.state: {e}")
        return False

    try:
        from store.reducers import root_reducer
        print("✓ store.reducers")
    except ImportError as e:
        print(f"❌ store.reducers: {e}")
        return False

    try:
        from store.middleware import DEFAULT_MIDDLEWARE
        print("✓ store.middleware")
    except ImportError as e:
        print(f"❌ store.middleware: {e}")
        return False

    return True


def test_service_imports():
    """Test service imports"""
    print("\nTesting service imports...")

    try:
        from services.camera_manager import CameraManager, CameraEvents
        print("✓ services.camera_manager.CameraManager")
        print("✓ services.camera_manager.CameraEvents")
    except ImportError as e:
        print(f"❌ services.camera_manager: {e}")
        return False

    try:
        from services.grbl_controller import GRBLController
        print("✓ services.grbl_controller.GRBLController")
    except ImportError as e:
        print(f"❌ services.grbl_controller: {e}")
        return False

    try:
        from services.hardware_service import HardwareService, MachineOrigin
        print("✓ services.hardware_service")
    except ImportError as e:
        print(f"❌ services.hardware_service: {e}")
        return False

    try:
        from services.registration_manager import RegistrationManager
        print("✓ services.registration_manager")
    except ImportError as e:
        print(f"❌ services.registration_manager: {e}")
        return False

    try:
        from services.routes_manager import RouteManager
        print("✓ services.routes_manager")
    except ImportError as e:
        print(f"❌ services.routes_manager: {e}")
        return False

    try:
        from services.configuration_service import ConfigurationService
        print("✓ services.configuration_service")
    except ImportError as e:
        print(f"❌ services.configuration_service: {e}")
        return False

    return True


def test_gui_imports():
    """Test GUI imports"""
    print("\nTesting GUI imports...")

    try:
        from gui.main_window import RegistrationGUI
        print("✓ gui.main_window.RegistrationGUI")
    except ImportError as e:
        print(f"❌ gui.main_window.RegistrationGUI: {e}")
        return False

    try:
        from gui.panel_configuration import ConfigurationPanel
        print("✓ gui.panel_configuration")
    except ImportError as e:
        print(f"❌ gui.panel_configuration: {e}")
        return False

    return True


def test_io_imports():
    """Test I/O imports"""
    print("\nTesting I/O imports...")

    try:
        from services.io.format_gcode import GCodeExporter
        print("✓ services.io.format_gcode")
    except ImportError as e:
        print(f"❌ services.io.format_gcode: {e}")
        return False

    try:
        from services.io.format_svg import SVGImporter, SVGExporter
        print("✓ services.io.format_svg")
    except ImportError as e:
        print(f"❌ services.io.format_svg: {e}")
        return False

    try:
        from services.io.manager import ImportExportManager
        print("✓ services.io.manager")
    except ImportError as e:
        print(f"❌ services.io.manager: {e}")
        return False

    return True


def test_configuration_imports():
    """Test configuration imports"""
    print("\nTesting configuration imports...")

    try:
        from services.configuration_bridge import initialize_camera_panel_with_config
        print("✓ services.configuration_bridge")
    except ImportError as e:
        print(f"❌ services.configuration_bridge: {e}")
        return False

    return True


def test_specific_main_imports():
    """Test the specific imports that main.py uses"""
    print("\nTesting main.py specific imports...")

    imports_to_test = [
        ("gui.main_window", "RegistrationGUI"),
        ("gui.panel_configuration", "ConfigurationPanel"),
        ("store.store", "ApplicationStore"),
        ("store.middleware", "DEFAULT_MIDDLEWARE"),
        ("services.camera_manager", "CameraManager"),
        ("services.grbl_controller", "GRBLController"),
        ("services.hardware_service", "HardwareService"),
        ("services.hardware_service", "MachineOrigin"),
        ("services.registration_manager", "RegistrationManager"),
        ("services.routes_manager", "RouteManager"),
        ("services.configuration_service", "ConfigurationService"),
        ("services.io.format_gcode", "GCodeExporter"),
        ("services.io.format_svg", "SVGImporter"),
        ("services.io.format_svg", "SVGExporter"),
        ("services.io.manager", "ImportExportManager"),
        ("services.configuration_bridge", "initialize_camera_panel_with_config"),
    ]

    all_success = True

    for module_name, class_name in imports_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"✓ {module_name}.{class_name}")
        except ImportError as e:
            print(f"❌ {module_name}.{class_name}: {e}")
            all_success = False
        except AttributeError as e:
            print(f"❌ {module_name}.{class_name}: {e}")
            all_success = False

    return all_success


def main():
    """Run all import tests"""
    print("Import Test - Checking All Dependencies")
    print("=" * 50)

    tests = [
        test_store_imports,
        test_service_imports,
        test_gui_imports,
        test_io_imports,
        test_configuration_imports,
        test_specific_main_imports,
    ]

    all_passed = True

    for test_func in tests:
        try:
            result = test_func()
            if not result:
                all_passed = False
        except Exception as e:
            print(f"❌ Error running {test_func.__name__}: {e}")
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL IMPORTS SUCCESSFUL!")
        print("The application should start without import errors.")
    else:
        print("❌ SOME IMPORTS FAILED!")
        print("Check the errors above and fix missing dependencies.")

    print("\nNext steps:")
    if all_passed:
        print("1. Try running: python main.py")
        print("2. If it still fails, there may be runtime issues to fix")
    else:
        print("1. Fix the import errors shown above")
        print("2. Make sure all required files exist")
        print("3. Check for typos in import statements")


if __name__ == '__main__':
    main()