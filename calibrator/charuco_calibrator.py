# charuco_calibrator.py

import numpy as np
from typing import List, Optional, Tuple
from board_manager import CharucoBoardManager
from calibration_strategy import CalibrationStrategy


class CharucoCalibrator:
    def __init__(self, board_manager: CharucoBoardManager, calibration_strategy: CalibrationStrategy):
        self.board_manager = board_manager
        self.calibration_strategy = calibration_strategy
        self.corners: List[np.ndarray] = []
        self.ids: List[np.ndarray] = []
        self.image_size: Optional[Tuple[int, int]] = None
        self.K = None
        self.D = None
        self.rvecs = None
        self.tvecs = None
        self.error = None

    def add_image(self, image: np.ndarray, min_markers: int = 6) -> bool:
        if self.image_size is None:
            self.image_size = image.shape[:2][::-1]  # width, height

        corners, ids = self.board_manager.detect(image)
        if corners is not None and len(corners) >= min_markers:
            self.corners.append(corners)
            self.ids.append(ids)
            return True
        return False

    def calibrate(self) -> bool:
        if len(self.corners) < 4:
            print("Not enough valid images for calibration")
            return False

        success, self.error, self.K, self.D, self.rvecs, self.tvecs = self.calibration_strategy.calibrate(
            self.corners, self.ids, self.board_manager.get_board(), self.image_size
        )
        return success

    def get_results(self):
        return self.K, self.D, self.error

    def save_calibration(self, filename: str):
        if self.K is None or self.D is None:
            raise ValueError("Calibration data is not available to save.")

        np.savez(
            filename,
            camera_matrix=self.K,
            dist_coeffs=self.D,
            image_size=self.image_size,
            calibration_error=self.error
        )
        print(f"Calibration data saved to: {filename}")

    def load_calibration(self, filename: str):
        data = np.load(filename)
        self.K = data["camera_matrix"]
        self.D = data["dist_coeffs"]
        self.image_size = tuple(data["image_size"])
        self.error = float(data["calibration_error"])
        print(f"Calibration data loaded from: {filename}")
