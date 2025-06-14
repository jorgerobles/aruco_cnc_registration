import numpy as np
import matplotlib.pyplot as plt


def compute_rectangle_transformation(p1, p2, p3):
    """
    Compute transformation matrix from 3 fiducial points that form part of a rectangle.
    The points should be 3 corners of a rectangle.

    Args:
        p1, p2, p3: Three corners of a rectangle (2D points)
                   Expected: two adjacent sides meeting at one corner

    Returns:
        3x3 transformation matrix that maps unit rectangle to the fiducial rectangle
        4th corner position (computed from rectangle constraint)
        rectangle dimensions (width, height)
    """
    p1, p2, p3 = np.array(p1), np.array(p2), np.array(p3)

    # Calculate vectors between points
    v12 = p2 - p1
    v13 = p3 - p1
    v23 = p3 - p2

    # Calculate distances
    d12 = np.linalg.norm(v12)
    d13 = np.linalg.norm(v13)
    d23 = np.linalg.norm(v23)

    # Determine rectangle configuration by checking for right angles
    tolerance = 1e-6

    # Check which point is the corner where two sides meet at right angle
    dot_12_13 = np.dot(v12, v13)  # Dot product at p1
    dot_21_23 = np.dot(-v12, v23)  # Dot product at p2
    dot_31_32 = np.dot(-v13, -v23)  # Dot product at p3

    if abs(dot_12_13) < tolerance:
        # Right angle at p1: p1 is the corner, p2 and p3 are adjacent
        corner1, corner2, corner3 = p1, p2, p3
        corner4 = corner2 + (corner3 - corner1)  # Complete the rectangle
        width, height = d12, d13

    elif abs(dot_21_23) < tolerance:
        # Right angle at p2: p2 is the corner, p1 and p3 are adjacent
        corner1, corner2, corner3 = p2, p1, p3
        corner4 = corner2 + (corner3 - corner1)
        width, height = d12, d23

    elif abs(dot_31_32) < tolerance:
        # Right angle at p3: p3 is the corner, p1 and p2 are adjacent
        corner1, corner2, corner3 = p3, p1, p2
        corner4 = corner2 + (corner3 - corner1)
        width, height = d13, d23

    else:
        # No clear right angle found - try to fit best rectangle
        # Assume p1 is corner and p2, p3 are adjacent
        print("Warning: No clear right angle found. Assuming p1 is the corner.")
        corner1, corner2, corner3 = p1, p2, p3
        corner4 = corner2 + (corner3 - corner1)
        width, height = d12, d13

    # Arrange corners in consistent order: corner1 (origin), corner2 (width), corner4 (height), corner3 (opposite)
    rectangle_corners = np.array([corner1, corner2, corner3, corner4])

    return corner1, corner2, corner3, corner4, width, height


def compute_rectangle_transform_robust(p1, p2, p3):
    """
    Robust computation of rectangle transformation by testing different corner arrangements.
    """
    p1, p2, p3 = np.array(p1), np.array(p2), np.array(p3)

    # Try different arrangements to find the best rectangle fit
    arrangements = [
        (p1, p2, p3),  # p1 as corner
        (p2, p1, p3),  # p2 as corner
        (p3, p1, p2),  # p3 as corner
    ]

    best_config = None
    best_score = float('inf')

    for corner, adj1, adj2 in arrangements:
        # Vectors from corner to adjacent points
        v1 = adj1 - corner
        v2 = adj2 - corner

        # Check perpendicularity (rectangle constraint)
        dot_product = np.dot(v1, v2)
        angle_score = abs(dot_product) / (np.linalg.norm(v1) * np.linalg.norm(v2))

        if angle_score < best_score:
            best_score = angle_score
            # Compute 4th corner
            corner4 = adj1 + (adj2 - corner)
            best_config = {
                'corners': [corner, adj1, adj2, corner4],
                'corner': corner,
                'adj1': adj1,
                'adj2': adj2,
                'corner4': corner4,
                'width': np.linalg.norm(v1),
                'height': np.linalg.norm(v2),
                'score': angle_score
            }

    return best_config


