#!/usr/bin/env python3
"""
Camera Debug Script
Test camera connectivity and basic functionality independently
"""

import cv2
import numpy as np
import sys
import time


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


def test_camera_with_aruco():
    """Test camera with ArUco marker detection"""
    print("\n=== ArUco Marker Detection Test ===")

    try:
        # Test if ArUco is available
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
        detector_params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
        print("✓ ArUco detection available")

        # Find working camera
        camera_id = test_camera_basic()
        if camera_id is None:
            return False

        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            print("❌ Could not open camera for ArUco test")
            return False

        print("Looking for ArUco markers... Press 'q' to quit")
        print("Show a 6x6 ArUco marker (ID 0-249) to the camera")

        start_time = time.time()
        while time.time() - start_time < 30:  # Test for 30 seconds
            ret, frame = cap.read()
            if not ret:
                continue

            # Detect markers
            corners, ids, rejected = detector.detectMarkers(frame)

            if ids is not None:
                print(f"✓ Detected {len(ids)} markers: {ids.flatten()}")
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
        return True

    except Exception as e:
        print(f"❌ ArUco test failed: {e}")
        return False


def debug_camera_manager():
    """Debug the CameraManager class specifically"""
    print("\n=== CameraManager Debug ===")

    try:
        # Try to import your CameraManager
        from camera_manager import CameraManager

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

    # Test 1: Basic camera connectivity
    working_camera = test_camera_basic()

    if working_camera is not None:
        # Test 2: Camera properties
        test_camera_properties(working_camera)

        # Test 3: Capture loop stability
        print(f"\nTesting capture stability...")
        stable = test_camera_capture_loop(working_camera, 5)

        if stable:
            print("✓ Camera capture is stable")
        else:
            print("❌ Camera capture is unstable")

        # Test 4: ArUco detection
        test_camera_with_aruco()

    # Test 5: Your CameraManager class
    debug_camera_manager()

    print("\n" + "=" * 50)
    print("Debug complete. Check the results above to identify issues.")

    if working_camera is not None:
        print(f"\n💡 Recommendation: Use camera ID {working_camera} in your application")
    else:
        print("\n⚠️  No working cameras found. Check:")
        print("   - Camera is connected and powered")
        print("   - Camera drivers are installed")
        print("   - Camera is not being used by another application")
        print("   - Try different USB ports")


if __name__ == "__main__":
    main()