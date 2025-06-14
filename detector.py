# aruco_detector_cli.py

import os
import cv2
import numpy as np
from typing import Tuple, List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class DetectionResult:
    """Container for ArUco detection results"""
    marker_corners: List[np.ndarray]
    marker_ids: np.ndarray
    rejected_candidates: List[np.ndarray]
    rvecs: Optional[np.ndarray] = None
    tvecs: Optional[np.ndarray] = None
    distances: Optional[List[float]] = None
    sizes: Optional[List[float]] = None


@dataclass
class CalibrationData:
    """Container for camera calibration data"""
    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray
    image_size: Tuple[int, int]
    calibration_error: float
    is_fisheye: bool = False


class UndistortionStrategy(ABC):
    """Abstract base class for undistortion strategies"""
    
    @abstractmethod
    def undistort(self, image: np.ndarray, calibration: CalibrationData) -> np.ndarray:
        pass
    
    @abstractmethod
    def get_optimal_camera_matrix(self, calibration: CalibrationData, alpha: float = 1.0) -> np.ndarray:
        pass


class StandardUndistortion(UndistortionStrategy):
    """Standard camera undistortion"""
    
    def undistort(self, image: np.ndarray, calibration: CalibrationData) -> np.ndarray:
        return cv2.undistort(image, calibration.camera_matrix, calibration.dist_coeffs)
    
    def get_optimal_camera_matrix(self, calibration: CalibrationData, alpha: float = 1.0) -> np.ndarray:
        h, w = calibration.image_size[1], calibration.image_size[0]
        new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(
            calibration.camera_matrix, calibration.dist_coeffs, (w, h), alpha, (w, h)
        )
        return new_camera_matrix


class FisheyeUndistortion(UndistortionStrategy):
    """Fisheye camera undistortion"""
    
    def undistort(self, image: np.ndarray, calibration: CalibrationData) -> np.ndarray:
        h, w = image.shape[:2]
        new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
            calibration.camera_matrix, calibration.dist_coeffs, (w, h), np.eye(3), balance=1.0
        )
        map1, map2 = cv2.fisheye.initUndistortRectifyMap(
            calibration.camera_matrix, calibration.dist_coeffs, np.eye(3), new_K, (w, h), cv2.CV_16SC2
        )
        return cv2.remap(image, map1, map2, interpolation=cv2.INTER_LINEAR)
    
    def get_optimal_camera_matrix(self, calibration: CalibrationData, alpha: float = 1.0) -> np.ndarray:
        h, w = calibration.image_size[1], calibration.image_size[0]
        return cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
            calibration.camera_matrix, calibration.dist_coeffs, (w, h), np.eye(3), balance=alpha
        )


class PoseEstimator:
    """Handles pose estimation for ArUco markers"""
    
    def __init__(self, marker_size: float):
        self.marker_size = marker_size
    
    def estimate_poses(self, corners: List[np.ndarray], ids: np.ndarray, 
                      calibration: CalibrationData) -> Tuple[np.ndarray, np.ndarray]:
        """Estimate poses for detected markers"""
        if calibration.is_fisheye:
            # For fisheye cameras, we need to handle pose estimation differently
            rvecs, tvecs = [], []
            for corner in corners:
                # Create object points for a single marker
                objp = np.array([
                    [-self.marker_size/2, self.marker_size/2, 0],
                    [self.marker_size/2, self.marker_size/2, 0],
                    [self.marker_size/2, -self.marker_size/2, 0],
                    [-self.marker_size/2, -self.marker_size/2, 0]
                ], dtype=np.float32)
                
                success, rvec, tvec = cv2.solvePnP(
                    objp, corner, calibration.camera_matrix, calibration.dist_coeffs
                )
                
                if success:
                    rvecs.append(rvec)
                    tvecs.append(tvec)
                else:
                    rvecs.append(np.zeros((3, 1)))
                    tvecs.append(np.zeros((3, 1)))
            
            return np.array(rvecs), np.array(tvecs)
        else:
            # Standard camera pose estimation
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                corners, self.marker_size, calibration.camera_matrix, calibration.dist_coeffs
            )
            return rvecs, tvecs
    
    def calculate_distances_and_sizes(self, tvecs: np.ndarray, rvecs: np.ndarray, 
                                    calibration: CalibrationData) -> Tuple[List[float], List[float]]:
        """Calculate distances and apparent sizes of markers"""
        distances = []
        apparent_sizes = []
        
        for i, tvec in enumerate(tvecs):
            # Distance is the magnitude of the translation vector
            distance = np.linalg.norm(tvec)
            distances.append(distance)
            
            # Calculate apparent size based on projection
            # Project the marker corners to image plane
            marker_3d_corners = np.array([
                [-self.marker_size/2, self.marker_size/2, 0],
                [self.marker_size/2, self.marker_size/2, 0],
                [self.marker_size/2, -self.marker_size/2, 0],
                [-self.marker_size/2, -self.marker_size/2, 0]
            ], dtype=np.float32)
            
            if calibration.is_fisheye:
                projected_corners, _ = cv2.fisheye.projectPoints(
                    marker_3d_corners.reshape(-1, 1, 3), rvecs[i], tvec, 
                    calibration.camera_matrix, calibration.dist_coeffs
                )
            else:
                projected_corners, _ = cv2.projectPoints(
                    marker_3d_corners, rvecs[i], tvec, 
                    calibration.camera_matrix, calibration.dist_coeffs
                )
            
            # Calculate size as average distance between adjacent corners
            projected_corners = projected_corners.reshape(-1, 2)
            side_lengths = []
            for j in range(4):
                p1 = projected_corners[j]
                p2 = projected_corners[(j + 1) % 4]
                side_lengths.append(np.linalg.norm(p1 - p2))
            
            apparent_size = np.mean(side_lengths)
            apparent_sizes.append(apparent_size)
        
        return distances, apparent_sizes


