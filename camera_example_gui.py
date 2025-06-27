from gui import CameraDisplay
import tkinter as tk

if __name__ == "__main__":
    import os

    def simple_logger(message, level="info"):
        print(f"[{level.upper()}] {message}")

    # Optional: path to calibration file (must contain 'camera_matrix' and 'dist_coeffs')
    CALIBRATION_FILE = "calibration_data.npz"  # Change or comment out if not available

    # Setup GUI
    root = tk.Tk()
    root.title("Camera Marker Display")

    # Create CameraManager instance
    from camera_manager import CameraManager
    cam_manager = CameraManager()

    if not cam_manager.connect():
        print("Failed to open camera.")
        exit(1)

    # Load calibration if available
    if os.path.exists(CALIBRATION_FILE):
        cam_manager.load_calibration(CALIBRATION_FILE)
    else:
        print(f"Calibration file not found: {CALIBRATION_FILE}")

    # Setup display
    display = CameraDisplay(root, cam_manager, logger=simple_logger)
    display.set_marker_length(20.0)
    display.start_feed()

    # Run application
    root.protocol("WM_DELETE_WINDOW", lambda: (display.stop_feed(), cam_manager.disconnect(), root.destroy()))
    root.mainloop()
