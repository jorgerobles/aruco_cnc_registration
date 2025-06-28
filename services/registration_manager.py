"""
Registration Manager
Handles camera-to-machine coordinate transformation logic
Enhanced with @event_aware decorator
"""

import numpy as np
from typing import List, Tuple, Optional
from services.event_broker import event_aware, RegistrationEvents


@event_aware()
class RegistrationManager:
    """Manages camera-to-machine coordinate registration with event notifications"""

    def __init__(self):
        self.calibration_points = []  # [(machine_pos, camera_tvec, norm_pos), ...]
        self.transformation_matrix = None
        self.translation_vector = None
        self._registration_error = None

        # self._event_broker is automatically available from decorator

    def add_calibration_point(self, machine_pos: np.ndarray, camera_tvec: np.ndarray, norm_pos: np.ndarray):
        """Add a calibration point to the registration dataset"""
        try:
            point_data = (machine_pos.copy(), camera_tvec.flatten().copy(), norm_pos)
            self.calibration_points.append(point_data)

            point_count = len(self.calibration_points)

            # Emit point added event
            self.emit(RegistrationEvents.POINT_ADDED, {
                'point_index': point_count - 1,
                'total_points': point_count,
                'machine_pos': machine_pos.copy(),
                'camera_tvec': camera_tvec.flatten().copy(),
                'norm_pos': norm_pos
            })

            # Auto-compute registration if we have enough points
            if point_count >= 3:
                try:
                    success = self.compute_registration()
                    if success:
                        self.emit(RegistrationEvents.AUTO_COMPUTED, {
                            'point_count': point_count,
                            'error': self._registration_error
                        })
                except Exception as e:
                    self.emit(RegistrationEvents.ERROR, f"Auto-registration failed: {e}")

        except Exception as e:
            error_msg = f"Failed to add calibration point: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            raise RuntimeError(error_msg)

    def remove_calibration_point(self, index: int) -> bool:
        """Remove a calibration point by index"""
        try:
            if 0 <= index < len(self.calibration_points):
                removed_point = self.calibration_points.pop(index)

                # Clear registration if we don't have enough points
                if len(self.calibration_points) < 3:
                    self._clear_registration()
                else:
                    # Recompute registration with remaining points
                    try:
                        self.compute_registration()
                    except Exception as e:
                        self.emit(RegistrationEvents.ERROR, f"Failed to recompute after point removal: {e}")

                self.emit(RegistrationEvents.POINT_REMOVED, {
                    'removed_index': index,
                    'total_points': len(self.calibration_points),
                    'removed_point': removed_point
                })

                return True
            else:
                self.emit(RegistrationEvents.ERROR, f"Invalid point index: {index}")
                return False

        except Exception as e:
            error_msg = f"Failed to remove calibration point: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            return False

    def clear_calibration_points(self):
        """Clear all calibration points"""
        try:
            point_count = len(self.calibration_points)
            self.calibration_points.clear()
            self._clear_registration()

            self.emit(RegistrationEvents.CLEARED, {
                'cleared_count': point_count
            })

        except Exception as e:
            error_msg = f"Failed to clear calibration points: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)

    def _clear_registration(self):
        """Internal method to clear computed registration"""
        self.transformation_matrix = None
        self.translation_vector = None
        self._registration_error = None

    def get_calibration_points_count(self) -> int:
        """Get number of calibration points"""
        return len(self.calibration_points)

    def get_machine_positions(self) -> List[np.ndarray]:
        """Get list of machine positions from calibration points"""
        return [point[0].copy() for point in self.calibration_points]

    def get_camera_positions(self) -> List[np.ndarray]:
        """Get list of camera positions from calibration points"""
        return [point[1].copy() for point in self.calibration_points]

    def get_calibration_point(self, index: int) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """Get a specific calibration point by index"""
        if 0 <= index < len(self.calibration_points):
            machine_pos, camera_tvec, norm_pos = self.calibration_points[index]
            return machine_pos.copy(), camera_tvec.copy(), norm_pos
        return None

    def compute_registration(self, force_recompute: bool = False) -> bool:
        """
        Compute rigid transformation from camera to machine coordinates

        Args:
            force_recompute: Force recomputation even if already computed

        Returns:
            True if successful, False otherwise
        """
        try:
            if len(self.calibration_points) < 3:
                error_msg = "Need at least 3 calibration points for registration"
                self.emit(RegistrationEvents.ERROR, error_msg)
                raise ValueError(error_msg)

            # Skip computation if already done and not forced
            if not force_recompute and self.is_registered():
                return True

            # Extract points
            machine_points = [point[0] for point in self.calibration_points]
            camera_points = [point[1] for point in self.calibration_points]

            # Compute rigid transformation
            self.transformation_matrix, self.translation_vector = self._compute_rigid_transform(
                camera_points, machine_points)

            # Calculate registration error
            self._registration_error = self._calculate_registration_error()

            # Emit successful computation event
            self.emit(RegistrationEvents.COMPUTED, {
                'point_count': len(self.calibration_points),
                'error': self._registration_error,
                'transformation_matrix': self.transformation_matrix.copy(),
                'translation_vector': self.translation_vector.copy()
            })

            return True

        except Exception as e:
            error_msg = f"Registration computation failed: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            raise RuntimeError(error_msg)

    def _compute_rigid_transform(self, A: List[np.ndarray], B: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute rigid transformation (rotation + translation) from point set A to B
        Using Kabsch algorithm
        """
        A = np.asarray(A)
        B = np.asarray(B)

        # Ensure we have 3D points (pad with zeros if needed)
        if A.shape[1] < 3:
            A = np.column_stack([A, np.zeros((A.shape[0], 3 - A.shape[1]))])
        if B.shape[1] < 3:
            B = np.column_stack([B, np.zeros((B.shape[0], 3 - B.shape[1]))])

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
            Vt[-1, :] *= -1
            R = Vt.T @ U.T

        # Compute translation
        t = centroid_B - R @ centroid_A

        return R, t

    def transform_point(self, camera_point: np.ndarray) -> np.ndarray:
        """Transform a point from camera coordinates to machine coordinates"""
        if not self.is_registered():
            error_msg = "Registration not computed - call compute_registration() first"
            self.emit(RegistrationEvents.ERROR, error_msg)
            raise ValueError(error_msg)

        try:
            # Ensure 3D point
            if len(camera_point) < 3:
                camera_point = np.append(camera_point, np.zeros(3 - len(camera_point)))

            transformed = self.transformation_matrix @ camera_point + self.translation_vector

            # Emit transformation event for debugging/logging
            self.emit(RegistrationEvents.POINT_TRANSFORMED, {
                'camera_point': camera_point.copy(),
                'machine_point': transformed.copy()
            })

            return transformed

        except Exception as e:
            error_msg = f"Point transformation failed: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            raise RuntimeError(error_msg)

    def transform_points(self, camera_points: List[np.ndarray]) -> List[np.ndarray]:
        """Transform multiple points from camera to machine coordinates"""
        try:
            transformed_points = []
            for point in camera_points:
                transformed_points.append(self.transform_point(point))

            self.emit(RegistrationEvents.BATCH_TRANSFORMED, {
                'point_count': len(camera_points),
                'camera_points': [p.copy() for p in camera_points],
                'machine_points': [p.copy() for p in transformed_points]
            })

            return transformed_points

        except Exception as e:
            error_msg = f"Batch transformation failed: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            raise RuntimeError(error_msg)

    def is_registered(self) -> bool:
        """Check if registration has been computed"""
        return (self.transformation_matrix is not None and
                self.translation_vector is not None)

    def save_registration(self, filename: str):
        """Save registration data to file"""
        try:
            if not self.is_registered():
                error_msg = "No registration data to save"
                self.emit(RegistrationEvents.ERROR, error_msg)
                raise ValueError(error_msg)

            save_data = {
                'rotation_matrix': self.transformation_matrix,
                'translation_vector': self.translation_vector,
                'calibration_points': self.calibration_points,
                'registration_error': self._registration_error
            }

            np.savez(filename, **save_data)

            self.emit(RegistrationEvents.SAVED, {
                'filename': filename,
                'point_count': len(self.calibration_points),
                'error': self._registration_error
            })

        except Exception as e:
            error_msg = f"Failed to save registration: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            raise RuntimeError(error_msg)

    def load_registration(self, filename: str):
        """Load registration data from file"""
        try:
            data = np.load(filename, allow_pickle=True)

            self.transformation_matrix = data["rotation_matrix"]
            self.translation_vector = data["translation_vector"]
            self.calibration_points = data["calibration_points"].tolist()

            # Load error if available (backwards compatibility)
            self._registration_error = data.get("registration_error", None)
            if self._registration_error is None:
                self._registration_error = self._calculate_registration_error()

            self.emit(RegistrationEvents.LOADED, {
                'filename': filename,
                'point_count': len(self.calibration_points),
                'error': self._registration_error
            })

        except Exception as e:
            error_msg = f"Failed to load registration: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            raise RuntimeError(error_msg)

    def get_registration_error(self) -> Optional[float]:
        """
        Get the current registration error (RMS)
        Returns None if registration not computed
        """
        return self._registration_error

    def _calculate_registration_error(self) -> Optional[float]:
        """
        Calculate registration error (RMS) for current calibration points
        Returns None if registration not computed
        """
        if not self.is_registered() or not self.calibration_points:
            return None

        try:
            errors = []
            for machine_pos, camera_tvec, _ in self.calibration_points:
                predicted_machine = self.transform_point(camera_tvec)
                error = np.linalg.norm(predicted_machine - machine_pos)
                errors.append(error)

            rms_error = np.sqrt(np.mean(np.square(errors)))
            return float(rms_error)

        except Exception as e:
            self.emit(RegistrationEvents.ERROR, f"Error calculating registration error: {e}")
            return None

    def get_registration_stats(self) -> dict:
        """Get comprehensive registration statistics"""
        stats = {
            'point_count': len(self.calibration_points),
            'is_registered': self.is_registered(),
            'registration_error': self._registration_error,
            'has_sufficient_points': len(self.calibration_points) >= 3
        }

        if self.is_registered() and self.calibration_points:
            # Calculate per-point errors
            point_errors = []
            for i, (machine_pos, camera_tvec, _) in enumerate(self.calibration_points):
                try:
                    predicted_machine = self.transform_point(camera_tvec)
                    error = np.linalg.norm(predicted_machine - machine_pos)
                    point_errors.append(error)
                except:
                    point_errors.append(float('inf'))

            stats.update({
                'point_errors': point_errors,
                'max_error': max(point_errors) if point_errors else None,
                'min_error': min(point_errors) if point_errors else None,
                'mean_error': np.mean(point_errors) if point_errors else None
            })

        return stats

    def validate_registration(self, tolerance: float = 1.0) -> bool:
        """
        Validate registration quality

        Args:
            tolerance: Maximum acceptable RMS error

        Returns:
            True if registration is valid, False otherwise
        """
        try:
            if not self.is_registered():
                self.emit(RegistrationEvents.VALIDATION_FAILED, {
                    'reason': 'No registration computed',
                    'tolerance': tolerance
                })
                return False

            if self._registration_error is None:
                self._registration_error = self._calculate_registration_error()

            is_valid = self._registration_error <= tolerance

            if is_valid:
                self.emit(RegistrationEvents.VALIDATION_PASSED, {
                    'error': self._registration_error,
                    'tolerance': tolerance
                })
            else:
                self.emit(RegistrationEvents.VALIDATION_FAILED, {
                    'error': self._registration_error,
                    'tolerance': tolerance,
                    'reason': f'Error {self._registration_error:.3f} exceeds tolerance {tolerance:.3f}'
                })

            return is_valid

        except Exception as e:
            error_msg = f"Registration validation failed: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            return False

    def reset(self):
        """Reset all registration data"""
        try:
            point_count = len(self.calibration_points)
            was_registered = self.is_registered()

            self.calibration_points.clear()
            self._clear_registration()

            self.emit(RegistrationEvents.RESET, {
                'cleared_points': point_count,
                'was_registered': was_registered
            })

        except Exception as e:
            error_msg = f"Failed to reset registration: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)