class ArUcoDetector:
    """Main ArUco detector class"""
    
    def __init__(self, calibration: CalibrationData, undistortion_strategy: UndistortionStrategy,
                 pose_estimator: PoseEstimator, dictionary=cv2.aruco.DICT_4X4_50):
        self.calibration = calibration
        self.undistortion_strategy = undistortion_strategy
        self.pose_estimator = pose_estimator
        
        # Initialize ArUco detector
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
        self.detector_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.detector_params)
    
    def detect_markers(self, image: np.ndarray, estimate_pose: bool = True) -> DetectionResult:
        """Detect ArUco markers in image"""
        # Convert to grayscale if needed
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Detect markers
        corners, ids, rejected = self.detector.detectMarkers(gray)
        
        result = DetectionResult(
            marker_corners=corners,
            marker_ids=ids,
            rejected_candidates=rejected
        )
        
        # Estimate poses if requested and markers found
        if estimate_pose and len(corners) > 0:
            rvecs, tvecs = self.pose_estimator.estimate_poses(corners, ids, self.calibration)
            distances, sizes = self.pose_estimator.calculate_distances_and_sizes(
                tvecs, rvecs, self.calibration
            )
            
            result.rvecs = rvecs
            result.tvecs = tvecs
            result.distances = distances
            result.sizes = sizes
        
        return result
    
    def undistort_image(self, image: np.ndarray) -> np.ndarray:
        """Undistort image using calibration data"""
        return self.undistortion_strategy.undistort(image, self.calibration)


