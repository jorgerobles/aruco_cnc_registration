"""
Updated Machine Area Window
Now properly uses calculated bounds from hardware service and origin configuration
Supports negative coordinate systems like (-450,-450) to (0,0)
"""

import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Callable

import numpy as np

from gui.window_machine_area_canvas import MachineAreaCanvas
from gui.window_machine_area_panel_controls import MachineAreaControls
from services.camera_manager import CameraEvents
from services.event_broker import event_aware, event_handler, EventPriority
from services.grbl_controller import GRBLEvents
from services.hardware_service import HardwareEvents
from services.registration_manager import RegistrationEvents


@event_aware()
class MachineAreaWindow:
    """Machine area visualization window with hardware service bounds integration"""

    def __init__(self, parent_window, grbl_controller, registration_manager, routes_service,
                 hardware_service, camera_manager, logger: Optional[Callable] = None):
        self.parent_window = parent_window
        self.grbl_controller = grbl_controller
        self.registration_manager = registration_manager
        self.routes_service = routes_service
        self.camera_manager = camera_manager
        self.hardware_service = hardware_service
        self.logger = logger

        # Window state
        self.window = None
        self.status_text = None
        self.is_visible = False
        self.auto_update = True
        self.update_thread = None
        self.update_running = False

        # Components
        self.canvas_component = None
        self.controls_component = None

        # Data state
        self.current_machine_position = np.array([0.0, 0.0, 0.0])
        self.current_camera_position = None
        self.camera_view_bounds = None
        self.camera_frame_bounds = None
        self.routes_bounds = None
        self.calibration_points = []
        self.actual_routes = []

        # Camera frame parameters
        self.camera_height_mm = 100.0
        self.pixels_per_mm = 5.0
        self.camera_resolution = (640, 480)

        # Route colors
        self.route_colors = ['#f5a623', '#7ed321', '#d0021b', '#9013fe', '#50e3c2']

        # Initialize machine bounds from hardware service
        self.machine_bounds = {}  # Initialize empty first
        self._update_machine_bounds_from_hardware()

        # Update rate
        self.update_rate_ms = 500

        self.log("Machine Area Window initialized with hardware service bounds")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def _update_machine_bounds_from_hardware(self):
        """Update machine bounds from hardware service"""
        try:
            if self.hardware_service:
                # Get calculated bounds from hardware service
                bounds = self.hardware_service.get_machine_bounds()

                # FORCE update machine bounds - don't use defaults
                self.machine_bounds = bounds.copy()  # Use the exact bounds from hardware service

                # Log the bounds for debugging
                origin_name = self.hardware_service.get_machine_origin_name()
                homing = self.hardware_service.get_homing_coordinates()

                self.log(f"BOUNDS UPDATE: Origin={origin_name}, Bounds=X({bounds['x_min']:.0f},{bounds['x_max']:.0f}) Y({bounds['y_min']:.0f},{bounds['y_max']:.0f})")

                # IMMEDIATELY update canvas if it exists
                if self.canvas_component:
                    self.canvas_component.set_machine_bounds(
                        bounds['x_min'], bounds['y_min'],
                        bounds['x_max'], bounds['y_max']
                    )
                    self.log(f"Canvas bounds updated to: X({bounds['x_min']:.0f},{bounds['x_max']:.0f}) Y({bounds['y_min']:.0f},{bounds['y_max']:.0f})")

                # Update controls if they exist
                if self.controls_component:
                    size = self.hardware_service.get_machine_size()
                    self.controls_component.set_machine_bounds(size['x'], size['y'])

            else:
                self.log("ERROR: No hardware service - cannot get bounds", "error")
                # Only use fallback if no hardware service
                self.machine_bounds = {
                    'x_min': 0.0, 'x_max': 450.0,
                    'y_min': 0.0, 'y_max': 450.0,
                    'z_min': 0.0, 'z_max': 80.0
                }

        except Exception as e:
            self.log(f"ERROR updating machine bounds: {e}", "error")
            # Only use safe defaults on error
            self.machine_bounds = {
                'x_min': 0.0, 'x_max': 450.0,
                'y_min': 0.0, 'y_max': 450.0,
                'z_min': 0.0, 'z_max': 80.0
            }

    # Event handlers
    @event_handler(GRBLEvents.POSITION_CHANGED)
    def _on_position_changed(self, position: List[float]):
        """Handle machine position changes"""
        try:
            self.current_machine_position = np.array(position[:3])
            if self.is_visible and self.auto_update:
                self.schedule_update()
        except Exception:
            pass

    @event_handler(CameraEvents.CONNECTED)
    def _on_camera_connected(self, success: bool):
        """Handle camera connection events"""
        if success:
            self.update_camera_info()
            if self.is_visible and self.auto_update:
                self.schedule_update()

    @event_handler(CameraEvents.CALIBRATION_LOADED)
    def _on_camera_calibration_loaded(self, file_path: str):
        """Handle camera calibration loaded"""
        self.update_camera_info()
        if self.is_visible and self.auto_update:
            self.schedule_update()

    @event_handler(RegistrationEvents.POINT_ADDED)
    def _on_calibration_point_added(self, point_data: dict):
        """Handle new calibration point"""
        self.update_calibration_points()
        if self.is_visible and self.auto_update:
            self.schedule_update()

    @event_handler(RegistrationEvents.COMPUTED)
    def _on_registration_computed(self, computation_data: dict):
        """Handle registration computation"""
        self.update_calibration_points()
        if self.is_visible and self.auto_update:
            self.schedule_update()

    @event_handler(RegistrationEvents.CLEARED)
    def _on_calibration_cleared(self, data: dict):
        """Handle calibration points cleared"""
        self.update_calibration_points()
        if self.is_visible and self.auto_update:
            self.schedule_update()

    @event_handler(HardwareEvents.CAMERA_OFFSET_UPDATED, EventPriority.NORMAL)
    def _on_camera_offset_updated(self, offset_data: dict):
        """Handle camera offset updates"""
        try:
            x, y, z = offset_data['x'], offset_data['y'], offset_data['z']

            if hasattr(self, 'current_machine_position'):
                machine_pos = self.current_machine_position
                camera_x = machine_pos[0] + x
                camera_y = machine_pos[1] + y
                self.current_camera_position = (camera_x, camera_y)
                self.update_camera_bounds()
                if self.is_visible:
                    self.schedule_update()

            self.log(f"Camera offset updated: X{x:.2f} Y{y:.2f} Z{z:.2f}")

        except Exception as e:
            self.log(f"Error handling camera offset update: {e}", "error")

    @event_handler(HardwareEvents.MACHINE_SIZE_UPDATED, EventPriority.HIGH)
    def _on_machine_size_updated(self, data: dict):
        """Handle machine size updates - recalculate bounds"""
        self.log(f"Machine size updated: {data['x']}×{data['y']}×{data['z']}mm")
        self._update_machine_bounds_from_hardware()
        if self.is_visible:
            self.schedule_update()

    @event_handler(HardwareEvents.MACHINE_ORIGIN_UPDATED, EventPriority.HIGH)
    def _on_machine_origin_updated(self, data: dict):
        """Handle machine origin updates - recalculate bounds"""
        self.log(f"Machine origin updated: {data['origin_name']}")
        self._update_machine_bounds_from_hardware()
        if self.is_visible:
            self.schedule_update()

    def show_window(self):
        """Show the machine area visualization window"""
        if self.window is not None:
            self.window.lift()
            self.window.focus_force()
            return

        self.create_window()
        self.is_visible = True
        self.start_update_thread()
        self.log("Machine area visualization window opened")

    def hide_window(self):
        """Hide the machine area visualization window"""
        if self.window is not None:
            self.stop_update_thread()
            self.window.destroy()
            self.window = None
            self.canvas_component = None
            self.controls_component = None
            self.is_visible = False
            self.log("Machine area visualization window closed")

    def create_window(self):
        """Create the visualization window with separated components"""
        try:
            self.window = tk.Toplevel(self.parent_window)
            self.window.title("Machine Area Visualization")
            self.window.geometry("900x600")
            self.window.resizable(True, True)
            self.window.attributes('-topmost', False)
            self.window.protocol("WM_DELETE_WINDOW", self.hide_window)

            self.setup_window_layout()
            self.setup_component_callbacks()
            self.update_display()

        except Exception as e:
            self.log(f"Error creating machine area window: {e}", "error")
            self.window = None

    def setup_window_layout(self):
        """Setup window layout with separated components"""
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Canvas frame (left side)
        canvas_frame = ttk.LabelFrame(main_frame, text="Machine Area View")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Create canvas component with current machine bounds
        self.canvas_component = MachineAreaCanvas(canvas_frame, logger=self.log)

        # FORCE set the bounds from hardware service
        if self.machine_bounds:
            self.canvas_component.set_machine_bounds(
                self.machine_bounds['x_min'], self.machine_bounds['y_min'],
                self.machine_bounds['x_max'], self.machine_bounds['y_max']
            )
            self.log(f"CANVAS SETUP: Set bounds to X({self.machine_bounds['x_min']:.0f},{self.machine_bounds['x_max']:.0f}) Y({self.machine_bounds['y_min']:.0f},{self.machine_bounds['y_max']:.0f})")

        # Controls frame (right side)
        controls_frame = ttk.LabelFrame(main_frame, text="Display Options")
        controls_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # Create controls component
        self.controls_component = MachineAreaControls(controls_frame, self.log)

        # Set initial values in controls from hardware service
        if self.hardware_service:
            try:
                size = self.hardware_service.get_machine_size()
                self.controls_component.set_machine_bounds(size['x'], size['y'])
                self.controls_component.set_camera_config(self.camera_height_mm, self.pixels_per_mm)
            except Exception as e:
                self.log(f"Error setting initial control values: {e}", "error")

        # Status frame (bottom)
        status_frame = ttk.Frame(self.window)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0, 5))
        self.setup_status_display(status_frame)

    def setup_component_callbacks(self):
        """Setup callbacks between components"""
        # Canvas redraw callback
        self.canvas_component.set_redraw_callback(self.schedule_update)

        # Controls callbacks
        callbacks = {
            'display_changed': self.on_display_options_changed,
            'zoom_in': self.canvas_component.zoom_in,
            'zoom_out': self.canvas_component.zoom_out,
            'reset_view': self.canvas_component.reset_view,
            'zoom_to_fit': self.canvas_component.zoom_to_fit,
            'camera_config_changed': self.on_camera_config_changed,
            'bounds_changed': self.on_bounds_changed_from_controls,
            'auto_update_changed': self.on_auto_update_changed,
            'manual_update': self.manual_update,
            'center_view': self.center_view,
            'update_camera_info': self.update_camera_info,
            'debug_show_data': self.debug_show_data
        }

        for name, callback in callbacks.items():
            self.controls_component.set_callback(name, callback)

    def setup_status_display(self, parent):
        """Setup status display"""
        try:
            self.status_text = tk.Text(parent, height=4, wrap=tk.WORD, font=('Consolas', 8))
            self.status_text.pack(fill=tk.X)
        except Exception as e:
            self.log(f"Error setting up status display: {e}", "error")

    # Component callback handlers
    def on_display_options_changed(self, options: dict):
        """Handle display option changes"""
        self.schedule_update()

    def on_camera_config_changed(self, config: dict):
        """Handle camera configuration changes"""
        try:
            self.camera_height_mm = config['height_mm']
            self.pixels_per_mm = config['pixels_per_mm']
            self.update_camera_frame_bounds()
            self.schedule_update()
            self.log(f"Camera config updated: Height={self.camera_height_mm}mm, Scale={self.pixels_per_mm}px/mm")
        except Exception as e:
            self.log(f"Error updating camera config: {e}", "error")

    def on_bounds_changed_from_controls(self, bounds: dict):
        """Handle machine bounds changes from controls panel"""
        try:
            # Update hardware service with new machine size
            if self.hardware_service:
                x_max = bounds['x_max']
                y_max = bounds['y_max']
                z_max = self.hardware_service.get_machine_size()['z']  # Keep current Z

                self.hardware_service.set_machine_size(x_max, y_max, z_max)
                self.log(f"Machine size updated from controls: {x_max}×{y_max}×{z_max}mm")

                # Bounds will be automatically updated via hardware service event
            else:
                # Fallback: update bounds directly
                self.machine_bounds['x_max'] = bounds['x_max']
                self.machine_bounds['y_max'] = bounds['y_max']

                self.canvas_component.set_machine_bounds(
                    self.machine_bounds['x_min'], self.machine_bounds['y_min'],
                    self.machine_bounds['x_max'], self.machine_bounds['y_max']
                )

                self.log(f"Machine bounds updated directly: X={bounds['x_max']}, Y={bounds['y_max']}")

        except Exception as e:
            self.log(f"Error updating bounds from controls: {e}", "error")

    def on_auto_update_changed(self, enabled: bool):
        """Handle auto update toggle"""
        self.auto_update = enabled
        if self.auto_update:
            self.start_update_thread()
        else:
            self.stop_update_thread()

    def manual_update(self):
        """Manually trigger update"""
        try:
            self.update_all_data()
            self.update_display()
        except Exception as e:
            self.log(f"Error in manual update: {e}", "warning")

    def center_view(self):
        """Center the view"""
        if self.canvas_component:
            self.canvas_component.reset_view()

    def debug_show_data(self):
        """Debug show data"""
        if not self.controls_component.is_debug_enabled():
            return

        debug_info = [
            f"Routes: {len(self.actual_routes) if self.actual_routes else 0}",
            f"Camera pos: {self.current_camera_position}",
            f"Routes bounds: {self.routes_bounds}",
            f"Machine bounds: X({self.machine_bounds['x_min']:.0f},{self.machine_bounds['x_max']:.0f}) Y({self.machine_bounds['y_min']:.0f},{self.machine_bounds['y_max']:.0f})"
        ]

        if self.canvas_component:
            view_info = self.canvas_component.get_view_info()
            debug_info.append(f"Zoom: {view_info['zoom_factor']:.2f}")
            debug_info.append(f"Pan: ({view_info['pan_offset'][0]:.0f}, {view_info['pan_offset'][1]:.0f})")

        if self.hardware_service:
            origin = self.hardware_service.get_machine_origin_name()
            homing = self.hardware_service.get_homing_coordinates()
            debug_info.append(f"Origin: {origin} → Home({homing['x']:.0f},{homing['y']:.0f})")

        self.log(f"DEBUG: {'; '.join(debug_info)}", "info")

    # Update methods
    def start_update_thread(self):
        """Start the automatic update thread"""
        if self.update_thread is not None and self.update_thread.is_alive():
            return

        self.update_running = True
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def stop_update_thread(self):
        """Stop the automatic update thread"""
        self.update_running = False
        if self.update_thread is not None:
            self.update_thread.join(timeout=1.0)

    def update_loop(self):
        """Main update loop"""
        while self.update_running:
            try:
                if self.auto_update and self.is_visible:
                    self.update_all_data()
                    if self.window is not None:
                        self.window.after_idle(self.update_display)

                time.sleep(max(self.update_rate_ms / 1000.0, 0.2))
            except Exception as e:
                self.log(f"Error in update loop: {e}", "error")
                time.sleep(1.0)

    def schedule_update(self):
        """Schedule a display update"""
        if self.window is not None:
            self.window.after_idle(self.update_display)

    def update_all_data(self):
        """Update all data from controllers and managers"""
        try:
            # Update machine position
            if self.grbl_controller and self.grbl_controller.is_connected:
                try:
                    current_time = time.time()
                    if not hasattr(self, '_last_grbl_update') or (current_time - self._last_grbl_update) > 0.5:
                        position = self.grbl_controller.get_position()
                        if position:
                            self.current_machine_position = np.array(position[:3])
                        self._last_grbl_update = current_time
                except Exception as e:
                    if not hasattr(self, '_last_grbl_error_time') or (
                            current_time - getattr(self, '_last_grbl_error_time', 0)) > 10.0:
                        self.log(f"GRBL communication error: {e}", "warning")
                        self._last_grbl_error_time = current_time

            # Update camera position
            self.update_camera_position()

            # Update routes
            if self.routes_service:
                try:
                    self.routes_bounds = self.routes_service.get_route_bounds()
                    self.actual_routes = self.routes_service.get_routes()
                except Exception:
                    self.routes_bounds = None
                    self.actual_routes = []
            else:
                self.routes_bounds = None
                self.actual_routes = []

            # Update calibration points
            self.update_calibration_points()

        except Exception as e:
            self.log(f"Error updating data: {e}", "error")

    def update_camera_position(self):
        """Update camera position based on machine position and offset"""
        try:
            if hasattr(self, 'current_machine_position') and self.hardware_service:
                offset = self.hardware_service.get_camera_offset()
                machine_pos = self.current_machine_position
                camera_x = machine_pos[0] + offset['x']
                camera_y = machine_pos[1] + offset['y']
                self.current_camera_position = (camera_x, camera_y)
                self.update_camera_bounds()
                self.update_camera_frame_bounds()
        except Exception:
            self.current_camera_position = None
            self.camera_view_bounds = None
            self.camera_frame_bounds = None

    def update_camera_bounds(self):
        """Update camera field of view bounds"""
        if not self.current_camera_position:
            self.camera_view_bounds = None
            return

        try:
            camera_fov_width = 50.0
            camera_fov_height = 40.0
            cam_x, cam_y = self.current_camera_position

            self.camera_view_bounds = {
                'x_min': cam_x - camera_fov_width / 2,
                'x_max': cam_x + camera_fov_width / 2,
                'y_min': cam_y - camera_fov_height / 2,
                'y_max': cam_y + camera_fov_height / 2
            }
        except Exception as e:
            self.camera_view_bounds = None

    def update_camera_frame_bounds(self):
        """Update camera frame bounds based on resolution and scale"""
        if not self.current_camera_position:
            self.camera_frame_bounds = None
            return

        try:
            frame_width_mm = self.camera_resolution[0] / self.pixels_per_mm
            frame_height_mm = self.camera_resolution[1] / self.pixels_per_mm
            cam_x, cam_y = self.current_camera_position

            self.camera_frame_bounds = {
                'x_min': cam_x - frame_width_mm / 2,
                'x_max': cam_x + frame_width_mm / 2,
                'y_min': cam_y - frame_height_mm / 2,
                'y_max': cam_y + frame_height_mm / 2,
                'width_mm': frame_width_mm,
                'height_mm': frame_height_mm
            }
        except Exception as e:
            self.camera_frame_bounds = None

    def update_calibration_points(self):
        """Update calibration points from registration manager"""
        self.calibration_points = []
        try:
            if self.registration_manager:
                machine_positions = self.registration_manager.get_machine_positions()
                self.calibration_points = [(pos[0], pos[1]) for pos in machine_positions]
        except Exception:
            pass

    def update_camera_info(self):
        """Update camera information from camera manager"""
        if not self.camera_manager:
            return

        try:
            camera_info = self.camera_manager.get_camera_info()
            if camera_info.get('connected', False):
                width = camera_info.get('width', 640)
                height = camera_info.get('height', 480)
                self.camera_resolution = (width, height)

                if self.controls_component:
                    self.controls_component.update_resolution_display(width, height)

                self.log(f"Camera info updated: {width}x{height}")

            self.update_camera_frame_bounds()
            self.schedule_update()

        except Exception as e:
            self.log(f"Error updating camera info: {e}", "error")

    def update_display(self):
        """Update the canvas display using components"""
        if not self.canvas_component:
            return

        try:
            # Get display options from controls
            display_options = self.controls_component.get_display_options()

            # Update zoom display
            view_info = self.canvas_component.get_view_info()
            self.controls_component.update_zoom_display(view_info['zoom_factor'])

            # Clear and redraw
            self.canvas_component.clear()

            # Draw elements based on display options
            if display_options['show_grid']:
                self.canvas_component.draw_grid()

            if display_options['show_machine_bounds']:
                self.canvas_component.draw_machine_bounds()

            # Draw origin marker (0,0) - where coordinate system origin is
            self.canvas_component.draw_origin_marker()

            # Draw homing position - where machine goes when homing
            if self.hardware_service:
                homing_pos = self.hardware_service.get_homing_position()
                self.canvas_component.draw_homing_position(homing_pos)

            if display_options['show_route_paths'] and self.actual_routes:
                self.canvas_component.draw_route_paths(self.actual_routes, self.route_colors)
            elif display_options['show_routes'] and self.routes_bounds:
                self.canvas_component.draw_routes(self.routes_bounds)

            if display_options['show_camera_frame'] and self.camera_frame_bounds:
                self.canvas_component.draw_camera_frame(self.camera_frame_bounds)

            if display_options['show_calibration_points']:
                self.canvas_component.draw_calibration_points(self.calibration_points)

            # Always draw machine position
            self.canvas_component.draw_machine_position(self.current_machine_position)

            if display_options['show_camera_position'] and self.current_camera_position:
                self.canvas_component.draw_camera_position(self.current_camera_position)

            # Update status
            self.update_status_display()

        except Exception as e:
            self.log(f"Error updating display: {e}", "error")

    def update_status_display(self):
        """Update status text display"""
        if not self.status_text:
            return

        try:
            status_lines = []

            # Machine status
            pos = self.current_machine_position
            status_lines.append(f"Machine: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})")

            # Machine bounds info
            bounds = self.machine_bounds
            status_lines.append(f"Bounds: X({bounds['x_min']:.0f},{bounds['x_max']:.0f}) Y({bounds['y_min']:.0f},{bounds['y_max']:.0f})")

            # Camera status
            if self.current_camera_position:
                cam_x, cam_y = self.current_camera_position
                status_lines.append(f"Camera: ({cam_x:.1f}, {cam_y:.1f})")
            else:
                status_lines.append("Camera: No position")

            # Routes status
            if self.actual_routes:
                total_points = sum(len(route) for route in self.actual_routes)
                status_lines.append(f"Routes: {len(self.actual_routes)} paths, {total_points} points")
            else:
                status_lines.append("Routes: None loaded")

            # View status with origin info
            if self.canvas_component:
                view_info = self.canvas_component.get_view_info()
                origin_name = self.hardware_service.get_machine_origin_name() if self.hardware_service else "unknown"
                status_lines.append(f"View: Zoom {view_info['zoom_factor']:.1f}x | Origin: {origin_name}")

            # Update text widget
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, "\n".join(status_lines))

        except Exception as e:
            self.log(f"Error updating status display: {e}", "error")

    # Public interface methods
    def set_machine_bounds(self, x_max: float, y_max: float, x_min: float = None, y_min: float = None):
        """Set machine bounds programmatically"""
        if self.hardware_service:
            # Update through hardware service for consistency
            current_size = self.hardware_service.get_machine_size()
            self.hardware_service.set_machine_size(
                abs(x_max - (x_min or 0)),
                abs(y_max - (y_min or 0)),
                current_size['z']
            )
        else:
            # Direct update as fallback
            self.machine_bounds = {
                'x_min': x_min or 0.0, 'x_max': x_max,
                'y_min': y_min or 0.0, 'y_max': y_max,
                'z_min': self.machine_bounds.get('z_min', 0.0),
                'z_max': self.machine_bounds.get('z_max', 80.0)
            }

            if self.canvas_component:
                self.canvas_component.set_machine_bounds(
                    self.machine_bounds['x_min'], self.machine_bounds['y_min'],
                    self.machine_bounds['x_max'], self.machine_bounds['y_max']
                )

    def get_window_status(self) -> dict:
        """Get current window status"""
        status = {
            'visible': self.is_visible,
            'auto_update': self.auto_update,
            'machine_bounds': self.machine_bounds.copy(),
            'current_machine_position': self.current_machine_position.tolist(),
            'current_camera_position': self.current_camera_position,
            'routes_bounds': self.routes_bounds,
            'calibration_points_count': len(self.calibration_points)
        }

        if self.hardware_service:
            status['hardware_info'] = {
                'origin': self.hardware_service.get_machine_origin_name(),
                'machine_size': self.hardware_service.get_machine_size(),
                'homing_coordinates': self.hardware_service.get_homing_coordinates()
            }

        if self.canvas_component:
            view_info = self.canvas_component.get_view_info()
            status.update(view_info)

        return status

    def cleanup(self):
        """Clean up resources"""
        self.stop_update_thread()
        if self.window:
            self.window.destroy()
        self.log("Machine area visualization cleaned up")