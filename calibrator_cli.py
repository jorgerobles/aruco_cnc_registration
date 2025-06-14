# charuco_calibrator_cli.py

import os
import time
import cv2
import numpy as np
from datetime import datetime
from typing import List, Tuple
from board_manager import CharucoBoardManager
from calibration_strategy import StandardCalibration, FisheyeCalibration
from charuco_calibrator import CharucoCalibrator



def get_user_inputs():
    camera_type = input("Camera type - (s)tandard or (f)isheye? [s]: ").lower() or 's'
    fisheye = camera_type.startswith('f')
    strategy = FisheyeCalibration() if fisheye else StandardCalibration()

    camera_id = int(input("Camera ID (0 for default): ") or "0")

    workflow = input("Workflow - (l)ive capture+calibration or (e)xisting images? [l]: ").lower() or 'l'

    board_config = {
        "squares_x": int(input("Number of squares in X direction [10]: ") or 10),
        "squares_y": int(input("Number of squares in Y direction [7]: ") or 7),
        "square_length": float(input("Square length in meters [0.015]: ") or 0.015),
        "marker_length": float(input("Marker length in meters [0.011]: ") or 0.011),
    }

    target_images = int(input("Number of calibration images to capture [15]: ") or "15")
    
    # Only ask for folder if using existing images workflow
    folder = ""
    if workflow.startswith('e'):
        folder = input("Path to calibration images folder: ")
    
    # Generate default filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    camera_type_str = "fisheye" if fisheye else "standard"
    default_filename = f"calibration_{camera_type_str}_{timestamp}.npz"
    
    save_file = input(f"Enter filename to save [{default_filename}] (leave empty to skip saving): ")
    if save_file == "":
        # User pressed enter - check if they want to use default or skip
        use_default = input(f"Use default filename '{default_filename}'? (y/n) [y]: ").lower()
        if use_default == "" or use_default.startswith('y'):
            save_file = default_filename
        else:
            save_file = None  # Skip saving
    elif save_file.lower() in ['n', 'no', 'skip']:
        save_file = None  # Skip saving
    
    # New autocapture options
    use_autocapture = input("Use autocapture? (y/n) [n]: ").lower().startswith('y')
    autocapture_delay = 2.0
    if use_autocapture:
        autocapture_delay = float(input("Autocapture delay in seconds [2.0]: ") or "2.0")

    return strategy, fisheye, camera_id, workflow, board_config, target_images, folder, save_file, use_autocapture, autocapture_delay
class CoverageTracker:
    """Tracks coverage of calibration patterns across the image for better calibration quality"""
    
    def __init__(self, image_size: Tuple[int, int], grid_size: Tuple[int, int] = (8, 6)):
        self.image_size = image_size  # (width, height)
        self.grid_size = grid_size    # (cols, rows)
        
        # Create coverage map: grid_size is (cols, rows) but numpy array is (rows, cols)
        self.coverage_map = np.zeros((grid_size[1], grid_size[0]), dtype=np.int16)
        
        self.cell_width = image_size[0] / grid_size[0]
        self.cell_height = image_size[1] / grid_size[1]
        
        print(f"Coverage tracker initialized:")
        print(f"  Image size: {image_size}")
        print(f"  Grid size: {grid_size} (cols x rows)")
        print(f"  Coverage map shape: {self.coverage_map.shape}")
        print(f"  Cell size: {self.cell_width:.1f} x {self.cell_height:.1f}")
    
    def update_coverage(self, corners: np.ndarray):
        """Update coverage based on detected corners"""
        if corners is None or len(corners) == 0:
            return
        
        for corner in corners:
            x, y = corner[0]  # corner is in format [[x, y]]
            
            # Calculate grid indices with safer bounds checking
            grid_x = int(x / self.cell_width)
            grid_y = int(y / self.cell_height)
            
            # Double-check bounds - ensure we don't exceed array dimensions
            if (grid_x < 0 or grid_x >= self.grid_size[0] or 
                grid_y < 0 or grid_y >= self.grid_size[1]):
                continue  # Skip invalid coordinates
            
            # Safe addition with bounds checking
            current_val = int(self.coverage_map[grid_y, grid_x])
            new_val = min(255, current_val + 30)
            self.coverage_map[grid_y, grid_x] = new_val
    
    def get_coverage_percentage(self) -> float:
        """Get percentage of image covered by calibration patterns"""
        covered_cells = np.sum(self.coverage_map > 0)
        total_cells = self.coverage_map.shape[0] * self.coverage_map.shape[1]
        return (covered_cells / total_cells) * 100
    
    def draw_coverage_overlay(self, image: np.ndarray) -> np.ndarray:
        """Draw coverage overlay on image"""
        overlay = image.copy()
        
        # Iterate through the coverage map properly
        for row in range(self.coverage_map.shape[0]):  # rows
            for col in range(self.coverage_map.shape[1]):  # cols
                x1 = int(col * self.cell_width)
                y1 = int(row * self.cell_height)
                x2 = int((col + 1) * self.cell_width)
                y2 = int((row + 1) * self.cell_height)
                
                coverage_val = int(self.coverage_map[row, col])
                if coverage_val > 0:
                    # Green overlay for covered areas - ensure value is within uint8 range
                    green_intensity = min(255, max(0, coverage_val))
                    color = (0, green_intensity, 0)
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        
        # Blend overlay with original image
        return cv2.addWeighted(image, 0.7, overlay, 0.3, 0)

