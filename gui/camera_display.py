"""
Camera Display Widget with Dependency Injection
Handles camera feed display and marker visualization
Uses dependency injection for overlay components
Using @event_aware decorator for clean event handling
"""

import tkinter as tk
import cv2
import numpy as np
from PIL import Image, ImageTk
from typing import Optional, Callable, List, Tuple, Dict, Type

from services.event_broker import (event_aware, event_handler, EventPriority)
from services.events import CameraEvents
from services.overlays.overlay_interface import FrameOverlay


@event_aware()
class CameraDisplay:
    """Widget for displaying camera feed with marker detection and pluggable overlays"""

    def __init__(self, parent, camera_manager,
                 logger: Optional[Callable] = None):
        self.parent = parent
        self.camera_manager = camera_manager
        self.logger = logger

        # Display state
        self.camera_running = False
        self.current_frame = None

        # Overlay management
        self._overlays: Dict[str, FrameOverlay] = {}

        # Create canvas
        self.canvas = tk.Canvas(parent, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Event handlers are automatically registered by @event_aware decorator

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    # Event handlers using decorators
    @event_handler(CameraEvents.DISCONNECTED, EventPriority.HIGH)
    def _on_camera_disconnected(self):
        """Handle camera disconnection"""
        self.stop_feed()
        self.log("Camera disconnected - stopping feed", "info")

    @event_handler(CameraEvents.ERROR)
    def _on_camera_error(self, error_message: str):
        """Handle camera errors"""
        self.log(f"Camera error in display: {error_message}", "error")

    @event_handler(CameraEvents.FRAME_CAPTURED)
    def _on_frame_captured(self, frame: np.ndarray):
        """Handle new frame from camera (optional use)"""
        # Could be used for additional processing or overlays
        pass

    # Dependency injection methods
    def inject_overlay(self, name: str, overlay: FrameOverlay):
        """
        Inject a frame overlay component

        Args:
            name: Unique identifier for the overlay
            overlay: Overlay component implementing FrameOverlay interface
        """
        self._overlays[name] = overlay
        self.log(f"Injected overlay: {name}")

    def remove_overlay(self, name: str):
        """
        Remove an overlay component

        Args:
            name: Identifier of the overlay to remove
        """
        if name in self._overlays:
            self._overlays.pop(name)
            self.log(f"Removed overlay: {name}")

    def get_overlay(self, name: str) -> Optional[FrameOverlay]:
        """
        Get an overlay component by name

        Args:
            name: Identifier of the overlay

        Returns:
            Overlay component or None if not found
        """
        return self._overlays.get(name)

    def list_overlays(self) -> List[str]:
        """Get list of injected overlay names"""
        return list(self._overlays.keys())

    # Generic overlay management methods
    def set_overlay_visibility(self, overlay_name: str, visible: bool):
        """Set visibility for a specific overlay"""
        overlay = self._overlays.get(overlay_name)
        if overlay:
            overlay.set_visibility(visible)
        else:
            raise ValueError(f"Overlay '{overlay_name}' not found")

    def get_overlay_visibility(self, overlay_name: str) -> bool:
        """Get visibility status for a specific overlay"""
        overlay = self._overlays.get(overlay_name)
        if overlay:
            return overlay.is_visible()
        else:
            raise ValueError(f"Overlay '{overlay_name}' not found")

    def toggle_overlay_visibility(self, overlay_name: str):
        """Toggle visibility for a specific overlay"""
        overlay = self._overlays.get(overlay_name)
        if overlay:
            overlay.set_visibility(not overlay.is_visible())
        else:
            raise ValueError(f"Overlay '{overlay_name}' not found")



    def start_feed(self):
        """Start camera feed display"""
        if not self.camera_manager.is_connected:
            self.log("Cannot start feed - camera not connected", "error")
            return

        self.camera_running = True
        self.log("Starting camera feed", "info")
        self._update_feed()

    def stop_feed(self):
        """Stop camera feed display"""
        if self.camera_running:
            self.camera_running = False

            # Clear the canvas
            self.canvas.delete("all")
            self._show_disconnected_message()

    def _show_disconnected_message(self):
        """Show disconnected message on canvas"""
        try:
            self.canvas.update_idletasks()
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:
                self.canvas.create_text(
                    canvas_width // 2,
                    canvas_height // 2,
                    text="Camera Disconnected",
                    fill="white",
                    font=("Arial", 16)
                )
        except:
            pass  # Canvas might not be ready

    def set_marker_length(self, length: float):
        """Set marker length for pose detection - DEPRECATED: Use MarkerDetectionOverlay instead"""
        # Keep for backward compatibility but log deprecation warning
        self.log("set_marker_length is deprecated. Use MarkerDetectionOverlay.set_marker_length() instead", "warning")

    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the current camera frame"""
        return self.current_frame.copy() if self.current_frame is not None else None

    def _update_feed(self):
        """Update camera feed display"""
        if not self.camera_running:
            return

        if not self.camera_manager.is_connected:
            self.log("Camera disconnected during feed", "error")
            self.stop_feed()
            return

        try:
            frame = self.camera_manager.capture_frame()
            if frame is not None:
                self.current_frame = frame.copy()

                # Process frame (basic processing only - overlays handle their own features)
                display_frame = self._process_frame(frame)

                # Apply all overlays in order
                display_frame = self._apply_overlays(display_frame)

                # Display the frame
                self._display_frame(display_frame)
            else:
                # No frame captured - camera might be disconnected
                if self.camera_running:
                    self.log("No frame captured - stopping feed", "error")
                    self.stop_feed()
                    return

        except Exception as e:
            self.log(f"Error in feed update: {e}", "error")

        # Schedule next update if still running
        if self.camera_running:
            self.parent.after(50, self._update_feed)

    def _apply_overlays(self, frame: np.ndarray) -> np.ndarray:
        """Apply all injected overlays to the frame"""
        result_frame = frame

        for name, overlay in self._overlays.items():
            try:
                if overlay.is_visible():
                    result_frame = overlay.apply_overlay(result_frame)
            except Exception as e:
                self.log(f"Error applying overlay '{name}': {e}", "error")

        return result_frame

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process frame - basic processing only, overlays handle specific features"""
        # Just return the frame as-is
        # Any processing like marker detection is now handled by overlays
        return frame

    def _display_frame(self, frame: np.ndarray):
        """Display frame on canvas with proper scaling"""
        try:
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)

            # Ensure canvas is ready
            self.canvas.update_idletasks()
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            # Use default size if canvas not ready
            if canvas_width <= 1 or canvas_height <= 1:
                canvas_width, canvas_height = 640, 480

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

        except Exception as e:
            self.log(f"Error displaying frame: {e}", "error")

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

    # Generic overlay utility methods
    def has_overlay_type(self, overlay_type: type) -> bool:
        """Check if any overlay of the specified type is injected"""
        return any(isinstance(overlay, overlay_type) for overlay in self._overlays.values())

    def get_overlays_of_type(self, overlay_type: type) -> List[FrameOverlay]:
        """Get all overlays of the specified type"""
        return [overlay for overlay in self._overlays.values() if isinstance(overlay, overlay_type)]

    def get_overlay_names_of_type(self, overlay_type: type) -> List[str]:
        """Get names of all overlays of the specified type"""
        return [name for name, overlay in self._overlays.items() if isinstance(overlay, overlay_type)]