"""
Example usage of the enhanced SVG Routes Overlay with debug information
Shows how to get detailed coordinate information and debug the AR overlay
"""

import numpy as np

from services.overlays.svg_routes_overlay import SVGRoutesOverlay
from services.registration_manager import RegistrationManager


def setup_test_registration():
    """Create a test registration manager with sample calibration points"""
    reg_manager = RegistrationManager()

    # Add some test calibration points
    # Format: (machine_pos, camera_tvec, norm_pos)
    calibration_points = [
        (np.array([10.0, 10.0, 0.0]), np.array([100.0, 100.0, 0.0]), np.array([0.1, 0.1])),
        (np.array([50.0, 10.0, 0.0]), np.array([500.0, 100.0, 0.0]), np.array([0.5, 0.1])),
        (np.array([50.0, 50.0, 0.0]), np.array([500.0, 500.0, 0.0]), np.array([0.5, 0.5])),
        (np.array([10.0, 50.0, 0.0]), np.array([100.0, 500.0, 0.0]), np.array([0.1, 0.5])),
    ]

    for machine_pos, camera_tvec, norm_pos in calibration_points:
        reg_manager.add_calibration_point(machine_pos, camera_tvec, norm_pos)

    # Compute registration
    success = reg_manager.compute_registration()
    print(f"Registration computed: {success}")
    print(f"Registration error: {reg_manager.get_registration_error():.3f} mm")

    return reg_manager


