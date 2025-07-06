"""
Machine Area Canvas Component
Handles canvas display, zoom, pan, and drawing operations
"""

import tkinter as tk
from typing import Tuple, List, Optional, Callable
import numpy as np


class MachineAreaCanvas:
    """Canvas component for machine area visualization with zoom/pan interactions"""

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

        # Machine bounds for coordinate transformation
        self.machine_bounds = {
            'x_min': 0.0, 'x_max': 400.0,
            'y_min': 0.0, 'y_max': 400.0
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
            'text': '#ffffff'
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
        # Apply base transformation
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

    def draw_grid(self, grid_spacing: float = 20.0):
        """Draw coordinate grid"""
        # Vertical lines
        x = self.machine_bounds['x_min']
        while x <= self.machine_bounds['x_max']:
            x1, y1 = self.machine_to_canvas(x, self.machine_bounds['y_min'])
            x2, y2 = self.machine_to_canvas(x, self.machine_bounds['y_max'])
            self.canvas.create_line(x1, y1, x2, y2, fill=self.colors['grid'], width=1)
            x += grid_spacing

        # Horizontal lines
        y = self.machine_bounds['y_min']
        while y <= self.machine_bounds['y_max']:
            x1, y1 = self.machine_to_canvas(self.machine_bounds['x_min'], y)
            x2, y2 = self.machine_to_canvas(self.machine_bounds['x_max'], y)
            self.canvas.create_line(x1, y1, x2, y2, fill=self.colors['grid'], width=1)
            y += grid_spacing

    def draw_machine_bounds(self):
        """Draw machine bounds rectangle"""
        x1, y1 = self.machine_to_canvas(self.machine_bounds['x_min'], self.machine_bounds['y_min'])
        x2, y2 = self.machine_to_canvas(self.machine_bounds['x_max'], self.machine_bounds['y_max'])

        self.canvas.create_rectangle(x1, y2, x2, y1, outline=self.colors['machine_bounds'], width=2, fill="")

        # Add coordinate labels
        self.canvas.create_text(x1 + 5, y1 - 5, text="(0,0)", fill=self.colors['text'], anchor=tk.SW)
        self.canvas.create_text(x2 - 5, y2 + 5,
                                text=f"({self.machine_bounds['x_max']},{self.machine_bounds['y_max']})",
                                fill=self.colors['text'], anchor=tk.NE)

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
            self.log(f"Error drawing routes: {e}", "error")

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
                self.canvas.create_line(*canvas_points, fill=color, width=2, smooth=True)

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
        size = 6
        self.canvas.create_line(canvas_x - size, canvas_y, canvas_x + size, canvas_y,
                                fill=self.colors['machine_position'], width=3)
        self.canvas.create_line(canvas_x, canvas_y - size, canvas_x, canvas_y + size,
                                fill=self.colors['machine_position'], width=3)

        # Add position label
        self.canvas.create_text(canvas_x + 10, canvas_y - 10,
                                text=f"M({x:.1f},{y:.1f})",
                                fill=self.colors['machine_position'], anchor=tk.W)

    def draw_camera_position(self, position: Tuple[float, float]):
        """Draw current camera position"""
        x, y = position
        canvas_x, canvas_y = self.machine_to_canvas(x, y)

        # Draw camera position as circle
        radius = 5
        self.canvas.create_oval(canvas_x - radius, canvas_y - radius,
                                canvas_x + radius, canvas_y + radius,
                                fill=self.colors['camera_position'], outline="white", width=2)

        # Add position label
        self.canvas.create_text(canvas_x + 10, canvas_y + 10,
                                text=f"C({x:.1f},{y:.1f})",
                                fill=self.colors['camera_position'], anchor=tk.W)

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
            corner_size = 8
            corners = [(x1, y2), (x2, y2), (x1, y1), (x2, y1)]
            corner_offsets = [(corner_size, corner_size), (-corner_size, corner_size),
                              (corner_size, -corner_size), (-corner_size, -corner_size)]

            for (cx, cy), (dx, dy) in zip(corners, corner_offsets):
                self.canvas.create_line(cx, cy, cx + dx, cy, fill=self.colors['camera_frame'], width=3)
                self.canvas.create_line(cx, cy, cx, cy + dy, fill=self.colors['camera_frame'], width=3)

            # Add frame info
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2

            frame_info = f"Frame: {frame_bounds.get('width_mm', 0):.1f}x{frame_bounds.get('height_mm', 0):.1f}mm"

            # Background for text
            self.canvas.create_rectangle(center_x - 40, center_y - 10, center_x + 40, center_y + 10,
                                         fill=self.colors['background'], outline=self.colors['camera_frame'], width=1)

            self.canvas.create_text(center_x, center_y, text=frame_info,
                                    fill=self.colors['camera_frame'], anchor=tk.CENTER, font=('Arial', 8))

        except Exception as e:
            self.log(f"Error drawing camera frame: {e}", "error")

    def draw_calibration_points(self, points: List[Tuple[float, float]]):
        """Draw calibration points"""
        for i, (x, y) in enumerate(points):
            canvas_x, canvas_y = self.machine_to_canvas(x, y)

            # Draw point
            self.canvas.create_oval(canvas_x - 3, canvas_y - 3, canvas_x + 3, canvas_y + 3,
                                    fill=self.colors['calibration_points'], outline="white", width=1)

            # Add point number
            self.canvas.create_text(canvas_x + 8, canvas_y - 8, text=str(i + 1),
                                    fill=self.colors['calibration_points'], anchor=tk.W)

    def get_view_info(self) -> dict:
        """Get current view information"""
        return {
            'zoom_factor': self.zoom_factor,
            'pan_offset': (self.pan_offset_x, self.pan_offset_y),
            'scale_factor': self.scale_factor,
            'machine_bounds': self.machine_bounds.copy()
        }