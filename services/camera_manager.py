import cv2
import numpy as np
from services.event_broker import event_aware, CameraEvents


@event_aware()
class CameraManager:
    def __init__(self, camera_id=0, dictionary=cv2.aruco.DICT_4X4_50):
        self.camera_id = camera_id
        self.cap = None
        self.camera_matrix = None
        self.dist_coeffs = None
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
        self.parameters = cv2.aruco.DetectorParameters()

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
            self._is_connected = success

            if success:
                # Test capture to ensure camera is working
                ret, test_frame = self.cap.read()
                if not ret:
                    success = False
                    self._is_connected = False
                    self.cap.release()
                    self.cap = None
                    self.emit(CameraEvents.ERROR, "Camera connected but unable to capture frames")

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

    def detect_marker_pose(self, image, marker_length):
        """Detect ArUco marker pose in image"""
        if self.camera_matrix is None or self.dist_coeffs is None:
            raise ValueError("Camera not calibrated")

        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            corners, ids, _ = cv2.aruco.detectMarkers(gray, self.aruco_dict, parameters=self.parameters)

            if ids is not None and len(ids) > 0:
                rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                    corners, marker_length, self.camera_matrix, self.dist_coeffs)

                # Draw markers for visualization
                cv2.aruco.drawDetectedMarkers(image, corners, ids)
                cv2.drawFrameAxes(image, self.camera_matrix, self.dist_coeffs,
                                  rvecs[0], tvecs[0], marker_length * 0.5)

                center = np.mean(corners[0][0], axis=0)
                h, w = image.shape[:2]
                norm_pos = (center[0] / w, center[1] / h)

                return rvecs[0][0], tvecs[0][0], norm_pos, image
            else:
                return None, None, None, image

        except Exception as e:
            error_msg = f"Error in marker detection: {e}"
            self.emit(CameraEvents.ERROR, error_msg)
            raise

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