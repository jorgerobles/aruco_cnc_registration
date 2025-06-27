# board_manager.py

import cv2
import numpy as np
from typing import Optional, Tuple


class CharucoBoardManager:
    def __init__(self, squares_x: int, squares_y: int, square_length: float,
                 marker_length: float, dictionary=cv2.aruco.DICT_4X4_50):
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
        self.charuco_board = cv2.aruco.CharucoBoard(
            (squares_x, squares_y), square_length, marker_length, self.aruco_dict
        )
        self.detector_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.detector_params)

    def generate_board_image(self, size: Tuple[int, int]) -> np.ndarray:
        return self.charuco_board.generateImage(size)

    def detect(self, image: np.ndarray, visualize: bool = False) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        marker_corners, marker_ids, _ = self.detector.detectMarkers(gray)

        if len(marker_corners) == 0:
            return None, None

        retval, corners, ids = cv2.aruco.interpolateCornersCharuco(
            marker_corners, marker_ids, gray, self.charuco_board
        )

        if visualize and retval > 0:
            cv2.aruco.drawDetectedMarkers(image, marker_corners, marker_ids)
            cv2.aruco.drawDetectedCornersCharuco(image, corners, ids)

        return (corners, ids) if retval > 0 else (None, None)

    def get_board(self):
        return self.charuco_board
