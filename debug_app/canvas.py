"""
Canvas - Visualization canvas for routes and registration points
Clean implementation referencing window_machine_area_canvas.py drawing patterns
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Tuple, Optional


class Canvas:
    """Canvas for visualizing routes and registration data with zoom and pan"""

    def __init__(self, parent):
        self.parent = parent

        # Machine coordinate system: 450x450mm, top-right origin (0,0) to (-450,-450)
        self.machine_bounds = {
            'x_min': -450.0,
            'x_max': 0.0,
            'y_min': -450.0,
            'y_max': 0.0,
            'width': 450.0,
            'height': 450.0
        }

        # View transformation (zoom and pan)
        self.view_scale = 1.0
        self.view_offset_x = 0.0
        self.view_offset_y = 0.0
        self.min_scale = 0.1
        self.max_scale = 20.0

        # Mouse interaction state
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.dragging = False

        # Current visualization data (for redraw)
        self.current_data = {
            'original_routes': None,
            'transformed_routes': None,
            'registration_points': None,
            'source_triangle': None,
            'destination_triangle': None
        }

        # Colors
        self.colors = {
            'background': '#f8f8f8',
            'grid': '#e0e0e0',
            'grid_major': '#c0c0c0',
            'origin': '#ff0000',
            'bounds': '#808080',
            'text': '#333333',
            'original_routes': ['#f5a623', '#7ed321', '#d0021b', '#9013fe', '#50e3c2'],
            'transformed_routes': ['#ff8c00', '#32cd32', '#dc143c', '#9400d3', '#00ced1'],
            'registration_points': '#cc0000',
            'source_triangle': '#0066cc',
            'destination_triangle': '#cc0000'
        }

        self.create_widgets()
        self.setup_mouse_bindings()
        self.draw_static_elements()

    def create_widgets(self):
        """Create canvas and coordinate label"""
        # Main frame
        main_frame = ttk.Frame(self.parent)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas
        self.canvas = tk.Canvas(
            main_frame,
            bg=self.colors['background'],
            width=800,
            height=600
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Coordinate display
        self.coord_label = ttk.Label(self.parent, text="Machine coordinates | Mouse: Drag=Pan, Wheel=Zoom, R=Reset")
        self.coord_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Mouse motion for coordinates
        self.canvas.bind('<Motion>', self._on_mouse_move)

    def setup_mouse_bindings(self):
        """Setup mouse interactions for zoom and pan"""
        # Mouse wheel for zoom
        self.canvas.bind('<MouseWheel>', self._on_mouse_wheel)
        self.canvas.bind('<Button-4>', self._on_mouse_wheel)  # Linux scroll up
        self.canvas.bind('<Button-5>', self._on_mouse_wheel)  # Linux scroll down

        # Mouse drag for pan
        self.canvas.bind('<ButtonPress-1>', self._on_mouse_press)
        self.canvas.bind('<B1-Motion>', self._on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_mouse_release)

        # Mouse motion for coordinates (always)
        self.canvas.bind('<Motion>', self._on_mouse_move)

        # Keyboard shortcuts
        self.canvas.bind('<KeyPress-r>', self._on_reset_view)
        self.canvas.bind('<KeyPress-R>', self._on_reset_view)  # Also capital R
        self.canvas.bind('<KeyPress-f>', self._on_fit_view)
        self.canvas.bind('<KeyPress-F>', self._on_fit_view)  # Also capital F

        # Make canvas focusable for keyboard events
        self.canvas.focus_set()

        # Ensure canvas gets focus when clicked
        def focus_canvas(event):
            self.canvas.focus_set()
            return self._on_mouse_press(event)

        self.canvas.bind('<Button-1>', focus_canvas)

    def machine_to_canvas(self, machine_x: float, machine_y: float) -> Tuple[int, int]:
        """Convert machine coordinates to canvas coordinates with zoom and pan - FIXED aspect ratio"""
        try:
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            # Handle case where canvas not yet drawn
            if canvas_width <= 1:
                canvas_width = 800
            if canvas_height <= 1:
                canvas_height = 600

            # Get canvas center
            center_x = canvas_width / 2
            center_y = canvas_height / 2

            # Normalize machine coordinates to 0-1 range
            norm_x = (machine_x - self.machine_bounds['x_min']) / self.machine_bounds['width']
            norm_y = (machine_y - self.machine_bounds['y_min']) / self.machine_bounds['height']

            # Flip Y axis for display (SVG coordinates)
            norm_y = 1 - norm_y

            # Use same scale for both axes to maintain aspect ratio
            # Base scale on the smaller canvas dimension to ensure everything fits
            margin = 60
            available_width = canvas_width - 2 * margin
            available_height = canvas_height - 2 * margin
            base_scale = min(available_width, available_height)

            # Convert normalized coordinates to pixels, maintaining square aspect ratio
            pixel_x = (norm_x - 0.5) * base_scale * self.view_scale
            pixel_y = (norm_y - 0.5) * base_scale * self.view_scale

            # Apply pan offset and center on canvas
            canvas_x = center_x + pixel_x + self.view_offset_x
            canvas_y = center_y + pixel_y + self.view_offset_y

            return int(canvas_x), int(canvas_y)

        except Exception:
            return 0, 0

    def canvas_to_machine(self, canvas_x: int, canvas_y: int) -> Tuple[float, float]:
        """Convert canvas coordinates to machine coordinates with zoom and pan - FIXED aspect ratio"""
        try:
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            if canvas_width <= 1:
                canvas_width = 800
            if canvas_height <= 1:
                canvas_height = 600

            # Get canvas center
            center_x = canvas_width / 2
            center_y = canvas_height / 2

            # Remove pan offset and center
            pixel_x = canvas_x - center_x - self.view_offset_x
            pixel_y = canvas_y - center_y - self.view_offset_y

            # Use same scale calculation as forward transform
            margin = 60
            available_width = canvas_width - 2 * margin
            available_height = canvas_height - 2 * margin
            base_scale = min(available_width, available_height)

            # Convert pixels back to normalized coordinates
            if self.view_scale != 0 and base_scale != 0:
                norm_x = pixel_x / (base_scale * self.view_scale) + 0.5
                norm_y = pixel_y / (base_scale * self.view_scale) + 0.5
            else:
                norm_x = norm_y = 0.5

            # Flip Y axis back
            norm_y = 1 - norm_y

            # Convert from normalized coordinates back to machine coordinates
            machine_x = self.machine_bounds['x_min'] + norm_x * self.machine_bounds['width']
            machine_y = self.machine_bounds['y_min'] + norm_y * self.machine_bounds['height']

            return machine_x, machine_y

        except Exception:
            return 0.0, 0.0

    def draw_static_elements(self):
        """Draw grid, bounds, and origin"""
        # Draw grid
        self._draw_grid()

        # Draw machine bounds
        self._draw_machine_bounds()

        # Draw origin
        self._draw_origin()

    def _draw_grid(self):
        """Draw coordinate grid"""
        # Major grid lines every 50mm
        for x in range(-450, 1, 50):
            x1, y1 = self.machine_to_canvas(x, -450)
            x2, y2 = self.machine_to_canvas(x, 0)
            self.canvas.create_line(x1, y1, x2, y2, fill=self.colors['grid_major'])

            # Grid labels (only if scale is reasonable)
            if self.view_scale > 0.3 and x != 0:
                label_x, label_y = self.machine_to_canvas(x, 0)
                self.canvas.create_text(label_x, label_y - 12, text=f"{x}",
                                      fill=self.colors['text'], font=('Arial', 8))

        for y in range(-450, 1, 50):
            x1, y1 = self.machine_to_canvas(-450, y)
            x2, y2 = self.machine_to_canvas(0, y)
            self.canvas.create_line(x1, y1, x2, y2, fill=self.colors['grid_major'])

            # Grid labels (only if scale is reasonable)
            if self.view_scale > 0.3 and y != 0:
                label_x, label_y = self.machine_to_canvas(0, y)
                self.canvas.create_text(label_x + 12, label_y, text=f"{y}",
                                      fill=self.colors['text'], font=('Arial', 8))

        # Minor grid lines every 10mm (only if zoomed in enough)
        if self.view_scale > 0.8:
            for x in range(-450, 1, 10):
                if x % 50 != 0:  # Skip major grid positions
                    x1, y1 = self.machine_to_canvas(x, -450)
                    x2, y2 = self.machine_to_canvas(x, 0)
                    self.canvas.create_line(x1, y1, x2, y2, fill=self.colors['grid'])

            for y in range(-450, 1, 10):
                if y % 50 != 0:  # Skip major grid positions
                    x1, y1 = self.machine_to_canvas(-450, y)
                    x2, y2 = self.machine_to_canvas(0, y)
                    self.canvas.create_line(x1, y1, x2, y2, fill=self.colors['grid'])

    def _draw_machine_bounds(self):
        """Draw machine area bounds"""
        x1, y1 = self.machine_to_canvas(-450, -450)
        x2, y2 = self.machine_to_canvas(0, 0)

        self.canvas.create_rectangle(x1, y1, x2, y2, outline=self.colors['bounds'], width=2)

        # Machine area label (only if scale is reasonable)
        if self.view_scale > 0.2:
            center_x, center_y = self.machine_to_canvas(-225, -225)
            font_size = max(8, min(14, int(12 * self.view_scale)))
            self.canvas.create_text(center_x, center_y, text="Machine Area\n450×450mm",
                                  fill=self.colors['bounds'], font=('Arial', font_size, 'bold'))

    def _draw_origin(self):
        """Draw origin marker at (0,0)"""
        origin_x, origin_y = self.machine_to_canvas(0, 0)

        # Origin cross (scale with zoom)
        size = max(8, min(20, int(12 * self.view_scale)))
        self.canvas.create_line(origin_x - size, origin_y, origin_x + size, origin_y,
                              fill=self.colors['origin'], width=3)
        self.canvas.create_line(origin_x, origin_y - size, origin_x, origin_y + size,
                              fill=self.colors['origin'], width=3)

        # Origin label (only if scale is reasonable)
        if self.view_scale > 0.4:
            font_size = max(8, min(12, int(10 * self.view_scale)))
            self.canvas.create_text(origin_x + 15, origin_y - 15, text="(0,0)",
                                  fill=self.colors['origin'], font=('Arial', font_size, 'bold'))

    def update_visualization(self, original_routes=None, transformed_routes=None,
                           registration_points=None, source_triangle=None, destination_triangle=None):
        """Update visualization with new data"""
        # Store current data for redraw
        self.current_data = {
            'original_routes': original_routes,
            'transformed_routes': transformed_routes,
            'registration_points': registration_points,
            'source_triangle': source_triangle,
            'destination_triangle': destination_triangle
        }

        self._redraw_all()

    def _redraw_all(self):
        """Redraw all elements (static + dynamic)"""
        # Clear everything
        self.canvas.delete('all')

        # Redraw static elements
        self.draw_static_elements()

        # Redraw dynamic elements
        data = self.current_data

        # Draw original routes (behind transformed routes)
        if data['original_routes']:
            self._draw_routes(data['original_routes'], 'original')

        # Draw registration points
        if data['registration_points']:
            self._draw_registration_points(data['registration_points'])

        # Draw triangles
        if data['source_triangle']:
            self._draw_triangle(data['source_triangle'], 'source')

        if data['destination_triangle']:
            self._draw_triangle(data['destination_triangle'], 'destination')

        # Draw transformed routes (on top)
        if data['transformed_routes']:
            self._draw_routes(data['transformed_routes'], 'transformed')

    def _draw_routes(self, routes: List[List[Tuple[float, float]]], route_type: str):
        """Draw routes with colors and labels"""
        if route_type == 'original':
            colors = self.colors['original_routes']
            prefix = 'R'
        else:
            colors = self.colors['transformed_routes']
            prefix = 'T'

        for route_idx, route in enumerate(routes):
            if len(route) < 2:
                continue

            color = colors[route_idx % len(colors)]

            # Convert route points to canvas coordinates
            canvas_points = []
            for x, y in route:
                canvas_x, canvas_y = self.machine_to_canvas(x, y)
                canvas_points.extend([canvas_x, canvas_y])

            if len(canvas_points) >= 4:
                # Draw route path
                line_width = max(1, int(3 * self.view_scale)) if route_type == 'transformed' else max(1, int(2 * self.view_scale))
                self.canvas.create_line(*canvas_points, fill=color, width=line_width, smooth=False)

                # Draw start point (green circle) - scale with zoom
                start_x, start_y = canvas_points[0], canvas_points[1]
                point_size = max(2, int(4 * self.view_scale))
                self.canvas.create_oval(start_x - point_size, start_y - point_size,
                                      start_x + point_size, start_y + point_size,
                                      fill='green', outline='white', width=1)

                # Draw end point (red square) - scale with zoom
                end_x, end_y = canvas_points[-2], canvas_points[-1]
                self.canvas.create_rectangle(end_x - point_size, end_y - point_size,
                                           end_x + point_size, end_y + point_size,
                                           fill='red', outline='white', width=1)

                # Route label (only if zoomed in enough)
                if self.view_scale > 0.3:
                    mid_idx = len(canvas_points) // 4 * 2
                    mid_x, mid_y = canvas_points[mid_idx], canvas_points[mid_idx + 1]
                    font_size = max(8, min(12, int(10 * self.view_scale)))

                    self.canvas.create_text(mid_x + 8, mid_y - 8, text=f"{prefix}{route_idx + 1}",
                                          fill=color, anchor=tk.W, font=('Arial', font_size, 'bold'))

    def _draw_registration_points(self, registration_points):
        """Draw registration points as diamonds with labels"""
        for i, point in enumerate(registration_points):
            machine_pos = point['machine_pos']
            x, y = machine_pos[0], machine_pos[1]
            canvas_x, canvas_y = self.machine_to_canvas(x, y)

            # Draw diamond - scale with zoom
            size = max(4, int(7 * self.view_scale))
            points = [
                canvas_x, canvas_y - size,  # Top
                canvas_x + size, canvas_y,  # Right
                canvas_x, canvas_y + size,  # Bottom
                canvas_x - size, canvas_y   # Left
            ]
            self.canvas.create_polygon(points, fill=self.colors['registration_points'],
                                     outline='white', width=2)

            # Point label (only if zoomed in enough)
            if self.view_scale > 0.3:
                font_size = max(8, min(12, int(10 * self.view_scale)))
                self.canvas.create_text(canvas_x + 12, canvas_y - 12, text=f"P{i + 1}",
                                      fill=self.colors['registration_points'], anchor=tk.W,
                                      font=('Arial', font_size, 'bold'))

    def _draw_triangle(self, triangle: List[Tuple[float, float]], triangle_type: str):
        """Draw triangle with labels"""
        if len(triangle) != 3:
            return

        if triangle_type == 'source':
            color = self.colors['source_triangle']
            dash = (6, 6)
            width = max(1, int(2 * self.view_scale))
        else:
            color = self.colors['destination_triangle']
            dash = None
            width = max(2, int(3 * self.view_scale))

        # Convert triangle points to canvas coordinates
        canvas_points = []
        for x, y in triangle:
            canvas_x, canvas_y = self.machine_to_canvas(x, y)
            canvas_points.extend([canvas_x, canvas_y])

        # Close the triangle
        canvas_points.extend([canvas_points[0], canvas_points[1]])

        # Draw triangle outline
        self.canvas.create_line(*canvas_points, fill=color, width=width, dash=dash)

        # Draw vertices - scale with zoom
        vertex_size = max(2, int(4 * self.view_scale))
        for i in range(0, len(canvas_points) - 2, 2):
            vertex_x, vertex_y = canvas_points[i], canvas_points[i + 1]
            self.canvas.create_oval(vertex_x - vertex_size, vertex_y - vertex_size,
                                  vertex_x + vertex_size, vertex_y + vertex_size,
                                  fill=color, outline='white', width=2)

        # Triangle label at center (only if zoomed in enough)
        if self.view_scale > 0.2:
            center_x = sum(canvas_points[i] for i in range(0, len(canvas_points) - 2, 2)) // 3
            center_y = sum(canvas_points[i] for i in range(1, len(canvas_points) - 1, 2)) // 3

            label = f"{triangle_type.capitalize()}\nTriangle"
            font_size = max(8, min(11, int(9 * self.view_scale)))
            self.canvas.create_text(center_x, center_y, text=label, fill=color,
                                  font=('Arial', font_size, 'bold'), justify=tk.CENTER)

    # Mouse event handlers
    def _on_mouse_wheel(self, event):
        """Handle mouse wheel for zooming"""
        try:
            # Determine zoom direction
            if event.delta > 0 or event.num == 4:  # Zoom in
                zoom_factor = 1.2
            else:  # Zoom out
                zoom_factor = 0.8

            # Calculate new scale
            new_scale = self.view_scale * zoom_factor

            # Apply zoom limits
            if new_scale < self.min_scale:
                new_scale = self.min_scale
                zoom_factor = new_scale / self.view_scale
            elif new_scale > self.max_scale:
                new_scale = self.max_scale
                zoom_factor = new_scale / self.view_scale

            # Get mouse position relative to canvas
            mouse_x = event.x
            mouse_y = event.y

            # Calculate the point in machine coordinates that's under the mouse
            machine_point_before = self.canvas_to_machine(mouse_x, mouse_y)

            # Update scale
            self.view_scale = new_scale

            # Calculate where that same machine point would be after zoom
            canvas_point_after = self.machine_to_canvas(machine_point_before[0], machine_point_before[1])

            # Adjust pan offset so the point under mouse stays in same place
            self.view_offset_x += mouse_x - canvas_point_after[0]
            self.view_offset_y += mouse_y - canvas_point_after[1]

            # Redraw everything
            self._redraw_all()

        except Exception as e:
            pass  # Silent error handling for smooth interaction

    def _on_mouse_press(self, event):
        """Handle mouse press for starting pan"""
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.dragging = True
        self.canvas.configure(cursor="fleur")  # Change cursor to indicate dragging
        # Prevent event from bubbling up
        return "break"

    def _on_mouse_drag(self, event):
        """Handle mouse drag for panning"""
        if not self.dragging:
            return "break"

        try:
            # Calculate drag distance in canvas pixels
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y

            # Apply drag distance directly to pan offset
            self.view_offset_x += dx
            self.view_offset_y += dy

            # Update last mouse position
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y

            # Redraw everything
            self._redraw_all()

        except Exception as e:
            print(f"Drag error: {e}")  # Debug output

        return "break"

    def _on_mouse_release(self, event):
        """Handle mouse release for ending pan"""
        self.dragging = False
        self.canvas.configure(cursor="")  # Reset cursor
        return "break"

    def _on_reset_view(self, event=None):
        """Reset view to default zoom and pan"""
        self.view_scale = 1.0
        self.view_offset_x = 0.0
        self.view_offset_y = 0.0
        self._redraw_all()

    def _on_fit_view(self, event=None):
        """Fit view to show all content (placeholder for future enhancement)"""
        # For now, just reset view
        self._on_reset_view()

    def _on_mouse_move(self, event):
        """Handle mouse motion for coordinate display"""
        try:
            machine_x, machine_y = self.canvas_to_machine(event.x, event.y)
            zoom_info = f" | Zoom: {self.view_scale:.1f}x"
            self.coord_label.config(text=f"Machine: X={machine_x:.1f}mm  Y={machine_y:.1f}mm{zoom_info}")
        except Exception:
            self.coord_label.config(text="Coordinate display error")