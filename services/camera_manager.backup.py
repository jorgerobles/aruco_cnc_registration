# services/camera_manager.py
"""
Refactored Camera Manager with Store Integration
Focuses on camera hardware control, store manages state
Simple, lean implementation following SOLID principles
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

# Backward compatibility: Keep CameraEvents for existing GUI components during transition
class CameraEvents:
    """
    Legacy CameraEvents class for backward compatibility
    Existing GUI components may still import this during incremental migration
    """
    CONNECTED = "camera.connected"
    DISCONNECTED = "camera.disconnected"
    FRAME_CAPTURED = "camera.frame_captured"
    ERROR = "camera.error"
    CALIBRATION_LOADED = "camera.calibration_loaded"
    FOV_CALCULATED = "camera.fov_calculated"
    FOV_UPDATED = "camera.fov_updated"


class CameraManager:
    """
    Hardware-focused camera manager with store integration
    Single responsibility: camera hardware control only
    State management: handled by store via actions
    """

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
        self._enable_capture_thread = enable_capture_thread  # Allow disabling for tests

        # ArUco setup for FOV calculation
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_parameters = cv2.aruco.DetectorParameters()

    @property
    def is_connected(self) -> bool:
        """Check hardware connection status"""
        return self._is_connected and self.cap is not None and self.cap.isOpened()

    def connect(self) -> bool:
        """
        Connect to camera hardware and return result
        Store handles state updates via actions
        """
        try:
            # Disconnect if already connected
            if self.is_connected:
                self.disconnect()

            optimal_backend = get_optimal_camera_backend()
            self.cap = cv2.VideoCapture(self.camera_id, optimal_backend)

            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_id)

            success = self.cap.isOpened()

            if success:
                # Configure camera
                rw, rh = self.resolution
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, rw)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, rh)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                # Test capture
                ret, test_frame = self.cap.read()
                if not ret:
                    success = False
                    self._is_connected = False
                    self.cap.release()
                    self.cap = None
                else:
                    self._is_connected = success
                    self._start_capture_thread()

            # Dispatch action to store instead of emitting event
            self.store.dispatch(CameraActions.connection_changed(success, self.camera_id))
            return success

        except Exception as e:
            # Dispatch action to store instead of emitting event
            self.store.dispatch(CameraActions.connection_changed(False, self.camera_id))
            self._is_connected = False
            return False

    def disconnect(self) -> bool:
        """
        Disconnect camera hardware and return result
        Store handles state updates via actions
        """
        try:
            self._stop_capture_thread()

            if self.cap:
                self.cap.release()
                self.cap = None

            was_connected = self._is_connected
            self._is_connected = False

            if was_connected:
                # Dispatch action to store instead of emitting event
                self.store.dispatch(CameraActions.connection_changed(False, self.camera_id))

            return True

        except Exception as e:
            return False

    def load_calibration(self, calibration_file_path: str) -> bool:
        """
        Load camera calibration and return result
        Store handles state updates via actions
        """
        try:
            # Load calibration data
            calibration_data = np.load(calibration_file_path)
            self.camera_matrix = calibration_data['camera_matrix']
            self.dist_coeffs = calibration_data['dist_coeffs']

            # Dispatch action to store instead of emitting event
            self.store.dispatch(CameraActions.calibration_loaded(True, calibration_file_path))
            return True

        except Exception as e:
            # Dispatch action to store instead of emitting event
            self.store.dispatch(CameraActions.calibration_loaded(False, calibration_file_path))
            return False

    def set_resolution(self, width: int, height: int) -> bool:
        """Set camera resolution and return result"""
        try:
            if self.cap and self.is_connected:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            self.resolution = (width, height)
            return True

        except Exception as e:
            return False

    def set_camera_id(self, camera_id: int) -> bool:
        """Change camera ID (requires reconnection if connected)"""
        try:
            was_connected = self.is_connected
            if was_connected:
                self.disconnect()

            self.camera_id = camera_id

            if was_connected:
                # Auto-reconnect if we were previously connected
                return self.connect()

            return True

        except Exception as e:
            return False

    def get_frame_sync(self) -> Optional[np.ndarray]:
        """
        Synchronous frame capture for immediate use
        Does not dispatch to store - used for manual operations
        """
        if not self.cap or not self._is_connected:
            return None

        try:
            ret, frame = self.cap.read()
            return frame if ret else None
        except Exception as e:
            return None

    def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information"""
        info = {
            "camera_id": self.camera_id,
            "connected": self.is_connected,
            "calibrated": self.camera_matrix is not None and self.dist_coeffs is not None,
            "resolution": self.resolution
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
        """Check if camera calibration is loaded"""
        return self.camera_matrix is not None and self.dist_coeffs is not None

    def get_calibration(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Get camera calibration matrices"""
        return self.camera_matrix, self.dist_coeffs

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

    # === FOV CALCULATION METHODS ===

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

    def calculate_fov_from_marker(self, marker_data: Dict) -> Optional[Dict]:
        """Calculate FOV from detected marker data"""
        if not marker_data or 'poses' not in marker_data:
            return None

        try:
            tvecs = np.array(marker_data['poses']['tvecs'])
            marker_length_mm = marker_data['marker_length_mm']

            if len(tvecs) > 0:
                # Use first marker for FOV calculation
                distance_mm = abs(tvecs[0][0][2])  # Z distance

                # Calculate FOV based on marker size and distance
                marker_pixel_size = np.linalg.norm(
                    np.array(marker_data['marker_corners'][0][0]) -
                    np.array(marker_data['marker_corners'][0][2])
                )

                if marker_pixel_size > 0:
                    mm_per_pixel = marker_length_mm / marker_pixel_size
                    frame_width_mm = self.resolution[0] * mm_per_pixel
                    frame_height_mm = self.resolution[1] * mm_per_pixel

                    fov_data = {
                        'width_mm': frame_width_mm,
                        'height_mm': frame_height_mm,
                        'distance_mm': distance_mm,
                        'mm_per_pixel': mm_per_pixel
                    }

                    return fov_data

            return None

        except Exception as e:
            return None

    # === PRIVATE METHODS ===

    def _start_capture_thread(self):
        """Start background capture thread for continuous frame updates"""
        if (self._enable_capture_thread and
                (self._capture_thread is None or not self._capture_thread.is_alive())):
            self._capture_running = True
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()

    def _stop_capture_thread(self):
        """Stop background capture thread"""
        self._capture_running = False
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=1.0)

    def _capture_loop(self):
        """
        Background capture loop - dispatches frame actions to store
        Core responsibility: continuous frame updates to store
        """
        while self._capture_running and self.is_connected:
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    # Detect ArUco markers for FOV calculation
                    marker_data = self._detect_markers(frame)

                    # Dispatch CAMERA_FRAME_UPDATED action to store
                    self.store.dispatch(CameraActions.frame_updated(frame.copy(), marker_data))

                    time.sleep(0.033)  # ~30fps
                else:
                    # Camera hardware failure
                    if self._is_connected:
                        self._is_connected = False
                        # Dispatch disconnection to store
                        self.store.dispatch(CameraActions.connection_changed(False, self.camera_id))
                    break

            except Exception as e:
                # Dispatch disconnection on error
                if self._is_connected:
                    self._is_connected = False
                    self.store.dispatch(CameraActions.connection_changed(False, self.camera_id))
                break

    def _detect_markers(self, frame: np.ndarray) -> Optional[Dict]:
        """Detect ArUco markers and return basic marker data"""
        try:
            corners, ids, _ = cv2.aruco.detectMarkers(frame, self.aruco_dict, parameters=self.aruco_parameters)

            if ids is not None and len(corners) > 0:
                return {
                    'markers_detected': len(ids),
                    'marker_ids': ids.flatten().tolist(),
                    'marker_corners': [corner.tolist() for corner in corners]
                }
            return None

        except Exception as e:
            return None