def demonstrate_debug_features():
    """Demonstrate all debug features of the SVG Routes Overlay"""

    print("=" * 80)
    print("SVG ROUTES OVERLAY DEBUG DEMONSTRATION")
    print("=" * 80)

    # Create registration manager
    print("\n1. Setting up registration manager...")
    reg_manager = setup_test_registration()

    # Create logger function
    def logger(message, level="info"):
        print(f"[{level.upper()}] {message}")

    # Create overlay with debug enabled
    print("\n2. Creating SVG Routes Overlay...")
    overlay = SVGRoutesOverlay(registration_manager=reg_manager, logger=logger)

    # Enable all debug features
    overlay.enable_debug_display(True)
    overlay.enable_route_bounds_display(True)
    overlay.enable_coordinate_grid(True)

    # Load SVG routes (you'll need to provide an actual SVG file)
    svg_file = "test_routes.svg"  # Replace with your SVG file path

    try:
        print(f"\n3. Loading SVG routes from: {svg_file}")
        overlay.load_routes_from_svg(svg_file)

        # Print automatic route summary
        print("\n4. Route coordinate analysis:")
        overlay.print_route_summary()

        # Get debug information programmatically
        print("\n5. Programmatic debug info access:")
        debug_info = overlay.get_debug_info()

        if debug_info:
            print(f"   File: {debug_info.get('file_path', 'N/A')}")
            print(f"   Routes: {debug_info.get('route_count', 0)}")
            print(f"   Transform mode: {debug_info.get('transform_mode', 'N/A')}")

            machine_bounds = debug_info.get('machine_bounds', {})
            if machine_bounds:
                print(
                    f"   Machine bounds center: ({machine_bounds.get('center_x', 0):.2f}, {machine_bounds.get('center_y', 0):.2f}) mm")
                print(
                    f"   Machine bounds size: {machine_bounds.get('width', 0):.2f} x {machine_bounds.get('height', 0):.2f} mm")

        # Set up camera position for AR
        print("\n6. Setting up AR camera position...")
        camera_position = np.array([30.0, 30.0, 100.0])  # x, y, z in mm
        overlay.update_camera_view(camera_position, scale_factor=5.0)

        # Get camera info
        camera_info = overlay.get_camera_info()
        print(f"   Camera position: {camera_info['camera_position']}")
        print(f"   Camera scale: {camera_info['camera_scale_factor']} px/mm")
        print(f"   Routes count: {camera_info['routes_count']}")

        # Demonstrate coordinate transformation
        print("\n7. Testing coordinate transformations...")
        if overlay.has_routes():
            # Get first route for testing
            routes = overlay.get_routes()
            if routes and routes[0]:
                first_route = routes[0]
                print(f"   First route has {len(first_route)} points")

                # Show first few points in machine coordinates
                for i, (x, y) in enumerate(first_route[:3]):
                    print(f"   Point {i}: Machine coords ({x:.2f}, {y:.2f}) mm")

                    # Convert to camera pixel coordinates (simulated frame size)
                    frame_shape = (480, 640)  # height, width
                    pixel_x, pixel_y = overlay.machine_to_camera_pixel(x, y, frame_shape)
                    print(f"   Point {i}: Pixel coords ({pixel_x}, {pixel_y})")

        # Test different transformation modes
        print("\n8. Testing transformation modes...")

        # Test registration mode
        print("   Testing registration transform mode...")
        overlay.set_use_registration_transform(True)
        reg_route_count = overlay.get_routes_count()
        print(f"   Routes with registration transform: {reg_route_count}")

        # Test manual mode
        print("   Testing manual transform mode...")
        overlay.set_use_registration_transform(False)
        manual_route_count = overlay.get_routes_count()
        print(f"   Routes with manual transform: {manual_route_count}")

        # Get bounds in different modes
        bounds = overlay.get_route_bounds()
        if bounds:
            print(f"   Manual mode bounds: X({bounds[0]:.2f}, {bounds[2]:.2f}) Y({bounds[1]:.2f}, {bounds[3]:.2f})")

        # Switch back to registration mode
        overlay.set_use_registration_transform(True)
        bounds = overlay.get_route_bounds()
        if bounds:
            print(
                f"   Registration mode bounds: X({bounds[0]:.2f}, {bounds[2]:.2f}) Y({bounds[1]:.2f}, {bounds[3]:.2f})")

        # Demonstrate route statistics
        print("\n9. Route statistics:")
        total_length = overlay.get_total_route_length()
        print(f"   Total route length: {total_length:.2f} mm")

        # Export comprehensive information
        print("\n10. Exporting comprehensive route information...")
        export_info = overlay.export_routes_info()
        print("   Export info keys:", list(export_info.keys()))

        if 'debug_info' in export_info:
            debug = export_info['debug_info']
            if 'individual_routes' in debug:
                print(f"   Individual routes info available for {len(debug['individual_routes'])} routes")
                for route_info in debug['individual_routes'][:2]:  # Show first 2
                    print(
                        f"     Route {route_info['index']}: {route_info['length_mm']:.2f}mm, {route_info['point_count']} points")

        # Demonstrate refresh functionality
        print("\n11. Testing refresh functionality...")
        overlay.refresh_transformation()
        print("   Transformation refreshed successfully")

        print("\n" + "=" * 80)
        print("DEBUG DEMONSTRATION COMPLETED SUCCESSFULLY")
        print("=" * 80)

    except FileNotFoundError:
        print(f"\nWARNING: SVG file '{svg_file}' not found.")
        print("Please provide a valid SVG file path to test route loading.")
        print("\nDemonstrating other features without actual routes...")

        # Demonstrate debug features without routes
        print("\n3. Testing debug features without routes...")

        # Test camera setup
        camera_position = np.array([0.0, 0.0, 100.0])
        overlay.update_camera_view(camera_position, scale_factor=10.0)

        camera_info = overlay.get_camera_info()
        print(f"   Camera position: {camera_info['camera_position']}")
        print(f"   Camera scale: {camera_info['camera_scale_factor']} px/mm")

        # Test debug info export (will be mostly empty)
        debug_info = overlay.get_debug_info()
        print(f"   Debug info available: {bool(debug_info)}")

    except Exception as e:
        print(f"\nERROR during demonstration: {e}")
        import traceback
        traceback.print_exc()


