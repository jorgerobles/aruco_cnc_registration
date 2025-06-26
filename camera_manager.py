import cv2
import numpy as np

class CameraManager:
    def __init__(self, camera_id=0, dictionary=cv2.aruco.DICT_4X4_50):
        self.camera_id = camera_id
        self.cap = None
        self.camera_matrix = None
        self.dist_coeffs = None
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
        self.parameters = cv2.aruco.DetectorParameters()

    def connect(self):
        self.cap = cv2.VideoCapture(self.camera_id)
        return self.cap.isOpened()

    def disconnect(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def capture_frame(self):
        if not self.cap:
            return None
        ret, frame = self.cap.read()
        return frame if ret else None

    def load_calibration(self, file_path):
        try:
            data = np.load(file_path)
            self.camera_matrix = data["camera_matrix"]
            self.dist_coeffs = data["dist_coeffs"]
            return True
        except Exception as e:
            print(f"Failed to load calibration: {e}")
            return False

    def detect_marker_pose(self, image, marker_length):
        if self.camera_matrix is None or self.dist_coeffs is None:
            raise ValueError("Camera not calibrated")

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