import cv2
import numpy as np
import math
import os
import json
import glob

from charuco_calibration import CharucoCalibrator
from fisheye_calibration import FisheyeCalibrator


class FiducialDetector:
    def __init__(self, camera_index=0, dictionary_type=cv2.aruco.DICT_6X6_250, marker_size=0.05,
                 camera_matrix=None, dist_coeffs=None, fisheye=False):
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            raise IOError(
                f"No se pudo abrir la cámara en el índice {camera_index}. Asegúrate de que esté conectada y no usada por otra aplicación.")

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_type)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        self.marker_size = marker_size
        self.fisheye = fisheye

        if camera_matrix is not None and camera_matrix.shape == (3, 3):
            self.camera_matrix = camera_matrix.astype(np.float32)
        else:
            print("Advertencia: matriz de cámara inválida. Usando valores predeterminados.")
            self.camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)

        if dist_coeffs is not None and len(dist_coeffs) >= 4:
            self.dist_coeffs = dist_coeffs.astype(np.float32)
        else:
            print("Advertencia: coeficientes de distorsión inválidos. Usando cero.")
            if fisheye:
                self.dist_coeffs = np.zeros((4, 1), dtype=np.float32)
            else:
                self.dist_coeffs = np.zeros((4, 1), dtype=np.float32)

    def undistort_frame(self, frame):
        """Undistort frame if using fisheye camera."""
        if not self.fisheye:
            return frame

        h, w = frame.shape[:2]

        # Generate new camera matrix for fisheye
        new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
            self.camera_matrix, self.dist_coeffs, (w, h), np.eye(3), balance=0.8
        )

        # Generate undistortion maps
        map1, map2 = cv2.fisheye.initUndistortRectifyMap(
            self.camera_matrix, self.dist_coeffs, np.eye(3), new_K, (w, h), cv2.CV_16SC2
        )

        # Apply undistortion
        undistorted = cv2.remap(frame, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

        # Update camera matrix for pose estimation
        self.undistort_camera_matrix = new_K
        return undistorted

    def detect_markers(self, frame):
        if frame is None:
            print("Frame vacío recibido en detect_markers.")
            return None, None, None, None

        # Undistort frame if fisheye
        if self.fisheye:
            frame = self.undistort_frame(frame)
            # Use undistorted camera matrix for pose estimation
            pose_camera_matrix = getattr(self, 'undistort_camera_matrix', self.camera_matrix)
            pose_dist_coeffs = np.zeros((4, 1), dtype=np.float32)  # No distortion after undistortion
        else:
            pose_camera_matrix = self.camera_matrix
            pose_dist_coeffs = self.dist_coeffs

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
                        object_points, corner[0], pose_camera_matrix, pose_dist_coeffs
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
                        cv2.drawFrameAxes(frame, pose_camera_matrix, pose_dist_coeffs,
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

        # Add fisheye indicator
        if self.fisheye:
            cv2.putText(frame, "FISHEYE MODE", (10, frame.shape[0] - 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

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
        if self.fisheye:
            print("Running in FISHEYE mode")
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


def find_latest_calibration_file(fisheye=False):
    """Find the most recent calibration file in the current directory."""
    if fisheye:
        calibration_files = glob.glob("fisheye_calibration*.npz")
    else:
        calibration_files = glob.glob("charuco_calibration*.npz")

    if calibration_files:
        # Sort by modification time, newest first
        calibration_files.sort(key=os.path.getmtime, reverse=True)
        return calibration_files[0]
    return None


def load_calibration_data(fisheye=False):
    """Load calibration data from file or use defaults."""
    calibration_file = find_latest_calibration_file(fisheye)

    if calibration_file:
        print(f"Found calibration file: {calibration_file}")
        try:
            if fisheye:
                calibrator = FisheyeCalibrator()
                calibrator.load_calibration(calibration_file)
                print("Fisheye calibration data loaded successfully!")
                return calibrator.camera_matrix, calibrator.dist_coeffs, True
            else:
                calibrator = CharucoCalibrator()
                calibrator.load_calibration(calibration_file)
                print("Charuco calibration data loaded successfully!")
                return calibrator.camera_matrix, calibrator.dist_coeffs, False
        except Exception as e:
            print(f"Error loading calibration file: {e}")
            print("Using default calibration parameters.")
    else:
        camera_type = "fisheye" if fisheye else "standard"
        print(f"No {camera_type} calibration file found. Using default parameters.")

    # Return default parameters if loading fails
    camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
    if fisheye:
        dist_coeffs = np.zeros((4, 1), dtype=np.float32)  # Fisheye uses 4 distortion coefficients
    else:
        dist_coeffs = np.zeros((4, 1), dtype=np.float32)
    return camera_matrix, dist_coeffs, fisheye


def run_fisheye_calibration_workflow(camera_id=0):
    """Run interactive fisheye calibration workflow."""
    print("\n" + "=" * 50)
    print("FISHEYE CALIBRATION WORKFLOW")
    print("=" * 50)

    # Get calibration parameters
    print("\nFisheye calibration requires a checkerboard pattern.")
    print("Default: 9x6 checkerboard with 25mm squares")

    try:
        width = int(input("Checkerboard width (inner corners) [9]: ") or "9")
        height = int(input("Checkerboard height (inner corners) [6]: ") or "6")
        square_size = float(input("Square size in mm [25.0]: ") or "25.0")
    except ValueError:
        print("Using default values: 9x6 checkerboard, 25mm squares")
        width, height, square_size = 9, 6, 25.0

    calibrator = FisheyeCalibrator(pattern_size=(width, height), square_size=square_size)

    # Live calibration
    print(f"\nStarting live fisheye calibration...")
    print("Instructions:")
    print("- Hold the checkerboard pattern in front of the camera")
    print("- Move it to different positions and angles")
    print("- Press SPACE when corners are detected to capture")
    print("- Press 'q' to finish calibration")
    print(f"- Target: capture at least 15 good images")

    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"Error: Could not open camera {camera_id}")
        return None

    captured_count = 0
    target_count = 15

    while captured_count < target_count:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ret_corners, corners = cv2.findChessboardCorners(
            gray, (width, height),
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        # Draw status
        status_color = (0, 255, 0) if ret_corners else (0, 0, 255)
        status_text = f"Corners: {'FOUND' if ret_corners else 'NOT FOUND'}"
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)
        cv2.putText(frame, f"Captured: {captured_count}/{target_count}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.putText(frame, "SPACE: capture, Q: finish", (10, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        if ret_corners:
            cv2.drawChessboardCorners(frame, (width, height), corners, ret_corners)

        cv2.imshow('Fisheye Calibration', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord(' ') and ret_corners:
            # Capture this frame for calibration
            temp_filename = f"temp_fisheye_calib_{captured_count}.jpg"
            cv2.imwrite(temp_filename, frame)

            if calibrator.add_calibration_image(temp_filename):
                captured_count += 1
                print(f"Captured image {captured_count}/{target_count}")

            # Clean up temp file
            os.remove(temp_filename)

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    if captured_count >= 4:
        print(f"\nPerforming fisheye calibration with {captured_count} images...")
        success = calibrator.calibrate()

        if success:
            # Save calibration
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"fisheye_calibration_{timestamp}.npz"
            calibrator.save_calibration(filename)

            print(f"Fisheye calibration completed successfully!")
            print(f"RMS error: {calibrator.calibration_error:.6f}")
            print(f"Saved to: {filename}")

            return calibrator.camera_matrix, calibrator.dist_coeffs
        else:
            print("Fisheye calibration failed!")
            return None
    else:
        print(f"Not enough images captured ({captured_count}). Need at least 4.")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("ArUco Fiducial Marker Detection System")
    print("Enhanced with Fisheye Camera Support")
    print("=" * 60)

    # Ask about creating ArUco markers
    aruco_input = input("\n¿Quieres crear marcadores ArUco? (s/n): ")
    if aruco_input.lower() == 's':
        print("Generating test ArUco markers...")
        for i in range(4):
            generate_aruco_marker(i)
        print("Markers generated in 'data' folder.")

    # Ask about camera type first
    print("\n" + "=" * 40)
    print("CAMERA TYPE SELECTION")
    print("=" * 40)
    print("1. Standard camera (pinhole model)")
    print("2. Fisheye camera (fisheye model)")

    camera_type_choice = input("\nSelect camera type (1/2) [1]: ").strip() or "1"
    use_fisheye = camera_type_choice == "2"

    if use_fisheye:
        print("Selected: Fisheye camera")
    else:
        print("Selected: Standard camera")

    # Ask about calibration
    print("\n" + "=" * 40)
    print("CALIBRATION OPTIONS")
    print("=" * 40)
    print("1. Use existing calibration file (if available)")
    print("2. Run new calibration")
    print("3. Skip calibration (use defaults)")

    choice = input("\nSelect option (1/2/3) [1]: ").strip() or "1"

    camera_matrix = None
    dist_coeffs = None
    fisheye_mode = use_fisheye

    if choice == "2":
        print("\nRunning new calibration...")

        # Ask about camera ID
        camera_id = int(input("Camera ID (0 for default): ") or "0")

        if use_fisheye:
            # Run fisheye calibration
            result = run_fisheye_calibration_workflow(camera_id)
            if result:
                camera_matrix, dist_coeffs = result
                fisheye_mode = True
                print("Fisheye calibration completed successfully!")
            else:
                print("Fisheye calibration failed, using default parameters.")
                camera_matrix, dist_coeffs, fisheye_mode = load_calibration_data(fisheye=use_fisheye)
        else:
            # Run standard charuco calibration
            calibrator = CharucoCalibrator()
            success = calibrator.live_calibration_workflow(camera_id, target_images=15)

            if success:
                camera_matrix = calibrator.camera_matrix
                dist_coeffs = calibrator.dist_coeffs
                fisheye_mode = False
                print("Standard calibration completed successfully!")
            else:
                print("Standard calibration failed, using default parameters.")
                camera_matrix, dist_coeffs, fisheye_mode = load_calibration_data(fisheye=use_fisheye)

    elif choice == "1":
        camera_matrix, dist_coeffs, fisheye_mode = load_calibration_data(fisheye=use_fisheye)

    else:  # choice == "3"
        print("Using default calibration parameters.")
        camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
        if use_fisheye:
            dist_coeffs = np.zeros((4, 1), dtype=np.float32)
        else:
            dist_coeffs = np.zeros((4, 1), dtype=np.float32)
        fisheye_mode = use_fisheye

    # Get marker size
    print("\n" + "=" * 40)
    print("MARKER SIZE CONFIGURATION")
    print("=" * 40)
    print("Print the generated markers and measure their actual size.")
    print("The generated markers are 200x200 pixels.")

    while True:
        try:
            size_input = input("\nEnter marker size in cm (default: 5.0): ").strip()
            if not size_input:
                marker_size = 0.05  # 5cm default
                break
            else:
                marker_size = float(size_input) / 100.0  # Convert cm to meters
                if marker_size > 0:
                    break
                else:
                    print("Size must be positive!")
        except ValueError:
            print("Please enter a valid number!")

    print(f"Using marker size: {marker_size * 100:.1f}cm")
    if fisheye_mode:
        print("Using FISHEYE camera model for detection")

    # Start detection
    print("\n" + "=" * 40)
    print("STARTING DETECTION")
    print("=" * 40)
    input("Press Enter when ready to start detection...")

    try:
        detector = FiducialDetector(
            marker_size=marker_size,
            camera_matrix=camera_matrix,
            dist_coeffs=dist_coeffs,
            fisheye=fisheye_mode
        )
        detector.run_detection()
    except KeyboardInterrupt:
        print("\nDetection stopped by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if 'detector' in locals():
            del detector
        cv2.destroyAllWindows()