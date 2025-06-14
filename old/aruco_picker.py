import cv2
import numpy as np
import cv2.aruco as aruco
from aligner import compute_rectangle_transform_robust, create_transformation_matrix


def detect_specific_marker_corner(image, marker_id, aruco_dict_type=aruco.DICT_4X4_50):
    """
    Detect a specific Aruco marker in an image and return its top-left corner.
    """
    aruco_dict = aruco.Dictionary_get(aruco_dict_type)
    parameters = aruco.DetectorParameters_create()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    corners, ids, _ = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)

    if ids is None:
        raise ValueError("No Aruco markers detected in image.")

    for i, id_val in enumerate(ids.flatten()):
        if id_val == marker_id:
            return corners[i][0][0]  # Top-left corner

    raise ValueError(f"Aruco marker ID {marker_id} not found in image.")


def get_transformation_from_three_images_with_ids(img1, id1, img2, id2, img3, id3):
    """
    Compute rectangle transformation from 3 separate data, each containing a specific Aruco marker.

    Args:
        img1, img2, img3: BGR data
        id1, id2, id3: Expected Aruco marker IDs in each image

    Returns:
        transformation_matrix: 3x3 matrix
        rect_config: dictionary with rectangle geometry
    """
    p1 = detect_specific_marker_corner(img1, id1)
    p2 = detect_specific_marker_corner(img2, id2)
    p3 = detect_specific_marker_corner(img3, id3)

    rect_config = compute_rectangle_transform_robust(p1, p2, p3)
    transformation_matrix = create_transformation_matrix(rect_config)

    return transformation_matrix, rect_config


if __name__ == "__main__":
    # Paths to your marker data
    img1_path = "marker_img_1.jpg"
    img2_path = "marker_img_2.jpg"
    img3_path = "marker_img_3.jpg"

    # The known marker IDs in each image
    marker_id1 = 10
    marker_id2 = 25
    marker_id3 = 42

    # Load the data
    img1 = cv2.imread(img1_path)
    img2 = cv2.imread(img2_path)
    img3 = cv2.imread(img3_path)

    if img1 is None or img2 is None or img3 is None:
        raise FileNotFoundError("One or more input data could not be loaded.")

    # Compute transformation
    T, config = get_transformation_from_three_images_with_ids(
        img1, marker_id1,
        img2, marker_id2,
        img3, marker_id3
    )

    # Output
    print("\n=== Rectangle Transformation Result ===")
    print("Transformation Matrix:\n", T)
    print("Rectangle Corners:\n", np.array(config['corners']))
    print(f"Rectangle Width: {config['width']:.3f}")
    print(f"Rectangle Height: {config['height']:.3f}")
    print(f"Aspect Ratio: {config['width'] / config['height']:.3f}")
