# calibration_strategy.py

import cv2
import numpy as np
from typing import List, Tuple


class CalibrationStrategy:
    def calibrate(self,
                  corners: List[np.ndarray],
                  ids: List[np.ndarray],
                  board,
                  image_size: Tuple[int, int]
                  ) -> Tuple[bool, float, np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
        raise NotImplementedError


class StandardCalibration(CalibrationStrategy):
    def calibrate(self, corners, ids, board, image_size):
        error, K, D, rvecs, tvecs = cv2.aruco.calibrateCameraCharuco(
            corners, ids, board, image_size, None, None
        )
        return True, error, K, D, rvecs, tvecs


class FisheyeCalibration(CalibrationStrategy):
    def calibrate(self, corners, ids, board, image_size):
        obj_points = []
        img_points = []
        for c, i in zip(corners, ids):
            obj_pts = board.getChessboardCorners()[i.flatten()]
            obj_points.append(obj_pts.reshape(-1, 1, 3))
            img_points.append(c)

        K = np.zeros((3, 3))
        D = np.zeros((4, 1))
        flags = (cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC |
                 cv2.fisheye.CALIB_CHECK_COND |
                 cv2.fisheye.CALIB_FIX_SKEW)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)

        error, K, D, rvecs, tvecs = cv2.fisheye.calibrate(
            obj_points, img_points, image_size, K, D,
            flags=flags, criteria=criteria
        )
        return True, error, K, D, rvecs, tvecs
