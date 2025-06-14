import cv2
import numpy as np
import math
import os
import json

from charuco_calibration import CharucoCalibrator

class FiducialDetector:
    def __init__(self, camera_index=0, dictionary_type=cv2.aruco.DICT_6X6_250, marker_size=0.05, camera_matrix=None, dist_coeffs=None):
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            raise IOError(f"No se pudo abrir la cámara en el índice {camera_index}. Asegúrate de que esté conectada y no usada por otra aplicación.")

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_type)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        self.marker_size = marker_size

        if camera_matrix is not None and camera_matrix.shape == (3, 3):
            self.camera_matrix = camera_matrix.astype(np.float32)
        else:
            print("Advertencia: matriz de cámara inválida. Usando valores predeterminados.")
            self.camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)

        if dist_coeffs is not None and dist_coeffs.shape[0] >= 4:
            self.dist_coeffs = dist_coeffs.astype(np.float32)
        else:
            print("Advertencia: coeficientes de distorsión inválidos. Usando cero.")
            self.dist_coeffs = np.zeros((4, 1), dtype=np.float32)

    def detect_markers(self, frame):
        if frame is None:
            print("Frame vacío recibido en detect_markers.")
            return None, None, None, None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = self.detector.detectMarkers(gray)
        angle = None

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

            rvecs, tvecs = [], []
            object_points = np.array([
                [-self.marker_size / 2, self.marker_size / 2, 0],
                [self.marker_size / 2, self.marker_size / 2, 0],
                [self.marker_size / 2, -self.marker_size / 2, 0],
                [-self.marker_size / 2, -self.marker_size / 2, 0]
            ], dtype=np.float32)

            for corner in corners:
                try:
                    success, rvec, tvec = cv2.solvePnP(
                        object_points, corner[0], self.camera_matrix, self.dist_coeffs
                    )
                    if success:
                        rvecs.append(rvec)
                        tvecs.append(tvec)
                    else:
                        rvecs.append(None)
                        tvecs.append(None)
                except Exception as e:
                    print(f"Pose estimation failed: {e}")
                    rvecs.append(None)
                    tvecs.append(None)

            for i in range(len(ids)):
                marker_center = np.mean(corners[i][0], axis=0).astype(int)

                if i < len(rvecs) and rvecs[i] is not None and tvecs[i] is not None:
                    try:
                        cv2.drawFrameAxes(frame, self.camera_matrix, self.dist_coeffs,
                                          rvecs[i], tvecs[i], 0.03)
                        distance = np.linalg.norm(tvecs[i])
                        cv2.putText(frame, f"Dist: {distance:.2f}m",
                                    (marker_center[0] - 30, marker_center[1] + 20),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                    except Exception:
                        pass

                pt1, pt2 = corners[i][0][0], corners[i][0][1]
                dx, dy = pt2[0] - pt1[0], pt2[1] - pt1[1]
                angle = math.degrees(math.atan2(dy, dx))
                cv2.putText(frame, f"Rot: {angle:.1f} deg",
                            (marker_center[0] - 30, marker_center[1] + 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

                cv2.putText(frame, f"ID: {ids[i][0]}",
                            (marker_center[0] - 20, marker_center[1] - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        return corners, ids, frame, angle

    def set_marker_size(self, size_meters):
        self.marker_size = size_meters
        print(f"Marker size updated to {size_meters}m ({size_meters * 100:.1f}cm)")

    def get_marker_size_info(self):
        return {
            'meters': self.marker_size,
            'centimeters': self.marker_size * 100,
            'millimeters': self.marker_size * 1000,
            'inches': self.marker_size * 39.3701
        }

    def run_detection(self):
        size_info = self.get_marker_size_info()
        print("Starting fiducial detection...")
        print(f"Current marker size: {size_info['centimeters']:.1f}cm ({size_info['meters']:.3f}m)")
        print("Controls:")
        print("  'q' - quit")
        print("  's' - save current frame")
        print("  '+' - increase marker size by 0.5cm")
        print("  '-' - decrease marker size by 0.5cm")
        print("  'r' - reset marker size to 5cm")
        print("  'i' - show current marker size info")

        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to capture frame")
                break

            corners, ids, annotated_frame, angle = self.detect_markers(frame)

            if annotated_frame is None:
                annotated_frame = frame.copy()
            if corners is None:
                corners = []
            if ids is None:
                ids = []

            if ids is not None and len(ids) > 0:
                detection_text = f"Detected: {len(ids)} markers"
                cv2.putText(annotated_frame, detection_text, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

                for i, marker_id in enumerate(ids):
                    if i < len(corners):
                        center = np.mean(corners[i][0], axis=0)
                        print(f"Marker {marker_id[0]}: Center at ({center[0]:.1f}, {center[1]:.1f}), Rot: {angle:.1f}")

            size_text = f"Marker size: {self.marker_size * 100:.1f}cm"
            cv2.putText(annotated_frame, size_text, (10, annotated_frame.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            cv2.imshow('Fiducial Detection', annotated_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                cv2.imwrite('fiducial_detection.jpg', annotated_frame)
                print("Frame saved as 'fiducial_detection.jpg'")
            elif key == ord('+') or key == ord('='):
                self.set_marker_size(self.marker_size + 0.005)
            elif key == ord('-'):
                new_size = max(0.005, self.marker_size - 0.005)
                self.set_marker_size(new_size)
            elif key == ord('r'):
                self.set_marker_size(0.05)
            elif key == ord('i'):
                info = self.get_marker_size_info()
                print(f"\nCurrent marker size:")
                print(f"  {info['meters']:.3f} meters")
                print(f"  {info['centimeters']:.1f} centimeters")
                print(f"  {info['millimeters']:.0f} millimeters")
                print(f"  {info['inches']:.2f} inches")


    def __del__(self):
        if hasattr(self, 'cap'):
            self.cap.release()
        cv2.destroyAllWindows()


def generate_aruco_marker(marker_id, marker_size=200, dictionary_type=cv2.aruco.DICT_6X6_250, save_path='data'):
    os.makedirs(save_path, exist_ok=True)
    aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_type)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size)

    filename = f"aruco_marker_{marker_id}.png"
    cv2.imwrite(os.path.join(save_path, filename), marker_img)
    print(f"Generated marker {marker_id} saved as '{filename}'")

    return marker_img


if __name__ == "__main__":
    aruco_input = input("\nQuieres crear marcadores aruco? (s/n)")
    if aruco_input.lower() == 's':
        print("Generating test ArUco markers...")
        for i in range(4):
            generate_aruco_marker(i)

    calibrator = CharucoCalibrator()

    camera_matrix, dist_coeffs = calibrator.load_calibration()

    print("\nPrint the generated markers and chessboard, then measure their size.")
    print("The generated markers are 200x200 pixels.")
    print("Measure the actual printed size and input it below.")

    while True:
        try:
            size_input = input("\nEnter marker size in cm (default: 5.0): ").strip()
            if not size_input:
                marker_size = 0.05
                break
            else:
                marker_size = float(size_input) / 100.0
                if marker_size > 0:
                    break
                else:
                    print("Size must be positive!")
        except ValueError:
            print("Please enter a valid number!")

    print(f"Using marker size: {marker_size * 100:.1f}cm")
    input("Press Enter when ready to start detection...")

    detector = FiducialDetector(marker_size=marker_size, camera_matrix=camera_matrix, dist_coeffs=dist_coeffs)

    try:
        detector.run_detection()
    except KeyboardInterrupt:
        print("\nDetection stopped by user")
    finally:
        del detector
