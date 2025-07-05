"""
Marker Detection Overlay
Handles ArUco marker detection and pose estimation as an overlay component
"""

from typing import Optional, Callable, Tuple

import cv2
import numpy as np

from services.overlays.overlay_interface import FrameOverlay


class MarkerDetectionOverlay(FrameOverlay):
    """Overlay component for ArUco marker detection and pose visualization"""

    def __init__(self, camera_manager, marker_length: float = 20.0,
                 dictionary=cv2.aruco.DICT_4X4_50, logger: Optional[Callable] = None):
        self.camera_manager = camera_manager
        self.marker_length = marker_length
        self.logger = logger

        # ArUco detection setup
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
        self.parameters = cv2.aruco.DetectorParameters()

        # Display settings
        self.visible = True
        self.show_axes = True
        self.show_markers = True
        self.show_pose_info = True
        self.axes_length_factor = 0.5  # Axes length as factor of marker length

        # Detection state
        self.last_detection = {
            'rvec': None,
            'tvec': None,
            'norm_pos': None,
            'marker_id': None,
            'corners': None
        }

        # Pose tracking callback
        self.pose_callback = None  # Optional callback for pose updates

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def set_visibility(self, visible: bool):
        """Toggle overlay visibility"""
        self.visible = visible

    def is_visible(self) -> bool:
        """Check if overlay is visible"""
        return self.visible

    def set_marker_length(self, length: float):
        """Set marker length for pose estimation"""
        self.marker_length = length
        self.log(f"Marker length set to: {length}")

    def set_axes_visibility(self, show_axes: bool):
        """Toggle coordinate axes display"""
        self.show_axes = show_axes

    def set_markers_visibility(self, show_markers: bool):
        """Toggle marker outline display"""
        self.show_markers = show_markers

    def set_pose_info_visibility(self, show_info: bool):
        """Toggle pose information text display"""
        self.show_pose_info = show_info

    def set_axes_length_factor(self, factor: float):
        """Set axes length as factor of marker length"""
        self.axes_length_factor = max(0.1, factor)

    def set_pose_callback(self, callback: Callable):
        """Set callback function for pose updates"""
        self.pose_callback = callback

    def get_last_detection(self) -> dict:
        """Get the last marker detection results"""
        return self.last_detection.copy()

    def apply_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Apply marker detection overlay to the frame"""
        if not self.visible:
            return frame

        # Check if camera is calibrated
        if (self.camera_manager.camera_matrix is None or
                self.camera_manager.dist_coeffs is None):
            return self._draw_calibration_warning(frame)

        try:
            return self._detect_and_draw_markers(frame)
        except Exception as e:
            self.log(f"Error in marker detection overlay: {e}", "error")
            return self._draw_error_message(frame, str(e))

    def _detect_and_draw_markers(self, frame: np.ndarray) -> np.ndarray:
        """Detect markers and draw overlay information"""
        overlay_frame = frame.copy()

        # Convert to grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect markers
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.parameters)

        if ids is not None and len(ids) > 0:
            # Get the first detected marker
            marker_id = ids[0][0]
            marker_corners = corners[0]

            # Estimate pose
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                [marker_corners], self.marker_length,
                self.camera_manager.camera_matrix,
                self.camera_manager.dist_coeffs)

            rvec = rvecs[0][0]
            tvec = tvecs[0][0]

            # Calculate normalized position
            center = np.mean(marker_corners[0], axis=0)
            h, w = frame.shape[:2]
            norm_pos = (center[0] / w, center[1] / h)

            # Update detection state
            self.last_detection.update({
                'rvec': rvec.copy(),
                'tvec': tvec.copy(),
                'norm_pos': norm_pos,
                'marker_id': marker_id,
                'corners': marker_corners.copy()
            })

            # Call pose callback if set
            if self.pose_callback:
                try:
                    self.pose_callback(rvec, tvec, norm_pos, marker_id)
                except Exception as e:
                    self.log(f"Error in pose callback: {e}", "error")

            # Draw marker outline
            if self.show_markers:
                cv2.aruco.drawDetectedMarkers(overlay_frame, corners, ids)

            # Draw coordinate axes
            if self.show_axes:
                axes_length = self.marker_length * self.axes_length_factor
                cv2.drawFrameAxes(
                    overlay_frame,
                    self.camera_manager.camera_matrix,
                    self.camera_manager.dist_coeffs,
                    rvec, tvec, axes_length)

            # Draw pose information
            if self.show_pose_info:
                self._draw_pose_info(overlay_frame, rvec, tvec, norm_pos, marker_id)

            # Draw success status
            cv2.putText(overlay_frame, "Marker detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        else:
            # No marker detected
            self._clear_detection_state()
            cv2.putText(overlay_frame, "No marker detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        return overlay_frame

    def _draw_pose_info(self, frame: np.ndarray, rvec: np.ndarray, tvec: np.ndarray,
                        norm_pos: Tuple[float, float], marker_id: int):
        """Draw pose information text on frame"""
        y_offset = 60
        line_height = 25

        # Marker ID
        cv2.putText(frame, f"ID: {marker_id}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_offset += line_height

        # Translation vector
        cv2.putText(frame, f"Pos: {tvec[0]:.1f}, {tvec[1]:.1f}, {tvec[2]:.1f}",
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_offset += line_height

        # Rotation vector (as Euler angles)
        rotation_matrix, _ = cv2.Rodrigues(rvec)
        euler_angles = self._rotation_matrix_to_euler(rotation_matrix)
        cv2.putText(frame, f"Rot: {euler_angles[0]:.1f}°, {euler_angles[1]:.1f}°, {euler_angles[2]:.1f}°",
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_offset += line_height

        # Normalized position
        cv2.putText(frame, f"Norm: {norm_pos[0]:.3f}, {norm_pos[1]:.3f}",
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    def _rotation_matrix_to_euler(self, R: np.ndarray) -> Tuple[float, float, float]:
        """Convert rotation matrix to Euler angles (in degrees)"""
        # Extract Euler angles from rotation matrix
        sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])

        singular = sy < 1e-6

        if not singular:
            x = np.arctan2(R[2, 1], R[2, 2])
            y = np.arctan2(-R[2, 0], sy)
            z = np.arctan2(R[1, 0], R[0, 0])
        else:
            x = np.arctan2(-R[1, 2], R[1, 1])
            y = np.arctan2(-R[2, 0], sy)
            z = 0

        # Convert to degrees
        return (np.degrees(x), np.degrees(y), np.degrees(z))

    def _clear_detection_state(self):
        """Clear the detection state when no marker is found"""
        self.last_detection.update({
            'rvec': None,
            'tvec': None,
            'norm_pos': None,
            'marker_id': None,
            'corners': None
        })

    def _draw_calibration_warning(self, frame: np.ndarray) -> np.ndarray:
        """Draw calibration warning on frame"""
        overlay_frame = frame.copy()
        cv2.putText(overlay_frame, "Camera not calibrated", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(overlay_frame, "Load calibration to enable marker detection", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        return overlay_frame

    def _draw_error_message(self, frame: np.ndarray, error_msg: str) -> np.ndarray:
        """Draw error message on frame"""
        overlay_frame = frame.copy()
        cv2.putText(overlay_frame, "Marker detection error", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(overlay_frame, error_msg[:50], (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        return overlay_frame

    # Convenience methods for external access
    def get_current_pose(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[Tuple[float, float]]]:
        """Get current marker pose (rvec, tvec, norm_pos)"""
        detection = self.last_detection
        return detection['rvec'], detection['tvec'], detection['norm_pos']

    def get_current_marker_id(self) -> Optional[int]:
        """Get current detected marker ID"""
        return self.last_detection['marker_id']

    def is_marker_detected(self) -> bool:
        """Check if a marker is currently detected"""
        return self.last_detection['tvec'] is not None

    def get_marker_distance(self) -> Optional[float]:
        """Get distance to marker (if detected)"""
        tvec = self.last_detection['tvec']
        if tvec is not None:
            return np.linalg.norm(tvec)
        return None