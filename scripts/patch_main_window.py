#!/usr/bin/env python3
# patch_main_window.py
"""
Simple patch to fix the RegistrationGUI constructor for store integration
"""


def patch_main_window():
    """Apply minimal patch to main_window.py"""
    import os
    from pathlib import Path

    main_window_file = Path("gui/main_window.py")

    if not main_window_file.exists():
        print("❌ gui/main_window.py not found")
        return False

    # Read the current file
    with open(main_window_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Backup the original
    backup_file = Path("gui/main_window.py.backup")
    if not backup_file.exists():
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✓ Backed up original main_window.py")

    # Apply patches
    patches_applied = 0

    # Patch 1: Update constructor to accept store parameter
    old_constructor = "def __init__(self, root, grbl_controller, camera_manager, registration_manager, route_manager, hardware_service):"
    new_constructor = "def __init__(self, root, grbl_controller, camera_manager, registration_manager, route_manager, hardware_service, store):"

    if old_constructor in content:
        content = content.replace(old_constructor, new_constructor)
        patches_applied += 1
        print("✓ Updated constructor signature")

    # Patch 2: Add store assignment
    if "self.hardware_service = hardware_service" in content and "self.store = store" not in content:
        content = content.replace(
            "self.hardware_service = hardware_service",
            "self.hardware_service = hardware_service\n        self.store = store  # Store integration"
        )
        patches_applied += 1
        print("✓ Added store assignment")

    # Patch 3: Update CameraPanel creation
    old_camera_panel = "self.calibration_panel = CameraPanel(scrollable_frame, self.camera_manager, self.hardware_service, self.log)"
    new_camera_panel = """self.calibration_panel = CameraPanel(
            scrollable_frame, 
            self.camera_manager, 
            self.hardware_service, 
            self.store,  # Store integration
            self.log    # Logger
        )"""

    if old_camera_panel in content:
        content = content.replace(old_camera_panel, new_camera_panel)
        patches_applied += 1
        print("✓ Updated CameraPanel creation")

    # Write the patched file
    if patches_applied > 0:
        with open(main_window_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Applied {patches_applied} patches to main_window.py")
        return True
    else:
        print("⚠️ No patches needed or patches already applied")
        return True


def main():
    print("Patching main_window.py for Store Integration")
    print("=" * 45)

    success = patch_main_window()

    if success:
        print("\n✅ main_window.py patched successfully!")
        print("\nNext steps:")
        print("1. Run: python create_store_files.py")
        print("2. Run: python main.py")
        print("3. Camera panel should work with store integration")
    else:
        print("\n❌ Failed to patch main_window.py")


if __name__ == '__main__':
    main()