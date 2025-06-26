"""
Camera Display Widget
Handles camera feed display and marker visualization
"""

import tkinter as tk
import cv2
import numpy as np
from PIL import Image, ImageTk
from typing import Optional, Callable


class CameraDisplay:
    """Widget for displaying camera feed with marker detection overlay"""

    def __init__(self, parent, camera_manager, logger: Optional[Callable] = None):
        self.parent = parent
        self.camera_manager = camera_manager
        self.logger = logger

        # Display state
        self.camera_running = False
        self.current_frame = None
        self.marker_length = 20.0

        # Create canvas
        self.canvas = tk.Canvas(parent, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def start_feed(self):
        """Start camera feed display"""
        self.camera_running = True
        self._update_feed()

    def stop_feed(self):
        """Stop camera feed display"""
        self.camera_running = False

    def set_marker_length(self, length: float):
        """Set marker length for pose detection"""
        self.marker_length = length

    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the current camera frame"""
        return self.current_frame.copy() if self.current_frame is not None else None

    def _update_feed(self):
        """Update camera feed display"""
        if not self.camera_running:
            return

        frame = self.camera_manager.capture_frame()
        if frame is not None:
            self.current_frame = frame.copy()

            # Try to detect markers and annotate frame
            display_frame = self._process_frame(frame)

            # Display the frame
            self._display_frame(display_frame)

        # Schedule next update
        self.parent.after(50, self._update_feed)

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process frame with marker detection and annotation"""
        try:
            rvec, tvec, norm_pos, annotated_frame = self.camera_manager.detect_marker_pose(
                frame, self.marker_length)

            if tvec is not None:
                # Draw marker info
                cv2.putText(annotated_frame, "Marker detected", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(annotated_frame, f"Pos: {tvec.flatten()}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                return annotated_frame
            else:
                cv2.putText(frame, "No marker detected", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                return frame

        except Exception as e:
            self.log(f"Marker detection error: {e}", "error")
            cv2.putText(frame, "Detection error", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            return frame

    def _display_frame(self, frame: np.ndarray):
        """Display frame on canvas with proper scaling"""
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)

        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width > 1 and canvas_height > 1:
            # Scale image to fit canvas while maintaining aspect ratio
            pil_image = self._scale_image(pil_image, canvas_width, canvas_height)

        # Convert to PhotoImage and display
        photo = ImageTk.PhotoImage(pil_image)
        self.canvas.delete("all")

        # Center the image on the canvas
        x_offset = (canvas_width - pil_image.width) // 2
        y_offset = (canvas_height - pil_image.height) // 2
        self.canvas.create_image(
            x_offset + pil_image.width // 2,
            y_offset + pil_image.height // 2,
            image=photo
        )

        # Keep a reference to prevent garbage collection
        self.canvas.image = photo

    def _scale_image(self, image: Image.Image, canvas_width: int, canvas_height: int) -> Image.Image:
        """Scale image to fit canvas while maintaining aspect ratio"""
        img_aspect = image.width / image.height
        canvas_aspect = canvas_width / canvas_height

        if img_aspect > canvas_aspect:
            # Image is wider than canvas
            new_width = canvas_width
            new_height = int(canvas_width / img_aspect)
        else:
            # Image is taller than canvas
            new_height = canvas_height
            new_width = int(canvas_height * img_aspect)

        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def capture_marker_pose(self) -> tuple:
        """
        Capture current marker pose
        Returns (rvec, tvec, norm_pos) or (None, None, None) if no marker detected
        """
        if self.current_frame is None:
            return None, None, None

        try:
            return self.camera_manager.detect_marker_pose(self.current_frame, self.marker_length)[:3]
        except Exception as e:
            self.log(f"Failed to capture marker pose: {e}", "error")
            return None, None, None