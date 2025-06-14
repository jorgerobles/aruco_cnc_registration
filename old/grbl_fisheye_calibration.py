import time

import cv2
import numpy as np
import serial


def open_grbl(port='/dev/ttyUSB0', baud=115200, timeout=2):
    s = serial.Serial(port, baud, timeout=timeout)
    s.flushInput()
    time.sleep(2)
    s.write(b"\r\n\r\n")  # Wake up
    time.sleep(2)
    s.flushInput()
    return s


def get_grbl_position(serial_conn):
    serial_conn.write(b"?\n")
    time.sleep(0.1)
    response = serial_conn.readlines()
    for line in response:
        if b"MPos:" in line:
            data = line.decode()
            try:
                mpos = data.split('MPos:')[1].split(' ')[0]
                x, y, z = map(float, mpos.split(','))
                return [x, y, z]
            except:
                pass
    raise ValueError("Failed to parse GRBL position")


def load_fisheye_calibration(npz_file_path):
    """
    Load fisheye camera calibration from NPZ file.

    Args:
        npz_file_path: Path to the NPZ calibration file

    Returns:
        camera_matrix, dist_coeffs, image_size
    """
    try:
        data = np.load(npz_file_path)
        camera_matrix = data['camera_matrix']
        dist_coeffs = data['dist_coeffs']
        image_size = tuple(data['image_size'])
        print(f"Loaded fisheye calibration from: {npz_file_path}")
        print(f"Camera matrix shape: {camera_matrix.shape}")
        print(f"Distortion coeffs shape: {dist_coeffs.shape}")
        print(f"Image size: {image_size}")
        return camera_matrix, dist_coeffs, image_size
    except Exception as e:
        raise ValueError(f"Failed to load fisheye calibration: {e}")


def undistort_fisheye_image(image, camera_matrix, dist_coeffs, balance=1.0, fov_scale=1.0):
    """
    Undistort a fisheye image using calibration parameters.

    Args:
        image: Input fisheye image
        camera_matrix: Camera intrinsic matrix
        dist_coeffs: Fisheye distortion coefficients
        balance: Balance parameter (0=retain all pixels, 1=no black pixels)
        fov_scale: FOV scaling factor

    Returns:
        Undistorted image
    """
    h, w = image.shape[:2]

    # Generate new camera matrix for undistortion
    new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
        camera_matrix, dist_coeffs, (w, h), np.eye(3), balance=balance, fov_scale=fov_scale
    )

    # Generate undistortion maps
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(
        camera_matrix, dist_coeffs, np.eye(3), new_K, (w, h), cv2.CV_16SC2
    )

    # Apply undistortion
    undistorted = cv2.remap(image, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    return undistorted, new_K


def detect_marker_pose_fisheye(image, aruco_dict, parameters, marker_length, camera_matrix, dist_coeffs,
                               undistort=True):
    """
    Detect ArUco marker pose in fisheye image with optional undistortion.

    Args:
        image: Input image (fisheye or undistorted)
        aruco_dict: ArUco dictionary
        parameters: Detection parameters
        marker_length: Physical marker length in mm
        camera_matrix: Camera intrinsic matrix
        dist_coeffs: Distortion coefficients
        undistort: Whether to undistort the image first

    Returns:
        rvec, tvec, normalized_position, undistorted_image (if undistort=True)
    """
    if undistort:
        # Undistort the fisheye image first
        undistorted_image, new_camera_matrix = undistort_fisheye_image(image, camera_matrix, dist_coeffs)
        working_image = undistorted_image
        working_camera_matrix = new_camera_matrix
        # For fisheye, we use zero distortion coefficients after undistortion
        working_dist_coeffs = np.zeros((4, 1))
    else:
        working_image = image
        working_camera_matrix = camera_matrix
        working_dist_coeffs = dist_coeffs
        undistorted_image = None

    gray = cv2.cvtColor(working_image, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=parameters)

    if ids is not None and len(ids) > 0:
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners, marker_length, working_camera_matrix, working_dist_coeffs
        )
        center = np.mean(corners[0][0], axis=0)
        h, w = working_image.shape[:2]
        norm_pos = (center[0] / w, center[1] / h)

        if undistort:
            return rvecs[0][0], tvecs[0][0], norm_pos, undistorted_image
        else:
            return rvecs[0][0], tvecs[0][0], norm_pos
    else:
        raise ValueError("Marker not detected")


