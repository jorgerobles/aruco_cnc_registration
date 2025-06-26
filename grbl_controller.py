import time
import serial
import re


class GRBLController:
    def __init__(self, port='/dev/ttyUSB0', baud=115200, timeout=2):
        self.serial_conn = None
        self.port = port
        self.baud = baud
        self.timeout = timeout

    def connect(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baud, timeout=self.timeout)
            self.serial_conn.flushInput()
            time.sleep(2)
            self.serial_conn.write(b"\r\n\r\n")  # Wake up
            time.sleep(2)
            self.serial_conn.flushInput()
            return True
        except Exception as e:
            print(f"Failed to connect to GRBL: {e}")
            return False

    def disconnect(self):
        if self.serial_conn:
            self.serial_conn.close()
            self.serial_conn = None

    def send_command(self, command: str):
        if not self.serial_conn:
            raise ValueError("GRBL not connected")

        self.serial_conn.write(f"{command}\n".encode())
        time.sleep(0.1)

        # Read response
        response_lines = []
        while self.serial_conn.in_waiting:
            line = self.serial_conn.readline().decode().strip()
            if line:
                response_lines.append(line)
        return response_lines

    def get_position(self, axes=None):
        """
        Get current machine position for specified axes.

        Args:
            axes (list or None): List of axis indices to return (0=X, 1=Y, 2=Z, 3=A, 4=B, 5=C)
                               If None, returns X, Y, Z by default (indices 0, 1, 2)

        Returns:
            list: Position values for requested axes in the same order as requested
                 Default: [x, y, z] positions

        Examples:
            get_position()           # Returns [x, y, z]
            get_position([0, 1])     # Returns [x, y]
            get_position([2])        # Returns [z]
            get_position([0, 1, 2, 3])  # Returns [x, y, z, a] if 4-axis machine
        """
        if not self.serial_conn:
            raise ValueError("GRBL not connected")

        # Default to X, Y, Z axes (indices 0, 1, 2)
        if axes is None:
            axes = [0, 1, 2]

        # Validate axes input
        if not isinstance(axes, (list, tuple)):
            raise ValueError("axes must be a list or tuple of axis indices")

        for axis in axes:
            if not isinstance(axis, int) or axis < 0:
                raise ValueError("axis indices must be non-negative integers")

        self.serial_conn.write(b"?\n")
        time.sleep(0.1)
        response = self.serial_conn.readlines()

        for line in response:
            line_str = line.decode() if isinstance(line, bytes) else str(line)

            # Use regex to find MPos data, ignoring everything after | or >
            mpos_match = re.search(r'MPos:([-+]?\d*\.?\d+(?:,[-+]?\d*\.?\d+)*)', line_str)

            if mpos_match:
                try:
                    # Extract the matched position string
                    mpos_str = mpos_match.group(1)

                    # Split by comma and convert to float, filtering out empty strings
                    position_values = []
                    for pos_str in mpos_str.split(','):
                        pos_str = pos_str.strip()
                        if pos_str:  # Only process non-empty strings
                            position_values.append(float(pos_str))

                    # Extract requested axes
                    result = []
                    for axis_idx in axes:
                        if axis_idx < len(position_values):
                            result.append(position_values[axis_idx])
                        else:
                            raise ValueError(
                                f"Axis {axis_idx} not available (only {len(position_values)} axes reported)")

                    return result

                except (ValueError, IndexError) as e:
                    raise ValueError(f"Failed to parse GRBL position values: {e}")

        raise ValueError("Failed to get position response from GRBL")

    def move_relative(self, x=0, y=0, z=0, feedrate=1000):
        cmd = f"G91 G1 X{x} Y{y} Z{z} F{feedrate}"
        return self.send_command(cmd)

    def move_absolute(self, x=None, y=None, z=None, feedrate=1000):
        cmd = "G90 G1"
        if x is not None:
            cmd += f" X{x}"
        if y is not None:
            cmd += f" Y{y}"
        if z is not None:
            cmd += f" Z{z}"
        cmd += f" F{feedrate}"
        return self.send_command(cmd)

    def home(self):
        return self.send_command("$H")

    def set_work_offset(self, offset_xyz, coordinate_system=1):
        cmd = f"G10 L20 P{coordinate_system} X{offset_xyz[0]:.3f} Y{offset_xyz[1]:.3f} Z{offset_xyz[2]:.3f}"
        return self.send_command(cmd)