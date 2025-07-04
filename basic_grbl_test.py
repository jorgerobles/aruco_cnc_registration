from services.grbl_controller import GRBLController

# Create controller
grbl = GRBLController()

# Connect
if grbl.connect("/dev/ttyUSB0", 115200):
    print("Connected!")

    # Do some work...
    grbl.send_command("?")

    print("aaa")
    # Disconnect cleanly
    grbl.disconnect()

    # Verify clean disconnect
    if grbl.is_properly_disconnected():
        print("Disconnected cleanly!")
    else:
        print("Disconnect issues detected:")
        print(grbl.get_disconnect_status())