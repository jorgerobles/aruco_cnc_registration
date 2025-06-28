"""
Handles camera connection, frame capture, and calibration
Marker detection moved to MarkerDetectionOverlay
"""

import cv2
import numpy as np
from services.event_broker import event_aware, CameraEvents


@event_aware()
class CameraManager:
    def __init__(self, camera_id=0, resolution=(640,480,)):
        self.camera_id = camera_id
        self.cap = None
        self.camera_matrix = None
        self.dist_coeffs = None
        self.resolution = resolution

        # Connection state
        self._is_connected = False

        # self._event_broker is automatically available from decorator

    @property
    def is_connected(self) -> bool:
        """Check if camera is currently connected"""
        return self._is_connected and self.cap is not None and self.cap.isOpened()

    def connect(self):
        """Connect to camera and emit connection event"""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            success = self.cap.isOpened()

            if success:
                # Set resolution to 1280x720
                rw, rh = self.resolution

                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, rw)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, rh)

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
        """Get camera information"""
        info = {
            "camera_id": self.camera_id,
            "connected": self.is_connected,
            "calibrated": self.camera_matrix is not None and self.dist_coeffs is not None
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