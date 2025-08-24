"""
Enhanced Marker Detection Overlay with Crosshair
Handles ArUco marker detection and pose estimation as an overlay component
Added crosshair functionality to help center markers with camera
"""

from typing import Optional, Callable, Tuple

import cv2
import numpy as np

from services.overlays.overlay_interface import FrameOverlay


class MarkerDetectionOverlay(FrameOverlay):
    """Overlay component for ArUco marker detection and pose visualization with crosshair"""

    def __init__(self, camera_manager, marker_length: float = 15.0,
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
        self.show_crosshair = True  # NEW: Crosshair visibility toggle
        self.axes_length_factor = 0.5  # Axes length as factor of marker length

        # Crosshair settings
        self.crosshair_size = 20  # Half-length of crosshair lines
        self.crosshair_thickness = 2
        self.crosshair_color = (0, 255, 255)  # Yellow color (BGR)
        self.crosshair_center_dot_size = 3
        self.crosshair_center_dot_color = (0, 0, 255)  # Red color (BGR)

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

    def set_crosshair_visibility(self, show_crosshair: bool):
        """Toggle crosshair display"""
        self.show_crosshair = show_crosshair
        self.log(f"Crosshair visibility set to: {show_crosshair}")

    def set_crosshair_size(self, size: int):
        """Set crosshair line length (half-length from center)"""
        self.crosshair_size = max(5, size)
        self.log(f"Crosshair size set to: {self.crosshair_size}")

    def set_crosshair_color(self, color: Tuple[int, int, int]):
        """Set crosshair color (BGR format)"""
        self.crosshair_color = color

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

        # Always draw crosshair first (even without calibration)
        overlay_frame = frame.copy()
        if self.show_crosshair:
            self._draw_crosshair(overlay_frame)

        # Check if camera is calibrated for marker detection
        if (self.camera_manager.camera_matrix is None or
                self.camera_manager.dist_coeffs is None):
            return self._draw_calibration_warning(overlay_frame)

        try:
            return self._detect_and_draw_markers(overlay_frame)
        except Exception as e:
            self.log(f"Error in marker detection overlay: {e}", "error")
            return self._draw_error_message(overlay_frame, str(e))

    def _draw_crosshair(self, frame: np.ndarray):
        """Draw crosshair at frame center to help align markers"""
        h, w = frame.shape[:2]
        center_x, center_y = w // 2, h // 2

        # Draw horizontal line
        cv2.line(frame,
                (center_x - self.crosshair_size, center_y),
                (center_x + self.crosshair_size, center_y),
                self.crosshair_color, self.crosshair_thickness)

        # Draw vertical line
        cv2.line(frame,
                (center_x, center_y - self.crosshair_size),
                (center_x, center_y + self.crosshair_size),
                self.crosshair_color, self.crosshair_thickness)

        # Draw center dot
        cv2.circle(frame, (center_x, center_y),
                  self.crosshair_center_dot_size,
                  self.crosshair_center_dot_color, -1)

    def _detect_and_draw_markers(self, frame: np.ndarray) -> np.ndarray:
        """Detect markers and draw overlay information"""
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
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)

            # Draw coordinate axes
            if self.show_axes:
                axes_length = self.marker_length * self.axes_length_factor
                cv2.drawFrameAxes(
                    frame,
                    self.camera_manager.camera_matrix,
                    self.camera_manager.dist_coeffs,
                    rvec, tvec, axes_length)

            # Draw pose information
            if self.show_pose_info:
                self._draw_pose_info(frame, rvec, tvec, norm_pos, marker_id)

            # Draw success status with centering help
            cv2.putText(frame, "Marker detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Show centering guidance
            self._draw_centering_guidance(frame, center, (w//2, h//2))

        else:
            # No marker detected
            self._clear_detection_state()
            cv2.putText(frame, "No marker detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(frame, "Position marker at crosshair", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        return frame

    def _draw_centering_guidance(self, frame: np.ndarray, marker_center: np.ndarray, frame_center: Tuple[int, int]):
        """Draw guidance to help center the marker"""
        marker_x, marker_y = int(marker_center[0]), int(marker_center[1])
        center_x, center_y = frame_center

        # Calculate offset
        offset_x = marker_x - center_x
        offset_y = marker_y - center_y
        distance = np.sqrt(offset_x**2 + offset_y**2)

        # Draw line from center to marker center
        cv2.line(frame, (center_x, center_y), (marker_x, marker_y), (255, 255, 0), 2)

        # Show centering status
        if distance < 30:  # Well centered
            status_text = "CENTERED"
            status_color = (0, 255, 0)  # Green
        elif distance < 80:  # Close to center
            status_text = "CLOSE"
            status_color = (0, 255, 255)  # Yellow
        else:  # Needs adjustment
            status_text = "ADJUST POSITION"
            status_color = (0, 0, 255)  # Red

        cv2.putText(frame, status_text, (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)

        # Show offset values
        offset_text = f"Offset: ({offset_x:+.0f}, {offset_y:+.0f})"
        cv2.putText(frame, offset_text, (10, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    def _draw_pose_info(self, frame: np.ndarray, rvec: np.ndarray, tvec: np.ndarray,
                       norm_pos: Tuple[float, float], marker_id: int):
        """Draw pose information on frame"""
        # Position text
        y_offset = 180
        line_height = 25

        # Marker ID
        cv2.putText(frame, f"Marker ID: {marker_id}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += line_height

        # Translation vector (position)
        cv2.putText(frame, f"Position: ({tvec[0]:.1f}, {tvec[1]:.1f}, {tvec[2]:.1f})",
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += line_height

        # Normalized position
        cv2.putText(frame, f"Norm Pos: ({norm_pos[0]:.3f}, {norm_pos[1]:.3f})",
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += line_height

        # Distance from camera
        distance = np.linalg.norm(tvec)
        cv2.putText(frame, f"Distance: {distance:.1f}mm",
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    def _clear_detection_state(self):
        """Clear detection state when no marker is found"""
        self.last_detection.update({
            'rvec': None,
            'tvec': None,
            'norm_pos': None,
            'marker_id': None,
            'corners': None
        })

    def _draw_calibration_warning(self, frame: np.ndarray) -> np.ndarray:
        """Draw calibration warning on frame"""
        cv2.putText(frame, "Camera not calibrated", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(frame, "Load calibration to enable marker detection", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        cv2.putText(frame, "Crosshair shows camera center", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        return frame

    def _draw_error_message(self, frame: np.ndarray, error_msg: str) -> np.ndarray:
        """Draw error message on frame"""
        cv2.putText(frame, "Marker detection error", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame, error_msg[:50], (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        return frame

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

    def get_centering_status(self) -> dict:
        """Get marker centering status relative to crosshair"""
        if not self.is_marker_detected():
            return {'centered': False, 'distance': None, 'offset': None}

        corners = self.last_detection['corners']
        if corners is None:
            return {'centered': False, 'distance': None, 'offset': None}

        # Calculate marker center
        marker_center = np.mean(corners[0], axis=0)

        # Get frame dimensions (assuming standard camera resolution)
        # In real usage, this should be passed or obtained from camera
        frame_center = (320, 240)  # Default for 640x480

        offset_x = marker_center[0] - frame_center[0]
        offset_y = marker_center[1] - frame_center[1]
        distance = np.sqrt(offset_x**2 + offset_y**2)

        return {
            'centered': distance < 30,
            'distance': distance,
            'offset': (offset_x, offset_y),
            'status': 'CENTERED' if distance < 30 else ('CLOSE' if distance < 80 else 'ADJUST POSITION')
        }