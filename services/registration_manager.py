"""
Fixed Registration Manager - 2D Consistent
Handles camera-to-machine coordinate transformation logic with clean event handling
All operations now consistently use 2D coordinates (X, Y only)
"""

import numpy as np
from typing import List, Tuple, Optional
from services.event_broker import event_aware
from services.regitration_interfaces import IRegistrationComputation, IRegistrationDataManager, IRegistrationPersistence


class RegistrationEvents:
    POINT_ADDED = "registration.point_added"
    POINT_REMOVED = "registration.point_removed"
    POINT_TRANSFORMED = "registration.point_transformed"
    BATCH_TRANSFORMED = "registration.batch_transformed"
    COMPUTED = "registration.computed"
    AUTO_COMPUTED = "registration.auto_computed"
    CLEARED = "registration.cleared"
    RESET = "registration.reset"
    SAVED = "registration.saved"
    LOADED = "registration.loaded"
    VALIDATION_PASSED = "registration.validation_passed"
    VALIDATION_FAILED = "registration.validation_failed"
    ERROR = "registration.error"
    DEBUG_INFO = "registration.debug_info"


@event_aware()
class RegistrationManager(IRegistrationComputation, IRegistrationDataManager, IRegistrationPersistence):
    """Manages camera-to-machine coordinate registration with consistent 2D operations"""

    def __init__(self):
        self.calibration_points = []  # [(machine_pos, camera_tvec, norm_pos), ...]
        self.transformation_matrix = None
        self.translation_vector = None
        self._registration_error = None

    def log(self, msg):
        pass

    def add_calibration_point(self, machine_pos: np.ndarray, camera_tvec: np.ndarray, norm_pos: np.ndarray):
        """Add a calibration point - store as 2D only"""
        try:
            # Ensure consistent 2D dimensions
            machine_pos_2d = self._ensure_2d(machine_pos)
            camera_tvec_2d = self._ensure_2d(camera_tvec.flatten())

            point_data = (machine_pos_2d.copy(), camera_tvec_2d.copy(), norm_pos)
            self.calibration_points.append(point_data)

            point_count = len(self.calibration_points)

            # Emit point added event
            self.emit(RegistrationEvents.POINT_ADDED, {
                'point_index': point_count - 1,
                'total_points': point_count,
                'machine_pos': machine_pos_2d.copy(),
                'camera_tvec': camera_tvec_2d.copy(),
                'norm_pos': norm_pos
            })

            # Auto-compute if we have enough points
            if point_count >= 3:
                success = self.compute_registration()
                if success:
                    self.emit(RegistrationEvents.AUTO_COMPUTED, {
                        'point_count': point_count,
                        'error': self._registration_error
                    })

            return True

        except Exception as e:
            error_msg = f"Failed to add 2D calibration point: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            return False

    def _ensure_2d(self, point: np.ndarray) -> np.ndarray:
        """Ensure point is 2D format (x, y)"""
        point = np.asarray(point, dtype=np.float64)
        if point.shape == ():
            return np.array([point, 0.0])
        elif len(point) == 1:
            return np.array([point[0], 0.0])
        elif len(point) >= 2:
            return point[:2]  # Take only X, Y - IGNORE Z
        else:
            return np.array([0.0, 0.0])

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
        """Compute 2D rigid transformation from camera to machine coordinates"""
        try:
            if len(self.calibration_points) < 3:
                error_msg = "Need at least 3 calibration points for registration"
                self.emit(RegistrationEvents.ERROR, error_msg)
                raise ValueError(error_msg)

            # Skip computation if already done and not forced
            if not force_recompute and self.is_registered():
                return True

            # Extract points and ensure consistent 2D format
            machine_points = []
            camera_points = []

            for machine_pos, camera_tvec, _ in self.calibration_points:
                machine_2d = self._ensure_2d(machine_pos)
                camera_2d = self._ensure_2d(camera_tvec)
                machine_points.append(machine_2d)
                camera_points.append(camera_2d)

            # Compute 2D rigid transformation
            self.transformation_matrix, self.translation_vector = self._compute_rigid_transform(
                camera_points, machine_points)

            # Calculate registration error
            self._registration_error = self._calculate_registration_error()

            # Emit successful computation event
            self.emit(RegistrationEvents.COMPUTED, {
                'point_count': len(self.calibration_points),
                'error': self._registration_error,
                'transformation_matrix': self.transformation_matrix.copy(),
                'translation_vector': self.translation_vector.copy(),
                'dimensions': '2D'
            })

            return True

        except Exception as e:
            error_msg = f"2D Registration computation failed: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            return False

    def _compute_rigid_transform(self, A: List[np.ndarray], B: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute 2D rigid transformation (rotation + translation) from point set A to B
        Using Kabsch algorithm with 2D points only
        """
        try:
            # Convert to numpy arrays and ensure 2D
            A_array = np.array([self._ensure_2d(point) for point in A])  # Shape: (N, 2)
            B_array = np.array([self._ensure_2d(point) for point in B])  # Shape: (N, 2)

            if A_array.shape[0] != B_array.shape[0]:
                raise ValueError(f"Point count mismatch: A has {A_array.shape[0]}, B has {B_array.shape[0]}")

            if A_array.shape[1] != 2 or B_array.shape[1] != 2:
                raise ValueError(f"Points must be 2D: A shape {A_array.shape}, B shape {B_array.shape}")

            # Compute centroids
            centroid_A = np.mean(A_array, axis=0)  # Shape: (2,)
            centroid_B = np.mean(B_array, axis=0)  # Shape: (2,)

            # Center the points
            AA = A_array - centroid_A  # Shape: (N, 2)
            BB = B_array - centroid_B  # Shape: (N, 2)

            # Compute cross-covariance matrix H = AA.T @ BB
            H = AA.T @ BB  # Shape: (2, 2)

            # SVD decomposition
            U, S, Vt = np.linalg.svd(H)

            # Compute rotation matrix
            R = Vt.T @ U.T  # Shape: (2, 2)

            # Ensure proper rotation (det(R) = 1)
            if np.linalg.det(R) < 0:
                Vt[-1, :] *= -1
                R = Vt.T @ U.T

            # Compute translation
            t = centroid_B - R @ centroid_A  # Shape: (2,)

            return R, t

        except Exception as e:
            raise RuntimeError(f"2D Rigid transform computation error: {e}")

    def transform_point(self, camera_point: np.ndarray) -> np.ndarray:
        """Transform a point from camera coordinates to machine coordinates - 2D ONLY"""
        if not self.is_registered():
            error_msg = "Registration not computed - call compute_registration() first"
            self.emit(RegistrationEvents.ERROR, error_msg)
            raise ValueError(error_msg)

        try:
            # Ensure 2D point
            camera_2d = self._ensure_2d(camera_point)

            # Apply transformation: R @ point + t
            transformed = self.transformation_matrix @ camera_2d + self.translation_vector

            # Emit transformation event for debugging/logging
            self.emit(RegistrationEvents.POINT_TRANSFORMED, {
                'camera_point': camera_2d.copy(),
                'machine_point': transformed.copy()
            })

            return transformed  # Returns 2D point

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
                'camera_points': [self._ensure_2d(p) for p in camera_points],
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

    def save_registration(self, filename: str) -> bool:
        """Save registration data to file - 2D CONSISTENT"""
        try:
            if not self.is_registered():
                error_msg = "No registration data to save"
                self.emit(RegistrationEvents.ERROR, error_msg)
                raise ValueError(error_msg)

            # Convert calibration points to a format that can be saved - KEEP 2D
            machine_positions = []
            camera_positions = []
            norm_positions = []

            for machine_pos, camera_tvec, norm_pos in self.calibration_points:
                machine_positions.append(self._ensure_2d(machine_pos))  # CHANGED: Keep 2D
                camera_positions.append(self._ensure_2d(camera_tvec))   # CHANGED: Keep 2D
                norm_positions.append(norm_pos)

            save_data = {
                'rotation_matrix': self.transformation_matrix,
                'translation_vector': self.translation_vector,
                'machine_positions': np.array(machine_positions),
                'camera_positions': np.array(camera_positions),
                'norm_positions': np.array(norm_positions),
                'registration_error': self._registration_error,
                'point_count': len(self.calibration_points),
                'dimensions': '2D'  # ADDED: Mark as 2D data
            }

            np.savez(filename, **save_data)

            self.emit(RegistrationEvents.SAVED, {
                'filename': filename,
                'point_count': len(self.calibration_points),
                'error': self._registration_error
            })

            return True

        except Exception as e:
            error_msg = f"Failed to save registration: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            return False

    def load_registration(self, filename: str) -> bool:
        """Load registration data from file - 2D CONSISTENT"""
        try:
            data = np.load(filename)

            # Load transformation data
            self.transformation_matrix = data["rotation_matrix"]
            self.translation_vector = data["translation_vector"]
            self._registration_error = float(data["registration_error"]) if "registration_error" in data else None

            # Load calibration points - ensure 2D consistency
            self.calibration_points = []
            machine_positions = data["machine_positions"]
            camera_positions = data["camera_positions"]
            norm_positions = data["norm_positions"]

            for i in range(len(machine_positions)):
                machine_pos = self._ensure_2d(machine_positions[i])  # CHANGED: Ensure 2D
                camera_pos = self._ensure_2d(camera_positions[i])    # CHANGED: Ensure 2D
                norm_pos = norm_positions[i]
                self.calibration_points.append((machine_pos, camera_pos, norm_pos))

            self.emit(RegistrationEvents.LOADED, {
                'filename': filename,
                'point_count': len(self.calibration_points),
                'error': self._registration_error
            })

            return True

        except Exception as e:
            error_msg = f"Failed to load registration: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            return False

    def get_registration_error(self) -> Optional[float]:
        """Get the current registration error (RMS)"""
        return self._registration_error

    def _calculate_registration_error(self) -> Optional[float]:
        """Calculate registration error (RMS) for current calibration points - 2D CONSISTENT"""
        if not self.is_registered() or not self.calibration_points:
            return None

        try:
            errors = []
            for machine_pos, camera_tvec, _ in self.calibration_points:
                predicted_machine = self.transform_point(camera_tvec)
                # FIXED: Use 2D comparison instead of 3D
                error = np.linalg.norm(predicted_machine - self._ensure_2d(machine_pos))
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
            'has_sufficient_points': len(self.calibration_points) >= 3,
            'dimensions': '2D'  # ADDED: Mark as 2D stats
        }

        if self.is_registered() and self.calibration_points:
            # Calculate per-point errors - 2D CONSISTENT
            point_errors = []
            for i, (machine_pos, camera_tvec, _) in enumerate(self.calibration_points):
                try:
                    predicted_machine = self.transform_point(camera_tvec)
                    # FIXED: Use 2D comparison
                    error = np.linalg.norm(predicted_machine - self._ensure_2d(machine_pos))
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
        """Validate registration quality"""
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

    def debug_calibration_points(self):
        """Debug method to print calibration point information"""
        debug_info = {
            'total_points': len(self.calibration_points),
            'dimensions': '2D',
            'points_detail': []
        }

        for i, (machine_pos, camera_tvec, norm_pos) in enumerate(self.calibration_points):
            point_detail = {
                'index': i,
                'machine_pos': machine_pos.tolist(),
                'machine_shape': machine_pos.shape,
                'camera_tvec': camera_tvec.tolist(),
                'camera_shape': camera_tvec.shape,
                'norm_pos': norm_pos
            }
            debug_info['points_detail'].append(point_detail)

        self.emit(RegistrationEvents.DEBUG_INFO, debug_info)

    def get_transformation_info(self) -> dict:
        """Get detailed information about the current transformation"""
        info = {
            'is_registered': self.is_registered(),
            'point_count': len(self.calibration_points),
            'registration_error': self._registration_error,
            'dimensions': '2D'
        }

        if self.is_registered():
            info.update({
                'rotation_matrix': self.transformation_matrix.tolist() if self.transformation_matrix is not None else None,
                'translation_vector': self.translation_vector.tolist() if self.translation_vector is not None else None,
                'rotation_matrix_shape': self.transformation_matrix.shape if self.transformation_matrix is not None else None,
                'translation_vector_shape': self.translation_vector.shape if self.translation_vector is not None else None
            })

        return info