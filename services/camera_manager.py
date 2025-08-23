# services/camera_manager_fixed.py
"""
Fixed Camera Manager with improved error handling and debugging
"""

import cv2
import numpy as np
import platform
import threading
import time
from typing import Optional, Dict, Any, Tuple

from store.actions import CameraActions
from store.store import ApplicationStore


def get_optimal_camera_backend():
    """Get the optimal camera backend for current platform"""
    system = platform.system().lower()
    if system == "windows":
        return cv2.CAP_DSHOW
    elif system == "linux":
        return cv2.CAP_V4L2
    elif system == "darwin":  # macOS
        return cv2.CAP_AVFOUNDATION
    else:
        return cv2.CAP_ANY


class CameraEvents:
    """Legacy CameraEvents for backward compatibility"""
    CONNECTED = "camera.connected"
    DISCONNECTED = "camera.disconnected"
    FRAME_CAPTURED = "camera.frame_captured"
    ERROR = "camera.error"
    CALIBRATION_LOADED = "camera.calibration_loaded"
    FOV_CALCULATED = "camera.fov_calculated"
    FOV_UPDATED = "camera.fov_updated"


class CameraManager:
    """Fixed camera manager with improved error handling"""

    def __init__(self, store: ApplicationStore, camera_id=0, resolution=(640, 480), enable_capture_thread=True):
        self.store = store
        self.camera_id = camera_id
        self.cap = None
        self.camera_matrix = None
        self.dist_coeffs = None
        self.resolution = resolution
        self._is_connected = False

        # Capture thread
        self._capture_thread = None
        self._capture_running = False
        self._enable_capture_thread = enable_capture_thread

        # Debug/monitoring
        self._frame_count = 0
        self._error_count = 0
        self._last_frame_time = 0

        # ArUco setup
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_parameters = cv2.aruco.DetectorParameters()

    def connect(self) -> bool:
        """Connect with improved error handling and debugging"""
        try:
            print(f"[CameraManager] Attempting to connect to camera {self.camera_id}")

            # Disconnect if already connected
            if self.is_connected:
                print("[CameraManager] Already connected, disconnecting first")
                self.disconnect()

            # Try optimal backend first
            optimal_backend = get_optimal_camera_backend()
            print(f"[CameraManager] Trying optimal backend: {optimal_backend}")

            self.cap = cv2.VideoCapture(self.camera_id, optimal_backend)

            if not self.cap.isOpened():
                print("[CameraManager] Optimal backend failed, trying default")
                self.cap = cv2.VideoCapture(self.camera_id)

            success = self.cap.isOpened()
            print(f"[CameraManager] Camera opened: {success}")

            if success:
                # Configure camera
                rw, rh = self.resolution
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, rw)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, rh)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                print(f"[CameraManager] Camera configured: {rw}x{rh}")

                # Test capture multiple times
                test_success = False
                for attempt in range(3):
                    print(f"[CameraManager] Test capture attempt {attempt + 1}")
                    ret, test_frame = self.cap.read()
                    if ret and test_frame is not None:
                        print(f"[CameraManager] Test frame: {test_frame.shape}")
                        test_success = True
                        break
                    else:
                        print(f"[CameraManager] Test capture failed: ret={ret}")
                        time.sleep(0.1)

                if test_success:
                    self._is_connected = True
                    print("[CameraManager] Connection successful")

                    if self._enable_capture_thread:
                        self._start_capture_thread()
                    else:
                        print("[CameraManager] Capture thread disabled")
                else:
                    print("[CameraManager] Test captures failed")
                    success = False
                    self._is_connected = False
                    self.cap.release()
                    self.cap = None

            # Dispatch to store
            self.store.dispatch(CameraActions.connection_changed(success, self.camera_id))
            print(f"[CameraManager] Connection result: {success}")
            return success

        except Exception as e:
            print(f"[CameraManager] Connection error: {e}")
            self.store.dispatch(CameraActions.connection_changed(False, self.camera_id))
            self._is_connected = False
            return False



    def get_frame_sync(self) -> Optional[np.ndarray]:
        """Get current frame synchronously"""
        if not self.cap or not self._is_connected:
            return None

        try:
            ret, frame = self.cap.read()
            return frame if ret and frame is not None else None
        except Exception as e:
            print(f"[CameraManager] Sync frame error: {e}")
            return None

    def _start_capture_thread(self):
        """Start capture thread with better error handling"""
        if not self._enable_capture_thread:
            return

        if self._capture_thread and self._capture_thread.is_alive():
            print("[CameraManager] Capture thread already running")
            return

        print("[CameraManager] Starting capture thread")
        self._capture_running = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

    # Fix for services/camera_manager.py - proper thread cleanup

    def _stop_capture_thread(self):
        """Stop capture thread with proper cleanup"""
        if not self._capture_running:
            return

        print("[CameraManager] Stopping capture thread")
        self._capture_running = False

        if self._capture_thread and self._capture_thread.is_alive():
            # Give thread a short time to stop gracefully
            self._capture_thread.join(timeout=0.5)
            if self._capture_thread.is_alive():
                print("[CameraManager] Capture thread did not stop cleanly - forcing")
                # Don't wait any longer, just continue
            else:
                print("[CameraManager] Capture thread stopped cleanly")

        self._capture_thread = None

    def _capture_loop(self):
        """Fixed capture loop with proper exit handling"""
        print("[CameraManager] Capture loop started")
        consecutive_failures = 0
        max_consecutive_failures = 10

        while self._capture_running and self.is_connected:
            try:
                # Check if we should still be running
                if not self._capture_running:
                    break

                if not self.cap or not self.cap.isOpened():
                    print("[CameraManager] Camera not available in capture loop")
                    break

                ret, frame = self.cap.read()

                if ret and frame is not None:
                    # Reset failure counter
                    consecutive_failures = 0
                    self._frame_count += 1
                    self._last_frame_time = time.time()

                    # Only process if still running
                    if self._capture_running:
                        # Detect markers (simplified)
                        marker_data = self._detect_markers_simple(frame)

                        # Dispatch to store only if still running
                        if self._capture_running:
                            self.store.dispatch(CameraActions.frame_updated(frame.copy(), marker_data))

                        # Log progress occasionally
                        if self._frame_count % 100 == 0:
                            print(f"[CameraManager] Captured {self._frame_count} frames")

                    time.sleep(0.033)  # ~30fps

                else:
                    consecutive_failures += 1
                    self._error_count += 1

                    # Only log if still running (not shutting down)
                    if self._capture_running:
                        print(
                            f"[CameraManager] Frame capture failed: {consecutive_failures}/{max_consecutive_failures}")

                    if consecutive_failures >= max_consecutive_failures:
                        print("[CameraManager] Too many consecutive failures, disconnecting")
                        break

                    time.sleep(0.1)  # Wait before retry

            except Exception as e:
                # Don't log errors during shutdown
                if self._capture_running:
                    print(f"[CameraManager] Capture loop error: {e}")
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    break
                time.sleep(0.1)

        # Cleanup on exit
        print("[CameraManager] Capture loop ending")
        if self._is_connected:
            print("[CameraManager] Capture loop ended, disconnecting")
            self._is_connected = False
            # Don't dispatch during shutdown if thread is stopping
            if self._capture_running:
                self.store.dispatch(CameraActions.connection_changed(False, self.camera_id))

    def disconnect(self) -> bool:
        """Fixed disconnect with proper thread cleanup"""
        try:
            print("[CameraManager] Disconnecting...")

            # Stop capture thread first - this is the key fix
            self._stop_capture_thread()

            # Release camera after thread is stopped
            if self.cap:
                self.cap.release()
                self.cap = None
                print("[CameraManager] Camera released")

            was_connected = self._is_connected
            self._is_connected = False

            if was_connected:
                self.store.dispatch(CameraActions.connection_changed(False, self.camera_id))
                print("[CameraManager] Disconnection dispatched to store")

            return True

        except Exception as e:
            print(f"[CameraManager] Disconnect error: {e}")
            return False

    # Also add this property check
    @property
    def is_connected(self) -> bool:
        """Check if camera is connected"""
        # Don't access cap if we're shutting down
        if not self._capture_running:
            return False
        return self._is_connected and self.cap is not None and self.cap.isOpened()

    def detect_marker_pose(self, frame: np.ndarray, marker_length_mm: float) -> Optional[Dict]:
        """
        Detect ArUco marker pose and calculate real-world coordinates
        Returns marker data for FOV calculation
        """
        if not self.is_calibrated():
            return None

        try:
            corners, ids, _ = cv2.aruco.detectMarkers(frame, self.aruco_dict, parameters=self.aruco_parameters)

            if ids is not None and len(corners) > 0:
                # Calculate pose for each marker
                rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                    corners, marker_length_mm, self.camera_matrix, self.dist_coeffs
                )

                marker_data = {
                    'markers_detected': len(ids),
                    'marker_ids': ids.flatten().tolist(),
                    'marker_corners': [corner.tolist() for corner in corners],
                    'poses': {
                        'rvecs': rvecs.tolist(),
                        'tvecs': tvecs.tolist()
                    },
                    'marker_length_mm': marker_length_mm
                }

                return marker_data

            return None

        except Exception as e:
            return None




    def _detect_markers_simple(self, frame: np.ndarray) -> Optional[Dict]:
        """Simplified marker detection - FIXED: Proper numpy array handling"""
        try:
            # Skip marker detection on most frames for performance
            if self._frame_count % 5 != 0:
                return None

            corners, ids, _ = cv2.aruco.detectMarkers(frame, self.aruco_dict, parameters=self.aruco_parameters)

            # FIX: Safe boolean check and complete type conversion
            if ids is not None and len(ids) > 0:
                return {
                    'markers_detected': int(len(ids)),  # Ensure Python int
                    'has_markers': True  # Simple boolean
                }
            else:
                return {
                    'markers_detected': 0,
                    'has_markers': False
                }

        except Exception as e:
            print(f"[CameraManager] Marker detection error: {e}")
            return None



    def load_calibration(self, calibration_file_path: str) -> bool:
        """Load calibration with error handling"""
        try:
            calibration_data = np.load(calibration_file_path)
            self.camera_matrix = calibration_data['camera_matrix']
            self.dist_coeffs = calibration_data['dist_coeffs']

            self.store.dispatch(CameraActions.calibration_loaded(True, calibration_file_path))
            print(f"[CameraManager] Calibration loaded: {calibration_file_path}")
            return True

        except Exception as e:
            print(f"[CameraManager] Calibration load error: {e}")
            self.store.dispatch(CameraActions.calibration_loaded(False, calibration_file_path))
            return False

    def save_calibration(self, file_path: str) -> bool:
        """Save current calibration data"""
        if not self.is_calibrated():
            return False

        try:
            np.savez(file_path,
                     camera_matrix=self.camera_matrix,
                     dist_coeffs=self.dist_coeffs)
            return True
        except Exception as e:
            return False

    def set_camera_id(self, camera_id: int) -> bool:
        """Set camera ID with reconnection if needed"""
        try:
            was_connected = self.is_connected
            if was_connected:
                self.disconnect()

            self.camera_id = camera_id

            if was_connected:
                return self.connect()

            return True

        except Exception as e:
            print(f"[CameraManager] Set camera ID error: {e}")
            return False

    def set_resolution(self, width: int, height: int) -> bool:
        """Set camera resolution"""
        try:
            if self.cap and self.is_connected:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            self.resolution = (width, height)
            print(f"[CameraManager] Resolution set: {width}x{height}")
            return True

        except Exception as e:
            print(f"[CameraManager] Set resolution error: {e}")
            return False


    def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information"""
        info = {
            "camera_id": self.camera_id,
            "connected": self.is_connected,
            "calibrated": self.camera_matrix is not None and self.dist_coeffs is not None,
            "resolution": self.resolution,
            "frame_count": self._frame_count,
            "error_count": self._error_count
        }

        if self.is_connected and self.cap:
            try:
                info.update({
                    "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "fps": self.cap.get(cv2.CAP_PROP_FPS)
                })
            except Exception:
                pass

        return info

    def is_calibrated(self) -> bool:
        """Check if camera is calibrated"""
        return self.camera_matrix is not None and self.dist_coeffs is not None

    def get_calibration(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Get calibration matrices"""
        return self.camera_matrix, self.dist_coeffs