class Visualizer:
    """Handles visualization of detection results"""
    
    @staticmethod
    def draw_markers(image: np.ndarray, result: DetectionResult, 
                    show_pose: bool = True, show_info: bool = True) -> np.ndarray:
        """Draw detected markers on image"""
        vis_image = image.copy()
        
        if len(result.marker_corners) == 0:
            return vis_image
        
        # Draw marker boundaries
        cv2.aruco.drawDetectedMarkers(vis_image, result.marker_corners, result.marker_ids)
        
        # Draw pose axes if available
        if show_pose and result.rvecs is not None and result.tvecs is not None:
            for i, (rvec, tvec) in enumerate(zip(result.rvecs, result.tvecs)):
                cv2.drawFrameAxes(vis_image, np.eye(3), np.zeros((4, 1)), rvec, tvec, 0.1)
        
        # Draw marker information
        if show_info and result.marker_ids is not None:
            for i, marker_id in enumerate(result.marker_ids.flatten()):
                # Get marker center
                corner = result.marker_corners[i][0]
                center = np.mean(corner, axis=0).astype(int)
                
                # Prepare info text
                info_lines = [f"ID: {marker_id}"]
                
                if result.distances and result.sizes:
                    distance = result.distances[i]
                    size = result.sizes[i]
                    info_lines.append(f"Dist: {distance:.3f}m")
                    info_lines.append(f"Size: {size:.1f}px")
                
                # Draw info background and text
                text_size = cv2.getTextSize(max(info_lines, key=len), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                bg_height = len(info_lines) * 20 + 10
                
                cv2.rectangle(vis_image, 
                            (center[0] - 5, center[1] - bg_height),
                            (center[0] + text_size[0] + 10, center[1] + 5),
                            (0, 0, 0), -1)
                
                for j, line in enumerate(info_lines):
                    cv2.putText(vis_image, line,
                              (center[0], center[1] - bg_height + 15 + j * 20),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return vis_image
    
    @staticmethod
    def draw_comparison(original: np.ndarray, undistorted: np.ndarray, 
                       result_orig: DetectionResult, result_undist: DetectionResult) -> np.ndarray:
        """Create side-by-side comparison of original and undistorted"""
        # Ensure both images are same size
        h, w = original.shape[:2]
        comparison = np.zeros((h, w * 2, 3), dtype=np.uint8)
        
        # Draw original with detections
        orig_vis = Visualizer.draw_markers(original, result_orig)
        comparison[:, :w] = orig_vis
        
        # Draw undistorted with detections
        undist_vis = Visualizer.draw_markers(undistorted, result_undist)
        comparison[:, w:] = undist_vis
        
        # Add labels
        cv2.putText(comparison, "Original + Distorted", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(comparison, "Undistorted + Corrected", (w + 10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        return comparison
    
    @staticmethod
    def draw_statistics_panel(image: np.ndarray, result: DetectionResult, 
                            calibration: CalibrationData, position: Tuple[int, int] = (10, 50)) -> np.ndarray:
        """Draw statistics panel on image"""
        vis_image = image.copy()
        x, y = position
        line_height = 25
        
        # Prepare statistics
        stats = [
            f"Markers detected: {len(result.marker_corners)}",
            f"Calibration error: {calibration.calibration_error:.4f}px",
            f"Camera type: {'Fisheye' if calibration.is_fisheye else 'Standard'}",
            f"Image size: {calibration.image_size[0]}x{calibration.image_size[1]}"
        ]
        
        if result.marker_ids is not None and len(result.marker_ids) > 0:
            marker_ids = result.marker_ids.flatten()
            stats.append(f"Marker IDs: {', '.join(map(str, marker_ids))}")
            
            if result.distances:
                avg_distance = np.mean(result.distances)
                stats.append(f"Avg distance: {avg_distance:.3f}m")
            
            if result.sizes:
                avg_size = np.mean(result.sizes)
                stats.append(f"Avg apparent size: {avg_size:.1f}px")
        
        # Draw background
        max_width = max(cv2.getTextSize(stat, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0][0] 
                       for stat in stats)
        bg_height = len(stats) * line_height + 20
        
        cv2.rectangle(vis_image, (x - 10, y - 15), 
                     (x + max_width + 20, y + bg_height - 15), (0, 0, 0), -1)
        cv2.rectangle(vis_image, (x - 10, y - 15), 
                     (x + max_width + 20, y + bg_height - 15), (255, 255, 255), 2)
        
        # Draw statistics
        for i, stat in enumerate(stats):
            cv2.putText(vis_image, stat, (x, y + i * line_height),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return vis_image


class CalibrationLoader:
    """Handles loading calibration data from files"""
    
    @staticmethod
    def load_from_npz(filename: str) -> CalibrationData:
        """Load calibration data from NPZ file"""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Calibration file not found: {filename}")
        
        data = np.load(filename)
        
        # Determine if fisheye based on distortion coefficients shape
        dist_coeffs = data["dist_coeffs"]
        is_fisheye = len(dist_coeffs.flatten()) == 4  # Fisheye has 4 coefficients
        
        return CalibrationData(
            camera_matrix=data["camera_matrix"],
            dist_coeffs=dist_coeffs,
            image_size=tuple(data["image_size"]),
            calibration_error=float(data["calibration_error"]),
            is_fisheye=is_fisheye
        )
    
    @staticmethod
    def list_calibration_files(directory: str = ".") -> List[str]:
        """List available calibration files in directory"""
        return [f for f in os.listdir(directory) if f.endswith('.npz')]


def get_user_inputs() -> Dict[str, Any]:
    """Get user inputs for detector configuration"""
    print("ArUco Detector Configuration")
    print("=" * 40)
    
    # List available calibration files
    cal_files = CalibrationLoader.list_calibration_files()
    if cal_files:
        print("Available calibration files:")
        for i, f in enumerate(cal_files):
            print(f"  {i+1}. {f}")
        
        file_choice = input(f"Select calibration file (1-{len(cal_files)}) or enter path: ")
        
        try:
            file_idx = int(file_choice) - 1
            if 0 <= file_idx < len(cal_files):
                calibration_file = cal_files[file_idx]
            else:
                raise ValueError()
        except ValueError:
            calibration_file = file_choice
    else:
        calibration_file = input("Enter path to calibration file (.npz): ")
    
    # Marker size
    marker_size = float(input("Enter marker size in meters [0.05]: ") or "0.05")
    
    # Input source
    input_source = input("Input source - (c)amera, (i)mage, or (v)ideo? [c]: ").lower() or 'c'
    
    camera_id = 0
    image_path = ""
    video_path = ""
    
    if input_source.startswith('c'):
        camera_id = int(input("Camera ID [0]: ") or "0")
    elif input_source.startswith('i'):
        image_path = input("Enter image path: ")
    elif input_source.startswith('v'):
        video_path = input("Enter video path: ")
    
    # Display options
    show_comparison = input("Show original vs undistorted comparison? (y/n) [y]: ").lower()
    show_comparison = show_comparison == "" or show_comparison.startswith('y')
    
    show_statistics = input("Show detection statistics? (y/n) [y]: ").lower()
    show_statistics = show_statistics == "" or show_statistics.startswith('y')
    
    return {
        'calibration_file': calibration_file,
        'marker_size': marker_size,
        'input_source': input_source,
        'camera_id': camera_id,
        'image_path': image_path,
        'video_path': video_path,
        'show_comparison': show_comparison,
        'show_statistics': show_statistics
    }


class DetectorCLI:
    """Main CLI application for ArUco detection"""
    
    def __init__(self, detector: ArUcoDetector, visualizer: Visualizer):
        self.detector = detector
        self.visualizer = visualizer
    
    def run_camera_detection(self, camera_id: int, show_comparison: bool, show_statistics: bool):
        """Run real-time camera detection"""
        cap = cv2.VideoCapture(camera_id)
        
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_id}")
        
        print(f"\nRunning real-time detection on camera {camera_id}")
        print("Controls:")
        print("  'q' - quit")
        print("  's' - save current frame")
        print("  'c' - toggle comparison view")
        print("  'i' - toggle statistics")
        
        frame_count = 0
        show_comp = show_comparison
        show_stats = show_statistics
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Detect on original image
            result_orig = self.detector.detect_markers(frame)
            
            # Create undistorted image and detect
            undistorted = self.detector.undistort_image(frame)
            result_undist = self.detector.detect_markers(undistorted)
            
            # Create visualization
            if show_comp:
                display_image = self.visualizer.draw_comparison(
                    frame, undistorted, result_orig, result_undist
                )
            else:
                display_image = self.visualizer.draw_markers(undistorted, result_undist)
            
            # Add statistics if requested
            if show_stats:
                display_image = self.visualizer.draw_statistics_panel(
                    display_image, result_undist, self.detector.calibration
                )
            
            cv2.imshow("ArUco Detection", display_image)
            
            # Handle key presses
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"detection_{timestamp}.jpg"
                cv2.imwrite(filename, display_image)
                print(f"Saved frame to {filename}")
            elif key == ord('c'):
                show_comp = not show_comp
                print(f"Comparison view: {'ON' if show_comp else 'OFF'}")
            elif key == ord('i'):
                show_stats = not show_stats
                print(f"Statistics: {'ON' if show_stats else 'OFF'}")
        
        cap.release()
        cv2.destroyAllWindows()
    
    def run_image_detection(self, image_path: str, show_comparison: bool, show_statistics: bool):
        """Run detection on single image"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Cannot load image: {image_path}")
        
        print(f"\nProcessing image: {image_path}")
        
        # Detect on original image
        result_orig = self.detector.detect_markers(image)
        
        # Create undistorted image and detect
        undistorted = self.detector.undistort_image(image)
        result_undist = self.detector.detect_markers(undistorted)
        
        # Print detection results
        self._print_detection_results(result_orig, result_undist)
        
        # Create visualization
        if show_comparison:
            display_image = self.visualizer.draw_comparison(
                image, undistorted, result_orig, result_undist
            )
        else:
            display_image = self.visualizer.draw_markers(undistorted, result_undist)
        
        # Add statistics if requested
        if show_statistics:
            display_image = self.visualizer.draw_statistics_panel(
                display_image, result_undist, self.detector.calibration
            )
        
        cv2.imshow("ArUco Detection - Press any key to close", display_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    def run_video_detection(self, video_path: str, show_comparison: bool, show_statistics: bool):
        """Run detection on video file"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        
        print(f"\nProcessing video: {video_path}")
        print("Controls:")
        print("  'q' - quit")
        print("  ' ' (space) - pause/resume")
        print("  's' - save current frame")
        
        paused = False
        frame_count = 0
        
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    print("End of video reached")
                    break
                frame_count += 1
            
            # Detect on original image
            result_orig = self.detector.detect_markers(frame)
            
            # Create undistorted image and detect
            undistorted = self.detector.undistort_image(frame)
            result_undist = self.detector.detect_markers(undistorted)
            
            # Create visualization
            if show_comparison:
                display_image = self.visualizer.draw_comparison(
                    frame, undistorted, result_orig, result_undist
                )
            else:
                display_image = self.visualizer.draw_markers(undistorted, result_undist)
            
            # Add statistics if requested
            if show_statistics:
                display_image = self.visualizer.draw_statistics_panel(
                    display_image, result_undist, self.detector.calibration
                )
            
            # Add frame counter and pause indicator
            status_text = f"Frame: {frame_count}"
            if paused:
                status_text += " [PAUSED]"
            
            cv2.putText(display_image, status_text, (10, display_image.shape[0] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow("ArUco Detection - Video", display_image)
            
            # Handle key presses
            key = cv2.waitKey(30 if not paused else 0) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):
                paused = not paused
                print(f"{'Paused' if paused else 'Resumed'}")
            elif key == ord('s'):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"video_frame_{frame_count}_{timestamp}.jpg"
                cv2.imwrite(filename, display_image)
                print(f"Saved frame to {filename}")
        
        cap.release()
        cv2.destroyAllWindows()
    
    def _print_detection_results(self, result_orig: DetectionResult, result_undist: DetectionResult):
        """Print detailed detection results"""
        print("\n" + "="*50)
        print("DETECTION RESULTS")
        print("="*50)
        
        print(f"Original image - Markers detected: {len(result_orig.marker_corners)}")
        print(f"Undistorted image - Markers detected: {len(result_undist.marker_corners)}")
        
        if result_undist.marker_ids is not None and len(result_undist.marker_ids) > 0:
            print("\nDetailed marker information (undistorted):")
            for i, marker_id in enumerate(result_undist.marker_ids.flatten()):
                print(f"  Marker ID {marker_id}:")
                if result_undist.distances and result_undist.sizes:
                    print(f"    Distance: {result_undist.distances[i]:.3f} m")
                    print(f"    Apparent size: {result_undist.sizes[i]:.1f} pixels")
                
                if result_undist.tvecs is not None:
                    tvec = result_undist.tvecs[i].flatten()
                    print(f"    Position (x,y,z): ({tvec[0]:.3f}, {tvec[1]:.3f}, {tvec[2]:.3f})")


def main():
    """Main application entry point"""
    try:
        # Get user configuration
        config = get_user_inputs()
        
        # Load calibration data
        print(f"\nLoading calibration from: {config['calibration_file']}")
        calibration = CalibrationLoader.load_from_npz(config['calibration_file'])
        
        print(f"Loaded calibration:")
        print(f"  Camera type: {'Fisheye' if calibration.is_fisheye else 'Standard'}")
        print(f"  Image size: {calibration.image_size}")
        print(f"  Calibration error: {calibration.calibration_error:.4f} pixels")
        
        # Create strategy objects based on camera type
        if calibration.is_fisheye:
            undistortion_strategy = FisheyeUndistortion()
        else:
            undistortion_strategy = StandardUndistortion()
        
        pose_estimator = PoseEstimator(config['marker_size'])
        
        # Create detector
        detector = ArUcoDetector(calibration, undistortion_strategy, pose_estimator, cv2.aruco.DICT_6X6_50)
        visualizer = Visualizer()
        
        # Create and run CLI
        cli = DetectorCLI(detector, visualizer)
        
        # Run appropriate detection mode
        if config['input_source'].startswith('c'):
            cli.run_camera_detection(
                config['camera_id'], 
                config['show_comparison'], 
                config['show_statistics']
            )
        elif config['input_source'].startswith('i'):
            cli.run_image_detection(
                config['image_path'], 
                config['show_comparison'], 
                config['show_statistics']
            )
        elif config['input_source'].startswith('v'):
            cli.run_video_detection(
                config['video_path'], 
                config['show_comparison'], 
                config['show_statistics']
            )
        
    except KeyboardInterrupt:
        print("\nDetection interrupted by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()