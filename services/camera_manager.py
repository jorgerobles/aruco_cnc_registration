"""
Enhanced Camera Manager with integrated FOV calculation from ArUco markers
Handles camera connection, frame capture, calibration, and automatic FOV measurement
"""

import cv2
import numpy as np
import platform
from typing import Optional, Dict, Any, Tuple
from services.event_broker import event_aware


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
    CONNECTED = "camera.connected"
    DISCONNECTED = "camera.disconnected"
    FRAME_CAPTURED = "camera.frame_captured"
    ERROR = "camera.error"
    CALIBRATION_LOADED = "camera.calibration_loaded"
    # NEW: FOV-related events
    FOV_CALCULATED = "camera.fov_calculated"
    FOV_UPDATED = "camera.fov_updated"


@event_aware()
class CameraManager:
    """Enhanced camera manager with integrated ArUco-based FOV calculation"""

    def __init__(self, camera_id=0, resolution=(640, 480)):
        self.camera_id = camera_id
        self.cap = None
        self.camera_matrix = None
        self.dist_coeffs = None
        self.resolution = resolution

        # Connection state
        self._is_connected = False

        # NEW: FOV calculation state
        self.current_fov = None
        self.fov_history = []
        self.max_fov_history = 10

        # ArUco setup for FOV calculation
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_parameters = cv2.aruco.DetectorParameters()

    @property
    def is_connected(self) -> bool:
        """Check if camera is currently connected"""
        return self._is_connected and self.cap is not None and self.cap.isOpened()

    def connect(self):
        """Connect to camera with platform-optimized backend"""
        try:
            # Get optimal backend for this platform
            optimal_backend = get_optimal_camera_backend()

            # Try optimal backend first
            self.cap = cv2.VideoCapture(self.camera_id, optimal_backend)

            # If optimal backend fails, fallback to default
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_id)

            success = self.cap.isOpened()

            if success:
                # Set resolution
                rw, rh = self.resolution
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, rw)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, rh)

                # Optimize for speed
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                # Test capture to ensure camera is working
                ret, test_frame = self.cap.read()
                if not ret:
                    success = False
                    self._is_connected = False
                    self.cap.release()
                    self.cap = None
                    self.emit(CameraEvents.ERROR, "Camera connected but unable to capture frames")
                else:
                    self._is_connected = success

            # Emit connection event with success status
            self.emit(CameraEvents.CONNECTED, success)
            return success

        except Exception as e:
            error_msg = f"Failed to connect to camera {self.camera_id}: {e}"
            self.emit(CameraEvents.ERROR, error_msg)
            self.emit(CameraEvents.CONNECTED, False)
            self._is_connected = False
            return False

    def disconnect(self):
        """Disconnect camera and emit disconnection event"""
        if self.cap:
            self.cap.release()
            self.cap = None

        was_connected = self._is_connected
        self._is_connected = False

        # Clear FOV data
        self.current_fov = None
        self.fov_history.clear()

        if was_connected:
            self.emit(CameraEvents.DISCONNECTED)

    def capture_frame(self):
        """Capture frame and emit frame event if successful"""
        if not self.cap or not self._is_connected:
            return None

        try:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                # Emit frame event for any listeners
                self.emit(CameraEvents.FRAME_CAPTURED, frame.copy())
                return frame
            else:
                # Camera might have been disconnected
                if self._is_connected:
                    self.emit(CameraEvents.ERROR, "Failed to capture frame - camera may be disconnected")
                    self._is_connected = False
                    self.emit(CameraEvents.DISCONNECTED)
                return None

        except Exception as e:
            error_msg = f"Error capturing frame: {e}"
            self.emit(CameraEvents.ERROR, error_msg)
            return None

    def load_calibration(self, file_path):
        """Load camera calibration data"""
        try:
            data = np.load(file_path)
            self.camera_matrix = data["camera_matrix"]
            self.dist_coeffs = data["dist_coeffs"]
            self.emit(CameraEvents.CALIBRATION_LOADED, file_path)
            return True
        except Exception as e:
            error_msg = f"Failed to load calibration: {e}"
            self.emit(CameraEvents.ERROR, error_msg)
            return False

    # NEW: FOV calculation methods

    def calculate_fov_from_frame(self, frame: np.ndarray, marker_size_mm: float) -> Optional[Dict[str, Any]]:
        """
        Calculate field of view from ArUco markers in a frame

        Args:
            frame: Camera frame containing ArUco marker
            marker_size_mm: Known size of the ArUco marker in millimeters

        Returns:
            Dictionary with FOV information or None if no marker detected
        """
        if not self.is_calibrated():
            return None

        try:
            # Convert to grayscale for marker detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detect ArUco markers
            corners, ids, _ = cv2.aruco.detectMarkers(
                gray, self.aruco_dict, parameters=self.aruco_parameters
            )

            if ids is not None and len(ids) > 0:
                # Use the first detected marker
                marker_corners = corners[0][0]  # Shape: (4, 2)

                # Calculate marker size in pixels
                # Distance between corner 0 and corner 1 (top edge)
                width_pixels = np.linalg.norm(marker_corners[1] - marker_corners[0])
                # Distance between corner 0 and corner 3 (left edge)
                height_pixels = np.linalg.norm(marker_corners[3] - marker_corners[0])
                avg_size_pixels = (width_pixels + height_pixels) / 2

                # Calculate pixels per mm
                pixels_per_mm = avg_size_pixels / marker_size_mm

                # Get camera resolution
                frame_height, frame_width = frame.shape[:2]

                # Calculate field of view
                fov_width_mm = frame_width / pixels_per_mm
                fov_height_mm = frame_height / pixels_per_mm

                # Estimate marker pose for distance calculation
                rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                    [marker_corners], marker_size_mm, self.camera_matrix, self.dist_coeffs
                )

                distance_mm = tvecs[0][0][2]  # Z distance

                fov_data = {
                    'width_mm': float(fov_width_mm),
                    'height_mm': float(fov_height_mm),
                    'pixels_per_mm': float(pixels_per_mm),
                    'marker_size_pixels': float(avg_size_pixels),
                    'marker_size_mm': float(marker_size_mm),
                    'distance_mm': float(distance_mm),
                    'frame_resolution': (frame_width, frame_height),
                    'marker_id': int(ids[0][0]),
                    'calculated_from': 'aruco_detection',
                    'timestamp': None  # Will be set by caller if needed
                }

                return fov_data

        except Exception as e:
            error_msg = f"Error calculating FOV from frame: {e}"
            self.emit(CameraEvents.ERROR, error_msg)

        return None

    def calculate_fov_from_current_frame(self, marker_size_mm: float) -> Optional[Dict[str, Any]]:
        """
        Calculate FOV from current camera frame

        Args:
            marker_size_mm: Known size of the ArUco marker in millimeters

        Returns:
            Dictionary with FOV information or None if no marker detected
        """
        if not self.is_connected:
            return None

        frame = self.capture_frame()
        if frame is None:
            return None

        fov_data = self.calculate_fov_from_frame(frame, marker_size_mm)

        if fov_data is not None:
            import time
            fov_data['timestamp'] = time.time()

            # Store in history
            self.fov_history.append(fov_data)
            if len(self.fov_history) > self.max_fov_history:
                self.fov_history.pop(0)

            # Update current FOV
            self.current_fov = fov_data

            # Emit event
            self.emit(CameraEvents.FOV_CALCULATED, fov_data)

        return fov_data

    def get_averaged_fov(self, num_samples: int = 5) -> Optional[Dict[str, Any]]:
        """
        Calculate FOV by averaging multiple samples for better accuracy

        Args:
            num_samples: Number of frames to sample and average

        Returns:
            Dictionary with averaged FOV information
        """
        if not self.is_connected or not self.is_calibrated():
            return None

        samples = []
        marker_size_mm = 15.0  # Default marker size, should be configurable

        for i in range(num_samples):
            fov_data = self.calculate_fov_from_current_frame(marker_size_mm)
            if fov_data is not None:
                samples.append(fov_data)

            # Small delay between samples
            import time
            time.sleep(0.1)

        if not samples:
            return None

        # Calculate averages
        avg_fov = {
            'width_mm': np.mean([s['width_mm'] for s in samples]),
            'height_mm': np.mean([s['height_mm'] for s in samples]),
            'pixels_per_mm': np.mean([s['pixels_per_mm'] for s in samples]),
            'distance_mm': np.mean([s['distance_mm'] for s in samples]),
            'frame_resolution': samples[0]['frame_resolution'],
            'calculated_from': 'averaged_aruco_detection',
            'num_samples': len(samples),
            'std_dev': {
                'width_mm': np.std([s['width_mm'] for s in samples]),
                'height_mm': np.std([s['height_mm'] for s in samples]),
                'pixels_per_mm': np.std([s['pixels_per_mm'] for s in samples])
            },
            'timestamp': time.time()
        }

        # Update current FOV
        self.current_fov = avg_fov

        # Emit event
        self.emit(CameraEvents.FOV_CALCULATED, avg_fov)

        return avg_fov

    def get_current_fov(self) -> Optional[Dict[str, Any]]:
        """Get the most recently calculated FOV data"""
        return self.current_fov.copy() if self.current_fov else None

    def get_fov_history(self) -> list:
        """Get history of FOV calculations"""
        return [fov.copy() for fov in self.fov_history]

    def clear_fov_data(self):
        """Clear FOV calculation history"""
        self.current_fov = None
        self.fov_history.clear()
        self.emit(CameraEvents.FOV_UPDATED, None)

    def pixel_to_real_world(self, pixel_x: float, pixel_y: float,
                           use_current_fov: bool = True) -> Optional[Tuple[float, float]]:
        """
        Convert pixel coordinates to real-world millimeters using current FOV

        Args:
            pixel_x, pixel_y: Pixel coordinates
            use_current_fov: Whether to use current FOV or require fresh calculation

        Returns:
            (x_mm, y_mm) offset from camera center in millimeters, or None if no FOV data
        """
        fov_data = self.current_fov

        if fov_data is None and use_current_fov:
            return None

        if fov_data is None:
            # Try to calculate FOV from current frame
            fov_data = self.calculate_fov_from_current_frame(20.0)  # Default marker size
            if fov_data is None:
                return None

        try:
            frame_width, frame_height = fov_data['frame_resolution']

            # Convert to center-relative coordinates
            center_x = frame_width / 2
            center_y = frame_height / 2

            offset_x_pixels = pixel_x - center_x
            offset_y_pixels = pixel_y - center_y

            # Convert to millimeters
            pixels_per_mm = fov_data['pixels_per_mm']
            offset_x_mm = offset_x_pixels / pixels_per_mm
            offset_y_mm = -offset_y_pixels / pixels_per_mm  # Flip Y axis

            return (offset_x_mm, offset_y_mm)

        except Exception as e:
            error_msg = f"Error converting pixel to real-world coordinates: {e}"
            self.emit(CameraEvents.ERROR, error_msg)
            return None

    def normalized_to_real_world(self, norm_x: float, norm_y: float) -> Optional[Tuple[float, float]]:
        """
        Convert normalized coordinates (0-1) to real-world millimeters using current FOV

        Args:
            norm_x, norm_y: Normalized coordinates (0-1)

        Returns:
            (x_mm, y_mm) offset from camera center in millimeters, or None if no FOV data
        """
        if self.current_fov is None:
            return None

        try:
            fov_width_mm = self.current_fov['width_mm']
            fov_height_mm = self.current_fov['height_mm']

            # Convert normalized to center-relative millimeters
            offset_x_mm = (norm_x - 0.5) * fov_width_mm
            offset_y_mm = (0.5 - norm_y) * fov_height_mm  # Flip Y axis

            return (offset_x_mm, offset_y_mm)

        except Exception as e:
            error_msg = f"Error converting normalized to real-world coordinates: {e}"
            self.emit(CameraEvents.ERROR, error_msg)
            return None

    # EXISTING METHODS (unchanged)

    def set_camera_id(self, camera_id: int):
        """Change camera ID (requires reconnection)"""
        was_connected = self.is_connected
        if was_connected:
            self.disconnect()

        self.camera_id = camera_id

        if was_connected:
            # Auto-reconnect if we were previously connected
            self.connect()

    def get_camera_info(self) -> dict:
        """Get camera information including FOV data"""
        info = {
            "camera_id": self.camera_id,
            "connected": self.is_connected,
            "calibrated": self.camera_matrix is not None and self.dist_coeffs is not None,
            "has_fov_data": self.current_fov is not None
        }

        if self.is_connected and self.cap:
            try:
                # Get camera properties
                info.update({
                    "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "fps": self.cap.get(cv2.CAP_PROP_FPS)
                })
            except Exception as e:
                self.emit(CameraEvents.ERROR, f"Error getting camera info: {e}")

        # Add FOV information if available
        if self.current_fov:
            info["fov"] = self.current_fov.copy()

        return info

    def is_calibrated(self) -> bool:
        """Check if camera calibration is loaded"""
        return self.camera_matrix is not None and self.dist_coeffs is not None

    def get_calibration(self) -> tuple:
        """Get camera calibration matrices"""
        return self.camera_matrix, self.dist_coeffs

    def save_calibration(self, file_path):
        """Save current calibration data"""
        if not self.is_calibrated():
            raise ValueError("No calibration data to save")

        try:
            np.savez(file_path,
                     camera_matrix=self.camera_matrix,
                     dist_coeffs=self.dist_coeffs)
            return True
        except Exception as e:
            error_msg = f"Failed to save calibration: {e}"
            self.emit(CameraEvents.ERROR, error_msg)
            return False