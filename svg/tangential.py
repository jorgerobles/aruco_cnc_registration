from vector import shift, angle, angle_diff


def routes_to_gcode(points, speed=1500, cut_depth=1.0, safety_height=5.0, initial_rotation=0, offset=5,
                    angle_threshold=10):
    """
    Generates G-Code for a CNC milling machine given a list of linear segments,
    where each segment has start and end coordinates.  Movements between
    segments are rapid (G0).

    Args:
        points: A list of tuples (x1, y1) representing the segments.
                Each tuple contains the starting coordinates (x1, y1) of a linear segment.
                The function calculates the ending coordinate internally.
        speed: The cutting speed in mm/min (default 1500).
        cut_depth: The cutting depth in mm (default 1.0).
        safety_height: The safety height in mm for changes with rotation (default 5.0).
        initial_rotation: The initial angle of the A axis in degrees (default 0).
        offset: The amount of shift to apply to each segment in mm (default 5).
        angle_threshold: The threshold for significant angle change in degrees (default 10).

    Returns:
        A string containing the generated G-Code.
    """

    gcode = []
    gcode.append("G90")  # Set absolute coordinates
    gcode.append("G21")  # Units in millimeters
    gcode.append(f"G0 Z{safety_height} F{speed}")  # Safety depth and speed
    current_z = safety_height

    if not points:
        return gcode  # If there are no segments, return the base code.

    x1, y1 = points[0]
    gcode.append(f"G0 X{x1:.3f} Y{y1:.3f}")  # Move to the first position rapidly (G0)
    current_angle = initial_rotation  # Initialize the current angle

    for i in range(1, len(points)):
        x1_next, y1_next = points[i]

        # Calculate the ending coordinates of the segment.
        (x1_seg, y1_seg, x2_seg, y2_seg) = shift(x1, y1, x1_next, y1_next, offset)  # Example displacement

        new_angle = angle(x1, y1, x1_next, y1_next)  # Calculates the angle for the next line.

        angle_delta = angle_diff(current_angle, new_angle)

        reverses_direction = (current_angle > 0 > new_angle) or (current_angle < 0 < new_angle)



        if (abs(angle_delta) > angle_threshold) or reverses_direction or i==1:
            if current_z != safety_height:
                gcode.append(f"G0 Z{safety_height}")  # Raise Z to safety height
                current_z = safety_height

            gcode.append(f"G0 X{x1_seg:.3f} Y{y1_seg:.3f} A{new_angle:.3f}")

        if current_z != cut_depth:
            gcode.append(f"G1 Z{cut_depth}")
            current_z = cut_depth

        if (abs(angle_delta) > angle_threshold) or reverses_direction or i==1:
            gcode.append(f"G1 X{x2_seg:.3f} Y{y2_seg:.3f} F{speed}")
        else:
            gcode.append(f"G1 X{x2_seg:.3f} Y{y2_seg:.3f} A{new_angle:.3f} F{speed}")


        x1, y1 = x1_next, y1_next  # Update the coordinates of the previous point
        current_angle = new_angle


    gcode.append(f"G0 Z{safety_height}")  # Raise the head to safety height (G0 movement)

    return gcode
