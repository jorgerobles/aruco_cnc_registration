# Fix for services/overlays/marker_detection_overlay.py
# This overlay likely has array boolean context issues too

import cv2
import numpy as np
from typing import Optional, Callable, Tuple


class MarkerDetectionOverlay:
    """Fixed MarkerDetectionOverlay - no more array boolean context errors"""

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
        self.axes_length_factor = 0.5

        # Detection state
        self.last_detection = {
            'rvec': None,
            'tvec': None,
            'norm_pos': None,
            'marker_id': None,
            'corners': None
        }

        self.pose_callback = None

    def apply_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Apply marker detection overlay - FIXED array boolean context"""
        if not self.visible:
            return frame

        # FIX: Proper None and array validation
        if frame is None or frame.size == 0:
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
        """Detect markers and draw overlay - FIXED all array boolean issues"""
        overlay_frame = frame.copy()

        # Convert to grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect markers
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.parameters)

        # FIX: Proper array validation instead of direct boolean check
        if ids is not None and len(ids) > 0:
            # Get the first detected marker
            marker_id = ids[0][0]
            marker_corners = corners[0]

            # FIX: Validate corners array properly
            if marker_corners is not None and marker_corners.size > 0:
                try:
                    # Estimate pose
                    rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                        [marker_corners], self.marker_length,
                        self.camera_manager.camera_matrix,
                        self.camera_manager.dist_coeffs)

                    # FIX: Validate pose estimation results
                    if rvecs is not None and tvecs is not None and len(rvecs) > 0 and len(tvecs) > 0:
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
                
                except Exception as e:
                    self.log(f"Error in pose estimation: {e}", "error")
                    # Clear detection state on error
                    self._clear_detection_state()
        else:
            # No marker detected
            self._clear_detection_state()
            cv2.putText(overlay_frame, "No marker detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        return overlay_frame

    def _draw_pose_info(self, frame: np.ndarray, rvec: np.ndarray, tvec: np.ndarray, 
                       norm_pos: Tuple[float, float], marker_id: int):
        """Draw pose information on frame - FIXED array handling"""
        try:
            # FIX: Validate arrays before using them
            if rvec is not None and tvec is not None:
                distance = np.linalg.norm(tvec)
                
                info_text = [
                    f"ID: {marker_id}",
                    f"Dist: {distance:.1f}mm",
                    f"Pos: ({norm_pos[0]:.2f}, {norm_pos[1]:.2f})",
                    f"XYZ: ({tvec[0]:.1f}, {tvec[1]:.1f}, {tvec[2]:.1f})"
                ]

                y_offset = 60
                for i, text in enumerate(info_text):
                    cv2.putText(frame, text, (10, y_offset + i * 25),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        except Exception as e:
            self.log(f"Error drawing pose info: {e}", "error")

    def _clear_detection_state(self):
        """Clear detection state when no marker is found"""
        self.last_detection.update({
            'rvec': None,
            'tvec': None,
            'norm_pos': None,
            'marker_id': None,
            'corners': None
        })

    def is_marker_detected(self) -> bool:
        """Check if a marker is currently detected - FIXED"""
        # FIX: Proper None check instead of array boolean evaluation
        return self.last_detection['tvec'] is not None

    def get_marker_distance(self) -> Optional[float]:
        """Get distance to marker - FIXED array handling"""
        tvec = self.last_detection['tvec']
        # FIX: Proper validation before using numpy operations
        if tvec is not None and tvec.size > 0:
            return np.linalg.norm(tvec)
        return None

    def get_current_pose(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[Tuple[float, float]]]:
        """Get current marker pose - FIXED array handling"""
        detection = self.last_detection
        return detection['rvec'], detection['tvec'], detection['norm_pos']

    def set_visibility(self, visible: bool):
        """Toggle overlay visibility"""
        self.visible = visible

    def is_visible(self) -> bool:
        """Check if overlay is visible"""
        return self.visible

    def set_marker_length(self, length: float):
        """Set marker length for pose estimation"""
        self.marker_length = length
        if self.logger:
            self.logger(f"Marker length set to: {length}")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

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


# KEY FIXES APPLIED:
# 1. All "if array:" changed to "if array is not None and array.size > 0:"
# 2. All "if corners:" changed to "if corners is not None and len(corners) > 0:"
# 3. All "if ids:" changed to "if ids is not None and len(ids) > 0:"
# 4. Added proper validation before numpy operations
# 5. Fixed marker detection boolean logic
# 6. Added exception handling for array operations