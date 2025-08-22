# tests/test_camera_manager.py
"""
Unit tests for the refactored CameraManager
Tests hardware control logic and store integration
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import numpy as np
import cv2
import threading
import time

from store.store import ApplicationStore
from store.state import ApplicationState, CameraState
from store.actions import CameraActions, ActionType
from services.camera_manager import CameraManager, get_optimal_camera_backend


class TestCameraManager(unittest.TestCase):
    """Test suite for the refactored CameraManager"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_store = Mock(spec=ApplicationStore)
        # Disable capture thread for testing to prevent interference
        self.camera_manager = CameraManager(store=self.mock_store, enable_capture_thread=False)

    def tearDown(self):
        """Clean up after tests"""
        if self.camera_manager.is_connected:
            self.camera_manager.disconnect()

    # === INITIALIZATION TESTS ===

    def test_initialization(self):
        """Test CameraManager initialization"""
        self.assertEqual(self.camera_manager.camera_id, 0)
        self.assertEqual(self.camera_manager.resolution, (640, 480))
        self.assertFalse(self.camera_manager.is_connected)
        self.assertIsNone(self.camera_manager.cap)
        self.assertIsNone(self.camera_manager.camera_matrix)
        self.assertIsNone(self.camera_manager.dist_coeffs)

    def test_initialization_with_custom_params(self):
        """Test initialization with custom parameters"""
        custom_store = Mock(spec=ApplicationStore)
        custom_manager = CameraManager(store=custom_store, camera_id=1, resolution=(1280, 720),
                                       enable_capture_thread=False)

        self.assertEqual(custom_manager.camera_id, 1)
        self.assertEqual(custom_manager.resolution, (1280, 720))
        self.assertIs(custom_manager.store, custom_store)
        self.assertFalse(custom_manager._enable_capture_thread)

    # === CONNECTION TESTS ===

    @patch('cv2.VideoCapture')
    def test_connect_success(self, mock_video_capture):
        """Test successful camera connection"""
        # Setup mock
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        # Test
        result = self.camera_manager.connect()

        # Verify result
        self.assertTrue(result)
        self.assertTrue(self.camera_manager.is_connected)

        # Verify store action dispatched
        self.mock_store.dispatch.assert_called()
        call_args = self.mock_store.dispatch.call_args[0][0]
        self.assertEqual(call_args.type, ActionType.CAMERA_CONNECTION_CHANGED)
        self.assertTrue(call_args.payload['connected'])
        self.assertEqual(call_args.payload['camera_id'], 0)

    @patch('cv2.VideoCapture')
    def test_connect_failure_camera_not_opened(self, mock_video_capture):
        """Test connection failure when camera doesn't open"""
        # Setup mock
        mock_cap = Mock()
        mock_cap.isOpened.return_value = False
        mock_video_capture.return_value = mock_cap

        # Test
        result = self.camera_manager.connect()

        # Verify result
        self.assertFalse(result)
        self.assertFalse(self.camera_manager.is_connected)

        # Verify store action dispatched
        call_args = self.mock_store.dispatch.call_args[0][0]
        self.assertEqual(call_args.type, ActionType.CAMERA_CONNECTION_CHANGED)
        self.assertFalse(call_args.payload['connected'])

    @patch('cv2.VideoCapture')
    def test_connect_failure_frame_read_error(self, mock_video_capture):
        """Test connection failure when frame read fails"""
        # Setup mock
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)  # Read failure
        mock_video_capture.return_value = mock_cap

        # Test
        result = self.camera_manager.connect()

        # Verify result
        self.assertFalse(result)
        self.assertFalse(self.camera_manager.is_connected)

        # Verify camera was released
        mock_cap.release.assert_called_once()

    @patch('cv2.VideoCapture')
    def test_connect_exception_handling(self, mock_video_capture):
        """Test connection exception handling"""
        # Setup mock to raise exception
        mock_video_capture.side_effect = Exception("Camera error")

        # Test
        result = self.camera_manager.connect()

        # Verify result
        self.assertFalse(result)
        self.assertFalse(self.camera_manager.is_connected)

        # Verify store action dispatched
        call_args = self.mock_store.dispatch.call_args[0][0]
        self.assertFalse(call_args.payload['connected'])

    def test_disconnect_when_not_connected(self):
        """Test disconnect when not connected"""
        result = self.camera_manager.disconnect()

        self.assertTrue(result)
        # Should not dispatch action if wasn't connected
        self.mock_store.dispatch.assert_not_called()

    @patch('cv2.VideoCapture')
    def test_disconnect_when_connected(self, mock_video_capture):
        """Test disconnect when connected"""
        # Setup connected state
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        # Connect first
        self.camera_manager.connect()
        self.mock_store.dispatch.reset_mock()  # Reset to check disconnect call

        # Test disconnect
        result = self.camera_manager.disconnect()

        # Verify result
        self.assertTrue(result)
        self.assertFalse(self.camera_manager.is_connected)

        # Verify camera was released
        mock_cap.release.assert_called()

        # Verify store action dispatched
        call_args = self.mock_store.dispatch.call_args[0][0]
        self.assertEqual(call_args.type, ActionType.CAMERA_CONNECTION_CHANGED)
        self.assertFalse(call_args.payload['connected'])

    # === CALIBRATION TESTS ===

    def test_load_calibration_success(self):
        """Test successful calibration loading"""
        # Create mock calibration data
        mock_camera_matrix = np.eye(3)
        mock_dist_coeffs = np.zeros((4, 1))

        with patch('numpy.load') as mock_load:
            mock_data = {
                'camera_matrix': mock_camera_matrix,
                'dist_coeffs': mock_dist_coeffs
            }
            mock_load.return_value = mock_data

            # Test
            result = self.camera_manager.load_calibration('/path/to/calibration.npz')

            # Verify result
            self.assertTrue(result)
            self.assertTrue(self.camera_manager.is_calibrated())
            np.testing.assert_array_equal(self.camera_manager.camera_matrix, mock_camera_matrix)
            np.testing.assert_array_equal(self.camera_manager.dist_coeffs, mock_dist_coeffs)

            # Verify store action
            call_args = self.mock_store.dispatch.call_args[0][0]
            self.assertEqual(call_args.type, ActionType.CAMERA_CALIBRATION_LOADED)
            self.assertTrue(call_args.payload['success'])
            self.assertEqual(call_args.payload['file_path'], '/path/to/calibration.npz')

    def test_load_calibration_failure(self):
        """Test calibration loading failure"""
        with patch('numpy.load') as mock_load:
            mock_load.side_effect = Exception("File not found")

            # Test
            result = self.camera_manager.load_calibration('/invalid/path.npz')

            # Verify result
            self.assertFalse(result)
            self.assertFalse(self.camera_manager.is_calibrated())

            # Verify store action
            call_args = self.mock_store.dispatch.call_args[0][0]
            self.assertEqual(call_args.type, ActionType.CAMERA_CALIBRATION_LOADED)
            self.assertFalse(call_args.payload['success'])

    def test_save_calibration_success(self):
        """Test successful calibration saving"""
        # Setup calibration data
        self.camera_manager.camera_matrix = np.eye(3)
        self.camera_manager.dist_coeffs = np.zeros((4, 1))

        with patch('numpy.savez') as mock_savez:
            result = self.camera_manager.save_calibration('/path/to/save.npz')

            self.assertTrue(result)
            mock_savez.assert_called_once_with(
                '/path/to/save.npz',
                camera_matrix=self.camera_manager.camera_matrix,
                dist_coeffs=self.camera_manager.dist_coeffs
            )

    def test_save_calibration_not_calibrated(self):
        """Test save calibration when not calibrated"""
        result = self.camera_manager.save_calibration('/path/to/save.npz')
        self.assertFalse(result)

    def test_save_calibration_failure(self):
        """Test save calibration failure"""
        # Setup calibration data
        self.camera_manager.camera_matrix = np.eye(3)
        self.camera_manager.dist_coeffs = np.zeros((4, 1))

        with patch('numpy.savez') as mock_savez:
            mock_savez.side_effect = Exception("Save error")

            result = self.camera_manager.save_calibration('/path/to/save.npz')
            self.assertFalse(result)

    # === CONFIGURATION TESTS ===

    def test_set_resolution(self):
        """Test setting camera resolution"""
        result = self.camera_manager.set_resolution(1280, 720)

        self.assertTrue(result)
        self.assertEqual(self.camera_manager.resolution, (1280, 720))

    @patch('cv2.VideoCapture')
    def test_set_resolution_when_connected(self, mock_video_capture):
        """Test setting resolution when camera is connected"""
        # Setup connected camera
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        self.camera_manager.connect()

        # Test resolution change
        result = self.camera_manager.set_resolution(1280, 720)

        self.assertTrue(result)
        self.assertEqual(self.camera_manager.resolution, (1280, 720))

        # Verify camera properties were set
        mock_cap.set.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        mock_cap.set.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    def test_set_camera_id_not_connected(self):
        """Test changing camera ID when not connected"""
        result = self.camera_manager.set_camera_id(1)

        self.assertTrue(result)
        self.assertEqual(self.camera_manager.camera_id, 1)

    @patch('cv2.VideoCapture')
    def test_set_camera_id_when_connected(self, mock_video_capture):
        """Test changing camera ID when connected (should reconnect)"""
        # Setup connected camera
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        self.camera_manager.connect()
        self.mock_store.dispatch.reset_mock()  # Reset to check disconnect call

        # Test camera ID change
        result = self.camera_manager.set_camera_id(1)

        self.assertTrue(result)
        self.assertEqual(self.camera_manager.camera_id, 1)
        # Should have disconnected and reconnected
        self.assertEqual(self.mock_store.dispatch.call_count, 2)  # disconnect + connect

    # === FRAME CAPTURE TESTS ===

    @patch('cv2.VideoCapture')
    def test_get_frame_sync_success(self, mock_video_capture):
        """Test synchronous frame capture"""
        # Setup connected camera
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, test_frame)
        mock_video_capture.return_value = mock_cap

        self.camera_manager.connect()

        # Test frame capture
        frame = self.camera_manager.get_frame_sync()

        self.assertIsNotNone(frame)
        np.testing.assert_array_equal(frame, test_frame)

    def test_get_frame_sync_not_connected(self):
        """Test frame capture when not connected"""
        frame = self.camera_manager.get_frame_sync()
        self.assertIsNone(frame)

    @patch('cv2.VideoCapture')
    def test_get_frame_sync_read_failure(self, mock_video_capture):
        """Test frame capture read failure"""
        # Setup connected camera with read failure
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.side_effect = [(True, np.zeros((480, 640, 3), dtype=np.uint8)), (False, None)]
        mock_video_capture.return_value = mock_cap

        self.camera_manager.connect()

        # Test frame capture failure
        frame = self.camera_manager.get_frame_sync()
        self.assertIsNone(frame)

    # === CAMERA INFO TESTS ===

    def test_get_camera_info_not_connected(self):
        """Test camera info when not connected"""
        info = self.camera_manager.get_camera_info()

        expected_info = {
            "camera_id": 0,
            "connected": False,
            "calibrated": False,
            "resolution": (640, 480)
        }

        self.assertEqual(info, expected_info)

    @patch('cv2.VideoCapture')
    def test_get_camera_info_connected(self, mock_video_capture):
        """Test camera info when connected"""
        # Setup connected camera
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
            cv2.CAP_PROP_FPS: 30.0
        }.get(prop, 0)
        mock_video_capture.return_value = mock_cap

        self.camera_manager.connect()

        info = self.camera_manager.get_camera_info()

        self.assertEqual(info["camera_id"], 0)
        self.assertTrue(info["connected"])
        self.assertFalse(info["calibrated"])
        self.assertEqual(info["width"], 640)
        self.assertEqual(info["height"], 480)
        self.assertEqual(info["fps"], 30.0)

    # === MARKER DETECTION TESTS ===

    @patch('cv2.aruco.detectMarkers')
    def test_detect_marker_pose_not_calibrated(self, mock_detect):
        """Test marker detection when not calibrated"""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.camera_manager.detect_marker_pose(frame, 15.0)

        self.assertIsNone(result)
        mock_detect.assert_not_called()

    @patch('cv2.aruco.detectMarkers')
    @patch('cv2.aruco.estimatePoseSingleMarkers')
    def test_detect_marker_pose_success(self, mock_estimate_pose, mock_detect):
        """Test successful marker detection"""
        # Setup calibration
        self.camera_manager.camera_matrix = np.eye(3)
        self.camera_manager.dist_coeffs = np.zeros((4, 1))

        # Setup mock detection
        mock_corners = [np.array([[[100, 100], [200, 100], [200, 200], [100, 200]]], dtype=np.float32)]
        mock_ids = np.array([[0]])
        mock_detect.return_value = (mock_corners, mock_ids, None)

        # Setup mock pose estimation
        mock_rvecs = np.array([[[0.1, 0.2, 0.3]]])
        mock_tvecs = np.array([[[10, 20, 100]]])
        mock_estimate_pose.return_value = (mock_rvecs, mock_tvecs, None)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.camera_manager.detect_marker_pose(frame, 15.0)

        self.assertIsNotNone(result)
        self.assertEqual(result['markers_detected'], 1)
        self.assertEqual(result['marker_ids'], [0])
        self.assertEqual(result['marker_length_mm'], 15.0)
        self.assertIn('poses', result)

    @patch('cv2.aruco.detectMarkers')
    def test_detect_marker_pose_no_markers(self, mock_detect):
        """Test marker detection with no markers found"""
        # Setup calibration
        self.camera_manager.camera_matrix = np.eye(3)
        self.camera_manager.dist_coeffs = np.zeros((4, 1))

        # Setup mock detection - no markers
        mock_detect.return_value = (None, None, None)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.camera_manager.detect_marker_pose(frame, 15.0)

        self.assertIsNone(result)

    # === CAPTURE THREAD TESTS ===

    @patch('cv2.VideoCapture')
    def test_capture_thread_disabled_for_testing(self, mock_video_capture):
        """Test that capture thread can be disabled for testing"""
        # Setup connected camera with capture thread disabled
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        # Connect should not start capture thread when disabled
        self.camera_manager.connect()

        # Verify thread is not started
        self.assertIsNone(self.camera_manager._capture_thread)
        self.assertFalse(self.camera_manager._capture_running)

    @patch('cv2.VideoCapture')
    def test_capture_thread_enabled_by_default(self, mock_video_capture):
        """Test that capture thread starts when enabled"""
        # Create camera manager with capture thread enabled
        enabled_manager = CameraManager(store=self.mock_store, enable_capture_thread=True)

        # Setup connected camera
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        # Connect should start capture thread when enabled
        enabled_manager.connect()

        # Verify thread is started
        self.assertIsNotNone(enabled_manager._capture_thread)
        self.assertTrue(enabled_manager._capture_running)

        # Cleanup
        enabled_manager.disconnect()

    @patch('cv2.VideoCapture')
    def test_capture_thread_lifecycle(self, mock_video_capture):
        """Test capture thread start and stop"""
        # Create camera manager with capture thread enabled
        enabled_manager = CameraManager(store=self.mock_store, enable_capture_thread=True)

        # Setup connected camera
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_video_capture.return_value = mock_cap

        # Connect (should start thread)
        enabled_manager.connect()

        # Verify thread is running
        self.assertIsNotNone(enabled_manager._capture_thread)
        self.assertTrue(enabled_manager._capture_running)

        # Wait a bit for thread to start
        time.sleep(0.1)

        # Disconnect (should stop thread)
        enabled_manager.disconnect()

        # Verify thread is stopped
        self.assertFalse(enabled_manager._capture_running)

    # === UTILITY FUNCTION TESTS ===

    @patch('platform.system')
    def test_get_optimal_camera_backend_windows(self, mock_system):
        """Test optimal camera backend for Windows"""
        mock_system.return_value = 'Windows'
        backend = get_optimal_camera_backend()
        self.assertEqual(backend, cv2.CAP_DSHOW)

    @patch('platform.system')
    def test_get_optimal_camera_backend_linux(self, mock_system):
        """Test optimal camera backend for Linux"""
        mock_system.return_value = 'Linux'
        backend = get_optimal_camera_backend()
        self.assertEqual(backend, cv2.CAP_V4L2)

    @patch('platform.system')
    def test_get_optimal_camera_backend_macos(self, mock_system):
        """Test optimal camera backend for macOS"""
        mock_system.return_value = 'Darwin'
        backend = get_optimal_camera_backend()
        self.assertEqual(backend, cv2.CAP_AVFOUNDATION)

    @patch('platform.system')
    def test_get_optimal_camera_backend_unknown(self, mock_system):
        """Test optimal camera backend for unknown system"""
        mock_system.return_value = 'Unknown'
        backend = get_optimal_camera_backend()
        self.assertEqual(backend, cv2.CAP_ANY)


