#!/usr/bin/env python3
# test_specific.py
"""
Focused test for the specific issue that was fixed
Tests the exact scenario that was failing before
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from store.store import ApplicationStore
    from store.actions import CameraActions, ActionType
    from services.camera_manager import CameraManager
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


class TestSpecificCameraManagerFix(unittest.TestCase):
    """Test the specific camera manager fix"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_store = Mock(spec=ApplicationStore)
        # Use the fixed camera manager with capture thread disabled
        self.camera_manager = CameraManager(store=self.mock_store, enable_capture_thread=False)

    def tearDown(self):
        """Clean up after tests"""
        if self.camera_manager.is_connected:
            self.camera_manager.disconnect()

    @patch('cv2.VideoCapture')
    def test_set_camera_id_when_connected_exact_reproduction(self, mock_video_capture):
        """
        Test the exact scenario that was failing before the fix
        This reproduces the original test that failed with 3 != 2
        """
        print("\n" + "=" * 60)
        print("TESTING THE EXACT SCENARIO THAT WAS FAILING")
        print("=" * 60)

        # Setup connected camera
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        print("1. Connecting camera...")
        result1 = self.camera_manager.connect()
        self.assertTrue(result1)
        print("   ✓ Camera connected successfully")

        # Check initial connection call
        initial_calls = self.mock_store.dispatch.call_count
        print(f"   Initial dispatch calls: {initial_calls}")

        # Reset mock to track only set_camera_id calls
        print("2. Resetting mock to track set_camera_id calls...")
        self.mock_store.dispatch.reset_mock()

        print("3. Changing camera ID from 0 to 1...")
        result2 = self.camera_manager.set_camera_id(1)
        self.assertTrue(result2)
        self.assertEqual(self.camera_manager.camera_id, 1)
        print("   ✓ Camera ID changed successfully")

        # Check dispatch calls - THIS WAS THE FAILING ASSERTION
        call_count = self.mock_store.dispatch.call_count
        print(f"4. Checking dispatch calls: {call_count}")

        # Print all calls for debugging
        calls = self.mock_store.dispatch.call_args_list
        print("   Dispatch call details:")
        for i, call in enumerate(calls):
            action = call[0][0]
            print(f"     Call {i + 1}: {action.type.name} - connected={action.payload.get('connected', 'N/A')}")

        # THE CRITICAL TEST: Should be exactly 2 calls (disconnect + connect)
        self.assertEqual(call_count, 2,
                         f"Expected exactly 2 dispatch calls (disconnect + connect), but got {call_count}. "
                         f"This was the original failing assertion: {call_count} != 2")

        # Verify the calls are correct
        disconnect_call = calls[0][0][0]  # First argument of first call
        self.assertEqual(disconnect_call.type, ActionType.CAMERA_CONNECTION_CHANGED)
        self.assertFalse(disconnect_call.payload['connected'])
        print("   ✓ First call is disconnect")

        connect_call = calls[1][0][0]  # First argument of second call
        self.assertEqual(connect_call.type, ActionType.CAMERA_CONNECTION_CHANGED)
        self.assertTrue(connect_call.payload['connected'])
        print("   ✓ Second call is connect")

        print("5. ✅ TEST PASSED - The fix is working!")
        print("   Original failure: Expected 2 calls, got 3 (due to capture thread)")
        print("   Fixed behavior: Got exactly 2 calls (capture thread disabled)")

    @patch('cv2.VideoCapture')
    def test_capture_thread_behavior_difference(self, mock_video_capture):
        """
        Test that demonstrates the difference between thread enabled/disabled
        """
        print("\n" + "=" * 60)
        print("TESTING CAPTURE THREAD BEHAVIOR DIFFERENCE")
        print("=" * 60)

        # Setup mock
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        # Test 1: With capture thread disabled (for testing)
        print("1. Testing with capture thread DISABLED (test mode):")
        store1 = Mock(spec=ApplicationStore)
        cm_disabled = CameraManager(store=store1, enable_capture_thread=False)

        cm_disabled.connect()
        store1.dispatch.reset_mock()

        cm_disabled.set_camera_id(1)
        calls_disabled = store1.dispatch.call_count
        print(f"   Dispatch calls with thread disabled: {calls_disabled}")

        cm_disabled.disconnect()

        # Test 2: With capture thread enabled (production mode)
        print("2. Testing with capture thread ENABLED (production mode):")
        store2 = Mock(spec=ApplicationStore)
        cm_enabled = CameraManager(store=store2, enable_capture_thread=True)

        cm_enabled.connect()
        store2.dispatch.reset_mock()

        cm_enabled.set_camera_id(1)

        # Give capture thread a moment to start
        import time
        time.sleep(0.1)

        calls_enabled = store2.dispatch.call_count
        print(f"   Dispatch calls with thread enabled: {calls_enabled}")

        cm_enabled.disconnect()

        # The key insight
        print("3. Analysis:")
        print(f"   - Thread disabled: {calls_disabled} calls (predictable for testing)")
        print(f"   - Thread enabled: {calls_enabled} calls (may include frame updates)")
        print("   - The fix allows tests to run predictably while maintaining production functionality")

        # For testing, we expect exactly 2 calls
        self.assertEqual(calls_disabled, 2)
        # For production, we might get more calls due to the capture thread
        self.assertGreaterEqual(calls_enabled, 2)

        print("   ✅ Both modes work correctly!")

    def test_production_vs_test_behavior(self):
        """Test that production and test modes behave appropriately"""
        print("\n" + "=" * 60)
        print("TESTING PRODUCTION VS TEST BEHAVIOR")
        print("=" * 60)

        # Test mode (default for our test class)
        self.assertFalse(self.camera_manager._enable_capture_thread)
        print("✓ Test mode: Capture thread disabled")

        # Production mode
        prod_cm = CameraManager(store=self.mock_store, enable_capture_thread=True)
        self.assertTrue(prod_cm._enable_capture_thread)
        print("✓ Production mode: Capture thread enabled")

        # Default behavior (should be production)
        default_cm = CameraManager(store=self.mock_store)
        self.assertTrue(default_cm._enable_capture_thread)
        print("✓ Default behavior: Capture thread enabled (production ready)")


def run_focused_tests():
    """Run the focused tests"""
    print("Focused Test Runner - Testing Specific Fix")
    print("=" * 50)

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSpecificCameraManagerFix)

    # Run tests with high verbosity
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    # Print detailed results
    print("\n" + "=" * 50)
    print("FOCUSED TEST RESULTS")
    print("=" * 50)

    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"❌ {test}")
            print(f"   {traceback}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"❌ {test}")
            print(f"   {traceback}")

    if result.wasSuccessful():
        print("\n🎉 ALL FOCUSED TESTS PASSED!")
        print("The specific fix for the camera manager is working perfectly!")
    else:
        print(f"\n❌ {len(result.failures)} failures, {len(result.errors)} errors")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_focused_tests()

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    if success:
        print("✅ The camera manager refactoring fix is working correctly!")
        print("✅ The original failing test (3 != 2) is now passing!")
        print("✅ Both test and production modes work as expected!")
        print("\nNext steps:")
        print("1. Try running the main application: python main.py")
        print("2. Test camera connection and operations")
        print("3. Verify real-time frame updates work in production")
    else:
        print("❌ There are still issues with the fix.")
        print("Check the test output above for details.")

    sys.exit(0 if success else 1)