def create_transformation_matrix(rectangle_config):
    """
    Create transformation matrix from unit rectangle to fiducial rectangle.

    Args:
        rectangle_config: Dictionary with rectangle configuration

    Returns:
        3x3 transformation matrix
    """
    # Unit rectangle corners: (0,0), (1,0), (0,1)
    unit_triangle = np.array([[0, 0], [1, 0], [0, 1]])

    # Corresponding fiducial corners
    corner = rectangle_config['corner']
    adj1 = rectangle_config['adj1']
    adj2 = rectangle_config['adj2']

    fiducial_triangle = np.array([corner, adj1, adj2])

    # Solve for transformation matrix using homogeneous coordinates
    unit_homo = np.column_stack([unit_triangle, np.ones(3)])
    fiducial_homo = np.column_stack([fiducial_triangle, np.ones(3)])

    T = fiducial_homo.T @ np.linalg.pinv(unit_homo.T)

    return T


def transform_points(points, transformation_matrix):
    """Transform N points using the transformation matrix."""
    points_homo = np.column_stack([points, np.ones(len(points))])
    transformed_homo = (transformation_matrix @ points_homo.T).T
    transformed_points = transformed_homo[:, :2] / transformed_homo[:, 2:3]
    return transformed_points


def create_sample_shape(n_points=20, center=(0, 0), scale=1):
    """Create a sample shape with N points."""
    angles = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    radii = scale * (1 + 0.3 * np.sin(5 * angles))
    x = center[0] + radii * np.cos(angles)
    y = center[1] + radii * np.sin(angles)
    return np.column_stack([x, y])


