# Working gui/camera_display_store.py - Get frames directly from camera manager

import tkinter as tk
from typing import Optional, Callable
import threading
import time
import cv2
import numpy as np
from PIL import Image, ImageTk

from store.store import ApplicationStore
from store.state import ApplicationState


class CameraDisplayStore:
    """Working camera display - direct frame access"""

    def __init__(self, parent: tk.Widget, store: ApplicationStore, camera_manager=None,
                 logger: Optional[Callable] = None):
        self.parent = parent
        self.store = store
        self.camera_manager = camera_manager
        self.logger = logger

        # UI elements
        self.canvas = None
        self.status_label = None
        self._current_image = None

        # Overlays
        self._overlays = {}

        # Display control
        self._running = False
        self._display_thread = None

        # Create UI
        self._create_widgets()

        # Subscribe to store for connection status only
        self._unsubscribe = self.store.subscribe(self._on_store_change)

        # Check initial connection state
        self._check_initial_connection()

        self.log("Working camera display with direct frame access initialized")

    def set_camera_manager(self, camera_manager):
        """Set camera manager"""
        self.camera_manager = camera_manager
        self.log("Camera manager set")

    def inject_overlay(self, name: str, overlay):
        """Inject overlay"""
        self._overlays[name] = overlay
        self.log(f"Overlay '{name}' injected")

    def _create_widgets(self):
        """Create UI widgets"""
        main_frame = tk.Frame(self.parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Status label
        self.status_label = tk.Label(
            main_frame,
            text="Camera: Disconnected",
            font=("TkDefaultFont", 9, "bold"),
            fg="red"
        )
        self.status_label.pack(pady=(0, 5))

        # Canvas for display
        self.canvas = tk.Canvas(
            main_frame,
            bg='black',
            width=640,
            height=480
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def _check_initial_connection(self):
        """Check initial connection state"""
        state = self.store.get_state()
        if state.camera.connected:
            self._start_display()
        else:
            self._stop_display()

    def _on_store_change(self, state: ApplicationState):
        """Handle store state changes - only for connection status"""
        camera_state = state.camera

        # Update connection status
        if camera_state.connected:
            self.status_label.config(
                text=f"Camera {camera_state.camera_id}: Connected",
                fg="green"
            )
            if not self._running:
                self._start_display()
        else:
            self.status_label.config(
                text="Camera: Disconnected",
                fg="red"
            )
            self._stop_display()
            self._clear_display()

    def _start_display(self):
        """Start display thread"""
        if self._running:
            return

        self._running = True
        self._display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self._display_thread.start()
        self.log("Display thread started")

    def _stop_display(self):
        """Stop display thread"""
        self._running = False
        if self._display_thread and self._display_thread.is_alive():
            # Give thread more time to stop and don't wait if it hangs
            try:
                self._display_thread.join(timeout=0.5)
                if self._display_thread.is_alive():
                    self.log("Display thread did not stop cleanly", "warning")
            except Exception:
                pass
        self._display_thread = None
        self.log("Display thread stopped")

    def _display_loop(self):
        """Main display loop - gets frames directly from camera manager"""
        while self._running:
            try:
                # Check if still running before trying to get frame
                if not self._running:
                    break

                if self.camera_manager and hasattr(self.camera_manager, 'get_frame_sync'):
                    # Get frame directly from camera manager
                    frame = self.camera_manager.get_frame_sync()

                    if frame is not None and hasattr(frame, 'shape'):
                        # Only schedule UI update if still running
                        if self._running:
                            self.parent.after(0, lambda f=frame.copy(): self._display_frame(f))

                time.sleep(0.033)  # ~30 FPS

            except Exception as e:
                # Don't log errors during shutdown
                if self._running:
                    self.log(f"Error in display loop: {e}", "error")
                time.sleep(0.1)

        self.log("Display loop exited")

    def _display_frame(self, frame):
        """Display frame with overlays"""
        try:
            if not isinstance(frame, np.ndarray):
                return

            # Apply overlays
            display_frame = frame.copy()
            for name, overlay in self._overlays.items():
                try:
                    if hasattr(overlay, 'apply_overlay'):
                        display_frame = overlay.apply_overlay(display_frame)
                except Exception as e:
                    self.log(f"Overlay '{name}' error: {e}", "error")

            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)

            # Fit to canvas
            canvas_width = self.canvas.winfo_width() or 640
            canvas_height = self.canvas.winfo_height() or 480

            # Scale to fit
            pil_image.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)

            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(pil_image)

            # Display
            self.canvas.delete("all")
            self.canvas.create_image(
                canvas_width // 2,
                canvas_height // 2,
                image=photo
            )

            # Keep reference
            self._current_image = photo

        except Exception as e:
            self.log(f"Display error: {e}", "error")

    def _clear_display(self):
        """Clear display"""
        self.canvas.delete("all")
        canvas_width = self.canvas.winfo_width() or 640
        canvas_height = self.canvas.winfo_height() or 480

        self.canvas.create_text(
            canvas_width // 2,
            canvas_height // 2,
            text="No Camera Feed",
            fill="white",
            font=("Arial", 16)
        )

    def stop_feed(self):
        """Stop camera feed (compatibility with old CameraDisplay)"""
        self._stop_display()

    def start_feed(self):
        """Start camera feed (compatibility with old CameraDisplay)"""
        state = self.store.get_state()
        if state.camera.connected:
            self._start_display()

    def cleanup(self):
        """Cleanup - call this before camera manager disconnect"""
        self.log("Starting cleanup...")

        # Stop display thread first
        self._stop_display()

        # Clear UI
        try:
            self._clear_display()
        except:
            pass

        # Unsubscribe from store
        if self._unsubscribe:
            try:
                self._unsubscribe()
                self._unsubscribe = None
            except:
                pass

        # Clear references
        self._current_image = None
        self.camera_manager = None

        self.log("Cleanup completed")

    def log(self, message: str, level: str = "info"):
        """Log message"""
        if self.logger:
            self.logger(f"[CameraDisplay] {message}", level)