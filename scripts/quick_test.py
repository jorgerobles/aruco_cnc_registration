#!/usr/bin/env python3
# quick_test.py
"""
Quick test runner for Python 3.13 compatibility
Simplified version that handles import issues gracefully
"""

import sys
import os
import unittest
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_imports():
    """Check that all required modules can be imported"""
    print("Checking imports...")

    try:
        import numpy as np
        print("✓ numpy")
    except ImportError:
        print("❌ numpy - install with: pip install numpy")
        return False

    try:
        import cv2
        print("✓ opencv-python")
    except ImportError:
        print("❌ opencv-python - install with: pip install opencv-python")
        return False

    try:
        from store.store import ApplicationStore
        print("✓ store.store")
    except ImportError as e:
        print(f"❌ store.store - {e}")
        return False

    try:
        from store.actions import CameraActions, ActionType
        print("✓ store.actions")
    except ImportError as e:
        print(f"❌ store.actions - {e}")
        return False

    try:
        from services.camera_manager import CameraManager
        print("✓ services.camera_manager")
    except ImportError as e:
        print(f"❌ services.camera_manager - {e}")
        return False

    print("✅ All imports successful!")
    return True


def test_camera_manager_basic():
    """Test basic CameraManager functionality"""
    print("\nTesting basic CameraManager functionality...")

    try:
        from store.store import ApplicationStore
        from services.camera_manager import CameraManager

        # Test creation
        store = ApplicationStore()
        cm = CameraManager(store=store, enable_capture_thread=False)
        print("✓ CameraManager creation")

        # Test properties
        assert cm.camera_id == 0
        assert cm.resolution == (640, 480)
        assert cm._enable_capture_thread == False
        print("✓ CameraManager properties")

        # Test store integration
        assert cm.store is store
        print("✓ Store integration")

        print("✅ Basic functionality tests passed!")
        return True

    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False


def run_single_test():
    """Run a single test to verify the fix"""
    print("\nRunning single test to verify fix...")

    try:
        from unittest.mock import Mock, patch
        import numpy as np
        from store.store import ApplicationStore
        from store.actions import ActionType
        from services.camera_manager import CameraManager

        # Setup
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

            # Reset mock to track only set_camera_id calls
            mock_store.dispatch.reset_mock()

            # Change camera ID (this was the failing test)
            result2 = camera_manager.set_camera_id(1)
            assert result2 == True
            assert camera_manager.camera_id == 1

            # Check dispatch calls - should be exactly 2 with thread disabled
            call_count = mock_store.dispatch.call_count
            assert call_count == 2, f"Expected 2 calls, got {call_count}"

            # Verify call types
            calls = mock_store.dispatch.call_args_list

            # First call should be disconnect
            disconnect_call = calls[0][0][0]
            assert disconnect_call.type == ActionType.CAMERA_CONNECTION_CHANGED
            assert disconnect_call.payload['connected'] == False

            # Second call should be connect
            connect_call = calls[1][0][0]
            assert connect_call.type == ActionType.CAMERA_CONNECTION_CHANGED
            assert connect_call.payload['connected'] == True

        print("✅ Single test passed - fix is working!")
        return True

    except Exception as e:
        print(f"❌ Single test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_camera_tests_simple():
    """Run camera tests using simple discovery"""
    print("\nRunning camera tests with simple discovery...")

    try:
        # Create test suite
        loader = unittest.TestLoader()

        # Try to load tests from the tests directory
        if Path("tests/test_camera_manager.py").exists():
            # Load specific test module
            spec = unittest.util.spec_from_file_location(
                "test_camera_manager",
                "tests/test_camera_manager.py"
            )
            module = unittest.util.module_from_spec(spec)
            sys.modules["test_camera_manager"] = module
            spec.loader.exec_module(module)

            # Get test classes
            test_classes = []
            for name in dir(module):
                obj = getattr(module, name)
                if (isinstance(obj, type) and
                        issubclass(obj, unittest.TestCase) and
                        obj != unittest.TestCase):
                    test_classes.append(obj)

            if not test_classes:
                print("❌ No test classes found in test_camera_manager.py")
                return False

            # Create suite and add tests
            suite = unittest.TestSuite()
            for test_class in test_classes:
                tests = loader.loadTestsFromTestCase(test_class)
                suite.addTests(tests)

            # Run tests
            runner = unittest.TextTestRunner(verbosity=2)
            result = runner.run(suite)

            if result.wasSuccessful():
                print("✅ All camera tests passed!")
                return True
            else:
                print(f"❌ {len(result.failures)} failures, {len(result.errors)} errors")
                return False
        else:
            print("❌ tests/test_camera_manager.py not found")
            return False

    except Exception as e:
        print(f"❌ Error running camera tests: {e}")
        return False


def main():
    """Main test runner"""
    print("Quick Test Runner for Python 3.13")
    print("=" * 40)

    # Check imports first
    if not check_imports():
        print("\n❌ Import check failed. Please install missing dependencies.")
        sys.exit(1)

    # Test basic functionality
    if not test_camera_manager_basic():
        print("\n❌ Basic functionality test failed.")
        sys.exit(1)

    # Run single test to verify fix
    if not run_single_test():
        print("\n❌ Single test verification failed.")
        sys.exit(1)

    # Run full camera tests if available
    print("\n" + "=" * 40)
    if run_camera_tests_simple():
        print("\n🎉 ALL TESTS PASSED!")
        print("The CameraManager refactoring is working correctly!")
    else:
        print("\n❌ Some tests failed, but basic functionality works.")

    print("\n" + "=" * 40)
    print("Next steps:")
    print("1. If all tests passed: Integration is successful!")
    print("2. If some tests failed: Check error messages above")
    print("3. Try the full application: python main.py")


if __name__ == '__main__':
    main()