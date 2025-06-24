import time
import serial

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

    def get_position(self):
        if not self.serial_conn:
            raise ValueError("GRBL not connected")

        self.serial_conn.write(b"?\n")
        time.sleep(0.1)
        response = self.serial_conn.readlines()

        for line in response:
            if b"MPos:" in line:
                data = line.decode()
                try:
                    mpos = data.split('MPos:')[1].split(' ')[0]
                    x, y, z = map(float, mpos.split(','))
                    return [x, y, z]
                except:
                    pass
        raise ValueError("Failed to parse GRBL position")

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
