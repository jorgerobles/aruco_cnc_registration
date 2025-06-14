import cv2
import numpy as np
import glob
import os
import time
from typing import Tuple, List, Optional, Union


class CharucoCalibrator:
    def __init__(self,
                 squares_x: int = 7,
                 squares_y: int = 5,
                 square_length: float = 0.04,
                 marker_length: float = 0.02,
                 dictionary: int = cv2.aruco.DICT_4X4_50,
                 fisheye: bool = False):
        """
        Initialize ChArUco camera calibrator.

        Args:
            squares_x: Number of squares in X direction
            squares_y: Number of squares in Y direction
            square_length: Length of each square (in meters)
            marker_length: Length of each ArUco marker (in meters)
            dictionary: ArUco dictionary to use
            fisheye: Whether to use fisheye camera model
        """
        self.squares_x = squares_x
        self.squares_y = squares_y
        self.square_length = square_length
        self.marker_length = marker_length
        self.fisheye = fisheye

        # Create ArUco dictionary and ChArUco board
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
        self.charuco_board = cv2.aruco.CharucoBoard(
            (squares_x, squares_y), square_length, marker_length, self.aruco_dict
        )

        # Detector parameters
        self.detector_params = cv2.aruco.DetectorParameters()
        self.detector_params.adaptiveThreshWinSizeMin = 3
        self.detector_params.adaptiveThreshWinSizeMax = 23
        self.detector_params.adaptiveThreshWinSizeStep = 10

        # Create detector
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.detector_params)

        # Storage for calibration data
        self.all_charuco_corners = []
        self.all_charuco_ids = []
        self.image_size = None

        # Calibration results
        self.camera_matrix = None
        self.dist_coeffs = None
        self.rvecs = None
        self.tvecs = None
        self.calibration_error = None

    def generate_board(self, output_path: str, image_size: Tuple[int, int] = (1200, 900)) -> np.ndarray:
        """
        Generate and save a ChArUco board image.

        Args:
            output_path: Path to save the board image
            image_size: Size of the output image (width, height)

        Returns:
            Generated board image
        """
        board_image = self.charuco_board.generateImage(image_size)
        cv2.imwrite(output_path, board_image)
        print(f"ChArUco board saved to: {output_path}")
        return board_image

    def detect_markers(self, image: np.ndarray, visualize: bool = False) -> Tuple[
        Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Detect ChArUco markers in an image.

        Args:
            image: Input image
            visualize: Whether to draw detected markers

        Returns:
            Tuple of (charuco_corners, charuco_ids)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Detect ArUco markers
        marker_corners, marker_ids, _ = self.detector.detectMarkers(gray)

        if len(marker_corners) == 0:
            return None, None

        # Interpolate ChArUco corners
        charuco_retval, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
            marker_corners, marker_ids, gray, self.charuco_board
        )

        if visualize and charuco_retval > 0:
            # Draw detected markers and corners
            cv2.aruco.drawDetectedMarkers(image, marker_corners, marker_ids)
            cv2.aruco.drawDetectedCornersCharuco(image, charuco_corners, charuco_ids)

        return charuco_corners if charuco_retval > 0 else None, charuco_ids if charuco_retval > 0 else None

    def add_calibration_image(self, image_path: str, min_markers: int = 6) -> bool:
        """
        Add a single calibration image.

        Args:
            image_path: Path to the calibration image
            min_markers: Minimum number of markers required

        Returns:
            True if enough markers were found and added successfully
        """
        image = cv2.imread(image_path)
        if image is None:
            print(f"Could not load image: {image_path}")
            return False

        if self.image_size is None:
            self.image_size = image.shape[:2][::-1]  # (width, height)

        charuco_corners, charuco_ids = self.detect_markers(image)

        if charuco_corners is not None and len(charuco_corners) >= min_markers:
            self.all_charuco_corners.append(charuco_corners)
            self.all_charuco_ids.append(charuco_ids)
            print(f"Added image: {os.path.basename(image_path)} ({len(charuco_corners)} corners)")
            return True
        else:
            detected = len(charuco_corners) if charuco_corners is not None else 0
            print(f"Insufficient markers in {os.path.basename(image_path)}: {detected}/{min_markers}")
            return False

    def add_calibration_images(self, image_folder: str, pattern: str = "*.jpg", min_markers: int = 6) -> int:
        """
        Add multiple calibration images from a folder.

        Args:
            image_folder: Path to folder containing calibration images
            pattern: File pattern to match
            min_markers: Minimum number of markers required per image

        Returns:
            Number of images successfully added
        """
        image_paths = glob.glob(os.path.join(image_folder, pattern))
        added_count = 0

        for image_path in sorted(image_paths):
            if self.add_calibration_image(image_path, min_markers):
                added_count += 1

        print(f"Successfully added {added_count} out of {len(image_paths)} images")
        return added_count

    def calibrate(self) -> bool:
        """
        Perform camera calibration using ChArUco board.

        Returns:
            True if calibration was successful
        """
        if len(self.all_charuco_corners) < 4:
            print("Error: Need at least 4 calibration images with sufficient markers")
            return False

        print(
            f"Calibrating {'fisheye' if self.fisheye else 'standard'} camera with {len(self.all_charuco_corners)} images...")

        try:
            if self.fisheye:
                # Fisheye calibration
                calibration_flags = (
                        cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC +
                        cv2.fisheye.CALIB_CHECK_COND +
                        cv2.fisheye.CALIB_FIX_SKEW
                )

                # Convert ChArUco corners to object points
                obj_points = []
                img_points = []

                for corners, ids in zip(self.all_charuco_corners, self.all_charuco_ids):
                    obj_pts = self.charuco_board.getChessboardCorners()[ids.flatten()]
                    obj_points.append(obj_pts.reshape(-1, 1, 3))
                    img_points.append(corners)

                # Initialize camera matrix and distortion coefficients
                K = np.zeros((3, 3))
                D = np.zeros((4, 1))

                self.calibration_error, self.camera_matrix, self.dist_coeffs, self.rvecs, self.tvecs = cv2.fisheye.calibrate(
                    obj_points, img_points, self.image_size, K, D,
                    flags=calibration_flags,
                    criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)
                )

            else:
                # Standard calibration
                self.calibration_error, self.camera_matrix, self.dist_coeffs, self.rvecs, self.tvecs = cv2.aruco.calibrateCameraCharuco(
                    self.all_charuco_corners, self.all_charuco_ids, self.charuco_board,
                    self.image_size, None, None
                )

            print(f"Calibration successful!")
            print(f"RMS error: {self.calibration_error:.6f}")
            print(f"Camera matrix:\n{self.camera_matrix}")
            print(f"Distortion coefficients: {self.dist_coeffs.ravel()}")

            return True

        except cv2.error as e:
            print(f"Calibration failed: {e}")
            return False

    def undistort_image(self, image_path: str, output_path: Optional[str] = None,
                        balance: float = 1.0, fov_scale: float = 1.0) -> np.ndarray:
        """
        Undistort an image using calibration results.

        Args:
            image_path: Path to the input image
            output_path: Optional path to save undistorted image
            balance: Balance parameter for fisheye (0=retain all pixels, 1=no black pixels)
            fov_scale: FOV scaling factor for fisheye

        Returns:
            Undistorted image
        """
        if self.camera_matrix is None:
            raise ValueError("Camera not calibrated yet")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")

        h, w = img.shape[:2]

        if self.fisheye:
            # Fisheye undistortion
            new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                self.camera_matrix, self.dist_coeffs, (w, h), np.eye(3),
                balance=balance, fov_scale=fov_scale
            )

            map1, map2 = cv2.fisheye.initUndistortRectifyMap(
                self.camera_matrix, self.dist_coeffs, np.eye(3), new_K, (w, h), cv2.CV_16SC2
            )
        else:
            # Standard undistortion
            new_K, roi = cv2.getOptimalNewCameraMatrix(
                self.camera_matrix, self.dist_coeffs, (w, h), 1, (w, h)
            )

            map1, map2 = cv2.initUndistortRectifyMap(
                self.camera_matrix, self.dist_coeffs, None, new_K, (w, h), cv2.CV_16SC2
            )

        # Apply undistortion
        undistorted = cv2.remap(img, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

        if output_path:
            cv2.imwrite(output_path, undistorted)
            print(f"Undistorted image saved to: {output_path}")

        return undistorted

    def estimate_pose(self, image: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Estimate pose of ChArUco board in image.

        Args:
            image: Input image

        Returns:
            Tuple of (rotation_vector, translation_vector) or (None, None) if failed
        """
        if self.camera_matrix is None:
            raise ValueError("Camera not calibrated yet")

        charuco_corners, charuco_ids = self.detect_markers(image)

        if charuco_corners is not None and len(charuco_corners) >= 4:
            if self.fisheye:
                # For fisheye, we need to use solvePnP with object points
                obj_pts = self.charuco_board.getChessboardCorners()[charuco_ids.flatten()]
                success, rvec, tvec = cv2.solvePnP(
                    obj_pts, charuco_corners, self.camera_matrix, self.dist_coeffs
                )
            else:
                success, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(
                    charuco_corners, charuco_ids, self.charuco_board,
                    self.camera_matrix, self.dist_coeffs, None, None
                )

            return (rvec, tvec) if success else (None, None)

        return None, None

    def draw_axis(self, image: np.ndarray, length: float = 0.1) -> np.ndarray:
        """
        Draw coordinate axis on image if board is detected.

        Args:
            image: Input image
            length: Length of axis arrows

        Returns:
            Image with axis drawn
        """
        rvec, tvec = self.estimate_pose(image)

        if rvec is not None and tvec is not None:
            if self.fisheye:
                # Use cv2.projectPoints for fisheye
                axis_points = np.array([
                    [0, 0, 0],
                    [length, 0, 0],
                    [0, length, 0],
                    [0, 0, -length]
                ], dtype=np.float64).reshape(-1, 1, 3)

                img_points, _ = cv2.fisheye.projectPoints(
                    axis_points, rvec, tvec, self.camera_matrix, self.dist_coeffs
                )
                img_points = img_points.reshape(-1, 2).astype(int)
            else:
                img_points, _ = cv2.projectPoints(
                    np.float32([[0, 0, 0], [length, 0, 0], [0, length, 0], [0, 0, -length]]).reshape(-1, 3),
                    rvec, tvec, self.camera_matrix, self.dist_coeffs
                )
                img_points = img_points.reshape(-1, 2).astype(int)

            # Draw axis
            corner = tuple(img_points[0])
            cv2.line(image, corner, tuple(img_points[1]), (0, 0, 255), 5)  # X - Red
            cv2.line(image, corner, tuple(img_points[2]), (0, 255, 0), 5)  # Y - Green
            cv2.line(image, corner, tuple(img_points[3]), (255, 0, 0), 5)  # Z - Blue

        return image

    def save_calibration(self, filename: str):
        """Save calibration results to file."""
        if self.camera_matrix is None:
            raise ValueError("No calibration data to save")

        np.savez(filename,
                 camera_matrix=self.camera_matrix,
                 dist_coeffs=self.dist_coeffs,
                 image_size=self.image_size,
                 calibration_error=self.calibration_error,
                 fisheye=self.fisheye,
                 squares_x=self.squares_x,
                 squares_y=self.squares_y,
                 square_length=self.square_length,
                 marker_length=self.marker_length)
        print(f"Calibration data saved to: {filename}")

    def load_calibration(self, filename: str):
        """Load calibration results from file."""
        data = np.load(filename)
        self.camera_matrix = data['camera_matrix']
        self.dist_coeffs = data['dist_coeffs']
        self.image_size = tuple(data['image_size'])
        self.calibration_error = float(data['calibration_error'])
        self.fisheye = bool(data['fisheye'])
        print(f"Calibration data loaded from: {filename}")

    def visualize_detection(self, image_path: str, output_path: Optional[str] = None) -> np.ndarray:
        """
        Visualize ChArUco detection on an image.

        Args:
            image_path: Path to the input image
            output_path: Optional path to save visualization

        Returns:
            Image with detections drawn
        """
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")

        # Detect and draw markers
        self.detect_markers(image, visualize=True)

        # Draw coordinate axis if calibrated
        if self.camera_matrix is not None:
            image = self.draw_axis(image)

        if output_path:
            cv2.imwrite(output_path, image)

        return image

    def capture_calibration_data(self,
                                 camera_id: int = 0,
                                 output_folder: str = "charuco_captures",
                                 target_images: int = 15,
                                 min_markers: int = 6,
                                 capture_delay: float = 2.0) -> int:
        """
        Interactive capture of calibration images with live feedback.

        Args:
            camera_id: Camera device ID (0 for default camera)
            output_folder: Folder to save captured images
            target_images: Target number of calibration images
            min_markers: Minimum markers required to accept an image
            capture_delay: Minimum delay between captures (seconds)

        Returns:
            Number of images successfully captured
        """
        # Create output folder
        os.makedirs(output_folder, exist_ok=True)

        # Initialize camera
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            print(f"Error: Could not open camera {camera_id}")
            return 0

        # Set camera properties
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)

        captured_count = 0
        last_capture_time = 0
        capture_quality_history = []

        print(f"\n=== ChArUco Calibration Capture ===")
        print(f"Target: {target_images} images")
        print(f"Minimum markers per image: {min_markers}")
        print("\nControls:")
        print("  SPACE - Capture image (when ready)")
        print("  'a' - Auto-capture mode toggle")
        print("  'q' - Quit")
        print("  'r' - Reset capture count")
        print("  's' - Save current frame")

        auto_capture = False

        while captured_count < target_images:
            ret, frame = cap.read()
            if not ret:
                print("Error reading from camera")
                break

            display_frame = frame.copy()

            # Detect ChArUco markers
            charuco_corners, charuco_ids = self.detect_markers(display_frame, visualize=True)

            # Calculate quality metrics
            marker_count = len(charuco_corners) if charuco_corners is not None else 0
            coverage_score = self._calculate_coverage_score(charuco_corners,
                                                            display_frame.shape) if charuco_corners is not None else 0

            # Determine capture readiness
            is_ready = marker_count >= min_markers and coverage_score > 0.3
            current_time = time.time()
            can_capture = (current_time - last_capture_time) > capture_delay

            # Draw status information
            self._draw_capture_status(display_frame, captured_count, target_images,
                                      marker_count, min_markers, coverage_score,
                                      is_ready and can_capture, auto_capture)

            # Auto-capture logic
            if auto_capture and is_ready and can_capture:
                # Check if this pose is sufficiently different from previous captures
                if self._is_pose_diverse(charuco_corners, capture_quality_history):
                    filename = os.path.join(output_folder, f"capture_{captured_count:03d}.jpg")
                    cv2.imwrite(filename, frame)

                    capture_quality_history.append({
                        'corners': charuco_corners.copy() if charuco_corners is not None else None,
                        'coverage': coverage_score,
                        'marker_count': marker_count
                    })

                    captured_count += 1
                    last_capture_time = current_time
                    print(f"Auto-captured image {captured_count}/{target_images} - Quality: {coverage_score:.2f}")

            cv2.imshow('ChArUco Calibration Capture', display_frame)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' ') and is_ready and can_capture:  # Space bar - manual capture
                filename = os.path.join(output_folder, f"capture_{captured_count:03d}.jpg")
                cv2.imwrite(filename, frame)

                capture_quality_history.append({
                    'corners': charuco_corners.copy() if charuco_corners is not None else None,
                    'coverage': coverage_score,
                    'marker_count': marker_count
                })

                captured_count += 1
                last_capture_time = current_time
                print(f"Captured image {captured_count}/{target_images} - Quality: {coverage_score:.2f}")

            elif key == ord('a'):  # Toggle auto-capture
                auto_capture = not auto_capture
                print(f"Auto-capture: {'ON' if auto_capture else 'OFF'}")

            elif key == ord('r'):  # Reset
                captured_count = 0
                capture_quality_history = []
                print("Capture count reset")

            elif key == ord('s'):  # Save current frame
                filename = os.path.join(output_folder, f"manual_save_{int(time.time())}.jpg")
                cv2.imwrite(filename, frame)
                print(f"Saved current frame to {filename}")

        cap.release()
        cv2.destroyAllWindows()

        print(f"\nCapture session completed: {captured_count} images saved to '{output_folder}'")
        return captured_count

    def _calculate_coverage_score(self, corners: np.ndarray, image_shape: Tuple[int, int, int]) -> float:
        """Calculate how well the corners cover the image area."""
        if corners is None or len(corners) < 4:
            return 0.0

        h, w = image_shape[:2]

        # Find bounding box of detected corners
        x_coords = corners[:, 0, 0]
        y_coords = corners[:, 0, 1]

        min_x, max_x = np.min(x_coords), np.max(x_coords)
        min_y, max_y = np.min(y_coords), np.max(y_coords)

        # Calculate coverage as fraction of image area
        coverage_area = (max_x - min_x) * (max_y - min_y)
        image_area = w * h

        return min(coverage_area / image_area, 1.0)

    def _is_pose_diverse(self, current_corners: np.ndarray, history: List[dict],
                         min_distance_threshold: float = 50.0) -> bool:
        """Check if current pose is sufficiently different from previous captures."""
        if not history or current_corners is None:
            return True

        # Calculate center of current corners
        current_center = np.mean(current_corners[:, 0, :], axis=0)

        for prev_capture in history[-5:]:  # Check last 5 captures
            if prev_capture['corners'] is None:
                continue

            prev_center = np.mean(prev_capture['corners'][:, 0, :], axis=0)
            distance = np.linalg.norm(current_center - prev_center)

            if distance < min_distance_threshold:
                return False

        return True

    def _draw_capture_status(self, image: np.ndarray, captured: int, target: int,
                             markers: int, min_markers: int, coverage: float,
                             ready: bool, auto_mode: bool):
        """Draw capture status overlay on image."""
        h, w = image.shape[:2]

        # Status panel background
        cv2.rectangle(image, (10, 10), (400, 150), (0, 0, 0), -1)
        cv2.rectangle(image, (10, 10), (400, 150), (255, 255, 255), 2)

        # Progress bar
        progress = captured / target
        bar_width = 300
        bar_height = 20
        cv2.rectangle(image, (50, 120), (50 + bar_width, 120 + bar_height), (100, 100, 100), -1)
        cv2.rectangle(image, (50, 120), (50 + int(bar_width * progress), 120 + bar_height), (0, 255, 0), -1)

        # Status text
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6

        # Progress
        cv2.putText(image, f"Progress: {captured}/{target}", (20, 35), font, font_scale, (255, 255, 255), 2)

        # Markers detected
        marker_color = (0, 255, 0) if markers >= min_markers else (0, 0, 255)
        cv2.putText(image, f"Markers: {markers}/{min_markers}", (20, 55), font, font_scale, marker_color, 2)

        # Coverage score
        coverage_color = (0, 255, 0) if coverage > 0.3 else (0, 255, 255) if coverage > 0.1 else (0, 0, 255)
        cv2.putText(image, f"Coverage: {coverage:.1%}", (20, 75), font, font_scale, coverage_color, 2)

        # Ready status
        status_text = "READY" if ready else "NOT READY"
        status_color = (0, 255, 0) if ready else (0, 0, 255)
        cv2.putText(image, status_text, (200, 55), font, font_scale, status_color, 2)

        # Auto mode indicator
        if auto_mode:
            cv2.putText(image, "AUTO", (200, 75), font, font_scale, (255, 255, 0), 2)

        # Instructions
        if ready:
            cv2.putText(image, "Press SPACE to capture", (20, h - 20), font, 0.5, (0, 255, 0), 1)
        else:
            cv2.putText(image, "Position board for better detection", (20, h - 20), font, 0.5, (0, 255, 255), 1)

    def live_calibration_workflow(self, camera_id: int = 0, target_images: int = 15) -> bool:
        """
        Complete live calibration workflow with capture and calibration.

        Args:
            camera_id: Camera device ID
            target_images: Target number of calibration images

        Returns:
            True if calibration was successful
        """
        print("=== Live ChArUco Calibration Workflow ===")

        # Step 1: Generate board if it doesn't exist
        board_path = "data/charuco_board.png"
        if not os.path.exists(board_path):
            print("Generating ChArUco board...")
            self.generate_board(board_path, (1200, 900))
            print(f"Board saved to {board_path}")
            print("Print this board and press Enter to continue...")
            input()

        # Step 2: Capture calibration images
        output_folder = f"charuco_captures_{int(time.time())}"
        captured_count = self.capture_calibration_data(
            camera_id=camera_id,
            output_folder=output_folder,
            target_images=target_images
        )

        if captured_count < 4:
            print(f"Insufficient images captured ({captured_count}). Need at least 4 for calibration.")
            return False

        # Step 3: Load captured images and calibrate
        print("\nLoading captured images for calibration...")
        added_count = self.add_calibration_images(output_folder, "*.jpg")

        if added_count >= 4:
            print("Performing calibration...")
            success = self.calibrate()

            if success:
                # Save calibration
                cal_filename = f"charuco_calibration_{'fisheye' if self.fisheye else 'standard'}_{int(time.time())}.npz"
                self.save_calibration(cal_filename)
                print(f"Calibration saved to {cal_filename}")

                # Test with live camera
                print("\nTesting calibration with live camera...")
                self.live_undistortion_demo(camera_id)

                return True
            else:
                print("Calibration failed!")
                return False
        else:
            print("Not enough valid images for calibration")
            return False

    def live_undistortion_demo(self, camera_id: int = 0):
        """
        Live demonstration of undistortion with pose estimation.

        Args:
            camera_id: Camera device ID
        """
        if self.camera_matrix is None:
            print("No calibration data available")
            return

        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            print(f"Error: Could not open camera {camera_id}")
            return

        print("\nLive Undistortion Demo")
        print("Controls: 'q' - quit, 't' - toggle undistortion, 'p' - toggle pose")

        show_undistorted = True
        show_pose = True

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if show_undistorted:
                # Create undistortion maps if not cached
                if not hasattr(self, '_undist_map1'):
                    h, w = frame.shape[:2]
                    if self.fisheye:
                        new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                            self.camera_matrix, self.dist_coeffs, (w, h), np.eye(3), balance=1.0
                        )
                        self._undist_map1, self._undist_map2 = cv2.fisheye.initUndistortRectifyMap(
                            self.camera_matrix, self.dist_coeffs, np.eye(3), new_K, (w, h), cv2.CV_16SC2
                        )
                    else:
                        new_K, _ = cv2.getOptimalNewCameraMatrix(
                            self.camera_matrix, self.dist_coeffs, (w, h), 1, (w, h)
                        )
                        self._undist_map1, self._undist_map2 = cv2.initUndistortRectifyMap(
                            self.camera_matrix, self.dist_coeffs, None, new_K, (w, h), cv2.CV_16SC2
                        )

                display_frame = cv2.remap(frame, self._undist_map1, self._undist_map2,
                                          cv2.INTER_LINEAR, cv2.BORDER_CONSTANT)
                window_title = "Undistorted View"
            else:
                display_frame = frame.copy()
                window_title = "Original View"

            # Show pose estimation
            if show_pose:
                display_frame = self.draw_axis(display_frame, length=0.05)
                charuco_corners, charuco_ids = self.detect_markers(display_frame, visualize=True)

            # Add status text
            status_text = f"Undistorted: {show_undistorted} | Pose: {show_pose}"
            cv2.putText(display_frame, status_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow(window_title, display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('t'):
                show_undistorted = not show_undistorted
                # Clear cached maps when switching
                if hasattr(self, '_undist_map1'):
                    delattr(self, '_undist_map1')
                    delattr(self, '_undist_map2')
            elif key == ord('p'):
                show_pose = not show_pose

        cap.release()
        cv2.destroyAllWindows()


def main():
    """Example usage with live capture workflow."""

    print("ChArUco Camera Calibration with Live Capture")
    print("=" * 50)

    # Choose camera type
    camera_type = input("Camera type - (s)tandard or (f)isheye? [s]: ").lower() or 's'
    fisheye_mode = camera_type.startswith('f')

    # Choose camera
    camera_id = int(input("Camera ID (0 for default): ") or "0")

    # Choose workflow
    workflow = input("Workflow - (l)ive capture+calibration or (e)xisting images? [l]: ").lower() or 'l'

    # Create calibrator
    calibrator = CharucoCalibrator(
        squares_x=10, squares_y=7,
        square_length=0.015,  # 4cm squares
        marker_length=0.011,  # 2cm markers
        fisheye=fisheye_mode
    )

    if workflow.startswith('l'):
        # Live capture and calibration workflow
        target_images = int(input("Number of calibration images to capture [15]: ") or "15")
        success = calibrator.live_calibration_workflow(camera_id, target_images)

        if success:
            print("Calibration completed successfully!")
        else:
            print("Calibration failed or was cancelled.")

    else:
        # Existing images workflow
        print("\n=== Using Existing Images ===")

        # Generate board if needed
        board_path = "data/charuco_board.png"
        if not os.path.exists(board_path):
            calibrator.generate_board(board_path, (1200, 900))
            print(f"ChArUco board saved to: {board_path}")

        # Load images from folder
        image_folder = input("Path to calibration images folder: ")
        if os.path.exists(image_folder):
            added_count = calibrator.add_calibration_images(image_folder, "*.jpg")

            if added_count >= 4:
                if calibrator.calibrate():
                    cal_filename = f"charuco_calibration_{'fisheye' if fisheye_mode else 'standard'}.npz"
                    calibrator.save_calibration(cal_filename)
                    print(f"Calibration saved to: {cal_filename}")

                    # Offer live demo
                    demo = input("Run live undistortion demo? [y]: ").lower() or 'y'
                    if demo.startswith('y'):
                        calibrator.live_undistortion_demo(camera_id)
            else:
                print(f"Not enough valid images found ({added_count})")
        else:
            print("Image folder not found")


if __name__ == "__main__":
    main()