def compute_rigid_transform(A, B):
    """Compute rigid transformation (rotation + translation) between two point sets."""
    A = np.asarray(A)
    B = np.asarray(B)
    centroid_A = np.mean(A, axis=0)
    centroid_B = np.mean(B, axis=0)

    AA = A - centroid_A
    BB = B - centroid_B

    H = AA.T @ BB
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[2, :] *= -1
        R = Vt.T @ U.T
    t = centroid_B - R @ centroid_A
    return R, t


def capture_and_register_fisheye(grbl_port, image_paths, marker_length, calib_file, undistort=True):
    """
    Capture and register camera-to-machine coordinate transformation using fisheye calibration.

    Args:
        grbl_port: GRBL serial port
        image_paths: List of image file paths
        marker_length: Physical marker length in mm
        calib_file: Path to fisheye calibration NPZ file
        undistort: Whether to undistort fisheye images before marker detection

    Returns:
        R, t, norm_positions
    """
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    camera_matrix, dist_coeffs, image_size = load_fisheye_calibration(calib_file)
    grbl = open_grbl(grbl_port)

    camera_points = []
    machine_points = []
    norm_positions = []

    print(f"Starting registration with {len(image_paths)} images...")
    print(f"Fisheye undistortion: {'Enabled' if undistort else 'Disabled'}")

    for i, img_path in enumerate(image_paths):
        input(f"Move machine to marker position and press ENTER to capture {img_path} ({i + 1}/{len(image_paths)})...")

        # Get GRBL machine position
        try:
            mpos = get_grbl_position(grbl)
            machine_points.append(mpos)
            print(f"Machine position: X={mpos[0]:.3f}, Y={mpos[1]:.3f}, Z={mpos[2]:.3f}")
        except Exception as e:
            print(f"Error getting machine position: {e}")
            continue

        # Capture and process image
        try:
            image = cv2.imread(img_path)
            if image is None:
                print(f"Could not load image: {img_path}")
                continue

            if undistort:
                rvec, tvec, norm, undistorted_img = detect_marker_pose_fisheye(
                    image, aruco_dict, parameters, marker_length, camera_matrix, dist_coeffs, undistort=True
                )
                # Optionally save undistorted image for debugging
                undistorted_path = img_path.replace('.jpg', '_undistorted.jpg').replace('.png', '_undistorted.png')
                cv2.imwrite(undistorted_path, undistorted_img)
                print(f"Saved undistorted image: {undistorted_path}")
            else:
                rvec, tvec, norm = detect_marker_pose_fisheye(
                    image, aruco_dict, parameters, marker_length, camera_matrix, dist_coeffs, undistort=False
                )

            camera_points.append(tvec.flatten())  # Flatten to ensure 1D array
            norm_positions.append(norm)
            print(f"Camera position: {tvec.flatten()}")
            print(f"Normalized position: {norm}")

        except Exception as e:
            print(f"Error processing image {img_path}: {e}")
            # Remove the corresponding machine point if image processing failed
            if len(machine_points) > len(camera_points):
                machine_points.pop()
            continue

    grbl.close()

    if len(camera_points) < 3:
        raise ValueError(f"Need at least 3 valid point pairs for registration, got {len(camera_points)}")

    print(f"\nComputing transformation with {len(camera_points)} point pairs...")
    R, t = compute_rigid_transform(camera_points, machine_points)

    # Calculate registration error
    transformed_points = [transform_point(cp, R, t) for cp in camera_points]
    errors = [np.linalg.norm(np.array(tp) - np.array(mp)) for tp, mp in zip(transformed_points, machine_points)]
    mean_error = np.mean(errors)
    max_error = np.max(errors)

    print(f"Registration completed!")
    print(f"Mean error: {mean_error:.3f} mm")
    print(f"Max error: {max_error:.3f} mm")

    return R, t, norm_positions


