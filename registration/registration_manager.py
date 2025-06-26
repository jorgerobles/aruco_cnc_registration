"""
Registration Manager
Handles camera-to-machine coordinate transformation logic
"""

import numpy as np
from typing import List, Tuple, Optional


class RegistrationManager:
    """Manages camera-to-machine coordinate registration"""

    def __init__(self):
        self.calibration_points = []  # [(machine_pos, camera_tvec, norm_pos), ...]
        self.transformation_matrix = None
        self.translation_vector = None

    def add_calibration_point(self, machine_pos: np.ndarray, camera_tvec: np.ndarray, norm_pos: np.ndarray):
        """Add a calibration point to the registration dataset"""
        point_data = (machine_pos, camera_tvec.flatten(), norm_pos)
        self.calibration_points.append(point_data)

    def clear_calibration_points(self):
        """Clear all calibration points"""
        self.calibration_points.clear()

    def get_calibration_points_count(self) -> int:
        """Get number of calibration points"""
        return len(self.calibration_points)

    def get_machine_positions(self) -> List[np.ndarray]:
        """Get list of machine positions from calibration points"""
        return [point[0] for point in self.calibration_points]

    def compute_registration(self) -> bool:
        """
        Compute rigid transformation from camera to machine coordinates
        Returns True if successful, False otherwise
        """
        if len(self.calibration_points) < 3:
            raise ValueError("Need at least 3 calibration points for registration")

        try:
            # Extract points
            machine_points = [point[0] for point in self.calibration_points]
            camera_points = [point[1] for point in self.calibration_points]

            # Compute rigid transformation
            self.transformation_matrix, self.translation_vector = self._compute_rigid_transform(
                camera_points, machine_points)

            return True

        except Exception as e:
            raise RuntimeError(f"Registration computation failed: {e}")

    def _compute_rigid_transform(self, A: List[np.ndarray], B: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute rigid transformation (rotation + translation) from point set A to B
        Using Kabsch algorithm
        """
        A = np.asarray(A)
        B = np.asarray(B)

        # Compute centroids
        centroid_A = np.mean(A, axis=0)
        centroid_B = np.mean(B, axis=0)

        # Center the points
        AA = A - centroid_A
        BB = B - centroid_B

        # Compute cross-covariance matrix
        H = AA.T @ BB

        # SVD decomposition
        U, _, Vt = np.linalg.svd(H)

        # Compute rotation matrix
        R = Vt.T @ U.T

        # Ensure proper rotation (det(R) = 1)
        if np.linalg.det(R) < 0:
            Vt[2, :] *= -1
            R = Vt.T @ U.T

        # Compute translation
        t = centroid_B - R @ centroid_A

        return R, t

    def transform_point(self, camera_point: np.ndarray) -> np.ndarray:
        """Transform a point from camera coordinates to machine coordinates"""
        if self.transformation_matrix is None or self.translation_vector is None:
            raise ValueError("Registration not computed - call compute_registration() first")

        return self.transformation_matrix @ camera_point + self.translation_vector

    def is_registered(self) -> bool:
        """Check if registration has been computed"""
        return self.transformation_matrix is not None and self.translation_vector is not None

    def save_registration(self, filename: str):
        """Save registration data to file"""
        if not self.is_registered():
            raise ValueError("No registration data to save")

        np.savez(filename,
                 rotation_matrix=self.transformation_matrix,
                 translation_vector=self.translation_vector,
                 calibration_points=self.calibration_points)

    def load_registration(self, filename: str):
        """Load registration data from file"""
        try:
            data = np.load(filename, allow_pickle=True)
            self.transformation_matrix = data["rotation_matrix"]
            self.translation_vector = data["translation_vector"]
            self.calibration_points = data["calibration_points"].tolist()
        except Exception as e:
            raise RuntimeError(f"Failed to load registration: {e}")

    def get_registration_error(self) -> Optional[float]:
        """
        Calculate registration error (RMS) for current calibration points
        Returns None if registration not computed
        """
        if not self.is_registered() or not self.calibration_points:
            return None

        errors = []
        for machine_pos, camera_tvec, _ in self.calibration_points:
            predicted_machine = self.transform_point(camera_tvec)
            error = np.linalg.norm(predicted_machine - machine_pos)
            errors.append(error)

        return np.sqrt(np.mean(np.square(errors)))