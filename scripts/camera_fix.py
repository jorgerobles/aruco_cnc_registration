#!/usr/bin/env python3
# camera_debug_fix.py
"""
Debug and fix camera connection issues
Helps identify why camera disconnects immediately after connecting
"""

import cv2
import numpy as np
import time
import threading
from pathlib import Path


def test_camera_basic(camera_id=0):
    """Basic camera test to see what's happening"""
    print(f"Testing camera {camera_id}...")

    try:
        # Test different backends
        backends = [
            ("Default", cv2.CAP_ANY),
            ("DirectShow (Windows)", cv2.CAP_DSHOW),
            ("V4L2 (Linux)", cv2.CAP_V4L2),
        ]

        for name, backend in backends:
            print(f"\nTrying {name} backend:")
            try:
                cap = cv2.VideoCapture(camera_id, backend)
                if cap.isOpened():
                    print(f"  ✓ Camera opened with {name}")

                    # Try to read a frame
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        h, w = frame.shape[:2]
                        print(f"  ✓ Frame captured: {w}x{h}")

                        # Try multiple frames
                        for i in range(5):
                            ret, frame = cap.read()
                            if ret:
                                print(f"  ✓ Frame {i + 1}: OK")
                            else:
                                print(f"  ❌ Frame {i + 1}: Failed")
                                break
                            time.sleep(0.1)
                    else:
                        print(f"  ❌ Could not read frame")

                    cap.release()
                    print(f"  ✓ Camera released")
                    return True
                else:
                    print(f"  ❌ Could not open camera with {name}")
            except Exception as e:
                print(f"  ❌ Error with {name}: {e}")

        return False

    except Exception as e:
        print(f"❌ Camera test failed: {e}")
        return False


def test_capture_thread_stability(camera_id=0):
    """Test if capture thread works stably"""
    print(f"\nTesting capture thread stability for camera {camera_id}...")

    try:
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            print("❌ Could not open camera")
            return False

        print("✓ Camera opened")

        # Set properties
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        frame_count = 0
        failed_count = 0
        start_time = time.time()

        print("Testing frame capture for 5 seconds...")

        while time.time() - start_time < 5.0:
            ret, frame = cap.read()
            if ret and frame is not None:
                frame_count += 1
                if frame_count % 30 == 0:  # Print every 30th frame
                    print(f"  Captured {frame_count} frames...")
            else:
                failed_count += 1
                if failed_count > 10:
                    print(f"  ❌ Too many failed reads ({failed_count})")
                    break

            time.sleep(0.033)  # ~30 FPS

        cap.release()

        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0

        print(f"✓ Captured {frame_count} frames in {elapsed:.1f}s ({fps:.1f} FPS)")
        print(f"  Failed reads: {failed_count}")

        return failed_count < frame_count * 0.1  # Less than 10% failure rate

    except Exception as e:
        print(f"❌ Capture thread test failed: {e}")
        return False