def transform_point(point, R, t):
    """Transform a point using rotation matrix R and translation vector t."""
    point = np.asarray(point).flatten()
    return R @ point + t


def set_work_offset(grbl, offset_xyz, coordinate_system=1):
    """Send G10 command to set work offset (G54=1, G55=2, etc.)"""
    cmd = f"G10 L20 P{coordinate_system} X{offset_xyz[0]:.3f} Y{offset_xyz[1]:.3f} Z{offset_xyz[2]:.3f}\n"
    grbl.write(cmd.encode())
    time.sleep(0.5)
    response = grbl.readlines()
    print(f"Work offset command sent: {cmd.strip()}")
    if response:
        for line in response:
            print(f"GRBL response: {line.decode().strip()}")


def save_registration(filename, R, t, norm_positions, calib_file):
    """Save registration data to NPZ file."""
    np.savez(filename,
             rotation_matrix=R,
             translation_vector=t,
             normalized_positions=norm_positions,
             calibration_file=calib_file)
    print(f"Registration data saved to: {filename}")


def load_registration(filename):
    """Load registration data from NPZ file."""
    data = np.load(filename, allow_pickle=True)
    R = data['rotation_matrix']
    t = data['translation_vector']
    norm_positions = data['normalized_positions']
    calib_file = str(data['calibration_file'])
    print(f"Registration data loaded from: {filename}")
    return R, t, norm_positions, calib_file


if __name__ == '__main__':
    # Configuration
    image_paths = ['marker1.jpg', 'marker2.jpg', 'marker3.jpg']
    marker_length = 20.0  # mm
    calibration_file = 'fisheye_calibration.npz'
    grbl_port = 'COM3'  # or '/dev/ttyUSB0' for Linux
    undistort_fisheye = True  # Set to False if using regular camera

    try:
        # Perform registration
        R, t, norm_positions = capture_and_register_fisheye(
            grbl_port, image_paths, marker_length, calibration_file, undistort=undistort_fisheye
        )

        # Save registration results
        save_registration('camera_machine_registration.npz', R, t, norm_positions, calibration_file)

        # Example usage: Transform a new marker detection to machine coordinates
        test_image_path = 'test_marker.jpg'
        if cv2.imread(test_image_path) is not None:
            print(f"\nTesting transformation with {test_image_path}...")

            # Load calibration
            camera_matrix, dist_coeffs, image_size = load_fisheye_calibration(calibration_file)

            # Setup ArUco detection
            aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            parameters = cv2.aruco.DetectorParameters()

            # Load and process test image
            test_image = cv2.imread(test_image_path)

            try:
                if undistort_fisheye:
                    _, tvec, _, _ = detect_marker_pose_fisheye(
                        test_image, aruco_dict, parameters, marker_length,
                        camera_matrix, dist_coeffs, undistort=True
                    )
                else:
                    _, tvec, _ = detect_marker_pose_fisheye(
                        test_image, aruco_dict, parameters, marker_length,
                        camera_matrix, dist_coeffs, undistort=False
                    )

                # Transform to machine coordinates
                machine_point = transform_point(tvec.flatten(), R, t)
                print(f"Detected marker camera position: {tvec.flatten()}")
                print(f"Mapped machine position: {machine_point}")

                # Send work offset to GRBL
                grbl = open_grbl(grbl_port)
                set_work_offset(grbl, machine_point, coordinate_system=1)
                grbl.close()

            except Exception as e:
                print(f"Error processing test image: {e}")
        else:
            print(f"Test image {test_image_path} not found, skipping test transformation")

    except Exception as e:
        print(f"Registration failed: {e}")