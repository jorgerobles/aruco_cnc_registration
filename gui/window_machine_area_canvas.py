"""
Updated Machine Area Canvas Component
Enhanced to properly handle negative coordinate bounds like (-450,-450) to (0,0)
Includes origin marker and proper coordinate transformation
"""

import tkinter as tk
from typing import Tuple, List, Optional, Callable
import numpy as np


class MachineAreaCanvas:
    """Canvas component for machine area visualization with negative bounds support"""

    def __init__(self, parent, width: int = 400, height: int = 400, logger: Optional[Callable] = None):
        self.parent = parent
        self.canvas_width = width
        self.canvas_height = height
        self.logger = logger

        # Create canvas
        self.canvas = tk.Canvas(
            parent,
            width=self.canvas_width,
            height=self.canvas_height,
            bg='#2b2b2b'
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Zoom and pan state
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.pan_offset_x = 0
        self.pan_offset_y = 0

        # Mouse interaction state
        self.dragging = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0

        # Display settings
        self.margin = 30
        self.scale_factor = 1.0

        # Machine bounds for coordinate transformation (will be set by parent)
        self.machine_bounds = {
            'x_min': 0.0, 'x_max': 450.0,
            'y_min': 0.0, 'y_max': 450.0
        }

        # Colors
        self.colors = {
            'background': '#2b2b2b',
            'machine_bounds': '#4a90e2',
            'routes': '#f5a623',
            'machine_position': '#d0021b',
            'camera_position': '#7ed321',
            'camera_bounds': '#50e3c2',
            'camera_frame': '#ff6b35',
            'calibration_points': '#9013fe',
            'grid': '#404040',
            'text': '#ffffff',
            'origin_marker': '#ff0000',
            'axes': '#888888'
        }

        # Setup mouse interactions
        self.setup_mouse_interactions()

        # Calculate initial scale
        self.calculate_scale_factor()

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def setup_mouse_interactions(self):
        """Setup mouse interactions for zoom and pan"""
        self.canvas.bind("<Button-1>", self._on_mouse_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)  # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)  # Linux scroll down

    def _on_mouse_press(self, event):
        """Handle mouse press for panning"""
        self.dragging = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.canvas.config(cursor="fleur")

    def _on_mouse_drag(self, event):
        """Handle mouse drag for panning"""
        if self.dragging:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y

            self.pan_offset_x += dx
            self.pan_offset_y += dy

            self.last_mouse_x = event.x
            self.last_mouse_y = event.y

            # Trigger redraw (parent should handle this)
            self._trigger_redraw()

    def _on_mouse_release(self, event):
        """Handle mouse release"""
        self.dragging = False
        self.canvas.config(cursor="")

    def _on_mouse_wheel(self, event):
        """Handle mouse wheel for zooming"""
        mouse_x = event.x
        mouse_y = event.y

        # Determine zoom direction
        if event.delta > 0 or event.num == 4:  # Zoom in
            zoom_change = 1.1
        else:  # Zoom out
            zoom_change = 0.9

        new_zoom = self.zoom_factor * zoom_change
        new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))

        if new_zoom != self.zoom_factor:
            # Zoom toward mouse position
            old_zoom = self.zoom_factor
            self.zoom_factor = new_zoom

            # Adjust pan to zoom toward mouse position
            zoom_ratio = new_zoom / old_zoom
            self.pan_offset_x = mouse_x + (self.pan_offset_x - mouse_x) * zoom_ratio
            self.pan_offset_y = mouse_y + (self.pan_offset_y - mouse_y) * zoom_ratio

            self._trigger_redraw()

    def _trigger_redraw(self):
        """Trigger redraw - to be overridden by parent"""
        pass

    def set_redraw_callback(self, callback: Callable):
        """Set callback for redraw events"""
        self._trigger_redraw = callback

    def zoom_in(self):
        """Zoom in by fixed amount"""
        new_zoom = self.zoom_factor * 1.2
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, new_zoom))
        self._trigger_redraw()

    def zoom_out(self):
        """Zoom out by fixed amount"""
        new_zoom = self.zoom_factor * 0.8
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, new_zoom))
        self._trigger_redraw()

    def reset_view(self):
        """Reset zoom and pan to default"""
        self.zoom_factor = 1.0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.calculate_scale_factor()
        self._trigger_redraw()

    def zoom_to_fit(self):
        """Zoom to fit all content"""
        self.reset_view()

    def set_machine_bounds(self, x_min: float, y_min: float, x_max: float, y_max: float):
        """Set machine bounds and recalculate scale"""
        self.machine_bounds = {
            'x_min': x_min, 'x_max': x_max,
            'y_min': y_min, 'y_max': y_max
        }
        self.calculate_scale_factor()
        self._trigger_redraw()

        # Log bounds for debugging
        if self.logger:
            self.logger(f"Canvas bounds set: X({x_min:.0f},{x_max:.0f}) Y({y_min:.0f},{y_max:.0f})")

    def calculate_scale_factor(self):
        """Calculate scale factor to fit machine bounds in canvas"""
        available_width = self.canvas_width - 2 * self.margin
        available_height = self.canvas_height - 2 * self.margin

        machine_width = self.machine_bounds['x_max'] - self.machine_bounds['x_min']
        machine_height = self.machine_bounds['y_max'] - self.machine_bounds['y_min']

        if machine_width <= 0 or machine_height <= 0:
            self.scale_factor = 1.0
            return

        scale_x = available_width / machine_width
        scale_y = available_height / machine_height
        self.scale_factor = min(scale_x, scale_y)

    def machine_to_canvas(self, x: float, y: float) -> Tuple[int, int]:
        """Convert machine coordinates to canvas coordinates with zoom and pan"""
        # Apply base transformation (handles negative coordinates correctly)
        base_x = self.margin + (x - self.machine_bounds['x_min']) * self.scale_factor
        base_y = self.canvas_height - self.margin - (y - self.machine_bounds['y_min']) * self.scale_factor

        # Apply zoom and pan
        canvas_center_x = self.canvas_width / 2
        canvas_center_y = self.canvas_height / 2

        zoomed_x = canvas_center_x + (base_x - canvas_center_x) * self.zoom_factor + self.pan_offset_x
        zoomed_y = canvas_center_y + (base_y - canvas_center_y) * self.zoom_factor + self.pan_offset_y

        return int(zoomed_x), int(zoomed_y)

    def clear(self):
        """Clear the canvas"""
        self.canvas.delete("all")

    def draw_grid(self, grid_spacing: float = 50.0):
        """Draw coordinate grid with proper spacing for negative coordinates"""
        # Calculate grid line positions
        x_min = self.machine_bounds['x_min']
        x_max = self.machine_bounds['x_max']
        y_min = self.machine_bounds['y_min']
        y_max = self.machine_bounds['y_max']

        # Adjust grid spacing based on coordinate range
        coord_range = max(x_max - x_min, y_max - y_min)
        if coord_range > 1000:
            grid_spacing = 100.0
        elif coord_range > 500:
            grid_spacing = 50.0
        elif coord_range > 200:
            grid_spacing = 25.0
        else:
            grid_spacing = 10.0

        # Draw vertical lines
        x_start = int(x_min / grid_spacing) * grid_spacing
        x = x_start
        while x <= x_max:
            if x_min <= x <= x_max:
                x1, y1 = self.machine_to_canvas(x, y_min)
                x2, y2 = self.machine_to_canvas(x, y_max)

                # Highlight zero line
                color = self.colors['axes'] if x == 0 else self.colors['grid']
                width = 2 if x == 0 else 1

                self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)

                # Add coordinate labels for major lines
                if x % (grid_spacing * 2) == 0:
                    label_x, label_y = self.machine_to_canvas(x, y_min)
                    self.canvas.create_text(label_x, label_y + 15, text=f"{x:.0f}",
                                          fill=self.colors['text'], font=('Arial', 8))
            x += grid_spacing

        # Draw horizontal lines
        y_start = int(y_min / grid_spacing) * grid_spacing
        y = y_start
        while y <= y_max:
            if y_min <= y <= y_max:
                x1, y1 = self.machine_to_canvas(x_min, y)
                x2, y2 = self.machine_to_canvas(x_max, y)

                # Highlight zero line
                color = self.colors['axes'] if y == 0 else self.colors['grid']
                width = 2 if y == 0 else 1

                self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)

                # Add coordinate labels for major lines
                if y % (grid_spacing * 2) == 0:
                    label_x, label_y = self.machine_to_canvas(x_min, y)
                    self.canvas.create_text(label_x - 15, label_y, text=f"{y:.0f}",
                                          fill=self.colors['text'], font=('Arial', 8))
            y += grid_spacing

    def draw_machine_bounds(self):
        """Draw machine bounds rectangle"""
        x1, y1 = self.machine_to_canvas(self.machine_bounds['x_min'], self.machine_bounds['y_min'])
        x2, y2 = self.machine_to_canvas(self.machine_bounds['x_max'], self.machine_bounds['y_max'])

        self.canvas.create_rectangle(x1, y2, x2, y1, outline=self.colors['machine_bounds'], width=2, fill="")

        # Add coordinate labels at corners
        bounds = self.machine_bounds

        # Bottom-left corner
        self.canvas.create_text(x1 + 5, y1 - 5,
                              text=f"({bounds['x_min']:.0f},{bounds['y_min']:.0f})",
                              fill=self.colors['text'], anchor=tk.SW, font=('Arial', 8))

        # Top-right corner
        self.canvas.create_text(x2 - 5, y2 + 5,
                              text=f"({bounds['x_max']:.0f},{bounds['y_max']:.0f})",
                              fill=self.colors['text'], anchor=tk.NE, font=('Arial', 8))

    def draw_origin_marker(self):
        """Draw origin marker at (0,0) - important for negative coordinate systems"""
        try:
            # Check if origin (0,0) is within bounds
            if (self.machine_bounds['x_min'] <= 0 <= self.machine_bounds['x_max'] and
                self.machine_bounds['y_min'] <= 0 <= self.machine_bounds['y_max']):

                origin_x, origin_y = self.machine_to_canvas(0, 0)

                # Draw origin crosshairs
                size = 12
                self.canvas.create_line(origin_x - size, origin_y, origin_x + size, origin_y,
                                      fill=self.colors['origin_marker'], width=3)
                self.canvas.create_line(origin_x, origin_y - size, origin_x, origin_y + size,
                                      fill=self.colors['origin_marker'], width=3)

                # Draw origin circle
                radius = 6
                self.canvas.create_oval(origin_x - radius, origin_y - radius,
                                      origin_x + radius, origin_y + radius,
                                      outline=self.colors['origin_marker'], width=2, fill="")

                # Add origin label
                self.canvas.create_text(origin_x + 15, origin_y - 15, text="ORIGIN (0,0)",
                                      fill=self.colors['origin_marker'], anchor=tk.W,
                                      font=('Arial', 10, 'bold'))
        except Exception as e:
            if self.logger:
                self.logger(f"Error drawing origin marker: {e}", "error")

    def draw_homing_position(self, homing_pos: dict):
        """Draw homing position marker - where machine goes when homing"""
        try:
            x, y = homing_pos['x'], homing_pos['y']

            # Check if homing position is within visible bounds
            if (self.machine_bounds['x_min'] <= x <= self.machine_bounds['x_max'] and
                self.machine_bounds['y_min'] <= y <= self.machine_bounds['y_max']):

                home_x, home_y = self.machine_to_canvas(x, y)

                # Draw homing position as square
                size = 8
                self.canvas.create_rectangle(home_x - size, home_y - size,
                                           home_x + size, home_y + size,
                                           fill=self.colors['text'], outline=self.colors['origin_marker'], width=2)

                # Add homing label
                self.canvas.create_text(home_x + 12, home_y + 12,
                                      text=f"HOME ({x:.0f},{y:.0f})",
                                      fill=self.colors['text'], anchor=tk.W,
                                      font=('Arial', 9, 'bold'))
        except Exception as e:
            if self.logger:
                self.logger(f"Error drawing homing position: {e}", "error")

    def draw_routes(self, routes_bounds: List[float]):
        """Draw routes bounds rectangle"""
        if not routes_bounds or len(routes_bounds) < 4:
            return

        try:
            x1, y1 = self.machine_to_canvas(routes_bounds[0], routes_bounds[1])
            x2, y2 = self.machine_to_canvas(routes_bounds[2], routes_bounds[3])

            self.canvas.create_rectangle(x1, y2, x2, y1, outline=self.colors['routes'], width=2, fill="",
                                         dash=(5, 5))

            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            self.canvas.create_text(center_x, center_y, text="Routes", fill=self.colors['routes'], anchor=tk.CENTER)
        except Exception as e:
            if self.logger:
                self.logger(f"Error drawing routes: {e}", "error")

    def draw_route_paths(self, routes: List[List[Tuple[float, float]]], route_colors: List[str]):
        """Draw actual route paths"""
        if not routes:
            return

        for route_idx, route in enumerate(routes):
            if len(route) < 2:
                continue

            color = route_colors[route_idx % len(route_colors)]

            canvas_points = []
            for point in route:
                if len(point) >= 2:
                    x, y = point[0], point[1]
                    canvas_x, canvas_y = self.machine_to_canvas(x, y)
                    canvas_points.extend([canvas_x, canvas_y])

            if len(canvas_points) >= 4:
                self.canvas.create_line(*canvas_points, fill=color, width=2, smooth=False)

                # Draw start point (green)
                start_x, start_y = canvas_points[0], canvas_points[1]
                self.canvas.create_oval(start_x - 3, start_y - 3, start_x + 3, start_y + 3,
                                        fill='green', outline='white', width=1)

                # Draw end point (red)
                end_x, end_y = canvas_points[-2], canvas_points[-1]
                self.canvas.create_rectangle(end_x - 3, end_y - 3, end_x + 3, end_y + 3,
                                             fill='red', outline='white', width=1)

                # Add route label
                mid_idx = len(canvas_points) // 4 * 2
                mid_x, mid_y = canvas_points[mid_idx], canvas_points[mid_idx + 1]
                self.canvas.create_text(mid_x + 5, mid_y - 5, text=f"R{route_idx + 1}",
                                        fill=color, anchor=tk.W, font=('Arial', 8, 'bold'))

    def draw_machine_position(self, position: Tuple[float, float, float]):
        """Draw current machine position"""
        x, y = position[0], position[1]
        canvas_x, canvas_y = self.machine_to_canvas(x, y)

        # Draw machine position as cross
        size = 8
        self.canvas.create_line(canvas_x - size, canvas_y, canvas_x + size, canvas_y,
                                fill=self.colors['machine_position'], width=3)
        self.canvas.create_line(canvas_x, canvas_y - size, canvas_x, canvas_y + size,
                                fill=self.colors['machine_position'], width=3)

        # Add position label
        self.canvas.create_text(canvas_x + 12, canvas_y - 12,
                                text=f"M({x:.1f},{y:.1f})",
                                fill=self.colors['machine_position'], anchor=tk.W,
                                font=('Arial', 9, 'bold'))

    def draw_camera_position(self, position: Tuple[float, float]):
        """Draw current camera position"""
        x, y = position
        canvas_x, canvas_y = self.machine_to_canvas(x, y)

        # Draw camera position as circle
        radius = 6
        self.canvas.create_oval(canvas_x - radius, canvas_y - radius,
                                canvas_x + radius, canvas_y + radius,
                                fill=self.colors['camera_position'], outline="white", width=2)

        # Add position label
        self.canvas.create_text(canvas_x + 12, canvas_y + 12,
                                text=f"C({x:.1f},{y:.1f})",
                                fill=self.colors['camera_position'], anchor=tk.W,
                                font=('Arial', 9))

    def draw_camera_frame(self, frame_bounds: dict):
        """Draw camera frame bounds based on resolution"""
        if not frame_bounds:
            return

        try:
            x1, y1 = self.machine_to_canvas(frame_bounds['x_min'], frame_bounds['y_min'])
            x2, y2 = self.machine_to_canvas(frame_bounds['x_max'], frame_bounds['y_max'])

            # Draw camera frame rectangle
            self.canvas.create_rectangle(x1, y2, x2, y1, outline=self.colors['camera_frame'], width=3, fill="")

            # Draw corner markers
            corner_size = 10
            corners = [(x1, y2), (x2, y2), (x1, y1), (x2, y1)]
            corner_offsets = [(corner_size, corner_size), (-corner_size, corner_size),
                              (corner_size, -corner_size), (-corner_size, -corner_size)]

            for (cx, cy), (dx, dy) in zip(corners, corner_offsets):
                self.canvas.create_line(cx, cy, cx + dx, cy, fill=self.colors['camera_frame'], width=3)
                self.canvas.create_line(cx, cy, cx, cy + dy, fill=self.colors['camera_frame'], width=3)

            # Add frame info
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2

            frame_info = f"Frame: {frame_bounds.get('width_mm', 0):.1f}×{frame_bounds.get('height_mm', 0):.1f}mm"

            # Background for text
            self.canvas.create_rectangle(center_x - 50, center_y - 10, center_x + 50, center_y + 10,
                                         fill=self.colors['background'], outline=self.colors['camera_frame'], width=1)

            self.canvas.create_text(center_x, center_y, text=frame_info,
                                    fill=self.colors['camera_frame'], anchor=tk.CENTER, font=('Arial', 8))

        except Exception as e:
            if self.logger:
                self.logger(f"Error drawing camera frame: {e}", "error")

    def draw_calibration_points(self, points: List[Tuple[float, float]]):
        """Draw calibration points"""
        for i, (x, y) in enumerate(points):
            canvas_x, canvas_y = self.machine_to_canvas(x, y)

            # Draw point
            self.canvas.create_oval(canvas_x - 4, canvas_y - 4, canvas_x + 4, canvas_y + 4,
                                    fill=self.colors['calibration_points'], outline="white", width=1)

            # Add point number
            self.canvas.create_text(canvas_x + 10, canvas_y - 10, text=str(i + 1),
                                    fill=self.colors['calibration_points'], anchor=tk.W,
                                    font=('Arial', 8, 'bold'))

    def get_view_info(self) -> dict:
        """Get current view information"""
        return {
            'zoom_factor': self.zoom_factor,
            'pan_offset': (self.pan_offset_x, self.pan_offset_y),
            'scale_factor': self.scale_factor,
            'machine_bounds': self.machine_bounds.copy()
        }

    def draw_transformation_triangles(self, source_triangle=None, destination_triangle=None):
        """
        Draw source and destination triangles for transformation debug visualization

        Args:
            source_triangle: List of 3 points [(x1,y1), (x2,y2), (x3,y3)] from route bounds
            destination_triangle: List of 3 points [(x1,y1), (x2,y2), (x3,y3)] from calibration
        """
        try:
            # Draw source triangle (from route bounds)
            if source_triangle and len(source_triangle) == 3:
                self._draw_debug_triangle(source_triangle,
                                          color='#00ff00',  # Green
                                          label_prefix='S',
                                          line_style='dashed')

            # Draw destination triangle (from calibration points)
            if destination_triangle and len(destination_triangle) == 3:
                self._draw_debug_triangle(destination_triangle,
                                          color='#ff00ff',  # Magenta
                                          label_prefix='D',
                                          line_style='solid')

            # Draw correspondence lines if both triangles exist
            if source_triangle and destination_triangle:
                self._draw_correspondence_lines(source_triangle, destination_triangle)

        except Exception as e:
            if self.logger:
                self.logger(f"Error drawing transformation triangles: {e}", "error")

    def _draw_debug_triangle(self, triangle_points, color='#00ff00', label_prefix='T', line_style='solid'):
        """
        Draw a single debug triangle with labeled vertices

        Args:
            triangle_points: List of 3 (x,y) tuples in machine coordinates
            color: Color for the triangle
            label_prefix: Prefix for vertex labels (S for source, D for destination)
            line_style: 'solid' or 'dashed'
        """
        # Convert points to canvas coordinates
        canvas_points = []
        for point in triangle_points:
            cx, cy = self.machine_to_canvas(point[0], point[1])
            canvas_points.append((cx, cy))

        # Draw triangle edges
        for i in range(3):
            p1 = canvas_points[i]
            p2 = canvas_points[(i + 1) % 3]

            if line_style == 'dashed':
                # Create dashed line
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                        fill=color, width=3, dash=(10, 5))
            else:
                # Solid line
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                        fill=color, width=3)

        # Draw and label vertices
        vertex_labels = ['BL', 'BR', 'TL']  # Bottom-Left, Bottom-Right, Top-Left
        vertex_colors = ['#ff0000', '#00ff00', '#0000ff']  # Red, Green, Blue

        for i, (canvas_point, machine_point) in enumerate(zip(canvas_points, triangle_points)):
            cx, cy = canvas_point
            mx, my = machine_point

            # Draw vertex circle
            radius = 8
            self.canvas.create_oval(cx - radius, cy - radius,
                                    cx + radius, cy + radius,
                                    fill=vertex_colors[i],
                                    outline=color, width=2)

            # Add vertex label
            label = f"{label_prefix}{i + 1}-{vertex_labels[i]}"
            self.canvas.create_text(cx + 15, cy - 15,
                                    text=label,
                                    fill=color,
                                    font=('Arial', 10, 'bold'),
                                    anchor=tk.W)

            # Add coordinate info
            coord_text = f"({mx:.1f}, {my:.1f})"
            self.canvas.create_text(cx + 15, cy,
                                    text=coord_text,
                                    fill=color,
                                    font=('Arial', 8),
                                    anchor=tk.W)

    def _draw_correspondence_lines(self, source_triangle, dest_triangle):
        """
        Draw lines showing correspondence between source and destination vertices
        """
        # Draw thin lines connecting corresponding vertices
        for i in range(3):
            # Convert to canvas coordinates
            src_x, src_y = self.machine_to_canvas(source_triangle[i][0], source_triangle[i][1])
            dst_x, dst_y = self.machine_to_canvas(dest_triangle[i][0], dest_triangle[i][1])

            # Draw correspondence line
            self.canvas.create_line(src_x, src_y, dst_x, dst_y,
                                    fill='#ffff00',  # Yellow
                                    width=1,
                                    dash=(5, 10))

            # Add arrow at destination end
            self._draw_arrow(src_x, src_y, dst_x, dst_y, color='#ffff00')

    def _draw_arrow(self, x1, y1, x2, y2, color='#ffff00', size=10):
        """Draw an arrow from (x1,y1) to (x2,y2)"""
        import math

        # Calculate angle
        angle = math.atan2(y2 - y1, x2 - x1)

        # Calculate arrow head points
        arrow_angle1 = angle + math.pi * 0.8
        arrow_angle2 = angle - math.pi * 0.8

        arrow_x1 = x2 + size * math.cos(arrow_angle1)
        arrow_y1 = y2 + size * math.sin(arrow_angle1)
        arrow_x2 = x2 + size * math.cos(arrow_angle2)
        arrow_y2 = y2 + size * math.sin(arrow_angle2)

        # Draw arrow head
        self.canvas.create_polygon(x2, y2, arrow_x1, arrow_y1, arrow_x2, arrow_y2,
                                   fill=color, outline=color)

    def draw_transformation_error_vectors(self, expected_points, actual_points):
        """
        Draw error vectors showing the difference between expected and actual positions

        Args:
            expected_points: List of expected positions after transformation
            actual_points: List of actual positions after transformation
        """
        if not expected_points or not actual_points:
            return

        if len(expected_points) != len(actual_points):
            return

        for i, (expected, actual) in enumerate(zip(expected_points, actual_points)):
            # Convert to canvas coordinates
            ex, ey = self.machine_to_canvas(expected[0], expected[1])
            ax, ay = self.machine_to_canvas(actual[0], actual[1])

            # Draw error vector
            self.canvas.create_line(ex, ey, ax, ay,
                                    fill='#ff0000',  # Red for error
                                    width=2,
                                    arrow=tk.LAST)

            # Calculate error magnitude
            error_mm = np.sqrt((expected[0] - actual[0]) ** 2 + (expected[1] - actual[1]) ** 2)

            # Draw error magnitude label
            mid_x = (ex + ax) / 2
            mid_y = (ey + ay) / 2
            self.canvas.create_text(mid_x, mid_y - 5,
                                    text=f"{error_mm:.2f}mm",
                                    fill='#ff0000',
                                    font=('Arial', 8))