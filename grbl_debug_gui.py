"""
GRBL Controller Debug GUI - FIXED VERSION
Simple interface for testing async command functionality
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
from datetime import datetime
import queue
from typing import Dict, Any
from concurrent.futures import Future

# Import GRBL controller and event system
from services.grbl_controller import GRBLController, CommandState
from services.event_broker import event_aware, event_handler, EventPriority
from services.events import GRBLEvents


@event_aware()
class GRBLDebugGUI:
    """Debug GUI for GRBL Controller with async command testing"""

    def __init__(self, root):
        self.root = root
        self.root.title("GRBL Controller Debug Interface")
        self.root.geometry("1000x700")

        # GRBL Controller instance
        self.grbl = GRBLController()

        # GUI update queue for thread-safe updates
        self.gui_queue = queue.Queue()

        # Command tracking
        self.active_futures: Dict[str, Future] = {}
        self.command_counter = 0

        # Initialize GUI
        self.setup_gui()
        self.setup_event_handlers()

        # Start GUI update loop
        self.update_gui()

    def setup_gui(self):
        """Setup the GUI layout"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

        # Connection frame
        self.setup_connection_frame(main_frame)

        # Command frame
        self.setup_command_frame(main_frame)

        # Jog frame
        self.setup_jog_frame(main_frame)

        # Output frame
        self.setup_output_frame(main_frame)

        # Status frame
        self.setup_status_frame(main_frame)

    def setup_connection_frame(self, parent):
        """Setup connection controls"""
        conn_frame = ttk.LabelFrame(parent, text="Connection", padding="5")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Port selection
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=(0, 5))
        self.port_var = tk.StringVar(value="COM3")
        port_entry = ttk.Entry(conn_frame, textvariable=self.port_var, width=10)
        port_entry.grid(row=0, column=1, padx=(0, 10))

        # Baudrate selection
        ttk.Label(conn_frame, text="Baudrate:").grid(row=0, column=2, padx=(0, 5))
        self.baudrate_var = tk.StringVar(value="115200")
        baudrate_combo = ttk.Combobox(conn_frame, textvariable=self.baudrate_var,
                                     values=["9600", "19200", "38400", "57600", "115200"],
                                     width=10, state="readonly")
        baudrate_combo.grid(row=0, column=3, padx=(0, 10))

        # Connect/Disconnect buttons
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.connect_grbl)
        self.connect_btn.grid(row=0, column=4, padx=(0, 5))

        self.disconnect_btn = ttk.Button(conn_frame, text="Disconnect", command=self.disconnect_grbl, state="disabled")
        self.disconnect_btn.grid(row=0, column=5)

        # Connection status
        self.conn_status_var = tk.StringVar(value="Disconnected")
        status_label = ttk.Label(conn_frame, textvariable=self.conn_status_var, foreground="red")
        status_label.grid(row=0, column=6, padx=(10, 0))

    def setup_command_frame(self, parent):
        """Setup command testing controls"""
        cmd_frame = ttk.LabelFrame(parent, text="Command Testing", padding="5")
        cmd_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        cmd_frame.columnconfigure(1, weight=1)

        # Command input
        ttk.Label(cmd_frame, text="Command:").grid(row=0, column=0, padx=(0, 5), sticky=tk.W)
        self.command_var = tk.StringVar()
        self.command_entry = ttk.Entry(cmd_frame, textvariable=self.command_var, width=30)
        self.command_entry.grid(row=0, column=1, padx=(0, 5), sticky=(tk.W, tk.E))
        self.command_entry.bind('<Return>', lambda e: self.send_command())

        # Timeout input
        ttk.Label(cmd_frame, text="Timeout:").grid(row=0, column=2, padx=(0, 5))
        self.timeout_var = tk.StringVar(value="5.0")
        timeout_entry = ttk.Entry(cmd_frame, textvariable=self.timeout_var, width=8)
        timeout_entry.grid(row=0, column=3, padx=(0, 10))

        # Command buttons
        self.send_btn = ttk.Button(cmd_frame, text="Send Command", command=self.send_command, state="disabled")
        self.send_btn.grid(row=0, column=4, padx=(0, 5))

        self.send_async_btn = ttk.Button(cmd_frame, text="Send Async", command=self.send_async_command, state="disabled")
        self.send_async_btn.grid(row=0, column=5, padx=(0, 5))

        # Quick command buttons
        quick_frame = ttk.Frame(cmd_frame)
        quick_frame.grid(row=1, column=0, columnspan=6, pady=(10, 0), sticky=(tk.W, tk.E))

        quick_commands = [
            ("Status (?)", "?"),
            ("Settings ($$)", "$$"),
            ("Version ($I)", "$I"),
            ("Home ($H)", "$H"),
            ("Reset", "RESET"),
            ("Emergency Stop", "!")
        ]

        for i, (label, cmd) in enumerate(quick_commands):
            btn = ttk.Button(quick_frame, text=label,
                           command=lambda c=cmd: self.quick_command(c),
                           state="disabled")
            btn.grid(row=0, column=i, padx=(0, 5))
            setattr(self, f"quick_btn_{i}", btn)  # Store reference for state management

    def setup_jog_frame(self, parent):
        """Setup jog controls for testing movement commands"""
        jog_frame = ttk.LabelFrame(parent, text="Jog Controls (Async Movement Testing)", padding="5")
        jog_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Distance and feed rate controls
        settings_frame = ttk.Frame(jog_frame)
        settings_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(settings_frame, text="Distance:").grid(row=0, column=0, padx=(0, 5))
        self.jog_distance_var = tk.StringVar(value="1.0")
        distance_combo = ttk.Combobox(settings_frame, textvariable=self.jog_distance_var,
                                     values=["0.1", "1.0", "10.0", "25.0", "50.0"],
                                     width=8, state="normal")
        distance_combo.grid(row=0, column=1, padx=(0, 20))

        ttk.Label(settings_frame, text="Feed Rate:").grid(row=0, column=2, padx=(0, 5))
        self.jog_feedrate_var = tk.StringVar(value="1000")
        feedrate_combo = ttk.Combobox(settings_frame, textvariable=self.jog_feedrate_var,
                                     values=["100", "500", "1000", "2000", "5000"],
                                     width=8, state="normal")
        feedrate_combo.grid(row=0, column=3, padx=(0, 20))

        # Jog mode selection
        ttk.Label(settings_frame, text="Mode:").grid(row=0, column=4, padx=(0, 5))
        self.jog_mode_var = tk.StringVar(value="Sync")
        mode_combo = ttk.Combobox(settings_frame, textvariable=self.jog_mode_var,
                                 values=["Sync", "Async"],
                                 width=8, state="readonly")
        mode_combo.grid(row=0, column=5, padx=(0, 20))

        # Emergency stop for jog operations
        self.jog_stop_btn = ttk.Button(settings_frame, text="STOP", command=self.emergency_stop_jog,
                                      state="disabled", style="Emergency.TButton")
        self.jog_stop_btn.grid(row=0, column=6, padx=(10, 0))

        # Create emergency button style
        style = ttk.Style()
        style.configure("Emergency.TButton", foreground="red")

        # XY Movement pad
        xy_frame = ttk.LabelFrame(jog_frame, text="XY Movement", padding="5")
        xy_frame.grid(row=1, column=0, padx=(0, 10), sticky=(tk.N, tk.S))

        # Y+ button
        self.y_plus_btn = ttk.Button(xy_frame, text="Y+", width=6,
                                    command=lambda: self.jog_move(y=1), state="disabled")
        self.y_plus_btn.grid(row=0, column=1, padx=2, pady=2)

        # X-, Home, X+ buttons
        self.x_minus_btn = ttk.Button(xy_frame, text="X-", width=6,
                                     command=lambda: self.jog_move(x=-1), state="disabled")
        self.x_minus_btn.grid(row=1, column=0, padx=2, pady=2)

        self.xy_home_btn = ttk.Button(xy_frame, text="XY\nHome", width=6,
                                     command=self.xy_home, state="disabled")
        self.xy_home_btn.grid(row=1, column=1, padx=2, pady=2)

        self.x_plus_btn = ttk.Button(xy_frame, text="X+", width=6,
                                    command=lambda: self.jog_move(x=1), state="disabled")
        self.x_plus_btn.grid(row=1, column=2, padx=2, pady=2)

        # Y- button
        self.y_minus_btn = ttk.Button(xy_frame, text="Y-", width=6,
                                     command=lambda: self.jog_move(y=-1), state="disabled")
        self.y_minus_btn.grid(row=2, column=1, padx=2, pady=2)

        # Z Movement controls
        z_frame = ttk.LabelFrame(jog_frame, text="Z Movement", padding="5")
        z_frame.grid(row=1, column=1, sticky=(tk.N, tk.S))

        self.z_plus_btn = ttk.Button(z_frame, text="Z+", width=8,
                                    command=lambda: self.jog_move(z=1), state="disabled")
        self.z_plus_btn.grid(row=0, column=0, padx=5, pady=2)

        self.z_home_btn = ttk.Button(z_frame, text="Z Home", width=8,
                                    command=self.z_home, state="disabled")
        self.z_home_btn.grid(row=1, column=0, padx=5, pady=2)

        self.z_minus_btn = ttk.Button(z_frame, text="Z-", width=8,
                                     command=lambda: self.jog_move(z=-1), state="disabled")
        self.z_minus_btn.grid(row=2, column=0, padx=5, pady=2)

        # Multi-axis movement controls
        multi_frame = ttk.LabelFrame(jog_frame, text="Multi-Axis & Special", padding="5")
        multi_frame.grid(row=1, column=2, sticky=(tk.N, tk.S), padx=(10, 0))

        # Diagonal movements
        self.diag1_btn = ttk.Button(multi_frame, text="X+Y+", width=8,
                                   command=lambda: self.jog_move(x=1, y=1), state="disabled")
        self.diag1_btn.grid(row=0, column=0, padx=2, pady=2)

        self.diag2_btn = ttk.Button(multi_frame, text="X-Y+", width=8,
                                   command=lambda: self.jog_move(x=-1, y=1), state="disabled")
        self.diag2_btn.grid(row=0, column=1, padx=2, pady=2)

        self.diag3_btn = ttk.Button(multi_frame, text="X+Y-", width=8,
                                   command=lambda: self.jog_move(x=1, y=-1), state="disabled")
        self.diag3_btn.grid(row=1, column=0, padx=2, pady=2)

        self.diag4_btn = ttk.Button(multi_frame, text="X-Y-", width=8,
                                   command=lambda: self.jog_move(x=-1, y=-1), state="disabled")
        self.diag4_btn.grid(row=1, column=1, padx=2, pady=2)

        # Full home button
        self.full_home_btn = ttk.Button(multi_frame, text="Full Home\n($H)", width=17,
                                       command=self.full_home, state="disabled")
        self.full_home_btn.grid(row=2, column=0, columnspan=2, padx=2, pady=5)

        # Store all jog buttons for easy state management
        self.jog_buttons = [
            self.y_plus_btn, self.x_minus_btn, self.xy_home_btn, self.x_plus_btn, self.y_minus_btn,
            self.z_plus_btn, self.z_home_btn, self.z_minus_btn,
            self.diag1_btn, self.diag2_btn, self.diag3_btn, self.diag4_btn, self.full_home_btn,
            self.jog_stop_btn
        ]

    def setup_output_frame(self, parent):
        """Setup output display"""
        output_frame = ttk.LabelFrame(parent, text="Output & Debug", padding="5")
        output_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)

        # Control frame
        control_frame = ttk.Frame(output_frame)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))

        # Debug level controls
        ttk.Label(control_frame, text="Debug Level:").grid(row=0, column=0, padx=(0, 5))

        self.debug_vars = {
            'enabled': tk.BooleanVar(value=True),
            'status_queries': tk.BooleanVar(value=False),
            'position_updates': tk.BooleanVar(value=False),
            'routine_responses': tk.BooleanVar(value=False),
            'buffer_operations': tk.BooleanVar(value=False),
            'command_flow': tk.BooleanVar(value=True)
        }

        col = 1
        for key, var in self.debug_vars.items():
            label = key.replace('_', ' ').title()
            cb = ttk.Checkbutton(control_frame, text=label, variable=var,
                               command=self.update_debug_settings)
            cb.grid(row=0, column=col, padx=(0, 10))
            col += 1

        # Clear button
        clear_btn = ttk.Button(control_frame, text="Clear", command=self.clear_output)
        clear_btn.grid(row=0, column=col, padx=(10, 0))

        # Output text area
        self.output_text = scrolledtext.ScrolledText(output_frame, height=20, width=80)
        self.output_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    def setup_status_frame(self, parent):
        """Setup status information display"""
        status_frame = ttk.LabelFrame(parent, text="Status Information", padding="5")
        status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E))

        # Current status
        info_frame = ttk.Frame(status_frame)
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        info_frame.columnconfigure(1, weight=1)
        info_frame.columnconfigure(3, weight=1)
        info_frame.columnconfigure(5, weight=1)

        ttk.Label(info_frame, text="Status:").grid(row=0, column=0, padx=(0, 5))
        self.status_var = tk.StringVar(value="Unknown")
        ttk.Label(info_frame, textvariable=self.status_var).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(info_frame, text="Position:").grid(row=0, column=2, padx=(20, 5))
        self.position_var = tk.StringVar(value="X:0.000 Y:0.000 Z:0.000")
        ttk.Label(info_frame, textvariable=self.position_var).grid(row=0, column=3, sticky=tk.W)

        # Buffer status
        buffer_frame = ttk.Frame(status_frame)
        buffer_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))

        ttk.Label(buffer_frame, text="Buffer:").grid(row=0, column=0, padx=(0, 5))
        self.buffer_var = tk.StringVar(value="Total:0 Pending:0 Sent:0 Completed:0")
        ttk.Label(buffer_frame, textvariable=self.buffer_var).grid(row=0, column=1, sticky=tk.W)

        # Update buffer status periodically
        self.update_buffer_status()

    def setup_event_handlers(self):
        """Setup event handlers for GRBL events"""
        # Note: Event handlers are automatically registered due to @event_handler decorators
        pass

    @event_handler(GRBLEvents.CONNECTED, EventPriority.HIGH)
    def on_grbl_connected(self, success: bool):
        """Handle GRBL connection events"""
        if success:
            self.gui_queue.put(('connection', 'Connected', 'green'))
            self.gui_queue.put(('enable_controls', True))
        else:
            self.gui_queue.put(('connection', 'Connection Failed', 'red'))

    @event_handler(GRBLEvents.DISCONNECTED, EventPriority.HIGH)
    def on_grbl_disconnected(self):
        """Handle GRBL disconnection events"""
        self.gui_queue.put(('connection', 'Disconnected', 'red'))
        self.gui_queue.put(('enable_controls', False))

    @event_handler(GRBLEvents.ERROR, EventPriority.NORMAL)
    def on_grbl_error(self, error_message: str):
        """Handle GRBL errors"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.gui_queue.put(('output', f"[{timestamp}] ERROR: {error_message}", 'red'))

    @event_handler(GRBLEvents.COMMAND_SENT, EventPriority.NORMAL)
    def on_command_sent(self, command: str):
        """Handle command sent events"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.gui_queue.put(('output', f"[{timestamp}] SENT: {command}", 'blue'))

    @event_handler(GRBLEvents.RESPONSE_RECEIVED, EventPriority.NORMAL)
    def on_response_received(self, response: str):
        """Handle response received events"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.gui_queue.put(('output', f"[{timestamp}] RECV: {response}", 'green'))

    @event_handler(GRBLEvents.STATUS_CHANGED, EventPriority.NORMAL)
    def on_status_changed(self, status: str):
        """Handle status changes"""
        self.gui_queue.put(('status', status))

    @event_handler(GRBLEvents.POSITION_CHANGED, EventPriority.NORMAL)
    def on_position_changed(self, position: list):
        """Handle position changes"""
        pos_str = f"X:{position[0]:.3f} Y:{position[1]:.3f} Z:{position[2]:.3f}"
        self.gui_queue.put(('position', pos_str))

    @event_handler("grbl.debug_info", EventPriority.LOW)
    def on_debug_info(self, message: str):
        """Handle debug information"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.gui_queue.put(('output', f"[{timestamp}] DEBUG: {message}", 'gray'))

    def connect_grbl(self):
        """Connect to GRBL in background thread"""
        def connect_thread():
            try:
                port = self.port_var.get()
                baudrate = int(self.baudrate_var.get())
                success = self.grbl.connect(port, baudrate)
                if not success:
                    self.gui_queue.put(('connection', 'Connection Failed', 'red'))
            except Exception as e:
                self.gui_queue.put(('output', f"Connection error: {e}", 'red'))
                self.gui_queue.put(('connection', 'Connection Failed', 'red'))

        self.add_output("Attempting to connect...")
        self.connect_btn.config(state="disabled")
        threading.Thread(target=connect_thread, daemon=True).start()

    def disconnect_grbl(self):
        """Disconnect from GRBL"""
        try:
            self.grbl.disconnect()
            self.add_output("Disconnected")
        except Exception as e:
            self.add_output(f"Disconnect error: {e}", 'red')

    def send_command(self):
        """Send synchronous command"""
        command = self.command_var.get().strip()
        if not command:
            return

        def send_thread():
            try:
                timeout = float(self.timeout_var.get())
                start_time = time.time()
                self.gui_queue.put(('output', f"Sending sync command: {command}", 'blue'))

                responses = self.grbl.send_command(command, timeout)
                elapsed = time.time() - start_time

                self.gui_queue.put(('output', f"Sync command completed in {elapsed:.3f}s", 'blue'))
                for response in responses:
                    self.gui_queue.put(('output', f"  Response: {response}", 'green'))

            except Exception as e:
                self.gui_queue.put(('output', f"Sync command error: {e}", 'red'))

        threading.Thread(target=send_thread, daemon=True).start()
        self.command_var.set("")

    def send_async_command(self):
        """Send asynchronous command"""
        command = self.command_var.get().strip()
        if not command:
            return

        try:
            timeout = float(self.timeout_var.get())
            self.command_counter += 1
            cmd_id = f"cmd_{self.command_counter}"

            future = self.grbl.send_command_async(command, timeout)
            self.active_futures[cmd_id] = future

            self.add_output(f"Async command {cmd_id} queued: {command}", 'blue')

            # Monitor the future in a separate thread
            def monitor_future():
                try:
                    start_time = time.time()
                    responses = future.result(timeout + 1.0)
                    elapsed = time.time() - start_time

                    self.gui_queue.put(('output', f"Async {cmd_id} completed in {elapsed:.3f}s", 'blue'))
                    for response in responses:
                        self.gui_queue.put(('output', f"  {cmd_id} Response: {response}", 'green'))

                except Exception as e:
                    self.gui_queue.put(('output', f"Async {cmd_id} error: {e}", 'red'))
                finally:
                    if cmd_id in self.active_futures:
                        del self.active_futures[cmd_id]

            threading.Thread(target=monitor_future, daemon=True).start()
            self.command_var.set("")

        except Exception as e:
            self.add_output(f"Async command error: {e}", 'red')

    def quick_command(self, command):
        """Send a quick command"""
        if command == "RESET":
            self.grbl.reset()
            self.add_output("Reset command sent", 'orange')
        elif command == "!":
            self.grbl.emergency_stop()
            self.add_output("Emergency stop sent", 'orange')
        else:
            self.command_var.set(command)
            self.send_command()

    def update_debug_settings(self):
        """Update GRBL debug settings"""
        if hasattr(self.grbl, 'set_debug_level'):
            self.grbl.set_debug_level(
                debug_enabled=self.debug_vars['enabled'].get(),
                log_status_queries=self.debug_vars['status_queries'].get(),
                log_position_updates=self.debug_vars['position_updates'].get(),
                log_routine_responses=self.debug_vars['routine_responses'].get(),
                log_buffer_operations=self.debug_vars['buffer_operations'].get(),
                log_command_flow=self.debug_vars['command_flow'].get()
            )

    def update_buffer_status(self):
        """Update buffer status display"""
        try:
            if hasattr(self.grbl, 'get_buffer_status'):
                status = self.grbl.get_buffer_status()
                status_text = (f"Total:{status['total_commands']} "
                             f"Pending:{status['pending']} "
                             f"Sent:{status['sent']} "
                             f"Completed:{status['completed']} "
                             f"Error:{status['error']} "
                             f"Timeout:{status['timeout']}")
                self.buffer_var.set(status_text)
        except:
            pass

        # Schedule next update
        self.root.after(1000, self.update_buffer_status)

    def clear_output(self):
        """Clear the output text area"""
        self.output_text.delete(1.0, tk.END)

    def add_output(self, message: str, color: str = 'black'):
        """Add message to output area"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.gui_queue.put(('output', f"[{timestamp}] {message}", color))

    def update_gui(self):
        """Process GUI updates from queue (thread-safe)"""
        try:
            while True:
                msg_type, *args = self.gui_queue.get_nowait()

                if msg_type == 'output':
                    message, color = args
                    self.output_text.insert(tk.END, message + '\n')
                    if color != 'black':
                        # Simple color coding (limited in tkinter)
                        pass
                    self.output_text.see(tk.END)

                elif msg_type == 'connection':
                    status, color = args
                    self.conn_status_var.set(status)

                elif msg_type == 'enable_controls':
                    enabled = args[0]
                    state = "normal" if enabled else "disabled"
                    self.send_btn.config(state=state)
                    self.send_async_btn.config(state=state)

                    # Enable/disable quick command buttons
                    for i in range(6):
                        btn = getattr(self, f"quick_btn_{i}", None)
                        if btn:
                            btn.config(state=state)

                    # Enable/disable jog buttons
                    for btn in self.jog_buttons:
                        btn.config(state=state)

                    self.connect_btn.config(state="disabled" if enabled else "normal")
                    self.disconnect_btn.config(state="normal" if enabled else "disabled")

                elif msg_type == 'status':
                    status = args[0]
                    self.status_var.set(status)

                elif msg_type == 'position':
                    position = args[0]
                    self.position_var.set(position)

        except queue.Empty:
            pass

        # Schedule next update
        self.root.after(50, self.update_gui)

    def jog_move(self, x=0, y=0, z=0):
        """Execute a jog movement using relative positioning"""
        try:
            distance = float(self.jog_distance_var.get())
            feed_rate = float(self.jog_feedrate_var.get())
            mode = self.jog_mode_var.get()

            # Calculate actual distances
            x_dist = x * distance
            y_dist = y * distance
            z_dist = z * distance

            # Create movement description for logging
            moves = []
            if x_dist != 0:
                moves.append(f"X{x_dist:+.1f}")
            if y_dist != 0:
                moves.append(f"Y{y_dist:+.1f}")
            if z_dist != 0:
                moves.append(f"Z{z_dist:+.1f}")
            move_desc = " ".join(moves) if moves else "No movement"

            self.add_output(f"Jog {mode}: {move_desc} @ F{feed_rate}", 'blue')

            if mode == "Async":
                # Use async jog for testing the async system
                def async_jog():
                    try:
                        start_time = time.time()
                        responses = self.grbl.move_relative(x_dist, y_dist, z_dist, feed_rate)
                        elapsed = time.time() - start_time

                        success = any("ok" in str(response).lower() for response in responses)
                        result = "completed" if success else "failed"

                        self.gui_queue.put(('output',
                                          f"Async jog {result} in {elapsed:.3f}s: {move_desc}",
                                          'green' if success else 'red'))

                        if not success:
                            for response in responses:
                                if "error" in str(response).lower():
                                    self.gui_queue.put(('output', f"  Error: {response}", 'red'))

                    except Exception as e:
                        self.gui_queue.put(('output', f"Async jog error: {e}", 'red'))

                threading.Thread(target=async_jog, daemon=True).start()

            else:
                # Synchronous jog
                def sync_jog():
                    try:
                        start_time = time.time()
                        success = self.grbl.move_to(
                            x=self.grbl.current_position[0] + x_dist if x_dist != 0 else None,
                            y=self.grbl.current_position[1] + y_dist if y_dist != 0 else None,
                            z=self.grbl.current_position[2] + z_dist if z_dist != 0 else None,
                            feed_rate=feed_rate
                        )
                        elapsed = time.time() - start_time

                        result = "completed" if success else "failed"
                        self.gui_queue.put(('output',
                                          f"Sync jog {result} in {elapsed:.3f}s: {move_desc}",
                                          'green' if success else 'red'))

                    except Exception as e:
                        self.gui_queue.put(('output', f"Sync jog error: {e}", 'red'))

                threading.Thread(target=sync_jog, daemon=True).start()

        except ValueError as e:
            self.add_output(f"Invalid jog parameters: {e}", 'red')
        except Exception as e:
            self.add_output(f"Jog error: {e}", 'red')

    def xy_home(self):
        """Home X and Y axes to current Z"""
        try:
            current_z = self.grbl.current_position[2]
            self.add_output(f"XY Home to (0, 0, {current_z:.3f})", 'orange')

            def home_xy():
                try:
                    success = self.grbl.move_to(x=0, y=0, z=current_z)
                    result = "completed" if success else "failed"
                    self.gui_queue.put(('output', f"XY home {result}", 'green' if success else 'red'))
                except Exception as e:
                    self.gui_queue.put(('output', f"XY home error: {e}", 'red'))

            threading.Thread(target=home_xy, daemon=True).start()

        except Exception as e:
            self.add_output(f"XY home error: {e}", 'red')

    def z_home(self):
        """Home Z axis to 0"""
        try:
            self.add_output("Z Home to 0", 'orange')

            def home_z():
                try:
                    success = self.grbl.move_to(z=0)
                    result = "completed" if success else "failed"
                    self.gui_queue.put(('output', f"Z home {result}", 'green' if success else 'red'))
                except Exception as e:
                    self.gui_queue.put(('output', f"Z home error: {e}", 'red'))

            threading.Thread(target=home_z, daemon=True).start()

        except Exception as e:
            self.add_output(f"Z home error: {e}", 'red')

    def full_home(self):
        """Execute full homing sequence ($H)"""
        try:
            self.add_output("Full homing sequence ($H)", 'orange')

            def home_all():
                try:
                    success = self.grbl.home()
                    result = "completed" if success else "failed"
                    self.gui_queue.put(('output', f"Full home {result}", 'green' if success else 'red'))
                except Exception as e:
                    self.gui_queue.put(('output', f"Full home error: {e}", 'red'))

            threading.Thread(target=home_all, daemon=True).start()

        except Exception as e:
            self.add_output(f"Full home error: {e}", 'red')

    def emergency_stop_jog(self):
        """Emergency stop for jog operations"""
        try:
            self.grbl.emergency_stop()
            self.add_output("EMERGENCY STOP sent!", 'red')
        except Exception as e:
            self.add_output(f"Emergency stop error: {e}", 'red')

    def on_closing(self):
        """Handle window closing"""
        try:
            self.grbl.disconnect()
        except:
            pass
        self.root.destroy()


def main():
    """Main function to run the debug GUI"""
    root = tk.Tk()

    # Create and configure the GUI
    app = GRBLDebugGUI(root)

    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # Start the GUI
    root.mainloop()


if __name__ == "__main__":
    main()