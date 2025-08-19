"""
Updated Machine Area Window with FOV Integration
Now uses only camera manager data for FOV - no manual controls
Supports negative coordinate systems and proper bounds from hardware service
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
    """Machine area visualization window with FOV integration and hardware service bounds"""

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

        # Camera resolution (for fallback calculations if no FOV data available)
        self.camera_resolution = (640, 480)

        # Route colors
        self.route_colors = ['#f5a623', '#7ed321', '#d0021b', '#9013fe', '#50e3c2']

        # Initialize machine bounds from hardware service
        self.machine_bounds = {}
        self._update_machine_bounds_from_hardware()

        # Update rate
        self.update_rate_ms = 500

        self.log("Machine Area Window initialized with camera manager FOV integration")

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def _update_machine_bounds_from_hardware(self):
        """Update machine bounds from hardware service"""
        try:
            if self.hardware_service:
                bounds = self.hardware_service.get_machine_bounds()
                self.machine_bounds = bounds.copy()

                origin_name = self.hardware_service.get_machine_origin_name()
                self.log(
                    f"BOUNDS UPDATE: Origin={origin_name}, Bounds=X({bounds['x_min']:.0f},{bounds['x_max']:.0f}) Y({bounds['y_min']:.0f},{bounds['y_max']:.0f})")

                # Update canvas if it exists
                if self.canvas_component:
                    self.canvas_component.set_machine_bounds(
                        bounds['x_min'], bounds['y_min'],
                        bounds['x_max'], bounds['y_max']
                    )

                # Update controls if they exist
                if self.controls_component:
                    size = self.hardware_service.get_machine_size()
                    self.controls_component.set_machine_bounds(size['x'], size['y'])

            else:
                self.log("ERROR: No hardware service - using fallback bounds", "error")
                self.machine_bounds = {
                    'x_min': 0.0, 'x_max': 450.0,
                    'y_min': 0.0, 'y_max': 450.0,
                    'z_min': 0.0, 'z_max': 80.0
                }

        except Exception as e:
            self.log(f"ERROR updating machine bounds: {e}", "error")
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

    @event_handler(CameraEvents.FOV_CALCULATED, EventPriority.NORMAL)
    def _on_fov_calculated(self, fov_data: dict):
        """Handle FOV calculation events"""
        self.log(f"FOV data received: {fov_data['width_mm']:.1f}×{fov_data['height_mm']:.1f}mm")
        self.update_camera_frame_bounds()
        self._update_camera_status_in_controls()
        if self.is_visible and self.auto_update:
            self.schedule_update()

    @event_handler(CameraEvents.FOV_UPDATED, EventPriority.NORMAL)
    def _on_fov_updated(self, fov_data):
        """Handle FOV data updates"""
        self.update_camera_frame_bounds()
        self._update_camera_status_in_controls()
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
        """Handle machine size updates"""
        self.log(f"Machine size updated: {data['x']}×{data['y']}×{data['z']}mm")
        self._update_machine_bounds_from_hardware()
        if self.is_visible:
            self.schedule_update()

    @event_handler(HardwareEvents.MACHINE_ORIGIN_UPDATED, EventPriority.HIGH)
    def _on_machine_origin_updated(self, data: dict):
        """Handle machine origin updates"""
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
        """Create the visualization window"""
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
        """Setup window layout"""
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Canvas frame (left side)
        canvas_frame = ttk.LabelFrame(main_frame, text="Machine Area View")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Create canvas component
        self.canvas_component = MachineAreaCanvas(canvas_frame, logger=self.log)

        # Set bounds from hardware service
        if self.machine_bounds:
            self.canvas_component.set_machine_bounds(
                self.machine_bounds['x_min'], self.machine_bounds['y_min'],
                self.machine_bounds['x_max'], self.machine_bounds['y_max']
            )

        # Controls frame (right side)
        controls_frame = ttk.LabelFrame(main_frame, text="Display Options")
        controls_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # Create controls component
        self.controls_component = MachineAreaControls(controls_frame, self.log)

        # Set initial values from hardware service
        if self.hardware_service:
            try:
                size = self.hardware_service.get_machine_size()
                self.controls_component.set_machine_bounds(size['x'], size['y'])
            except Exception as e:
                self.log(f"Error setting initial control values: {e}", "error")

        # Update camera status in controls
        self._update_camera_status_in_controls()

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
            'bounds_changed': self.on_bounds_changed_from_controls,
            'auto_update_changed': self.on_auto_update_changed,
            'manual_update': self.manual_update,
            'center_view': self.center_view,
            'update_camera_info': self.update_camera_info,
            'calculate_fov': self.calculate_fov,  # NEW: FOV calculation callback
            'debug_show_data': self.debug_show_data,
            'toggle_triangles': self.toggle_triangle_debug,
            'toggle_errors': self.toggle_error_vectors
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

    def on_bounds_changed_from_controls(self, bounds: dict):
        """Handle machine bounds changes from controls panel"""
        try:
            if self.hardware_service:
                x_max = bounds['x_max']
                y_max = bounds['y_max']
                z_max = self.hardware_service.get_machine_size()['z']

                self.hardware_service.set_machine_size(x_max, y_max, z_max)
                self.log(f"Machine size updated from controls: {x_max}×{y_max}×{z_max}mm")
            else:
                # Fallback: update bounds directly
                self.machine_bounds['x_max'] = bounds['x_max']
                self.machine_bounds['y_max'] = bounds['y_max']

                self.canvas_component.set_machine_bounds(
                    self.machine_bounds['x_min'], self.machine_bounds['y_min'],
                    self.machine_bounds['x_max'], self.machine_bounds['y_max']
                )

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

    def calculate_fov(self):
        """Trigger FOV calculation via camera manager"""
        if not self.camera_manager:
            self.log("No camera manager available for FOV calculation", "warning")
            return

        try:
            if not self.camera_manager.is_connected:
                self.log("Camera not connected - cannot calculate FOV", "warning")
                return

            if not self.camera_manager.is_calibrated():
                self.log("Camera not calibrated - cannot calculate FOV", "warning")
                return

            # Trigger FOV calculation with default marker size (should be configurable)
            marker_size_mm = 20.0  # This should ideally come from settings
            fov_data = self.camera_manager.calculate_fov_from_current_frame(marker_size_mm)

            if fov_data:
                self.log(f"FOV calculated: {fov_data['width_mm']:.1f}×{fov_data['height_mm']:.1f}mm")
            else:
                self.log("FOV calculation failed - no ArUco marker detected", "warning")

        except Exception as e:
            self.log(f"Error triggering FOV calculation: {e}", "error")

    def debug_show_data(self):
        """Debug show data including FOV information"""
        if not self.controls_component.is_debug_enabled():
            return

        debug_info = [
            f"Routes: {len(self.actual_routes) if self.actual_routes else 0}",
            f"Camera pos: {self.current_camera_position}",
            f"Routes bounds: {self.routes_bounds}",
            f"Machine bounds: X({self.machine_bounds['x_min']:.0f},{self.machine_bounds['x_max']:.0f}) Y({self.machine_bounds['y_min']:.0f},{self.machine_bounds['y_max']:.0f})"
        ]

        # Add FOV debug info from camera manager
        if self.camera_manager:
            fov_data = self.camera_manager.get_current_fov()
            if fov_data:
                debug_info.append(
                    f"FOV: {fov_data['width_mm']:.1f}×{fov_data['height_mm']:.1f}mm @ {fov_data['distance_mm']:.1f}mm [Source: {fov_data.get('calculated_from', 'unknown')}]")
            else:
                debug_info.append("FOV: No data from camera manager")

        if self.canvas_component:
            view_info = self.canvas_component.get_view_info()
            debug_info.append(f"Zoom: {view_info['zoom_factor']:.2f}")
            debug_info.append(f"Pan: ({view_info['pan_offset'][0]:.0f}, {view_info['pan_offset'][1]:.0f})")

        if self.hardware_service:
            origin = self.hardware_service.get_machine_origin_name()
            homing = self.hardware_service.get_homing_position()
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
        """Update camera field of view bounds (legacy - for compatibility)"""
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
        """Update camera frame bounds using FOV data from camera manager only"""
        if not self.current_camera_position:
            self.camera_frame_bounds = None
            return

        try:
            cam_x, cam_y = self.current_camera_position

            # Get FOV data from camera manager only
            fov_data = None
            if self.camera_manager:
                fov_data = self.camera_manager.get_current_fov()

            if fov_data:
                # Use camera manager FOV data for precise frame bounds
                frame_width_mm = fov_data['width_mm']
                frame_height_mm = fov_data['height_mm']
                pixels_per_mm = fov_data['pixels_per_mm']

                self.camera_frame_bounds = {
                    'x_min': cam_x - frame_width_mm / 2,
                    'x_max': cam_x + frame_width_mm / 2,
                    'y_min': cam_y - frame_height_mm / 2,
                    'y_max': cam_y + frame_height_mm / 2,
                    'width_mm': frame_width_mm,
                    'height_mm': frame_height_mm,
                    'using_fov_data': True
                }
            else:
                # No FOV data available - don't show camera frame
                self.camera_frame_bounds = None


        except Exception as e:

            self.camera_frame_bounds = None

    def _update_camera_status_in_controls(self):
        """Update camera status information in controls panel"""
        if not self.controls_component:
            return

        try:
            # Get camera info
            connected = False
            calibrated = False
            resolution = (640, 480)
            fov_data = None

            if self.camera_manager:
                camera_info = self.camera_manager.get_camera_info()
                connected = camera_info.get('connected', False)
                calibrated = camera_info.get('calibrated', False)

                if connected:
                    resolution = (
                        camera_info.get('width', 640),
                        camera_info.get('height', 480)
                    )

                fov_data = self.camera_manager.get_current_fov()

            # Update controls
            self.controls_component.update_camera_status(connected, calibrated)
            self.controls_component.update_resolution_display(resolution[0], resolution[1])
            self.controls_component.update_fov_status(fov_data)

        except Exception as e:
            self.log(f"Error updating camera status in controls: {e}", "error")

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

                self.log(f"Camera info updated: {width}x{height}")

            # Update camera status in controls
            self._update_camera_status_in_controls()

            # Update frame bounds with new resolution/FOV data
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

            # Draw origin marker (0,0)
            self.canvas_component.draw_origin_marker()

            # Draw homing position
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

            if hasattr(self.controls_component,
                       'show_triangles_var') and self.controls_component.show_triangles_var.get():
                self.enable_triangle_debug_mode()

            # Update status
            self.update_status_display()

        except Exception as e:
            self.log(f"Error updating display: {e}", "error")

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

    def get_current_fov_info(self) -> dict:
        """Get current FOV information for external use"""
        fov_info = {
            'has_fov_data': False,
            'source': 'none',
            'width_mm': 0.0,
            'height_mm': 0.0,
            'distance_mm': 0.0,
            'pixels_per_mm': 0.0
        }

        try:
            if self.camera_manager:
                fov_data = self.camera_manager.get_current_fov()
                if fov_data:
                    fov_info.update({
                        'has_fov_data': True,
                        'source': 'camera_manager',
                        'width_mm': fov_data['width_mm'],
                        'height_mm': fov_data['height_mm'],
                        'distance_mm': fov_data['distance_mm'],
                        'pixels_per_mm': fov_data['pixels_per_mm'],
                        'calculated_from': fov_data.get('calculated_from', 'unknown')
                    })
                else:
                    fov_info.update({
                        'has_fov_data': False,
                        'source': 'no_data'
                    })

        except Exception as e:
            self.log(f"Error getting FOV info: {e}", "error")

        return fov_info

    def force_fov_update(self):
        """Force update of FOV data and camera frame bounds"""
        try:
            self.update_camera_frame_bounds()
            self._update_camera_status_in_controls()
            if self.is_visible:
                self.schedule_update()
            self.log("FOV data force updated")
        except Exception as e:
            self.log(f"Error in force FOV update: {e}", "error")

    def get_window_status(self) -> dict:
        """Get current window status including FOV information"""
        status = {
            'visible': self.is_visible,
            'auto_update': self.auto_update,
            'machine_bounds': self.machine_bounds.copy(),
            'current_machine_position': self.current_machine_position.tolist(),
            'current_camera_position': self.current_camera_position,
            'routes_bounds': self.routes_bounds,
            'calibration_points_count': len(self.calibration_points),
            'fov_info': self.get_current_fov_info()
        }

        if self.hardware_service:
            status['hardware_info'] = {
                'origin': self.hardware_service.get_machine_origin_name(),
                'machine_size': self.hardware_service.get_machine_size(),
                'homing_coordinates': self.hardware_service.get_homing_position()
            }

        if self.canvas_component:
            view_info = self.canvas_component.get_view_info()
            status.update(view_info)

        if self.camera_frame_bounds:
            status['camera_frame_info'] = {
                'width_mm': self.camera_frame_bounds['width_mm'],
                'height_mm': self.camera_frame_bounds['height_mm'],
                'using_fov_data': self.camera_frame_bounds.get('using_fov_data', False)
            }

        return status

    def get_enhanced_status(self) -> dict:
        """Get enhanced status with detailed FOV and camera information"""
        base_status = self.get_window_status()

        # Add enhanced FOV details from camera manager
        if self.camera_manager:
            try:
                camera_info = self.camera_manager.get_camera_info()
                base_status['camera_manager_info'] = {
                    'connected': camera_info.get('connected', False),
                    'calibrated': camera_info.get('calibrated', False),
                    'resolution': f"{camera_info.get('width', 0)}x{camera_info.get('height', 0)}",
                    'has_fov_data': camera_info.get('fov') is not None
                }

                if camera_info.get('fov'):
                    base_status['camera_manager_info']['fov_details'] = camera_info['fov']

            except Exception as e:
                self.log(f"Error getting enhanced camera info: {e}", "error")

        return base_status

    def cleanup(self):
        """Clean up resources"""
        self.stop_update_thread()
        if self.window:
            self.window.destroy()
        self.log("Machine area visualization with camera manager FOV integration cleaned up")

    def update_status_display(self):
        """Update status text display - MODIFIED for 2D registration status"""
        if not self.status_text:
            return

        try:
            status_lines = []

            # Machine status (still 3D for machine itself)
            pos = self.current_machine_position
            status_lines.append(f"Machine: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})")

            # Machine bounds info
            bounds = self.machine_bounds
            status_lines.append(
                f"Bounds: X({bounds['x_min']:.0f},{bounds['x_max']:.0f}) Y({bounds['y_min']:.0f},{bounds['y_max']:.0f})")

            # MODIFIED: Camera status - Updated for 2D
            if self.current_camera_position:
                cam_x, cam_y = self.current_camera_position
                # Updated camera display for 2D
                camera_line = f"Camera: ({cam_x:.1f}, {cam_y:.1f}) [2D]"  # CHANGED: added [2D] label

                # Add FOV status from camera manager
                if self.camera_manager:
                    fov_data = self.camera_manager.get_current_fov()
                    if fov_data:
                        source = fov_data.get('calculated_from', 'unknown')
                        camera_line += f" | FOV: {fov_data['width_mm']:.1f}×{fov_data['height_mm']:.1f}mm [{source}]"
                    else:
                        camera_line += " | FOV: No data"

                status_lines.append(camera_line)
            else:
                status_lines.append("Camera: No position [2D mode]")  # CHANGED: added [2D mode]

            # Routes status
            if self.actual_routes:
                total_points = sum(len(route) for route in self.actual_routes)
                status_lines.append(f"Routes: {len(self.actual_routes)} paths, {total_points} points")
            else:
                status_lines.append("Routes: None loaded")

            # ADDED: Registration status - New section for 2D registration info
            if hasattr(self, 'registration_manager') and self.registration_manager:
                if self.registration_manager.is_registered():
                    error = self.registration_manager.get_registration_error() or 0.0
                    point_count = self.registration_manager.get_calibration_points_count()
                    status_lines.append(f"Registration: 2D mode, {point_count} points, RMS: {error:.3f}mm")
                else:
                    point_count = self.registration_manager.get_calibration_points_count()
                    needed = max(0, 3 - point_count)
                    status_lines.append(f"Registration: 2D mode, need {needed} more points")

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

    def enable_triangle_debug_mode(self):
        """Enable triangle debug visualization mode"""
        try:
            if not self.canvas_component:
                self.log("Canvas component not available", "error")
                return

            # Get source triangle from route bounds
            source_triangle = self._get_source_triangle_from_routes()

            # Get destination triangle from calibration points
            dest_triangle = self._get_destination_triangle_from_calibration()

            # Draw the triangles
            if source_triangle or dest_triangle:
                self.canvas_component.draw_transformation_triangles(source_triangle, dest_triangle)
                self.log("Triangle debug visualization enabled")
            else:
                self.log("No triangles available for debug visualization", "warning")

        except Exception as e:
            self.log(f"Error enabling triangle debug mode: {e}", "error")

    def _get_source_triangle_from_routes(self):
        """Extract source triangle from route bounds"""
        try:
            if not self.routes_service or not self.routes_service.is_loaded():
                return None

            routes = self.routes_service.get_routes()
            if not routes:
                return None

            # Find actual outermost vertices (as per the fixed RouteTransformer logic)
            all_points = []
            for route in routes:
                all_points.extend(route)

            if not all_points:
                return None

            all_points = np.array(all_points)

            # Find the actual extreme points
            # Bottom-left: minimize x+y
            bottom_left_idx = np.argmin(all_points[:, 0] + all_points[:, 1])
            bottom_left = all_points[bottom_left_idx]

            # Bottom-right: bottom points, then rightmost
            y_threshold = np.percentile(all_points[:, 1], 25)
            bottom_points = all_points[all_points[:, 1] <= y_threshold]
            bottom_right_idx = np.argmax(bottom_points[:, 0])
            bottom_right = bottom_points[bottom_right_idx]

            # Top-left: top points, then leftmost
            y_threshold = np.percentile(all_points[:, 1], 75)
            top_points = all_points[all_points[:, 1] >= y_threshold]
            top_left_idx = np.argmin(top_points[:, 0])
            top_left = top_points[top_left_idx]

            return [tuple(bottom_left), tuple(bottom_right), tuple(top_left)]

        except Exception as e:
            self.log(f"Error getting source triangle: {e}", "error")
            return None

    def _get_destination_triangle_from_calibration(self):
        """Extract destination triangle from calibration points"""
        try:
            if not self.calibration_points or len(self.calibration_points) < 3:
                return None

            # Get first 3 calibration points
            points = self.calibration_points[:3]

            # Reorder to match expected pattern (bottom-left, bottom-right, top-left)
            points_array = np.array(points)

            # Sort by Y to separate bottom from top
            y_sorted_indices = np.argsort(points_array[:, 1])

            # Get bottom two points
            bottom_indices = y_sorted_indices[:2]
            top_index = y_sorted_indices[2]

            bottom_points = points_array[bottom_indices]

            # Sort bottom points by X
            x_sorted = np.argsort(bottom_points[:, 0])
            bottom_left = bottom_points[x_sorted[0]]
            bottom_right = bottom_points[x_sorted[1]]
            top_left = points_array[top_index]

            return [tuple(bottom_left), tuple(bottom_right), tuple(top_left)]

        except Exception as e:
            self.log(f"Error getting destination triangle: {e}", "error")
            return None

    def toggle_triangle_debug(self):
        """Toggle triangle debug visualization on/off"""
        try:
            if self.controls_component.show_triangles_var.get():
                # Enable triangle debug mode
                self.enable_triangle_debug_mode()
            else:
                # Disable - just redraw without triangles
                self.update_display()

        except Exception as e:
            self.log(f"Error toggling triangle debug: {e}", "error")

    def toggle_error_vectors(self):
        """Toggle error vector visualization on/off"""
        try:
            if self.controls_component.show_errors_var.get():
                # TODO: Implement error vector visualization
                self.log("Error vector visualization not yet implemented", "warning")
            else:
                self.update_display()

        except Exception as e:
            self.log(f"Error toggling error vectors: {e}", "error")