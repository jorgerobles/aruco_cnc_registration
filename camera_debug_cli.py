#!/usr/bin/env python3
"""
Camera Debug Script
Test camera connectivity and basic functionality independently
"""

import cv2
import time


def list_available_cameras():
    """List all available cameras using cv2_enumerate_cameras if available"""
    print("=== Available Cameras ===")

    cameras = []

    # Try using cv2_enumerate_cameras if available
    try:
        from cv2_enumerate_cameras import enumerate_cameras
        print("Using cv2_enumerate_cameras for detailed camera info...")

        for camera_info in enumerate_cameras(cv2.CAP_GSTREAMER):
            cameras.append({
                'index': camera_info.index,
                'name': camera_info.name,
                'backend': 'GStreamer'
            })
            print(f'{camera_info.index}: {camera_info.name}')

        # Also try other backends
        try:
            for camera_info in enumerate_cameras(cv2.CAP_V4L2):
                if not any(cam['index'] == camera_info.index for cam in cameras):
                    cameras.append({
                        'index': camera_info.index,
                        'name': camera_info.name,
                        'backend': 'V4L2'
                    })
                    print(f'{camera_info.index}: {camera_info.name} (V4L2)')
        except:
            pass

    except ImportError:
        print("cv2_enumerate_cameras not available, using basic detection...")

        # Fallback to basic detection
        for camera_id in range(10):  # Check first 10 camera indices
            cap = cv2.VideoCapture(camera_id)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    cameras.append({
                        'index': camera_id,
                        'name': f'Camera {camera_id}',
                        'backend': 'Default'
                    })
                    print(f'{camera_id}: Camera {camera_id}')
                cap.release()
            else:
                cap.release()

    if not cameras:
        print("No cameras found!")
        return None

    return cameras


def select_camera_interactive(cameras):
    """Allow user to select a camera from the list"""
    if not cameras:
        return None

    print(f"\nFound {len(cameras)} camera(s)")
    print("\nSelect a camera to test:")

    for i, camera in enumerate(cameras):
        print(f"  {i + 1}. Index {camera['index']}: {camera['name']} ({camera['backend']})")

    while True:
        try:
            choice = input(f"\nEnter choice (1-{len(cameras)}) or 'q' to quit: ").strip()

            if choice.lower() == 'q':
                return None

            choice_num = int(choice)
            if 1 <= choice_num <= len(cameras):
                selected_camera = cameras[choice_num - 1]
                print(f"Selected: {selected_camera['name']} (Index {selected_camera['index']})")
                return selected_camera['index']
            else:
                print(f"Please enter a number between 1 and {len(cameras)}")

        except ValueError:
            print("Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\nOperation cancelled")
            return None


def test_camera_basic():
    """Test basic camera connectivity"""
    print("=== Basic Camera Test ===")

    # Try different camera indices
    for camera_id in range(5):  # Test cameras 0-4
        print(f"\nTesting camera {camera_id}...")
        cap = cv2.VideoCapture(camera_id)

        if cap.isOpened():
            # Try to read a frame
            ret, frame = cap.read()
            if ret and frame is not None:
                height, width = frame.shape[:2]
                print(f"✓ Camera {camera_id} working - Resolution: {width}x{height}")

                # Test a few frames
                for i in range(5):
                    ret, frame = cap.read()
                    if not ret:
                        print(f"✗ Camera {camera_id} failed after {i} frames")
                        break
                else:
                    print(f"✓ Camera {camera_id} stable for 5 frames")

                cap.release()
                return camera_id  # Return first working camera
            else:
                print(f"✗ Camera {camera_id} opened but can't read frames")
        else:
            print(f"✗ Camera {camera_id} not available")

        cap.release()

    print("\n❌ No working cameras found")
    return None


def test_specific_camera(camera_id):
    """Test a specific camera by ID"""
    print(f"\n=== Testing Camera {camera_id} ===")

    cap = cv2.VideoCapture(camera_id)

    if cap.isOpened():
        # Try to read a frame
        ret, frame = cap.read()
        if ret and frame is not None:
            height, width = frame.shape[:2]
            print(f"✓ Camera {camera_id} working - Resolution: {width}x{height}")

            # Test frame stability
            successful_frames = 0
            total_frames = 10

            for i in range(total_frames):
                ret, frame = cap.read()
                if ret and frame is not None:
                    successful_frames += 1
                time.sleep(0.1)  # Small delay between frames

            success_rate = (successful_frames / total_frames) * 100
            print(f"✓ Frame stability: {successful_frames}/{total_frames} frames ({success_rate:.1f}%)")

            cap.release()
            return True
        else:
            print(f"✗ Camera {camera_id} opened but can't read frames")
    else:
        print(f"✗ Camera {camera_id} not available")

    cap.release()
    return False


def test_camera_properties(camera_id):
    """Test camera properties and settings"""
    print(f"\n=== Camera {camera_id} Properties ===")

    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print("❌ Could not open camera")
        return

    # Test common properties
    properties = {
        'Width': cv2.CAP_PROP_FRAME_WIDTH,
        'Height': cv2.CAP_PROP_FRAME_HEIGHT,
        'FPS': cv2.CAP_PROP_FPS,
        'Format': cv2.CAP_PROP_FORMAT,
        'Brightness': cv2.CAP_PROP_BRIGHTNESS,
        'Contrast': cv2.CAP_PROP_CONTRAST,
        'Exposure': cv2.CAP_PROP_EXPOSURE,
        'Auto Exposure': cv2.CAP_PROP_AUTO_EXPOSURE
    }

    for name, prop in properties.items():
        try:
            value = cap.get(prop)
            print(f"{name}: {value}")
        except Exception as e:
            print(f"{name}: Error - {e}")

    cap.release()