class FocusAnalyzer:
    """Analyzes image focus quality for better calibration results"""
    
    @staticmethod
    def calculate_sharpness(image: np.ndarray, corners: np.ndarray = None) -> float:
        """Calculate image sharpness using Laplacian variance"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        if corners is not None and len(corners) > 0:
            # Focus on regions around detected corners for more accurate assessment
            mask = np.zeros(gray.shape, dtype=np.uint8)
            for corner in corners:
                x, y = int(corner[0][0]), int(corner[0][1])
                # Create circular regions around corners
                cv2.circle(mask, (x, y), 30, 255, -1)
            
            # Apply mask to focus analysis on corner regions
            masked_gray = cv2.bitwise_and(gray, gray, mask=mask)
            laplacian = cv2.Laplacian(masked_gray, cv2.CV_64F)
            # Only consider non-zero regions
            non_zero_mask = mask > 0
            if np.any(non_zero_mask):
                return laplacian[non_zero_mask].var()
        
        # Fallback to full image analysis
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return laplacian.var()
    
    @staticmethod
    def assess_focus_quality(sharpness: float) -> Tuple[str, str]:
        """Assess focus quality based on sharpness value"""
        if sharpness > 1000:
            return "EXCELLENT", "green"
        elif sharpness > 500:
            return "GOOD", "yellow"
        elif sharpness > 200:
            return "ACCEPTABLE", "orange"
        else:
            return "POOR - BLURRY", "red"
    
    @staticmethod
    def draw_focus_indicator(image: np.ndarray, sharpness: float, 
                           position: Tuple[int, int] = (50, 200)) -> np.ndarray:
        """Draw focus quality indicator on image"""
        quality, color_name = FocusAnalyzer.assess_focus_quality(sharpness)
        
        # Color mapping
        color_map = {
            "green": (0, 255, 0),
            "yellow": (0, 255, 255),
            "orange": (0, 165, 255),
            "red": (0, 0, 255)
        }
        color = color_map.get(color_name, (255, 255, 255))
        
        x, y = position
        
        # Background rectangle
        cv2.rectangle(image, (x-5, y-20), (x+250, y+5), (0, 0, 0), -1)
        cv2.rectangle(image, (x-5, y-20), (x+250, y+5), color, 2)
        
        # Focus text
        text = f"Focus: {quality} ({sharpness:.0f})"
        cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return image
    
class QualityTracker:
    """Tracks overall quality metrics for calibration assessment"""
    
    def __init__(self):
        self.focus_scores = []
        self.corner_counts = []
        self.blurry_images = 0
        self.excellent_images = 0
    
    def add_measurement(self, sharpness: float, corner_count: int):
        """Add quality measurement for an image"""
        self.focus_scores.append(sharpness)
        self.corner_counts.append(corner_count)
        
        quality, _ = FocusAnalyzer.assess_focus_quality(sharpness)
        if quality == "POOR - BLURRY":
            self.blurry_images += 1
        elif quality == "EXCELLENT":
            self.excellent_images += 1
    
    def get_quality_summary(self) -> dict:
        """Get overall quality summary"""
        if not self.focus_scores:
            return {}
        
        avg_sharpness = np.mean(self.focus_scores)
        min_sharpness = np.min(self.focus_scores)
        max_sharpness = np.max(self.focus_scores)
        avg_corners = np.mean(self.corner_counts)
        
        total_images = len(self.focus_scores)
        blurry_percentage = (self.blurry_images / total_images) * 100
        excellent_percentage = (self.excellent_images / total_images) * 100
        
        overall_quality, _ = FocusAnalyzer.assess_focus_quality(avg_sharpness)
        
        return {
            "total_images": total_images,
            "avg_sharpness": avg_sharpness,
            "min_sharpness": min_sharpness,
            "max_sharpness": max_sharpness,
            "avg_corners": avg_corners,
            "blurry_images": self.blurry_images,
            "blurry_percentage": blurry_percentage,
            "excellent_images": self.excellent_images,
            "excellent_percentage": excellent_percentage,
            "overall_quality": overall_quality
        }
    """Handles progress display and visual feedback"""
    
    @staticmethod
    def draw_progress_bar(image: np.ndarray, current: int, total: int, 
                         position: Tuple[int, int] = (50, 50), 
                         size: Tuple[int, int] = (300, 20)) -> np.ndarray:
        """Draw progress bar on image"""
        x, y = position
        width, height = size
        
        # Background
        cv2.rectangle(image, (x, y), (x + width, y + height), (50, 50, 50), -1)
        cv2.rectangle(image, (x, y), (x + width, y + height), (255, 255, 255), 2)
        
        # Progress fill
        if total > 0:
            progress_width = int((current / total) * width)
            cv2.rectangle(image, (x + 2, y + 2), (x + progress_width - 2, y + height - 2), (0, 255, 0), -1)
        
        # Text
        text = f"{current}/{total}"
        font_scale = 0.6
        thickness = 1
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
        text_x = x + (width - text_size[0]) // 2
        text_y = y + (height + text_size[1]) // 2
        cv2.putText(image, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
        
        return image
    
    @staticmethod
    def draw_info_panel(image: np.ndarray, info_dict: dict, position: Tuple[int, int] = (50, 100)) -> np.ndarray:
        """Draw information panel on image"""
        x, y = position
        line_height = 25
        font_scale = 0.6
        thickness = 1
        
        for i, (key, value) in enumerate(info_dict.items()):
            text = f"{key}: {value}"
            text_y = y + i * line_height
            cv2.putText(image, text, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
        
        return image

class ProgressDisplay:
    """Handles progress display and visual feedback"""
    
    @staticmethod
    def draw_progress_bar(image: np.ndarray, current: int, total: int, 
                         position: Tuple[int, int] = (50, 50), 
                         size: Tuple[int, int] = (300, 20)) -> np.ndarray:
        """Draw progress bar on image"""
        x, y = position
        width, height = size
        
        # Background
        cv2.rectangle(image, (x, y), (x + width, y + height), (50, 50, 50), -1)
        cv2.rectangle(image, (x, y), (x + width, y + height), (255, 255, 255), 2)
        
        # Progress fill
        if total > 0:
            progress_width = int((current / total) * width)
            cv2.rectangle(image, (x + 2, y + 2), (x + progress_width - 2, y + height - 2), (0, 255, 0), -1)
        
        # Text
        text = f"{current}/{total}"
        font_scale = 0.6
        thickness = 1
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
        text_x = x + (width - text_size[0]) // 2
        text_y = y + (height + text_size[1]) // 2
        cv2.putText(image, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
        
        return image
    
    @staticmethod
    def draw_info_panel(image: np.ndarray, info_dict: dict, position: Tuple[int, int] = (50, 100)) -> np.ndarray:
        """Draw information panel on image"""
        x, y = position
        line_height = 25
        font_scale = 0.6
        thickness = 1
        
        for i, (key, value) in enumerate(info_dict.items()):
            text = f"{key}: {value}"
            text_y = y + i * line_height
            cv2.putText(image, text, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
        
        return image


class CalibratorCLI:
    def __init__(self, strategy, fisheye, board_config, use_autocapture=False, autocapture_delay=2.0):
        board_manager = CharucoBoardManager(
            squares_x=board_config["squares_x"],
            squares_y=board_config["squares_y"],
            square_length=board_config["square_length"],
            marker_length=board_config["marker_length"]
        )
        self.calibrator = CharucoCalibrator(board_manager, strategy)
        self.fisheye = fisheye
        self.use_autocapture = use_autocapture
        self.autocapture_delay = autocapture_delay
        self.coverage_tracker = None
        self.quality_tracker = QualityTracker()
        self.last_capture_time = 0

    def run(self, camera_id, workflow, target_images, folder, save_file):
        if workflow.startswith('l'):
            self.live_capture_flow(camera_id, target_images)
        else:
            self.image_folder_flow(folder)
        self.perform_calibration(save_file)

    def live_capture_flow(self, camera_id, target_images):
        cap = cv2.VideoCapture(camera_id)
        
        # Get initial frame to determine image size
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture initial frame")
            return
        
        image_size = (frame.shape[1], frame.shape[0])  # (width, height)
        self.coverage_tracker = CoverageTracker(image_size)

        os.makedirs("captures", exist_ok=True)
        count = 0
        
        print(f"\nStarting live capture...")
        print(f"Target: {target_images} images")
        if self.use_autocapture:
            print(f"Autocapture enabled (delay: {self.autocapture_delay}s)")
        print("Controls:")
        print("  'q' - quit")
        print("  'c' - manual capture (good focus required)")
        print("  'f' - force capture (even if blurry)")
        print("  's' - toggle coverage overlay")
        
        show_coverage = False
        
        while count < target_images:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Create a copy for detection/visualization (this will be modified)
            display_frame = frame.copy()
            
            # Detect board on the display copy (with visualization)
            corners, ids = self.calibrator.board_manager.detect(display_frame, visualize=True)
            
            # Calculate focus quality using original frame
            current_sharpness = 0
            if corners is not None and len(corners) > 0:
                current_sharpness = FocusAnalyzer.calculate_sharpness(frame, corners)
            
            # Update coverage tracker
            if corners is not None:
                self.coverage_tracker.update_coverage(corners)
            
            # Check if we should capture
            should_capture = False
            capture_reason = ""
            focus_quality, _ = FocusAnalyzer.assess_focus_quality(current_sharpness)
            
            if corners is not None and len(corners) >= 6:
                current_time = time.time()
                
                # Only capture if focus is acceptable or better
                if focus_quality not in ["POOR - BLURRY"]:
                    if self.use_autocapture:
                        if current_time - self.last_capture_time >= self.autocapture_delay:
                            should_capture = True
                            capture_reason = "AUTO"
                            self.last_capture_time = current_time
            
            # Manual capture check
            key = cv2.waitKey(1) & 0xFF
            if key == ord('c') and corners is not None and len(corners) >= 6:
                if focus_quality not in ["POOR - BLURRY"]:
                    should_capture = True
                    capture_reason = "MANUAL"
                else:
                    print("Warning: Image too blurry for capture. Improve focus first.")
            elif key == ord('f') and corners is not None and len(corners) >= 6:
                # Force capture even if blurry (with warning)
                should_capture = True
                capture_reason = "FORCED"
                print("Warning: Forced capture of blurry image!")
            elif key == ord('s'):
                show_coverage = not show_coverage
            elif key == ord('q'):
                break
            
            # Capture image if needed (using original frame without overlays)
            if should_capture:
                filename = f"captures/img_{count:03d}.jpg"
                cv2.imwrite(filename, frame)  # Save original frame without overlays
                self.calibrator.add_image(frame)  # Add original frame to calibrator
                
                # Track quality metrics
                self.quality_tracker.add_measurement(current_sharpness, len(corners))
                
                count += 1
                print(f"Captured {filename} ({capture_reason}) - Coverage: {self.coverage_tracker.get_coverage_percentage():.1f}% - Focus: {focus_quality}")
            
            # Add coverage overlay if requested (on display_frame which already has detection overlays)
            if show_coverage and self.coverage_tracker:
                display_frame = self.coverage_tracker.draw_coverage_overlay(display_frame)
            
            # Add focus indicator
            if corners is not None and len(corners) > 0:
                display_frame = FocusAnalyzer.draw_focus_indicator(display_frame, current_sharpness)
            
            # Add progress bar
            display_frame = ProgressDisplay.draw_progress_bar(display_frame, count, target_images)
            
            # Add info panel
            info_dict = {
                "Detected corners": len(corners) if corners is not None else 0,
                "Coverage": f"{self.coverage_tracker.get_coverage_percentage():.1f}%",
                "Focus": f"{focus_quality} ({current_sharpness:.0f})",
                "Mode": "AUTO" if self.use_autocapture else "MANUAL"
            }
            
            if corners is not None and len(corners) >= 6:
                if focus_quality == "POOR - BLURRY":
                    info_dict["Status"] = "BLURRY - IMPROVE FOCUS"
                else:
                    info_dict["Status"] = "READY"
                    # Add countdown for autocapture
                    if self.use_autocapture:
                        time_since_last = time.time() - self.last_capture_time
                        remaining = max(0, self.autocapture_delay - time_since_last)
                        if remaining > 0:
                            info_dict["Next capture"] = f"{remaining:.1f}s"
            else:
                info_dict["Status"] = "SEARCHING"
            
            display_frame = ProgressDisplay.draw_info_panel(display_frame, info_dict)
            
            # Status indicator (now includes focus state)
            if corners is not None and len(corners) >= 6:
                if focus_quality == "POOR - BLURRY":
                    status_color = (0, 0, 255)  # Red for blurry
                else:
                    status_color = (0, 255, 0)  # Green for ready
            else:
                status_color = (0, 165, 255)  # Orange for searching
            cv2.circle(display_frame, (30, 30), 15, status_color, -1)
            
            cv2.imshow("Live Capture - Enhanced", display_frame)
        
        cap.release()
        cv2.destroyAllWindows()
        
        print(f"\nCapture completed!")
        print(f"Final coverage: {self.coverage_tracker.get_coverage_percentage():.1f}%")
        
        # Print quality summary
        quality_summary = self.quality_tracker.get_quality_summary()
        if quality_summary:
            print(f"\n--- QUALITY SUMMARY ---")
            print(f"Images captured: {quality_summary['total_images']}")
            print(f"Average focus quality: {quality_summary['overall_quality']}")
            print(f"Average sharpness: {quality_summary['avg_sharpness']:.0f}")
            print(f"Excellent images: {quality_summary['excellent_images']} ({quality_summary['excellent_percentage']:.1f}%)")
            print(f"Blurry images: {quality_summary['blurry_images']} ({quality_summary['blurry_percentage']:.1f}%)")
            print(f"Average corners detected: {quality_summary['avg_corners']:.1f}")
            
            if quality_summary['blurry_percentage'] > 20:
                print("WARNING: High percentage of blurry images detected!")
                print("Consider improving lighting or camera stability for better results.")

    def image_folder_flow(self, folder):
        if not os.path.exists(folder):
            print("Folder not found.")
            return
        
        images = [os.path.join(folder, f) for f in os.listdir(folder) 
                 if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        
        print(f"\nProcessing {len(images)} images from folder...")
        
        processed_count = 0
        valid_count = 0
        
        for i, img_path in enumerate(images):
            img = cv2.imread(img_path)
            if img is not None:
                processed_count += 1
                if self.calibrator.add_image(img):
                    valid_count += 1
                
                # Show progress
                progress = (i + 1) / len(images) * 100
                print(f"Progress: {progress:.1f}% - Valid images: {valid_count}/{processed_count}", end='\r')
        
        print(f"\nProcessing completed!")
        print(f"Total processed: {processed_count}")
        print(f"Valid for calibration: {valid_count}")

    def perform_calibration(self, save_file):
        print(f"\nStarting calibration with {len(self.calibrator.corners)} images...")
        
        if self.calibrator.calibrate():
            K, D, error = self.calibrator.get_results()
            print("\n" + "="*50)
            print("CALIBRATION SUCCESSFUL!")
            print("="*50)
            print("Camera Matrix (K):")
            print(K)
            print("\nDistortion Coefficients (D):")
            print(D.ravel())
            print(f"\nReprojection Error: {error:.4f} pixels")
            
            # Enhanced quality assessment including focus data
            quality_assessment = []
            
            # Reprojection error assessment
            if error < 0.5:
                error_quality = "EXCELLENT"
            elif error < 1.0:
                error_quality = "GOOD"
            elif error < 2.0:
                error_quality = "ACCEPTABLE"
            else:
                error_quality = "POOR - Consider recalibrating"
            
            quality_assessment.append(f"Reprojection Error: {error_quality}")
            
            # Coverage assessment
            if self.coverage_tracker:
                coverage = self.coverage_tracker.get_coverage_percentage()
                if coverage >= 80:
                    coverage_quality = "EXCELLENT"
                elif coverage >= 60:
                    coverage_quality = "GOOD"
                elif coverage >= 40:
                    coverage_quality = "ACCEPTABLE"
                else:
                    coverage_quality = "POOR - Low coverage"
                
                quality_assessment.append(f"Coverage ({coverage:.1f}%): {coverage_quality}")
            
            # Focus quality assessment
            quality_summary = self.quality_tracker.get_quality_summary()
            if quality_summary:
                focus_quality = quality_summary['overall_quality']
                blurry_percentage = quality_summary['blurry_percentage']
                
                if blurry_percentage < 10:
                    focus_assessment = "EXCELLENT"
                elif blurry_percentage < 20:
                    focus_assessment = "GOOD"
                elif blurry_percentage < 40:
                    focus_assessment = "ACCEPTABLE"
                else:
                    focus_assessment = "POOR - Too many blurry images"
                
                quality_assessment.append(f"Focus Quality: {focus_assessment}")
                quality_assessment.append(f"Overall Focus: {focus_quality}")
            
            # Overall assessment
            print(f"\n--- QUALITY ASSESSMENT ---")
            for assessment in quality_assessment:
                print(assessment)
            
            # Warnings and recommendations
            warnings = []
            if error > 1.0:
                warnings.append("High reprojection error - consider recalibrating with better images")
            if self.coverage_tracker and self.coverage_tracker.get_coverage_percentage() < 60:
                warnings.append("Low coverage - capture images from more diverse viewpoints")
            if quality_summary and quality_summary['blurry_percentage'] > 20:
                warnings.append("Many blurry images detected - improve lighting and camera stability")
            if len(self.calibrator.corners) < 10:
                warnings.append("Few calibration images - consider capturing more for better accuracy")
            
            if warnings:
                print(f"\n--- RECOMMENDATIONS ---")
                for warning in warnings:
                    print(f"• {warning}")

            # Save calibration results
            if save_file:
                self.calibrator.save_calibration(save_file)
                print(f"\nResults saved to: {save_file}")
            else:
                print(f"\nCalibration results not saved (saving was skipped)")
        else:
            print("\n" + "="*50)
            print("CALIBRATION FAILED!")
            print("="*50)
            print("Possible reasons:")
            print("- Not enough valid images")
            print("- Poor quality detections")
            print("- Insufficient coverage of image area")
            print("- Board detection issues")
            print("- Too many blurry images")


if __name__ == "__main__":
    try:
        inputs = get_user_inputs()
        strategy, fisheye, camera_id, workflow, board_config, target_images, folder, save_file, use_autocapture, autocapture_delay = inputs
        
        cli = CalibratorCLI(strategy, fisheye, board_config, use_autocapture, autocapture_delay)
        cli.run(camera_id, workflow, target_images, folder, save_file)
        
    except KeyboardInterrupt:
        print("\nCalibration interrupted by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cv2.destroyAllWindows()