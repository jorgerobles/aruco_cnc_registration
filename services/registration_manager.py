"""
Fixed Registration Manager
Handles camera-to-machine coordinate transformation logic with clean event handling
Eliminates duplicate logging and improper use of ERROR events for success messages
"""

import numpy as np
from typing import List, Tuple, Optional
from services.event_broker import event_aware, RegistrationEvents


@event_aware()
class RegistrationManager:
    """Manages camera-to-machine coordinate registration with clean event notifications"""

    def __init__(self):
        self.calibration_points = []  # [(machine_pos, camera_tvec, norm_pos), ...]
        self.transformation_matrix = None
        self.translation_vector = None
        self._registration_error = None

        # self._event_broker is automatically available from decorator

    def add_calibration_point(self, machine_pos: np.ndarray, camera_tvec: np.ndarray, norm_pos: np.ndarray):
        """Add a calibration point to the registration dataset"""
        try:
            # Ensure consistent dimensions - use only first 3 dimensions
            machine_pos_3d = self._ensure_3d(machine_pos)
            camera_tvec_3d = self._ensure_3d(camera_tvec.flatten())

            point_data = (machine_pos_3d.copy(), camera_tvec_3d.copy(), norm_pos)
            self.calibration_points.append(point_data)

            point_count = len(self.calibration_points)

            # Emit point added event
            self.emit(RegistrationEvents.POINT_ADDED, {
                'point_index': point_count - 1,
                'total_points': point_count,
                'machine_pos': machine_pos_3d.copy(),
                'camera_tvec': camera_tvec_3d.copy(),
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

    def _ensure_3d(self, point: np.ndarray) -> np.ndarray:
        """Ensure point is exactly 3D"""
        point = np.asarray(point).flatten()

        if len(point) >= 3:
            # Take only first 3 dimensions if more are provided
            return point[:3].copy()
        else:
            # Pad with zeros if less than 3 dimensions
            padded = np.zeros(3)
            padded[:len(point)] = point
            return padded

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

            # Extract points and ensure consistent 3D format
            machine_points = []
            camera_points = []

            for machine_pos, camera_tvec, _ in self.calibration_points:
                machine_3d = self._ensure_3d(machine_pos)
                camera_3d = self._ensure_3d(camera_tvec)
                machine_points.append(machine_3d)
                camera_points.append(camera_3d)

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
            # Don't re-raise to prevent cascade failures
            return False

    def _compute_rigid_transform(self, A: List[np.ndarray], B: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute rigid transformation (rotation + translation) from point set A to B
        Using Kabsch algorithm with proper dimension handling
        """
        try:
            # Convert to numpy arrays and ensure 3D
            A_array = np.array([self._ensure_3d(point) for point in A])  # Shape: (N, 3)
            B_array = np.array([self._ensure_3d(point) for point in B])  # Shape: (N, 3)

            if A_array.shape[0] != B_array.shape[0]:
                raise ValueError(f"Point count mismatch: A has {A_array.shape[0]}, B has {B_array.shape[0]}")

            if A_array.shape[1] != 3 or B_array.shape[1] != 3:
                raise ValueError(f"Points must be 3D: A shape {A_array.shape}, B shape {B_array.shape}")

            # Compute centroids
            centroid_A = np.mean(A_array, axis=0)  # Shape: (3,)
            centroid_B = np.mean(B_array, axis=0)  # Shape: (3,)

            # Center the points
            AA = A_array - centroid_A  # Shape: (N, 3)
            BB = B_array - centroid_B  # Shape: (N, 3)

            # Compute cross-covariance matrix H = AA.T @ BB
            H = AA.T @ BB  # Shape: (3, 3)

            # SVD decomposition
            U, S, Vt = np.linalg.svd(H)

            # Compute rotation matrix
            R = Vt.T @ U.T  # Shape: (3, 3)

            # Ensure proper rotation (det(R) = 1)
            if np.linalg.det(R) < 0:
                Vt[-1, :] *= -1
                R = Vt.T @ U.T

            # Compute translation
            t = centroid_B - R @ centroid_A  # Shape: (3,)

            return R, t

        except Exception as e:
            raise RuntimeError(f"Rigid transform computation error: {e}")

    def transform_point(self, camera_point: np.ndarray) -> np.ndarray:
        """Transform a point from camera coordinates to machine coordinates"""
        if not self.is_registered():
            error_msg = "Registration not computed - call compute_registration() first"
            self.emit(RegistrationEvents.ERROR, error_msg)
            raise ValueError(error_msg)

        try:
            # Ensure 3D point
            camera_3d = self._ensure_3d(camera_point)

            # Apply transformation: R @ point + t
            transformed = self.transformation_matrix @ camera_3d + self.translation_vector

            # Emit transformation event for debugging/logging
            self.emit(RegistrationEvents.POINT_TRANSFORMED, {
                'camera_point': camera_3d.copy(),
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
                'camera_points': [self._ensure_3d(p) for p in camera_points],
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
        """Save registration data to file"""
        try:
            if not self.is_registered():
                error_msg = "No registration data to save"
                self.emit(RegistrationEvents.ERROR, error_msg)
                raise ValueError(error_msg)

            # Convert calibration points to a format that can be saved
            machine_positions = []
            camera_positions = []
            norm_positions = []

            for machine_pos, camera_tvec, norm_pos in self.calibration_points:
                machine_positions.append(self._ensure_3d(machine_pos))
                camera_positions.append(self._ensure_3d(camera_tvec))
                norm_positions.append(norm_pos)

            save_data = {
                'rotation_matrix': self.transformation_matrix,
                'translation_vector': self.translation_vector,
                'machine_positions': np.array(machine_positions),
                'camera_positions': np.array(camera_positions),
                'norm_positions': np.array(norm_positions),
                'registration_error': self._registration_error,
                'point_count': len(self.calibration_points)
            }

            np.savez(filename, **save_data)

            # Emit save success event (no longer using ERROR for success messages)
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
        """Load registration data from file"""
        try:
            data = np.load(filename, allow_pickle=True)

            self.transformation_matrix = data["rotation_matrix"]
            self.translation_vector = data["translation_vector"]

            # Handle both old and new save formats
            if "calibration_points" in data:
                # Old format - directly saved calibration_points
                self.calibration_points = data["calibration_points"].tolist()
            else:
                # New format - separate arrays
                machine_positions = data["machine_positions"]
                camera_positions = data["camera_positions"]
                norm_positions = data["norm_positions"]

                # Reconstruct calibration points
                self.calibration_points = []
                for i in range(len(machine_positions)):
                    machine_pos = machine_positions[i]
                    camera_pos = camera_positions[i]
                    norm_pos = norm_positions[i]
                    self.calibration_points.append((machine_pos, camera_pos, norm_pos))

            # Load error if available (backwards compatibility)
            self._registration_error = data.get("registration_error", None)
            if self._registration_error is None:
                self._registration_error = self._calculate_registration_error()

            # Emit load success event (no longer using ERROR for success messages)
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
                error = np.linalg.norm(predicted_machine - self._ensure_3d(machine_pos))
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
                    error = np.linalg.norm(predicted_machine - self._ensure_3d(machine_pos))
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

    def save_registration_json(self, filename: str) -> bool:
        """Save registration data to JSON file (human-readable backup)"""
        try:
            import json

            if not self.is_registered():
                error_msg = "No registration data to save"
                self.emit(RegistrationEvents.ERROR, error_msg)
                return False

            # Convert numpy arrays to lists for JSON serialization
            save_data = {
                'rotation_matrix': self.transformation_matrix.tolist(),
                'translation_vector': self.translation_vector.tolist(),
                'registration_error': float(self._registration_error) if self._registration_error else None,
                'point_count': len(self.calibration_points),
                'calibration_points': []
            }

            # Convert calibration points to JSON-serializable format
            for i, (machine_pos, camera_tvec, norm_pos) in enumerate(self.calibration_points):
                point_data = {
                    'index': i,
                    'machine_position': self._ensure_3d(machine_pos).tolist(),
                    'camera_position': self._ensure_3d(camera_tvec).tolist(),
                    'normalized_position': norm_pos if isinstance(norm_pos, (list, tuple)) else float(norm_pos)
                }
                save_data['calibration_points'].append(point_data)

            # Save to JSON file
            with open(filename, 'w') as f:
                json.dump(save_data, f, indent=2)

            return True

        except Exception as e:
            error_msg = f"Failed to save registration to JSON: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            return False

    def load_registration_json(self, filename: str) -> bool:
        """Load registration data from JSON file"""
        try:
            import json

            with open(filename, 'r') as f:
                data = json.load(f)

            self.transformation_matrix = np.array(data["rotation_matrix"])
            self.translation_vector = np.array(data["translation_vector"])
            self._registration_error = data.get("registration_error")

            # Reconstruct calibration points
            self.calibration_points = []
            for point_data in data["calibration_points"]:
                machine_pos = np.array(point_data["machine_position"])
                camera_pos = np.array(point_data["camera_position"])
                norm_pos = point_data["normalized_position"]
                self.calibration_points.append((machine_pos, camera_pos, norm_pos))

            self.emit(RegistrationEvents.LOADED, {
                'filename': filename,
                'point_count': len(self.calibration_points),
                'error': self._registration_error
            })

            return True

        except Exception as e:
            error_msg = f"Failed to load registration from JSON: {e}"
            self.emit(RegistrationEvents.ERROR, error_msg)
            return False

    def debug_calibration_points(self):
        """Debug method to print calibration point information"""
        # Create a special debug info event instead of misusing ERROR
        debug_info = {
            'total_points': len(self.calibration_points),
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

        # Emit as a debug info event rather than error
        self.emit(RegistrationEvents.DEBUG_INFO, debug_info)

    def get_transformation_info(self) -> dict:
        """Get detailed information about the current transformation"""
        info = {
            'is_registered': self.is_registered(),
            'point_count': len(self.calibration_points),
            'registration_error': self._registration_error
        }

        if self.is_registered():
            info.update({
                'rotation_matrix': self.transformation_matrix.tolist() if self.transformation_matrix is not None else None,
                'translation_vector': self.translation_vector.tolist() if self.translation_vector is not None else None,
                'rotation_matrix_shape': self.transformation_matrix.shape if self.transformation_matrix is not None else None,
                'translation_vector_shape': self.translation_vector.shape if self.translation_vector is not None else None
            })

        return info