def create_fixed_camera_manager():
    """Create a fixed version of the camera manager with better error handling"""

    content = '''# services/camera_manager_fixed.py
"""
Fixed Camera Manager with improved error handling and debugging
"""

import cv2
import numpy as np
import platform
import threading
import time
from typing import Optional, Dict, Any, Tuple

from store.actions import CameraActions
from store.store import ApplicationStore


def get_optimal_camera_backend():
    """Get the optimal camera backend for current platform"""
    system = platform.system().lower()
    if system == "windows":
        return cv2.CAP_DSHOW
    elif system == "linux":
        return cv2.CAP_V4L2
    elif system == "darwin":  # macOS
        return cv2.CAP_AVFOUNDATION
    else:
        return cv2.CAP_ANY


class CameraEvents:
    """Legacy CameraEvents for backward compatibility"""
    CONNECTED = "camera.connected"
    DISCONNECTED = "camera.disconnected"
    FRAME_CAPTURED = "camera.frame_captured"
    ERROR = "camera.error"
    CALIBRATION_LOADED = "camera.calibration_loaded"
    FOV_CALCULATED = "camera.fov_calculated"
    FOV_UPDATED = "camera.fov_updated"


class CameraManager:
    """Fixed camera manager with improved error handling"""

    def __init__(self, store: ApplicationStore, camera_id=0, resolution=(640, 480), enable_capture_thread=True):
        self.store = store
        self.camera_id = camera_id
        self.cap = None
        self.camera_matrix = None
        self.dist_coeffs = None
        self.resolution = resolution
        self._is_connected = False

        # Capture thread
        self._capture_thread = None
        self._capture_running = False
        self._enable_capture_thread = enable_capture_thread

        # Debug/monitoring
        self._frame_count = 0
        self._error_count = 0
        self._last_frame_time = 0

        # ArUco setup
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_parameters = cv2.aruco.DetectorParameters()

    def connect(self) -> bool:
        """Connect with improved error handling and debugging"""
        try:
            print(f"[CameraManager] Attempting to connect to camera {self.camera_id}")

            # Disconnect if already connected
            if self.is_connected:
                print("[CameraManager] Already connected, disconnecting first")
                self.disconnect()

            # Try optimal backend first
            optimal_backend = get_optimal_camera_backend()
            print(f"[CameraManager] Trying optimal backend: {optimal_backend}")

            self.cap = cv2.VideoCapture(self.camera_id, optimal_backend)

            if not self.cap.isOpened():
                print("[CameraManager] Optimal backend failed, trying default")
                self.cap = cv2.VideoCapture(self.camera_id)

            success = self.cap.isOpened()
            print(f"[CameraManager] Camera opened: {success}")

            if success:
                # Configure camera
                rw, rh = self.resolution
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, rw)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, rh)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                print(f"[CameraManager] Camera configured: {rw}x{rh}")

                # Test capture multiple times
                test_success = False
                for attempt in range(3):
                    print(f"[CameraManager] Test capture attempt {attempt + 1}")
                    ret, test_frame = self.cap.read()
                    if ret and test_frame is not None:
                        print(f"[CameraManager] Test frame: {test_frame.shape}")
                        test_success = True
                        break
                    else:
                        print(f"[CameraManager] Test capture failed: ret={ret}")
                        time.sleep(0.1)

                if test_success:
                    self._is_connected = True
                    print("[CameraManager] Connection successful")

                    if self._enable_capture_thread:
                        self._start_capture_thread()
                    else:
                        print("[CameraManager] Capture thread disabled")
                else:
                    print("[CameraManager] Test captures failed")
                    success = False
                    self._is_connected = False
                    self.cap.release()
                    self.cap = None

            # Dispatch to store
            self.store.dispatch(CameraActions.connection_changed(success, self.camera_id))
            print(f"[CameraManager] Connection result: {success}")
            return success

        except Exception as e:
            print(f"[CameraManager] Connection error: {e}")
            self.store.dispatch(CameraActions.connection_changed(False, self.camera_id))
            self._is_connected = False
            return False

    def disconnect(self) -> bool:
        """Disconnect with improved cleanup"""
        try:
            print("[CameraManager] Disconnecting...")

            # Stop capture thread first
            self._stop_capture_thread()

            # Release camera
            if self.cap:
                self.cap.release()
                self.cap = None
                print("[CameraManager] Camera released")

            was_connected = self._is_connected
            self._is_connected = False

            if was_connected:
                self.store.dispatch(CameraActions.connection_changed(False, self.camera_id))
                print("[CameraManager] Disconnection dispatched to store")

            return True

        except Exception as e:
            print(f"[CameraManager] Disconnect error: {e}")
            return False

    def _start_capture_thread(self):
        """Start capture thread with better error handling"""
        if not self._enable_capture_thread:
            return

        if self._capture_thread and self._capture_thread.is_alive():
            print("[CameraManager] Capture thread already running")
            return

        print("[CameraManager] Starting capture thread")
        self._capture_running = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

    def _stop_capture_thread(self):
        """Stop capture thread with timeout"""
        if not self._capture_running:
            return

        print("[CameraManager] Stopping capture thread")
        self._capture_running = False

        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
            if self._capture_thread.is_alive():
                print("[CameraManager] Warning: Capture thread did not stop cleanly")

    def _capture_loop(self):
        """Improved capture loop with better error handling"""
        print("[CameraManager] Capture loop started")
        consecutive_failures = 0
        max_consecutive_failures = 10

        while self._capture_running and self.is_connected:
            try:
                if not self.cap or not self.cap.isOpened():
                    print("[CameraManager] Camera not available in capture loop")
                    break

                ret, frame = self.cap.read()

                if ret and frame is not None:
                    # Reset failure counter
                    consecutive_failures = 0
                    self._frame_count += 1
                    self._last_frame_time = time.time()

                    # Detect markers (simplified)
                    marker_data = self._detect_markers_simple(frame)

                    # Dispatch to store
                    self.store.dispatch(CameraActions.frame_updated(frame.copy(), marker_data))

                    # Log progress occasionally
                    if self._frame_count % 100 == 0:
                        print(f"[CameraManager] Captured {self._frame_count} frames")

                    time.sleep(0.033)  # ~30fps

                else:
                    consecutive_failures += 1
                    self._error_count += 1

                    print(f"[CameraManager] Frame capture failed: {consecutive_failures}/{max_consecutive_failures}")

                    if consecutive_failures >= max_consecutive_failures:
                        print("[CameraManager] Too many consecutive failures, disconnecting")
                        break

                    time.sleep(0.1)  # Wait before retry

            except Exception as e:
                print(f"[CameraManager] Capture loop error: {e}")
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    break
                time.sleep(0.1)

        # Cleanup on exit
        if self._is_connected:
            print("[CameraManager] Capture loop ended, disconnecting")
            self._is_connected = False
            self.store.dispatch(CameraActions.connection_changed(False, self.camera_id))

    def _detect_markers_simple(self, frame: np.ndarray) -> Optional[Dict]:
        """Simplified marker detection"""
        try:
            # Skip marker detection on most frames for performance
            if self._frame_count % 5 != 0:
                return None

            corners, ids, _ = cv2.aruco.detectMarkers(frame, self.aruco_dict, parameters=self.aruco_parameters)

            if ids is not None and len(corners) > 0:
                return {
                    'markers_detected': len(ids),
                    'marker_ids': ids.flatten().tolist(),
                    'marker_corners': [corner.tolist() for corner in corners]
                }
            return None

        except Exception as e:
            print(f"[CameraManager] Marker detection error: {e}")
            return None

    @property
    def is_connected(self) -> bool:
        """Check if camera is connected"""
        return self._is_connected and self.cap is not None and self.cap.isOpened()

    def load_calibration(self, calibration_file_path: str) -> bool:
        """Load calibration with error handling"""
        try:
            calibration_data = np.load(calibration_file_path)
            self.camera_matrix = calibration_data['camera_matrix']
            self.dist_coeffs = calibration_data['dist_coeffs']

            self.store.dispatch(CameraActions.calibration_loaded(True, calibration_file_path))
            print(f"[CameraManager] Calibration loaded: {calibration_file_path}")
            return True

        except Exception as e:
            print(f"[CameraManager] Calibration load error: {e}")
            self.store.dispatch(CameraActions.calibration_loaded(False, calibration_file_path))
            return False

    def set_camera_id(self, camera_id: int) -> bool:
        """Set camera ID with reconnection if needed"""
        try:
            was_connected = self.is_connected
            if was_connected:
                self.disconnect()

            self.camera_id = camera_id

            if was_connected:
                return self.connect()

            return True

        except Exception as e:
            print(f"[CameraManager] Set camera ID error: {e}")
            return False

    def set_resolution(self, width: int, height: int) -> bool:
        """Set camera resolution"""
        try:
            if self.cap and self.is_connected:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            self.resolution = (width, height)
            print(f"[CameraManager] Resolution set: {width}x{height}")
            return True

        except Exception as e:
            print(f"[CameraManager] Set resolution error: {e}")
            return False

    def get_frame_sync(self) -> Optional[np.ndarray]:
        """Get frame synchronously"""
        if not self.cap or not self._is_connected:
            return None

        try:
            ret, frame = self.cap.read()
            return frame if ret else None
        except Exception as e:
            print(f"[CameraManager] Sync frame error: {e}")
            return None

    def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information"""
        info = {
            "camera_id": self.camera_id,
            "connected": self.is_connected,
            "calibrated": self.camera_matrix is not None and self.dist_coeffs is not None,
            "resolution": self.resolution,
            "frame_count": self._frame_count,
            "error_count": self._error_count
        }

        if self.is_connected and self.cap:
            try:
                info.update({
                    "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "fps": self.cap.get(cv2.CAP_PROP_FPS)
                })
            except Exception:
                pass

        return info

    def is_calibrated(self) -> bool:
        """Check if camera is calibrated"""
        return self.camera_matrix is not None and self.dist_coeffs is not None

    def get_calibration(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Get calibration matrices"""
        return self.camera_matrix, self.dist_coeffs
'''

    # Write the fixed camera manager
    with open("services/camera_manager_fixed.py", 'w', encoding='utf-8') as f:
        f.write(content)

    print("✓ Created fixed camera manager: services/camera_manager_fixed.py")