# Example usage
if __name__ == "__main__":
    # Example 1: Perfect rectangle fiducials (3:2 ratio)
    print("=== Example 1: Rectangle Fiducials (3:2 ratio) ===")
    rect_fiducials = np.array([
        [0, 0],  # Corner
        [3, 0],  # Adjacent corner (width)
        [0, 2],  # Adjacent corner (height)
    ])

    rect_config = compute_rectangle_transform_robust(
        rect_fiducials[0], rect_fiducials[1], rect_fiducials[2]
    )

    T_rect = create_transformation_matrix(rect_config)

    print("Rectangle fiducials:", rect_fiducials)
    print("Computed 4th corner:", rect_config['corner4'])
    print(f"Rectangle dimensions: {rect_config['width']:.2f} x {rect_config['height']:.2f}")
    print(f"Aspect ratio: {rect_config['width'] / rect_config['height']:.2f}")
    print("Transformation matrix:")
    print(T_rect)

    # Example 2: Rotated and scaled rectangle
    print("\n=== Example 2: Rotated Rectangle Fiducials ===")
    angle = np.pi / 4  # 45 degrees
    scale_x, scale_y = 2.0, 1.5
    rotation = np.array([[np.cos(angle), -np.sin(angle)],
                         [np.sin(angle), np.cos(angle)]])

    # Create rotated rectangle
    base_corners = np.array([[0, 0], [scale_x, 0], [0, scale_y]])
    rotated_fiducials = np.array([
        [2, 1] + rotation @ base_corners[0],  # Translated and rotated corner
        [2, 1] + rotation @ base_corners[1],  # Rotated width vector
        [2, 1] + rotation @ base_corners[2],  # Rotated height vector
    ])

    rect_config_rot = compute_rectangle_transform_robust(
        rotated_fiducials[0], rotated_fiducials[1], rotated_fiducials[2]
    )

    T_rect_rot = create_transformation_matrix(rect_config_rot)

    print("Rotated fiducials:", rotated_fiducials)
    print("Computed 4th corner:", rect_config_rot['corner4'])
    print(f"Rectangle dimensions: {rect_config_rot['width']:.2f} x {rect_config_rot['height']:.2f}")

    # Example 3: Different aspect ratio rectangle
    print("\n=== Example 3: Wide Rectangle (5:1 ratio) ===")
    wide_fiducials = np.array([
        [1, 1],  # Corner
        [6, 1],  # Width = 5
        [1, 2],  # Height = 1
    ])

    wide_config = compute_rectangle_transform_robust(
        wide_fiducials[0], wide_fiducials[1], wide_fiducials[2]
    )

    T_wide = create_transformation_matrix(wide_config)

    print("Wide rectangle fiducials:", wide_fiducials)
    print("Computed 4th corner:", wide_config['corner4'])
    print(f"Rectangle dimensions: {wide_config['width']:.2f} x {wide_config['height']:.2f}")
    print(f"Aspect ratio: {wide_config['width'] / wide_config['height']:.2f}")

    # Create sample shapes to transform
    shape1 = create_sample_shape(20, center=(0.3, 0.3), scale=0.2)
    shape2 = create_sample_shape(12, center=(0.7, 0.6), scale=0.15)
    grid_points = np.array([[i * 0.1, j * 0.1] for i in range(11) for j in range(11)])

    # Transform shapes using all three transformation matrices
    transformed_shape1_rect = transform_points(shape1, T_rect)
    transformed_shape2_rect = transform_points(shape2, T_rect)
    transformed_grid_rect = transform_points(grid_points, T_rect)

    transformed_shape1_rot = transform_points(shape1, T_rect_rot)
    transformed_shape2_rot = transform_points(shape2, T_rect_rot)

    transformed_shape1_wide = transform_points(shape1, T_wide)
    transformed_shape2_wide = transform_points(shape2, T_wide)

    # Plotting
    plt.figure(figsize=(18, 12))

    # Original shapes and unit rectangle
    plt.subplot(2, 4, 1)
    plt.plot(shape1[:, 0], shape1[:, 1], 'b-o', markersize=3, alpha=0.7, label='Shape 1')
    plt.plot(shape2[:, 0], shape2[:, 1], 'r-o', markersize=3, alpha=0.7, label='Shape 2')
    unit_rect = np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]])
    plt.plot(unit_rect[:, 0], unit_rect[:, 1], 'k-', linewidth=2, label='Unit Rectangle')
    plt.scatter(grid_points[::10, 0], grid_points[::10, 1], c='gray', s=10, alpha=0.5)
    plt.axis('equal')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.title('Original Shapes in Unit Rectangle')

    # 3:2 Rectangle transformation
    plt.subplot(2, 4, 2)
    plt.plot(transformed_shape1_rect[:, 0], transformed_shape1_rect[:, 1],
             'b-o', markersize=3, alpha=0.7, label='Shape 1')
    plt.plot(transformed_shape2_rect[:, 0], transformed_shape2_rect[:, 1],
             'r-o', markersize=3, alpha=0.7, label='Shape 2')
    # Plot rectangle boundary
    rect_corners = np.array(rect_config['corners'] + [rect_config['corners'][0]])
    plt.plot(rect_corners[:, 0], rect_corners[:, 1], 'k-', linewidth=2, label='Rectangle')
    plt.plot(rect_fiducials[:, 0], rect_fiducials[:, 1], 'go', markersize=8, label='3 Fiducials')
    plt.plot(rect_config['corner4'][0], rect_config['corner4'][1], 'mo', markersize=8, label='4th Corner')
    plt.scatter(transformed_grid_rect[::10, 0], transformed_grid_rect[::10, 1], c='gray', s=10, alpha=0.5)
    plt.axis('equal')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.title('3:2 Rectangle Transform')

    # Rotated rectangle transformation
    plt.subplot(2, 4, 3)
    plt.plot(transformed_shape1_rot[:, 0], transformed_shape1_rot[:, 1],
             'b-o', markersize=3, alpha=0.7, label='Shape 1')
    plt.plot(transformed_shape2_rot[:, 0], transformed_shape2_rot[:, 1],
             'r-o', markersize=3, alpha=0.7, label='Shape 2')
    rot_corners = np.array(rect_config_rot['corners'] + [rect_config_rot['corners'][0]])
    plt.plot(rot_corners[:, 0], rot_corners[:, 1], 'k-', linewidth=2, label='Rectangle')
    plt.plot(rotated_fiducials[:, 0], rotated_fiducials[:, 1], 'go', markersize=8, label='3 Fiducials')
    plt.plot(rect_config_rot['corner4'][0], rect_config_rot['corner4'][1], 'mo', markersize=8, label='4th Corner')
    plt.axis('equal')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.title('Rotated Rectangle Transform')

    # Wide rectangle transformation
    plt.subplot(2, 4, 4)
    plt.plot(transformed_shape1_wide[:, 0], transformed_shape1_wide[:, 1],
             'b-o', markersize=3, alpha=0.7, label='Shape 1')
    plt.plot(transformed_shape2_wide[:, 0], transformed_shape2_wide[:, 1],
             'r-o', markersize=3, alpha=0.7, label='Shape 2')
    wide_corners = np.array(wide_config['corners'] + [wide_config['corners'][0]])
    plt.plot(wide_corners[:, 0], wide_corners[:, 1], 'k-', linewidth=2, label='Rectangle')
    plt.plot(wide_fiducials[:, 0], wide_fiducials[:, 1], 'go', markersize=8, label='3 Fiducials')
    plt.plot(wide_config['corner4'][0], wide_config['corner4'][1], 'mo', markersize=8, label='4th Corner')
    plt.axis('equal')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.title('Wide Rectangle Transform (5:1)')

    # Verification plots - show unit rectangle transformed to fiducials
    unit_corners = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])

    for i, (T, config, title) in enumerate([
        (T_rect, rect_config, "3:2 Rectangle"),
        (T_rect_rot, rect_config_rot, "Rotated Rectangle"),
        (T_wide, wide_config, "Wide Rectangle"),
        (T_rect, rect_config, "Grid Deformation")
    ]):
        plt.subplot(2, 4, 5 + i)

        if i == 3:  # Grid deformation view
            plt.scatter(transformed_grid_rect[:, 0], transformed_grid_rect[:, 1],
                        c='blue', s=15, alpha=0.6, label='Transformed Grid')
            rect_corners = np.array(config['corners'] + [config['corners'][0]])
            plt.plot(rect_corners[:, 0], rect_corners[:, 1], 'k-', linewidth=2)
        else:
            transformed_unit = transform_points(unit_corners, T)
            plt.plot(transformed_unit[[0, 1, 2, 3, 0], 0], transformed_unit[[0, 1, 2, 3, 0], 1],
                     'b-o', linewidth=2, markersize=6, label='Unit Rect → Fiducials')

            # Plot original fiducials for comparison
            fiducials = [rect_fiducials, rotated_fiducials, wide_fiducials][i]
            plt.plot(fiducials[:, 0], fiducials[:, 1], 'ro', markersize=8, label='Original Fiducials')

        plt.axis('equal')
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.title(f'{title} Verification')

    plt.tight_layout()
    plt.show()

    # Transform many arbitrary points
    print("\n=== Transform Many Points ===")
    np.random.seed(42)
    many_points = np.random.rand(50, 2)

    transformed_many_rect = transform_points(many_points, T_rect)
    transformed_many_wide = transform_points(many_points, T_wide)

    print(f"Transformed {len(many_points)} random points:")
    print(
        f"  Original range: x=[{many_points[:, 0].min():.3f}, {many_points[:, 0].max():.3f}], y=[{many_points[:, 1].min():.3f}, {many_points[:, 1].max():.3f}]")
    print(
        f"  3:2 rectangle: x=[{transformed_many_rect[:, 0].min():.3f}, {transformed_many_rect[:, 0].max():.3f}], y=[{transformed_many_rect[:, 1].min():.3f}, {transformed_many_rect[:, 1].max():.3f}]")
    print(
        f"  Wide rectangle: x=[{transformed_many_wide[:, 0].min():.3f}, {transformed_many_wide[:, 0].max():.3f}], y=[{transformed_many_wide[:, 1].min():.3f}, {transformed_many_wide[:, 1].max():.3f}]")