def demonstrate_ui_integration():
    """Show how to integrate debug features with the UI panel"""

    print("\n" + "=" * 80)
    print("UI INTEGRATION EXAMPLE")
    print("=" * 80)

    try:
        import tkinter as tk
        from panel_svg import SVGRoutesPanel

        # Create a simple test window
        root = tk.Tk()
        root.title("SVG Routes Debug UI Test")
        root.geometry("400x800")

        # Create registration manager
        reg_manager = setup_test_registration()

        # Create overlay
        def logger(message, level="info"):
            print(f"[UI-{level.upper()}] {message}")

        overlay = SVGRoutesOverlay(registration_manager=reg_manager, logger=logger)

        # Create panel
        panel = SVGRoutesPanel(root, overlay, logger=logger)

        # Add instruction label
        instruction_text = """
SVG Routes Debug UI Test

Features to try:
1. Load SVG Routes - Load an SVG file
2. Toggle debug options in Debug & Visualization section
3. Use Print Route Summary to see coordinates
4. Try Show Debug Window for detailed info
5. Export Debug Info to save to file
6. Adjust camera scale and see coordinate changes

Debug features include:
- Coordinate bounds display
- Individual route information
- Transform mode comparison
- Camera position tracking
- Registration status
        """

        info_label = tk.Label(root, text=instruction_text, justify=tk.LEFT,
                              font=("TkDefaultFont", 8), wraplength=380)
        info_label.pack(pady=10, padx=10)

        print("\nUI Test window created.")
        print("- Try loading an SVG file using the 'Load SVG Routes' button")
        print("- Enable debug options in the 'Debug & Visualization' section")
        print("- Use 'Print Route Summary' to see detailed coordinate information")
        print("- Click 'Show Debug Window' for a comprehensive debug view")
        print("- Use 'Export Debug Info' to save debug information to a file")
        print("\nClose the window to continue...")

        # Don't actually run the mainloop in this example
        # root.mainloop()

        print("UI integration example completed.")

    except ImportError as e:
        print(f"UI integration requires tkinter: {e}")
        print("The debug features work independently of the UI.")


def create_sample_svg_file():
    """Create a sample SVG file for testing if none exists"""

    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100mm" height="100mm" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <!-- Sample route 1: Rectangle -->
  <path d="M 10 10 L 40 10 L 40 40 L 10 40 Z" fill="none" stroke="black" stroke-width="1"/>

  <!-- Sample route 2: Circle-like path -->
  <path d="M 60 25 Q 75 10 90 25 Q 75 40 60 25" fill="none" stroke="black" stroke-width="1"/>

  <!-- Sample route 3: Zigzag -->
  <path d="M 10 60 L 30 50 L 50 60 L 70 50 L 90 60" fill="none" stroke="black" stroke-width="1"/>

  <!-- Sample route 4: Curved path -->
  <path d="M 20 80 Q 50 70 80 80" fill="none" stroke="black" stroke-width="1"/>
</svg>'''

    try:
        with open("test_routes.svg", "w") as f:
            f.write(svg_content)
        print("Created sample SVG file: test_routes.svg")
        return "test_routes.svg"
    except Exception as e:
        print(f"Could not create sample SVG file: {e}")
        return None


def main():
    """Main demonstration function"""

    print("SVG Routes Overlay Debug Features Demonstration")
    print("This example shows how to use the enhanced debug capabilities.")
    print("\nCreating sample SVG file for testing...")

    # Create a sample SVG file
    svg_file = create_sample_svg_file()

    if svg_file:
        print(f"Using sample SVG file: {svg_file}")

    # Run the main demonstration
    demonstrate_debug_features()

    # Show UI integration example
    demonstrate_ui_integration()

    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    print("\nKey debug features demonstrated:")
    print("1. Automatic coordinate analysis and logging")
    print("2. Machine vs SVG coordinate space comparison")
    print("3. Registration vs manual transform mode testing")
    print("4. Camera position and scale factor effects")
    print("5. Individual route statistics and bounds")
    print("6. Programmatic access to debug information")
    print("7. Export capabilities for debug data")
    print("8. UI integration with debug controls")
    print("\nThe debug information helps you understand:")
    print("- Where routes are positioned in machine coordinates")
    print("- How coordinate transformations affect route placement")
    print("- Camera positioning and scale effects on AR display")
    print("- Registration quality and coordinate accuracy")
    print("- Individual route characteristics and statistics")


if __name__ == "__main__":
    main()