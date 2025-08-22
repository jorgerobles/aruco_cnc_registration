#!/usr/bin/env python3
# test_fix.py
"""
Quick verification script for the camera manager test fix
Run this to verify the fix works before running the full test suite
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from store.store import ApplicationStore
    from store.actions import CameraActions, ActionType
    from services.camera_manager import CameraManager

    print("✓ Imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def test_camera_manager_creation():
    """Test camera manager creation with new parameter"""
    print("\nTesting camera manager creation...")

    store = ApplicationStore()

    # Test with capture thread enabled (default)
    cm_enabled = CameraManager(store=store)
    assert cm_enabled._enable_capture_thread == True
    print("✓ Default capture thread enabled")

    # Test with capture thread disabled
    cm_disabled = CameraManager(store=store, enable_capture_thread=False)
    assert cm_disabled._enable_capture_thread == False
    print("✓ Capture thread can be disabled")

    # Test with custom parameters
    cm_custom = CameraManager(store=store, camera_id=1, resolution=(1280, 720), enable_capture_thread=False)
    assert cm_custom.camera_id == 1
    assert cm_custom.resolution == (1280, 720)
    assert cm_custom._enable_capture_thread == False
    print("✓ Custom parameters work correctly")


def test_store_dispatch_behavior():
    """Test the specific failing scenario"""
    print("\nTesting store dispatch behavior...")

    mock_store = Mock(spec=ApplicationStore)
    camera_manager = CameraManager(store=mock_store, enable_capture_thread=False)

    with patch('cv2.VideoCapture') as mock_video_capture:
        # Setup mock
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        # Connect first
        result1 = camera_manager.connect()
        assert result1 == True
        print("✓ Initial connect successful")

        # Reset mock to track only set_camera_id calls
        mock_store.dispatch.reset_mock()

        # Change camera ID (this was failing)
        result2 = camera_manager.set_camera_id(1)
        assert result2 == True
        assert camera_manager.camera_id == 1
        print("✓ Camera ID change successful")

        # Check dispatch calls
        call_count = mock_store.dispatch.call_count
        print(f"✓ Dispatch call count: {call_count}")

        if call_count >= 2:
            calls = mock_store.dispatch.call_args_list

            # Check first call (disconnect)
            disconnect_call = calls[0][0][0]
            assert disconnect_call.type == ActionType.CAMERA_CONNECTION_CHANGED
            assert disconnect_call.payload['connected'] == False
            print("✓ Disconnect action dispatched correctly")

            # Find connect call
            connect_found = False
            for call in calls:
                action = call[0][0]
                if (action.type == ActionType.CAMERA_CONNECTION_CHANGED and
                        action.payload['connected'] == True):
                    connect_found = True
                    break

            assert connect_found
            print("✓ Connect action dispatched correctly")

        print(f"✓ Expected behavior: exactly 2 dispatch calls, got {call_count}")

        # With capture thread disabled, we should get exactly 2 calls
        assert call_count == 2


def test_capture_thread_behavior():
    """Test capture thread enabling/disabling"""
    print("\nTesting capture thread behavior...")

    mock_store = Mock(spec=ApplicationStore)

    # Test disabled capture thread
    cm_disabled = CameraManager(store=mock_store, enable_capture_thread=False)

    with patch('cv2.VideoCapture') as mock_video_capture:
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        # Connect with disabled capture thread
        cm_disabled.connect()

        # Should not start capture thread
        assert cm_disabled._capture_thread is None
        assert cm_disabled._capture_running == False
        print("✓ Capture thread disabled correctly")

        cm_disabled.disconnect()

    # Test enabled capture thread
    cm_enabled = CameraManager(store=mock_store, enable_capture_thread=True)

    with patch('cv2.VideoCapture') as mock_video_capture:
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        # Connect with enabled capture thread
        cm_enabled.connect()

        # Should start capture thread
        assert cm_enabled._capture_thread is not None
        assert cm_enabled._capture_running == True
        print("✓ Capture thread enabled correctly")

        cm_enabled.disconnect()


def run_specific_failing_test():
    """Run the specific test that was failing"""
    print("\nRunning the specific failing test...")

    try:
        # Import the test class
        from tests.test_camera_manager import TestCameraManager

        # Create test instance
        test_instance = TestCameraManager()
        test_instance.setUp()

        # Run the specific test
        test_instance.test_set_camera_id_when_connected()
        print("✓ test_set_camera_id_when_connected PASSED")

    except Exception as e:
        print(f"❌ test_set_camera_id_when_connected FAILED: {e}")
        raise


def main():
    """Run all verification tests"""
    print("Camera Manager Test Fix Verification")
    print("=" * 50)

    try:
        test_camera_manager_creation()
        test_store_dispatch_behavior()
        test_capture_thread_behavior()
        run_specific_failing_test()

        print("\n" + "=" * 50)
        print("🎉 ALL VERIFICATION TESTS PASSED!")
        print("The fix should resolve the failing test.")
        print("\nYou can now run:")
        print("  python run_tests.py --camera")
        print("  python run_tests.py --all")

    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()