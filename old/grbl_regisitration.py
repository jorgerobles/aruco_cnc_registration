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


def load_camera_calibration(file_path):
    fs = cv2.FileStorage(file_path, cv2.FILE_STORAGE_READ)
    camera_matrix = fs.getNode("camera_matrix").mat()
    dist_coeffs = fs.getNode("distortion_coefficients").mat()
    fs.release()
    return camera_matrix, dist_coeffs


def detect_marker_pose(image, aruco_dict, parameters, marker_length, camera_matrix, dist_coeffs):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=parameters)

    if ids is not None and len(ids) > 0:
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(corners, marker_length, camera_matrix, dist_coeffs)
        center = np.mean(corners[0][0], axis=0)
        h, w = image.shape[:2]
        norm_pos = (center[0] / w, center[1] / h)
        return rvecs[0][0], tvecs[0][0], norm_pos
    else:
        raise ValueError("Marker not detected")


def compute_rigid_transform(A, B):
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


def capture_and_register(grbl_port, image_paths, marker_length, calib_file):
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    camera_matrix, dist_coeffs = load_camera_calibration(calib_file)
    grbl = open_grbl(grbl_port)

    camera_points = []
    machine_points = []
    norm_positions = []

    for img_path in image_paths:
        input(f"Move machine to marker position and press ENTER to capture {img_path}...")

        # Get GRBL machine position
        mpos = get_grbl_position(grbl)
        machine_points.append(mpos)

        # Capture image from file or camera
        image = cv2.imread(img_path)
        rvec, tvec, norm = detect_marker_pose(image, aruco_dict, parameters, marker_length, camera_matrix, dist_coeffs)
        camera_points.append(tvec)
        norm_positions.append(norm)

    R, t = compute_rigid_transform(camera_points, machine_points)
    return R, t, norm_positions


def transform_point(point, R, t):
    return R @ point + t


def set_work_offset(grbl, offset_xyz, coordinate_system=1):
    """Send G10 command to set work offset (G54=1, G55=2, etc.)"""
    cmd = f"G10 L20 P{coordinate_system} X{offset_xyz[0]:.3f} Y{offset_xyz[1]:.3f} Z{offset_xyz[2]:.3f}\n"
    grbl.write(cmd.encode())
    time.sleep(0.5)
    grbl.flushInput()


if __name__ == '__main__':
    image_paths = ['marker1.jpg', 'marker2.jpg', 'marker3.jpg']
    marker_length = 20.0  # mm
    calibration_file = 'camera_calib.yml'
    grbl_port = 'COM3'  # or '/dev/ttyUSB0'

    R, t, norm_positions = capture_and_register(grbl_port, image_paths, marker_length, calibration_file)

    # Suppose you detect a new marker in a new image:
    test_image = cv2.imread('test_marker.jpg')
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    camera_matrix, dist_coeffs = load_camera_calibration(calibration_file)

    _, tvec, _ = detect_marker_pose(test_image, aruco_dict, parameters, marker_length, camera_matrix, dist_coeffs)

    # Transform to machine coordinates
    machine_point = transform_point(tvec, R, t)
    print("Mapped machine position:", machine_point)

    # Send G10 work offset to GRBL (e.g., to set G54)
    grbl = open_grbl(grbl_port)
    set_work_offset(grbl, machine_point, coordinate_system=1)