def main():
    """Run camera diagnosis and create fixes"""
    print("Camera Debug and Fix Tool")
    print("=" * 30)

    # Test basic camera functionality
    camera_works = test_camera_basic(0)

    if camera_works:
        print("\n✅ Basic camera test passed")

        # Test capture thread stability
        stable = test_capture_thread_stability(0)

        if stable:
            print("\n✅ Capture thread test passed")
        else:
            print("\n⚠️ Capture thread is unstable")
    else:
        print("\n❌ Basic camera test failed")

    # Create fixed camera manager
    print("\nCreating fixed camera manager...")
    create_fixed_camera_manager()

    print("\n" + "=" * 50)
    print("RECOMMENDATIONS:")

    if camera_works:
        print("✓ Your camera hardware is working")
        print("✓ The issue is likely in the capture thread or error handling")
        print("\nTo fix:")
        print("1. Replace services/camera_manager.py with services/camera_manager_fixed.py")
        print("2. Or copy the improved error handling from the fixed version")
        print("3. The fixed version has better debugging and error recovery")
    else:
        print("❌ Camera hardware issues detected")
        print("\nTroubleshooting:")
        print("1. Make sure camera is not used by another application")
        print("2. Try different camera IDs (0, 1, 2, etc.)")
        print("3. Check camera drivers")
        print("4. Try different USB ports")

    print("\nThe fixed camera manager includes:")
    print("- Better error messages and debugging")
    print("- Improved capture thread stability")
    print("- Better handling of connection failures")
    print("- Configurable error tolerance")


if __name__ == '__main__':
    main()