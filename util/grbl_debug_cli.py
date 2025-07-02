#!/usr/bin/env python3
"""
GRBL Connection Troubleshooting Script
Run this to diagnose connection issues with your GRBL controller
"""

import serial
import serial.tools.list_ports
import os
import time
import subprocess
import sys


def check_system_info():
    """Check basic system information"""
    print("=== System Information ===")
    print(f"Operating System: {os.name}")
    print(f"Python Version: {sys.version}")
    print()


def list_available_ports():
    """List all available serial ports"""
    print("=== Available Serial Ports ===")
    ports = serial.tools.list_ports.comports()

    if not ports:
        print("No serial ports found!")
        return []

    available_ports = []
    for port in ports:
        print(f"Port: {port.device}")
        print(f"  Description: {port.description}")
        print(f"  Hardware ID: {port.hwid}")
        print(f"  Manufacturer: {port.manufacturer}")
        print()
        available_ports.append(port.device)

    return available_ports


def check_port_permissions(port_path):
    """Check if we have permissions to access the port"""
    print(f"=== Port Permissions Check: {port_path} ===")

    if not os.path.exists(port_path):
        print(f"❌ Port {port_path} does not exist!")
        return False

    # Check if readable/writable
    readable = os.access(port_path, os.R_OK)
    writable = os.access(port_path, os.W_OK)

    print(f"Readable: {'✅' if readable else '❌'}")
    print(f"Writable: {'✅' if writable else '❌'}")

    if not (readable and writable):
        print("\n🔧 Permission Fix Suggestions:")
        print(f"1. Add your user to the dialout group:")
        print(f"   sudo usermod -a -G dialout $USER")
        print(f"2. Change port permissions temporarily:")
        print(f"   sudo chmod 666 {port_path}")
        print(f"3. Or run with sudo (not recommended for regular use)")
        print("\nAfter adding to dialout group, you need to log out and back in.")

    print()
    return readable and writable


def test_basic_connection(port_path, baudrates=[115200, 9600, 57600, 38400]):
    """Test basic serial connection with different baudrates"""
    print(f"=== Testing Basic Connection: {port_path} ===")

    for baudrate in baudrates:
        print(f"Testing {baudrate} baud...")
        try:
            ser = serial.Serial(port_path, baudrate, timeout=2)
            time.sleep(2)  # Wait for potential Arduino reset

            # Try to read any initial data
            if ser.in_waiting:
                initial_data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                print(f"  Initial data received: {repr(initial_data)}")

            # Test if we can write
            ser.write(b'\r\n')
            time.sleep(0.5)

            if ser.in_waiting:
                response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                print(f"  Response to newline: {repr(response)}")

            ser.close()
            print(f"  ✅ Basic connection successful at {baudrate} baud")
            return True

        except serial.SerialException as e:
            print(f"  ❌ Failed at {baudrate} baud: {e}")
        except Exception as e:
            print(f"  ❌ Unexpected error at {baudrate} baud: {e}")

    print("❌ No successful basic connection at any baudrate")
    return False


def test_grbl_communication(port_path, baudrate=115200):
    """Test GRBL-specific communication"""
    print(f"=== Testing GRBL Communication: {port_path} at {baudrate} baud ===")

    try:
        ser = serial.Serial(port_path, baudrate, timeout=3)
        time.sleep(2)  # Wait for GRBL initialization

        # Clear any initial messages
        while ser.in_waiting:
            ser.read(ser.in_waiting)
            time.sleep(0.1)

        # Test commands in order
        test_commands = [
            (b'\r\n', "Newline test"),
            (b'?\r\n', "Status query"),
            (b'$\r\n', "Settings query"),
            (b'$#\r\n', "Parameters query"),
        ]

        for command, description in test_commands:
            print(f"Testing: {description}")
            ser.write(command)
            time.sleep(1)

            response = ""
            if ser.in_waiting:
                response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')

            print(f"  Command: {repr(command)}")
            print(f"  Response: {repr(response)}")

            if "Grbl" in response or "ok" in response or "$" in response:
                print(f"  ✅ GRBL detected!")
                ser.close()
                return True
            print()

        ser.close()
        print("❌ No GRBL responses detected")
        return False

    except Exception as e:
        print(f"❌ GRBL communication test failed: {e}")
        return False


def check_device_connection():
    """Check if device is physically connected"""
    print("=== Device Connection Check ===")

    # Check dmesg for recent USB device connections (Linux)
    if os.name == 'posix':
        try:
            result = subprocess.run(['dmesg', '|', 'tail', '-20'],
                                    capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                print("Recent kernel messages (look for USB/serial device connections):")
                print(result.stdout)
        except Exception as e:
            print(f"Could not check dmesg: {e}")

    print("\n🔧 Physical Connection Checklist:")
    print("1. ✓ USB cable is properly connected")
    print("2. ✓ GRBL board is powered on")
    print("3. ✓ USB cable supports data (not just power)")
    print("4. ✓ Try a different USB port")
    print("5. ✓ Try a different USB cable")
    print()


def main():
    """Main troubleshooting function"""
    print("🔍 GRBL Connection Troubleshooting Tool")
    print("=====================================\n")

    # Check system info
    check_system_info()

    # List available ports
    available_ports = list_available_ports()

    # Check device connection
    check_device_connection()

    # Test the specific port
    target_port = "/dev/ttyUSB0"

    # Check if target port exists and has permissions
    has_permissions = check_port_permissions(target_port)

    if has_permissions:
        # Test basic connection
        basic_ok = test_basic_connection(target_port)

        if basic_ok:
            # Test GRBL communication
            grbl_ok = test_grbl_communication(target_port)

            if grbl_ok:
                print("🎉 SUCCESS: GRBL communication working!")
            else:
                print("⚠️  Basic connection works, but GRBL not responding")
                print("   - Check if correct firmware is loaded")
                print("   - Try different baudrate")
                print("   - Device might not be GRBL-compatible")

    # Suggest alternative ports if target port failed
    if not has_permissions or target_port not in available_ports:
        print(f"\n🔧 Alternative ports to try:")
        for port in available_ports:
            if port != target_port:
                print(f"   - {port}")

    print("\n📋 Summary of common solutions:")
    print("1. Add user to dialout group: sudo usermod -a -G dialout $USER")
    print("2. Check USB cable and connections")
    print("3. Try different port (ttyACM0, ttyUSB1, etc.)")
    print("4. Verify GRBL firmware is loaded on the device")
    print("5. Check baudrate (usually 115200 for GRBL)")


if __name__ == "__main__":
    main()