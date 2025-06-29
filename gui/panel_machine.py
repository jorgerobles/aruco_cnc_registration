"""
Enhanced Machine Control Panel with integrated pronterface-style jogging interface
Combines the original machine control with the concentric ring jogging UI
Fully wired with events and GRBL controller integration
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional
import threading
import time
import math


class MachineControlPanel:
    """Machine control panel with integrated concentric ring jogging interface"""

    def __init__(self, parent, grbl_controller, logger: Optional[Callable] = None):
        self.grbl_controller = grbl_controller
        self.logger = logger

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Enhanced Machine Control")
        self.frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)

        # Variables
        self.step_size_var = tk.StringVar(value="10")
        self.feed_rate_var = tk.StringVar(value="1000")

        # Debug variables
        self.jog_timeout_var = tk.StringVar(value="3.0")
        self.use_async_jog_var = tk.BooleanVar(value=True)

        # State tracking
        self.last_jog_time = 0
        self.jog_in_progress = False
        self._jog_lock = threading.Lock()

        # Position display
        self.position_label = ttk.Label(self.frame, text="Position: Not connected")
        self.status_label = ttk.Label(self.frame, text="Status: Unknown")

        # Jogging interface variables
        self.canvas = None
        self.canvas_objects = []

        # Button configurations for concentric circles - smaller radii
        self.button_configs = [
            {'radius': 15, 'step': 0, 'color': '#e74c3c', 'count': 1},    # Center HOME button
            {'radius': 40, 'step': 1, 'color': '#f39c12', 'count': 4},    # First ring - step 1
            {'radius': 65, 'step': 10, 'color': '#27ae60', 'count': 4},   # Second ring - step 10
            {'radius': 90, 'step': 50, 'color': '#3498db', 'count': 4},   # Third ring - step 50
            {'radius': 115, 'step': 100, 'color': '#9b59b6', 'count': 4}  # Fourth ring - step 100
        ]

        # Z-axis step values and colors
        self.z_steps = [1, 10, 50, 100]
        self.z_colors = ['#f39c12', '#27ae60', '#3498db', '#9b59b6']

        # A-axis step values and colors (for 4th axis if available)
        self.a_steps = [15, 45, 90, 180]
        self.a_colors = ['#e67e22', '#16a085', '#2980b9', '#8e44ad']

        self._setup_widgets()

        # Listen to GRBL events for automatic updates
        if hasattr(self.grbl_controller, 'listen'):
            from services.event_broker import GRBLEvents
            self.grbl_controller.listen(GRBLEvents.POSITION_CHANGED, self._on_position_changed)
            self.grbl_controller.listen(GRBLEvents.STATUS_CHANGED, self._on_status_changed)
            self.grbl_controller.listen(GRBLEvents.COMMAND_SENT, self._on_command_sent)
            self.grbl_controller.listen(GRBLEvents.RESPONSE_RECEIVED, self._on_response_received)

    def log(self, message: str, level: str = "info"):
        """Log message if logger is available"""
        if self.logger:
            self.logger(message, level)

    def _on_position_changed(self, position):
        """Handle position change events from GRBL"""
        self.position_label.config(
            text=f"Position: X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}"
        )
        self.log(f"Position updated: X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f}")

    def _on_status_changed(self, status):
        """Handle status change events from GRBL"""
        self.status_label.config(text=f"Status: {status}")
        self.log(f"Status changed: {status}")

    def _on_command_sent(self, command):
        """Handle command sent events"""
        self.log(f"→ SENT: {command}", "sent")

    def _on_response_received(self, response):
        """Handle response received events"""
        self.log(f"← RECV: {response}", "received")

    def _setup_widgets(self):
        """Setup all control widgets"""
        # Create notebook for tabbed interface
        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # Tab 1: Enhanced Jogging Interface
        jog_frame = ttk.Frame(notebook)
        notebook.add(jog_frame, text="Jogging Interface")
        self._setup_jogging_interface(jog_frame)

        # Tab 2: Debug/Settings
        debug_frame = ttk.Frame(notebook)
        notebook.add(debug_frame, text="Debug/Settings")
        self._setup_debug_controls(debug_frame)

    def _setup_jogging_interface(self, parent):
        """Setup the enhanced jogging interface with concentric rings"""
        # Status display at top
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=5)

        self.position_label.pack(in_=status_frame, anchor=tk.W)
        self.status_label.pack(in_=status_frame, anchor=tk.W)

        # Settings frame
        settings_frame = ttk.LabelFrame(parent, text="Jog Settings")
        settings_frame.pack(fill=tk.X, pady=5, padx=5)

        # Step size and feed rate controls
        controls_frame = ttk.Frame(settings_frame)
        controls_frame.pack(pady=5)

        ttk.Label(controls_frame, text="Step:").pack(side=tk.LEFT)
        step_combo = ttk.Combobox(controls_frame, textvariable=self.step_size_var,
                                  values=["0.1", "1", "10", "50", "100"], width=8)
        step_combo.pack(side=tk.LEFT, padx=(2, 10))

        ttk.Label(controls_frame, text="Feed:").pack(side=tk.LEFT)
        feed_combo = ttk.Combobox(controls_frame, textvariable=self.feed_rate_var,
                                  values=["100", "500", "1000", "2000", "3000"], width=8)
        feed_combo.pack(side=tk.LEFT, padx=2)

        # Jog status indicator
        self.jog_status_label = ttk.Label(controls_frame, text="Ready", foreground="green")
        self.jog_status_label.pack(side=tk.LEFT, padx=10)

        # Main jogging layout frame
        main_jog_frame = ttk.Frame(parent)
        main_jog_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create horizontal layout: Z-axis | XY Jogging | Settings
        layout_frame = ttk.Frame(main_jog_frame)
        layout_frame.pack(fill=tk.BOTH, expand=True)

        # Left column for Z-axis control
        self.z_frame = ttk.LabelFrame(layout_frame, text="Z-AXIS", width=60)
        self.z_frame.pack(side='left', fill='y', padx=(0, 10))
        self.z_frame.pack_propagate(False)

        # Center area for XY jogging with concentric rings
        self.center_frame = ttk.LabelFrame(layout_frame, text="XY JOGGING")
        self.center_frame.pack(side='left', fill=tk.BOTH, expand=True)

        # Right column for quick controls and emergency
        self.right_frame = ttk.LabelFrame(layout_frame, text="CONTROLS", width=60)
        self.right_frame.pack(side='right', fill='y', padx=(10, 0))
        self.right_frame.pack_propagate(False)

        # Setup individual sections
        self._setup_z_axis_controls()
        self._setup_xy_jogging_canvas()
        self._setup_quick_controls()

        # Legend below the jogging interface
        self._setup_legend()

    def _setup_z_axis_controls(self):
        """Create unified Z-axis control buttons"""
        # All Z buttons in order from +100 to -100
        z_buttons = [
            ("+Z", 100, self.z_colors[3]),  # +Z 100
            ("+Z", 50, self.z_colors[2]),   # +Z 50
            ("+Z", 10, self.z_colors[1]),   # +Z 10
            ("+Z", 1, self.z_colors[0]),    # +Z 1
            ("-Z", 1, self.z_colors[0]),    # -Z 1
            ("-Z", 10, self.z_colors[1]),   # -Z 10
            ("-Z", 50, self.z_colors[2]),   # -Z 50
            ("-Z", 100, self.z_colors[3])   # -Z 100
        ]

        for direction, step, color in z_buttons:
            arrow = "↑" if direction == "+Z" else "↓"
            btn = tk.Button(self.z_frame, text=f"{arrow} {step}", font=('Arial', 8, 'bold'),
                            bg=color, fg='white', relief='raised', bd=1, width=5, height=1,
                            command=lambda d=direction, s=step: self.jog_axis(d, s))
            btn.pack(pady=0, padx=2, fill='x')

    def _setup_xy_jogging_canvas(self):
        """Setup the canvas with concentric ring jogging interface"""
        # Canvas for drawing concentric button layout - smaller size, no background color
        self.canvas = tk.Canvas(self.center_frame, width=250, height=250,
                               bg='white', highlightthickness=0)
        self.canvas.pack(expand=True, padx=5, pady=5)

        # Create the concentric button layout
        self._create_concentric_buttons()

        # Bind canvas events
        self.canvas.bind('<Button-1>', self._on_canvas_click)
        self.canvas.bind('<Motion>', self._on_canvas_motion)
        self.canvas.bind('<Configure>', self._on_canvas_resize)

    def _setup_quick_controls(self):
        """Setup unified quick control buttons"""
        # All control buttons in logical order
        control_buttons = [
            ("🛑 STOP", self.emergency_stop, '#e74c3c'),
            ("▶️ Resume", self.resume, '#27ae60'),
            ("🔄 Reset", self.soft_reset, '#3498db'),
            ("🏠 Home", self.home_machine, '#9b59b6'),
            ("📍 Update", self.update_position, '#34495e'),
            ("⌂ Zero", self.go_to_zero, '#2c3e50')
        ]

        for text, command, color in control_buttons:
            btn = tk.Button(self.right_frame, text=text, command=command,
                           bg=color, fg='white', font=('Arial', 8, 'bold'),
                           relief='raised', bd=1, width=8, height=1)
            btn.pack(pady=0, padx=2, fill='x')

    def _setup_legend(self):
        """Setup compact legend below the jogging interface"""
        legend_frame = ttk.LabelFrame(self.frame, text="Step Sizes")
        legend_frame.pack(fill=tk.X, pady=5, padx=5)

        # Create compact legend in horizontal layout
        legend_grid = ttk.Frame(legend_frame)
        legend_grid.pack(pady=5)

        # Compact legend entries - only color boxes with numbers
        legend_items = [
            ('🏠', '#e74c3c'),
            ('1', '#f39c12'),
            ('10', '#27ae60'),
            ('50', '#3498db'),
            ('100', '#9b59b6')
        ]

        for i, (text, color) in enumerate(legend_items):
            # Color indicator with number/symbol
            color_frame = tk.Frame(legend_grid, bg=color, width=40, height=25)
            color_frame.grid(row=0, column=i, padx=3, pady=2)
            color_frame.pack_propagate(False)

            # Symbol/number in color box
            symbol_label = tk.Label(color_frame, text=text,
                                   bg=color, fg='white', font=('Arial', 10, 'bold'))
            symbol_label.place(relx=0.5, rely=0.5, anchor='center')

    def _create_concentric_buttons(self):
        """Create all concentric buttons - draw from outside to inside"""
        self.canvas_objects.clear()
        center_x, center_y = 125, 125  # Adjusted for smaller canvas

        # Draw rings from largest to smallest (reverse order)
        for ring_idx, config in enumerate(reversed(self.button_configs)):
            radius = config['radius']
            step = config['step']
            color = config['color']
            count = config['count']
            actual_ring_idx = len(self.button_configs) - 1 - ring_idx

            if count == 1:  # Center HOME button (draw last)
                continue
            else:  # Ring buttons - draw from outside to inside
                self._create_ring_buttons(center_x, center_y, radius, step, color, count, actual_ring_idx)

        # Draw center button last (on top)
        center_config = self.button_configs[0]
        self._create_center_button(center_x, center_y, center_config['radius'],
                                  center_config['step'], center_config['color'])

    def _create_center_button(self, cx, cy, radius, step, color):
        """Create the center HOME button as a circle"""
        circle_id = self.canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius,
            fill=color, outline='white', width=3
        )

        text_id = self.canvas.create_text(
            cx, cy, text="HOME", fill='white',
            font=('Arial', 12, 'bold'), justify='center'
        )

        center_info = {
            'circle_id': circle_id,
            'text_id': text_id,
            'direction': 'HOME',
            'step': 0,
            'center': (cx, cy),
            'radius': radius,
            'color': color,
            'hover_color': self._lighten_color(color)
        }

        self.canvas_objects.append(center_info)

    def _create_ring_buttons(self, cx, cy, radius, step, color, count, ring_idx):
        """Create complete segmented circles for each step group"""
        if count != 4:
            return

        directions = ['+Y', '+X', '-Y', '-X']

        gap_between_segments = 8
        arc_span = 90 - gap_between_segments

        for i in range(count):
            base_angles = [90, 0, 270, 180]
            center_angle = base_angles[i]
            start_angle = center_angle - (arc_span / 2)

            axis_direction = directions[i]

            # Create arc without any text/arrows
            arc_id = self.canvas.create_arc(
                cx - radius, cy - radius, cx + radius, cy + radius,
                start=start_angle, extent=arc_span,
                fill=color, outline='white', width=2,
                style='pieslice'
            )

            arc_info = {
                'arc_id': arc_id,
                'text_id': None,  # No text
                'direction': axis_direction,
                'step': step,
                'center': (cx, cy),
                'outer_radius': radius,
                'inner_radius': radius - 12,  # Smaller ring thickness
                'start_angle': start_angle,
                'end_angle': start_angle + arc_span,
                'center_angle': center_angle,
                'color': color,
                'hover_color': self._lighten_color(color)
            }

            self.canvas_objects.append(arc_info)

    def _lighten_color(self, color):
        """Create a lighter version of a color for hover effects"""
        color_map = {
            '#e74c3c': '#ec7063',
            '#f39c12': '#f8c471',
            '#27ae60': '#58d68d',
            '#3498db': '#85c1e9',
            '#9b59b6': '#bb8fce',
            '#e67e22': '#f0b27a',
            '#16a085': '#76d7c4',
            '#2980b9': '#7fb3d3',
            '#8e44ad': '#a569bd'
        }
        return color_map.get(color, color)

    def _on_canvas_click(self, event):
        """Handle canvas click events"""
        x, y = event.x, event.y

        for obj in self.canvas_objects:
            if self._is_point_in_object(x, y, obj):
                if obj['direction'] == 'HOME':
                    self.home_machine()
                else:
                    self.jog_axis(obj['direction'], obj['step'])
                break

    def _on_canvas_motion(self, event):
        """Handle mouse motion for hover effects"""
        x, y = event.x, event.y

        # Reset all objects to normal color
        for obj in self.canvas_objects:
            if 'arc_id' in obj:
                self.canvas.itemconfig(obj['arc_id'], fill=obj['color'])
            elif 'circle_id' in obj:
                self.canvas.itemconfig(obj['circle_id'], fill=obj['color'])

        # Find and highlight hovered object
        hovered_obj = None
        min_radius = float('inf')

        for obj in self.canvas_objects:
            if self._is_point_in_object(x, y, obj):
                if 'circle_id' in obj:
                    hovered_obj = obj
                    break
                elif 'arc_id' in obj:
                    obj_radius = obj['outer_radius']
                    if obj_radius < min_radius:
                        min_radius = obj_radius
                        hovered_obj = obj

        if hovered_obj:
            if 'arc_id' in hovered_obj:
                self.canvas.itemconfig(hovered_obj['arc_id'], fill=hovered_obj['hover_color'])
            elif 'circle_id' in hovered_obj:
                self.canvas.itemconfig(hovered_obj['circle_id'], fill=hovered_obj['hover_color'])
            self.canvas.config(cursor='hand2')
        else:
            self.canvas.config(cursor='')

    def _is_point_in_object(self, x, y, obj):
        """Check if point is within an arc or circle object"""
        cx, cy = obj['center']
        dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)

        if 'circle_id' in obj:
            return dist <= obj['radius']

        elif 'arc_id' in obj:
            outer_radius = obj['outer_radius']
            inner_radius = obj['inner_radius']

            if dist > outer_radius or dist < inner_radius:
                return False

            dx = x - cx
            dy = y - cy
            angle = math.degrees(math.atan2(-dy, dx))

            if angle < 0:
                angle += 360

            start_angle = obj['start_angle'] % 360
            end_angle = obj['end_angle'] % 360

            if start_angle > end_angle:
                return angle >= start_angle or angle <= end_angle
            else:
                return start_angle <= angle <= end_angle

        return False

    def _on_canvas_resize(self, event):
        """Handle canvas resize to keep buttons centered"""
        canvas_width = event.width
        canvas_height = event.height
        center_x = canvas_width // 2
        center_y = canvas_height // 2
        self._update_button_positions(center_x, center_y)

    def _update_button_positions(self, center_x, center_y):
        """Update all button positions when canvas is resized"""
        for obj in self.canvas_objects:
            if 'arc_id' in obj:
                self.canvas.delete(obj['arc_id'])
                if obj['text_id']:
                    self.canvas.delete(obj['text_id'])
            elif 'circle_id' in obj:
                self.canvas.delete(obj['circle_id'])
                self.canvas.delete(obj['text_id'])

        self.canvas_objects.clear()

        # Use smaller center coordinates for the smaller canvas
        center_x = min(center_x, 125)
        center_y = min(center_y, 125)

        # Recreate concentric buttons at new center
        for ring_idx, config in enumerate(reversed(self.button_configs)):
            radius = config['radius']
            step = config['step']
            color = config['color']
            count = config['count']
            actual_ring_idx = len(self.button_configs) - 1 - ring_idx

            if count == 1:  # Center button (draw last)
                continue
            else:  # Ring buttons
                self._create_ring_buttons(center_x, center_y, radius, step, color, count, actual_ring_idx)

        # Draw center button last (on top)
        center_config = self.button_configs[0]
        self._create_center_button(center_x, center_y, center_config['radius'],
                                  center_config['step'], center_config['color'])

    def _update_connection_info(self):
        """Update connection info display"""
        if hasattr(self, 'info_text'):
            try:
                info = self.grbl_controller.get_connection_info()
                info_str = "Connection Information:\n"
                for key, value in info.items():
                    info_str += f"{key}: {value}\n"

                self.info_text.delete(1.0, tk.END)
                self.info_text.insert(tk.END, info_str)
            except:
                pass

        # Schedule next update
        self.frame.after(2000, self._update_connection_info)

    # Jogging Methods
    def jog_axis(self, direction: str, step: float):
        """Handle jogging for specific axis and direction"""
        if direction == "HOME":
            self.home_machine()
            return

        # Map direction to axis movements
        axis_map = {
            '+X': (1, 0, 0),
            '-X': (-1, 0, 0),
            '+Y': (0, 1, 0),
            '-Y': (0, -1, 0),
            '+Z': (0, 0, 1),
            '-Z': (0, 0, -1)
        }

        if direction in axis_map:
            x_mult, y_mult, z_mult = axis_map[direction]
            self.jog_safe(x=x_mult * step, y=y_mult * step, z=z_mult * step)
        else:
            self.log(f"Unknown direction: {direction}", "error")

    def jog_safe(self, x=0, y=0, z=0):
        """Safe jogging with freeze prevention"""
        with self._jog_lock:
            if self.jog_in_progress:
                self.log("⚠️ Jog already in progress, skipping", "warning")
                return

            self.jog_in_progress = True
            self.jog_status_label.config(text="Jogging...", foreground="orange")

        try:
            if self.use_async_jog_var.get():
                threading.Thread(target=self._jog_worker, args=(x, y, z), daemon=True).start()
            else:
                self._jog_synchronous(x, y, z)

        except Exception as e:
            self.log(f"❌ Jog initiation failed: {e}", "error")
            self._reset_jog_status()

    def _jog_worker(self, x, y, z):
        """Async worker for jogging"""
        try:
            self._jog_synchronous(x, y, z)
        except Exception as e:
            self.log(f"❌ Async jog failed: {e}", "error")
        finally:
            # Reset status on main thread
            self.frame.after(0, self._reset_jog_status)

    def _jog_synchronous(self, x, y, z):
        """Synchronous jogging with detailed logging"""
        try:
            if not self.grbl_controller.is_connected:
                self.log("❌ GRBL not connected", "error")
                return

            # Use custom step size if provided, otherwise use current setting
            if x == 0 and y == 0 and z == 0:
                return

            feed_rate = float(self.feed_rate_var.get())
            timeout = float(self.jog_timeout_var.get())

            self.log(f"🎯 Starting jog: X{x:+.3f} Y{y:+.3f} Z{z:+.3f} @ F{feed_rate} (timeout: {timeout}s)")

            # Record start time
            start_time = time.time()

            # Set custom timeout for this jog operation
            if hasattr(self.grbl_controller, 'set_jog_timeout'):
                self.grbl_controller.set_jog_timeout(timeout)

            # Use the controller's move_relative method
            try:
                responses = self.grbl_controller.move_relative(x, y, z, feed_rate)
                elapsed = time.time() - start_time
                self.log(f"⏱️ Jog completed in {elapsed:.3f}s")

                # Check responses
                success = False
                error_found = False

                for response in responses:
                    self.log(f"Jog response: {response}")
                    if "ok" in response.lower():
                        success = True
                    elif "error" in response.lower():
                        error_found = True
                        self.log(f"❌ Jog error: {response}", "error")

                if success and not error_found:
                    self.log("✅ Jog completed successfully")
                elif error_found:
                    self.log("❌ Jog completed with errors", "error")
                else:
                    self.log("⚠️ Jog status unclear - no OK received", "warning")

            except Exception as cmd_error:
                elapsed = time.time() - start_time
                self.log(f"❌ Jog command failed after {elapsed:.3f}s: {cmd_error}", "error")

                # Try to send emergency stop if jog failed
                try:
                    self.log("🛑 Attempting emergency stop due to jog failure")
                    self.grbl_controller.emergency_stop()
                except:
                    pass

        except ValueError:
            self.log("❌ Invalid step size or feed rate", "error")
        except Exception as e:
            self.log(f"❌ Jog failed: {e}", "error")

    def _reset_jog_status(self):
        """Reset jog status indicators"""
        with self._jog_lock:
            self.jog_in_progress = False
        self.jog_status_label.config(text="Ready", foreground="green")

    # Machine Control Methods
    def update_position(self):
        """Update machine position display"""
        try:
            if not self.grbl_controller.is_connected:
                self.position_label.config(text="Position: Not connected")
                self.log("❌ GRBL not connected", "warning")
                return

            self.log("📍 Updating position...")
            start_time = time.time()

            pos = self.grbl_controller.get_position()
            elapsed = time.time() - start_time

            self.position_label.config(text=f"Position: X{pos[0]:.3f} Y{pos[1]:.3f} Z{pos[2]:.3f}")
            self.log(f"✅ Position updated in {elapsed:.3f}s: X{pos[0]:.3f} Y{pos[1]:.3f} Z{pos[2]:.3f}")

        except Exception as e:
            self.position_label.config(text="Position: Error reading")
            self.log(f"❌ Error reading position: {e}", "error")

    def home_machine(self):
        """Home the machine"""
        try:
            if not self.grbl_controller.is_connected:
                messagebox.showerror("Error", "GRBL not connected")
                return

            self.log("🏠 Initiating homing sequence...")
            start_time = time.time()

            success = self.grbl_controller.home()
            elapsed = time.time() - start_time

            if success:
                self.log(f"✅ Homing completed successfully in {elapsed:.3f}s")
                self.update_position()
            else:
                self.log(f"❌ Homing failed after {elapsed:.3f}s", "error")
                messagebox.showerror("Error", "Homing failed")

        except Exception as e:
            self.log(f"❌ Homing failed: {e}", "error")
            messagebox.showerror("Error", f"Homing failed: {e}")

    def go_to_zero(self):
        """Go to work coordinate zero"""
        try:
            if not self.grbl_controller.is_connected:
                messagebox.showerror("Error", "GRBL not connected")
                return

            feed_rate = float(self.feed_rate_var.get())
            self.log(f"🎯 Moving to work zero @ F{feed_rate}")
            start_time = time.time()

            success = self.grbl_controller.move_to(0, 0, 0, feed_rate)
            elapsed = time.time() - start_time

            if success:
                self.log(f"✅ Moved to work zero in {elapsed:.3f}s")
            else:
                self.log(f"❌ Failed to move to work zero after {elapsed:.3f}s", "error")

        except Exception as e:
            self.log(f"❌ Go to zero failed: {e}", "error")
            messagebox.showerror("Error", f"Go to zero failed: {e}")

    def emergency_stop(self):
        """Emergency stop the machine"""
        try:
            if not self.grbl_controller.is_connected:
                return

            self.log("🛑 EMERGENCY STOP", "error")
            success = self.grbl_controller.emergency_stop()

            if success:
                self.log("✅ Feed hold activated")
                self._reset_jog_status()  # Reset jog status on emergency stop
            else:
                self.log("❌ Emergency stop may have failed", "error")

        except Exception as e:
            self.log(f"❌ Emergency stop failed: {e}", "error")

    def resume(self):
        """Resume from feed hold"""
        try:
            if not self.grbl_controller.is_connected:
                return

            self.log("▶️ Resuming...")
            success = self.grbl_controller.resume()

            if success:
                self.log("✅ Resumed from feed hold")
            else:
                self.log("❌ Resume may have failed", "warning")

        except Exception as e:
            self.log(f"❌ Resume failed: {e}", "error")

    def soft_reset(self):
        """Perform soft reset"""
        try:
            if not self.grbl_controller.is_connected:
                return

            self.log("🔄 Performing soft reset...")
            success = self.grbl_controller.reset()

            if success:
                self.log("✅ Soft reset successful")
                self._reset_jog_status()  # Reset jog status after reset
                self.update_position()
            else:
                self.log("❌ Soft reset may have failed", "warning")

        except Exception as e:
            self.log(f"❌ Soft reset failed: {e}", "error")

    # Debug and Testing Methods
    def test_connection(self):
        """Test GRBL connection and communication"""
        try:
            if not self.grbl_controller.is_connected:
                self.log("❌ GRBL not connected", "error")
                return

            self.log("🔍 Testing GRBL connection...")

            # Test status query
            start_time = time.time()
            try:
                status = self.grbl_controller.get_status()
                elapsed = time.time() - start_time
                self.log(f"✅ Status query successful: {status} ({elapsed:.3f}s)")
            except Exception as e:
                self.log(f"❌ Status query failed: {e}", "error")

            # Test position query
            start_time = time.time()
            try:
                position = self.grbl_controller.get_position()
                elapsed = time.time() - start_time
                self.log(f"✅ Position query successful: X{position[0]:.3f} Y{position[1]:.3f} Z{position[2]:.3f} ({elapsed:.3f}s)")
            except Exception as e:
                self.log(f"❌ Position query failed: {e}", "error")

            # Get connection info
            info = self.grbl_controller.get_connection_info()
            self.log(f"📊 Connection info: {info}")

        except Exception as e:
            self.log(f"❌ Connection test failed: {e}", "error")

    def get_detailed_status(self):
        """Get detailed GRBL status"""
        try:
            if not self.grbl_controller.is_connected:
                self.log("❌ GRBL not connected", "error")
                return

            # Send manual status query
            self.log("📊 Requesting detailed status...")
            responses = self.grbl_controller.send_command("?")

            for response in responses:
                self.log(f"Status response: {response}")

        except Exception as e:
            self.log(f"❌ Status query failed: {e}", "error")

    def _setup_debug_controls(self, parent):
        """Setup debug and settings controls"""
        # Connection testing
        test_frame = ttk.LabelFrame(parent, text="Connection Testing")
        test_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(test_frame, text="Test Connection", command=self.test_connection).pack(side=tk.LEFT, padx=2)
        ttk.Button(test_frame, text="Get Status", command=self.get_detailed_status).pack(side=tk.LEFT, padx=2)

        # Jog settings
        jog_settings_frame = ttk.LabelFrame(parent, text="Jog Settings")
        jog_settings_frame.pack(fill=tk.X, pady=5, padx=5)

        # Timeout setting
        timeout_frame = ttk.Frame(jog_settings_frame)
        timeout_frame.pack(pady=2)
        ttk.Label(timeout_frame, text="Jog Timeout (s):").pack(side=tk.LEFT)
        ttk.Entry(timeout_frame, textvariable=self.jog_timeout_var, width=8).pack(side=tk.LEFT, padx=2)

        # Async jog toggle
        ttk.Checkbutton(jog_settings_frame, text="Use Async Jogging",
                       variable=self.use_async_jog_var).pack(pady=2)

        # Connection info
        info_frame = ttk.LabelFrame(parent, text="Connection Info")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)

        self.info_text = tk.Text(info_frame, height=10, width=50)
        scrollbar = ttk.Scrollbar(info_frame, orient="vertical", command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=scrollbar.set)

        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Update connection info periodically
        self._update_connection_info()

    # Legacy compatibility methods
    def jog(self, x=0, y=0, z=0):
        """Legacy jog method - redirects to safe jog"""
        self.log("⚠️ Using legacy jog method - redirecting to safe jog")
        self.jog_safe(x, y, z)


# Usage example and integration helper
def create_enhanced_machine_panel(parent, grbl_controller, logger=None):
    """
    Helper function to create the enhanced machine control panel

    Args:
        parent: Tkinter parent widget
        grbl_controller: Instance of GRBLController with event support
        logger: Optional logging function

    Returns:
        EnhancedMachineControlPanel instance
    """
    return EnhancedMachineControlPanel(parent, grbl_controller, logger)


# Demo/Test function
def demo_enhanced_panel():
    """Demo function to test the enhanced panel"""
    import tkinter as tk
    from tkinter import scrolledtext

    # Mock GRBL controller for testing
    class MockGRBLController:
        def __init__(self):
            self.is_connected = True
            self.current_position = [0.0, 0.0, 0.0]
            self.current_status = "Idle"

        def listen(self, event_type, callback):
            pass

        def get_position(self):
            return self.current_position.copy()

        def get_status(self):
            return self.current_status

        def move_relative(self, x, y, z, feed_rate):
            print(f"Mock jog: X{x:+.3f} Y{y:+.3f} Z{z:+.3f} @ F{feed_rate}")
            self.current_position[0] += x
            self.current_position[1] += y
            self.current_position[2] += z
            return ["ok"]

        def home(self):
            print("Mock homing")
            self.current_position = [0.0, 0.0, 0.0]
            return True

        def move_to(self, x, y, z, feed_rate):
            print(f"Mock move to: X{x} Y{y} Z{z} @ F{feed_rate}")
            return True

        def emergency_stop(self):
            print("Mock emergency stop")
            return True

        def resume(self):
            print("Mock resume")
            return True

        def reset(self):
            print("Mock reset")
            return True

        def send_command(self, cmd):
            print(f"Mock command: {cmd}")
            return ["ok"]

        def get_connection_info(self):
            return {
                'is_connected': True,
                'status': 'Mock Controller',
                'position': self.current_position
            }

    # Create demo window
    root = tk.Tk()
    root.title("Enhanced Machine Control Panel Demo")
    root.geometry("1000x800")

    # Create log display
    log_frame = tk.Frame(root)
    log_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

    tk.Label(log_frame, text="Log Output:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
    log_text = scrolledtext.ScrolledText(log_frame, height=8, width=80)
    log_text.pack(fill=tk.X)

    def logger(message, level="info"):
        log_text.insert(tk.END, f"[{level.upper()}] {message}\n")
        log_text.see(tk.END)

    # Create mock controller and panel
    mock_controller = MockGRBLController()
    panel = create_enhanced_machine_panel(root, mock_controller, logger)

    logger("Enhanced Machine Control Panel Demo Started", "info")
    logger("This is a mock controller for testing the interface", "info")

    root.mainloop()


if __name__ == "__main__":
    demo_enhanced_panel()