def test_camera_capture_loop(camera_id, duration=10):
    """Test continuous camera capture"""
    print(f"\n=== Camera {camera_id} Capture Loop Test ({duration}s) ===")

    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print("❌ Could not open camera")
        return False

    print("Starting capture loop... Press 'q' to quit early")

    start_time = time.time()
    frame_count = 0
    successful_frames = 0

    while time.time() - start_time < duration:
        ret, frame = cap.read()
        frame_count += 1

        if ret and frame is not None:
            successful_frames += 1

            # Display frame (optional - comment out if running headless)
            try:
                cv2.imshow(f'Camera {camera_id} Test', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            except:
                # Running without display
                pass
        else:
            print(f"Frame {frame_count} failed")

    cap.release()
    cv2.destroyAllWindows()

    success_rate = (successful_frames / frame_count) * 100 if frame_count > 0 else 0
    print(f"Capture results: {successful_frames}/{frame_count} frames successful ({success_rate:.1f}%)")

    return success_rate > 90


def test_camera_with_aruco(camera_id):
    """Test camera with ArUco marker detection"""
    print(f"\n=== ArUco Marker Detection Test (Camera {camera_id}) ===")

    try:
        # Test if ArUco is available
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
        detector_params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
        print("✓ ArUco detection available")

        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            print("❌ Could not open camera for ArUco test")
            return False

        print("Looking for ArUco markers... Press 'q' to quit")
        print("Show a 6x6 ArUco marker (ID 0-249) to the camera")

        start_time = time.time()
        markers_detected = False

        while time.time() - start_time < 30:  # Test for 30 seconds
            ret, frame = cap.read()
            if not ret:
                continue

            # Detect markers
            corners, ids, rejected = detector.detectMarkers(frame)

            if ids is not None:
                if not markers_detected:
                    print(f"✓ Detected {len(ids)} markers: {ids.flatten()}")
                    markers_detected = True
                # Draw detected markers
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)

            try:
                cv2.imshow('ArUco Test', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            except:
                pass

        cap.release()
        cv2.destroyAllWindows()

        if markers_detected:
            print("✓ ArUco detection working")
        else:
            print("⚠️  No ArUco markers detected (try showing a marker to the camera)")

        return True

    except Exception as e:
        print(f"❌ ArUco test failed: {e}")
        return False


def debug_camera_manager():
    """Debug the CameraManager class specifically"""
    print("\n=== CameraManager Debug ===")

    try:
        # Try to import your CameraManager
        from services.camera_manager import CameraManager

        camera_manager = CameraManager()
        print("✓ CameraManager imported successfully")

        # Test connection
        print("Testing camera manager connection...")
        if hasattr(camera_manager, 'connect'):
            result = camera_manager.connect()
            print(f"Connection result: {result}")

        # Test frame capture
        print("Testing frame capture...")
        if hasattr(camera_manager, 'capture_frame'):
            frame = camera_manager.capture_frame()
            if frame is not None:
                print(f"✓ Frame captured: {frame.shape}")
            else:
                print("❌ Frame capture returned None")

        # Test marker detection
        if hasattr(camera_manager, 'detect_marker_pose') and frame is not None:
            print("Testing marker detection...")
            result = camera_manager.detect_marker_pose(frame, 20.0)
            print(f"Marker detection result: {type(result)}")

        # Cleanup
        if hasattr(camera_manager, 'disconnect'):
            camera_manager.disconnect()

    except ImportError as e:
        print(f"❌ Could not import CameraManager: {e}")
        print("Make sure camera_manager.py is in the same directory")
    except Exception as e:
        print(f"❌ CameraManager test failed: {e}")


def main():
    """Run all camera tests"""
    print("Camera Debugging Tool")
    print("=" * 50)

    # Basic OpenCV info
    print(f"OpenCV Version: {cv2.__version__}")

    # Step 1: List available cameras
    cameras = list_available_cameras()

    if not cameras:
        print("\n⚠️  No cameras found. Check:")
        print("   - Camera is connected and powered")
        print("   - Camera drivers are installed")
        print("   - Camera is not being used by another application")
        print("   - Try different USB ports")
        return

    # Step 2: Let user select a camera
    selected_camera_id = select_camera_interactive(cameras)

    if selected_camera_id is None:
        print("No camera selected. Exiting.")
        return

    # Step 3: Test the selected camera
    print(f"\n{'=' * 50}")
    print(f"Testing Selected Camera {selected_camera_id}")
    print(f"{'=' * 50}")

    # Test basic functionality
    if test_specific_camera(selected_camera_id):
        # Test camera properties
        test_camera_properties(selected_camera_id)

        # Test capture loop stability
        print(f"\nTesting capture stability...")
        stable = test_camera_capture_loop(selected_camera_id, 5)

        if stable:
            print("✓ Camera capture is stable")
        else:
            print("❌ Camera capture is unstable")

        # Test ArUco detection
        test_camera_with_aruco(selected_camera_id)
    else:
        print(f"❌ Camera {selected_camera_id} failed basic tests")

    # Test CameraManager class
    debug_camera_manager()

    print("\n" + "=" * 50)
    print("Debug complete. Check the results above to identify issues.")
    print(f"\n💡 Recommendation: Use camera ID {selected_camera_id} in your application")


if __name__ == "__main__":
    main()