import cv2
import numpy as np
import glob
import os
from typing import Tuple, List, Optional


class FisheyeCalibrator:
    def __init__(self, pattern_size: Tuple[int, int] = (9, 6), square_size: float = 1.0):
        """
        Initialize fisheye camera calibrator.

        Args:
            pattern_size: (width, height) of checkerboard pattern (inner corners)
            square_size: Size of each square in the checkerboard (in mm or any unit)
        """
        self.pattern_size = pattern_size
        self.square_size = square_size
        self.calibration_flags = (
                cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC +
                cv2.fisheye.CALIB_CHECK_COND +
                cv2.fisheye.CALIB_FIX_SKEW
        )

        # Prepare object points
        self.objp = np.zeros((1, pattern_size[0] * pattern_size[1], 3), np.float32)
        self.objp[0, :, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
        self.objp *= square_size

        # Storage for calibration data
        self.objpoints = []  # 3D points in real world space
        self.imgpoints = []  # 2D points in image plane
        self.image_size = None

        # Calibration results
        self.camera_matrix = None
        self.dist_coeffs = None
        self.rvecs = None
        self.tvecs = None
        self.calibration_error = None

    def add_calibration_image(self, image_path: str) -> bool:
        """
        Add a single calibration image.

        Args:
            image_path: Path to the calibration image

        Returns:
            True if corners were found and added successfully
        """
        img = cv2.imread(image_path)
        if img is None:
            print(f"Could not load image: {image_path}")
            return False

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if self.image_size is None:
            self.image_size = gray.shape[::-1]

        # Find chessboard corners
        ret, corners = cv2.findChessboardCorners(
            gray, self.pattern_size,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        if ret:
            # Refine corner positions
            corners = cv2.cornerSubPix(
                gray, corners, (3, 3), (-1, -1),
                criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
            )

            self.objpoints.append(self.objp)
            self.imgpoints.append(corners)
            print(f"Added calibration image: {os.path.basename(image_path)}")
            return True
        else:
            print(f"Could not find corners in: {os.path.basename(image_path)}")
            return False

    def add_calibration_images(self, image_folder: str, pattern: str = "*.jpg") -> int:
        """
        Add multiple calibration images from a folder.

        Args:
            image_folder: Path to folder containing calibration images
            pattern: File pattern to match (e.g., "*.jpg", "*.png")

        Returns:
            Number of images successfully added
        """
        image_paths = glob.glob(os.path.join(image_folder, pattern))
        added_count = 0

        for image_path in image_paths:
            if self.add_calibration_image(image_path):
                added_count += 1

        print(f"Successfully added {added_count} out of {len(image_paths)} images")
        return added_count

    def calibrate(self) -> bool:
        """
        Perform fisheye camera calibration.

        Returns:
            True if calibration was successful
        """
        if len(self.objpoints) < 4:
            print("Error: Need at least 4 calibration images")
            return False

        print(f"Calibrating with {len(self.objpoints)} images...")

        # Initialize camera matrix and distortion coefficients
        K = np.zeros((3, 3))
        D = np.zeros((4, 1))

        try:
            # Perform fisheye calibration
            self.calibration_error, self.camera_matrix, self.dist_coeffs, self.rvecs, self.tvecs = cv2.fisheye.calibrate(
                self.objpoints, self.imgpoints, self.image_size, K, D,
                flags=self.calibration_flags,
                criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)
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
        Undistort a fisheye image using calibration results.

        Args:
            image_path: Path to the fisheye image
            output_path: Optional path to save undistorted image
            balance: Balance parameter (0=retain all pixels, 1=no black pixels)
            fov_scale: FOV scaling factor

        Returns:
            Undistorted image
        """
        if self.camera_matrix is None:
            raise ValueError("Camera not calibrated yet")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")

        h, w = img.shape[:2]

        # Generate new camera matrix
        new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
            self.camera_matrix, self.dist_coeffs, (w, h), np.eye(3), balance=balance, fov_scale=fov_scale
        )

        # Generate undistortion maps
        map1, map2 = cv2.fisheye.initUndistortRectifyMap(
            self.camera_matrix, self.dist_coeffs, np.eye(3), new_K, (w, h), cv2.CV_16SC2
        )

        # Apply undistortion
        undistorted = cv2.remap(img, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

        if output_path:
            cv2.imwrite(output_path, undistorted)
            print(f"Undistorted image saved to: {output_path}")

        return undistorted

    def save_calibration(self, filename: str):
        """Save calibration results to file."""
        if self.camera_matrix is None:
            raise ValueError("No calibration data to save")

        np.savez(filename,
                 camera_matrix=self.camera_matrix,
                 dist_coeffs=self.dist_coeffs,
                 image_size=self.image_size,
                 calibration_error=self.calibration_error)
        print(f"Calibration data saved to: {filename}")

    def load_calibration(self, filename: str):
        """Load calibration results from file."""
        data = np.load(filename)
        self.camera_matrix = data['camera_matrix']
        self.dist_coeffs = data['dist_coeffs']
        self.image_size = tuple(data['image_size'])
        self.calibration_error = float(data['calibration_error'])
        print(f"Calibration data loaded from: {filename}")

    def visualize_corners(self, image_path: str, output_path: Optional[str] = None) -> np.ndarray:
        """
        Visualize detected corners on a calibration image.

        Args:
            image_path: Path to the calibration image
            output_path: Optional path to save visualization

        Returns:
            Image with corners drawn
        """
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        ret, corners = cv2.findChessboardCorners(
            gray, self.pattern_size,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        if ret:
            corners = cv2.cornerSubPix(
                gray, corners, (3, 3), (-1, -1),
                criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
            )
            cv2.drawChessboardCorners(img, self.pattern_size, corners, ret)

        if output_path:
            cv2.imwrite(output_path, img)

        return img


def main():
    """Example usage of the FisheyeCalibrator."""
    # Initialize calibrator
    # For a 9x6 checkerboard with 25mm squares
    calibrator = FisheyeCalibrator(pattern_size=(9, 6), square_size=25.0)

    # Add calibration images
    # Replace with your calibration images folder
    calibration_folder = "calibration_images"
    added_count = calibrator.add_calibration_images(calibration_folder, "*.jpg")

    if added_count > 0:
        # Perform calibration
        success = calibrator.calibrate()

        if success:
            # Save calibration results
            calibrator.save_calibration("fisheye_calibration.npz")

            # Undistort a test image
            test_image = "test_fisheye.jpg"
            if os.path.exists(test_image):
                undistorted = calibrator.undistort_image(test_image, "undistorted_output.jpg")
                print("Test image undistorted successfully")
    else:
        print("No calibration images found. Please check the image folder path.")


if __name__ == "__main__":
    main()