class TestCameraManagerIntegration(unittest.TestCase):
    """Integration tests with real store"""

    def setUp(self):
        """Set up integration test fixtures"""
        self.store = ApplicationStore()
        # Disable capture thread for testing to prevent interference
        self.camera_manager = CameraManager(store=self.store, enable_capture_thread=False)

    def test_store_integration_connection_state(self):
        """Test that camera connection updates store state"""
        # Subscribe to store changes
        state_changes = []

        def track_changes(state):
            state_changes.append(state.camera.connected)

        unsubscribe = self.store.subscribe(track_changes)

        try:
            # Initial state should be disconnected
            initial_state = self.store.get_state()
            self.assertFalse(initial_state.camera.connected)

            # Mock a successful connection (we can't test real hardware in unit tests)
            with patch('cv2.VideoCapture') as mock_video_capture:
                mock_cap = Mock()
                mock_cap.isOpened.return_value = True
                mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
                mock_video_capture.return_value = mock_cap

                # Connect should update store
                self.camera_manager.connect()

                # Check store state
                current_state = self.store.get_state()
                self.assertTrue(current_state.camera.connected)
                self.assertEqual(current_state.camera.camera_id, 0)

                # Disconnect should update store
                self.camera_manager.disconnect()

                final_state = self.store.get_state()
                self.assertFalse(final_state.camera.connected)

        finally:
            unsubscribe()


if __name__ == '__main__':
    # Run specific test suites
    suite = unittest.TestSuite()

    # Add all test methods
    suite.addTest(unittest.makeSuite(TestCameraManager))
    suite.addTest(unittest.makeSuite(TestCameraManagerIntegration))

    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")

    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")