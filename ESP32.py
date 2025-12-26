import hid
import time

# ==========================================
# CONFIGURATION
# ==========================================
TARGET_VENDOR_ID = 0x06a3
TARGET_PRODUCT_ID = 0xff32
POLL_DELAY = 0.001  # Use a smaller delay for smoother tracking

# --- R660 Wheel/Pedal Byte Mapping ---
# Byte 0: Report ID. We only care about ID 0x07.
# Byte 1: Steering (relative, 8-bit, wraps)
# Byte 3: Gas      (absolute, 8-bit, 255=off, 0=full)
# Byte 4: Brake    (absolute, 8-bit, 0=off, 255=full)
STEER_BYTE_INDEX = 1
REPORT_ID_BYTE_INDEX = 0
GAS_BYTE_INDEX = 3
BRAKE_BYTE_INDEX = 4

STEER_MIN = -2045
STEER_MAX = 2045

# ==========================================
# DEVICE LISTING
# ==========================================
def list_devices():
    devices = hid.enumerate()
    print(f"{'VID':<8} {'PID':<8} {'Product Name'}")
    print("-" * 50)
    for d in devices:
        vid = d.get('vendor_id', 0)
        pid = d.get('product_id', 0)
        name = d.get('product_string', 'Unknown')
        print(f"0x{vid:04x}  0x{pid:04x}  {name}")
    print("-" * 50)

# ==========================================
# DATA INTERPRETER
# ==========================================
def sniff_data():
    """
    Connects to the R660 wheel, reads its HID data, and interprets it into
    meaningful steering, gas, and brake values.
    """
    device = None
    try:
        device = hid.device()
        device.open(TARGET_VENDOR_ID, TARGET_PRODUCT_ID)
        device.set_nonblocking(1)

        print("Connected. Reading wheel and pedal data... (Ctrl+C to stop)")
        print(f"\n{'Steering':>10} | {'Gas':>5} | {'Brake':>5}")
        print("-" * 32)

        # State variables for steering reconstruction
        last_steer_raw = None
        steer_position = 0

        while True:
            # Read a data packet (8 bytes)
            data = device.read(8)
            if not data:
                time.sleep(POLL_DELAY)
                continue

            # The device sends multiple report types. The one with ID 0x07
            # contains the axis data we care about. Ignore all others.
            if data[REPORT_ID_BYTE_INDEX] != 0x07:
                time.sleep(POLL_DELAY)
                continue

            # --- 1. Steering Reconstruction ---
            current_steer_raw = data[STEER_BYTE_INDEX]
            if last_steer_raw is not None:
                # Calculate delta, handling the 8-bit wrap-around.
                # If the jump is > 127, it's a wrap-around in one direction.
                # If the jump is < -127, it's a wrap-around in the other.
                delta = current_steer_raw - last_steer_raw
                if delta > 127:
                    delta -= 256
                elif delta < -127:
                    delta += 256

                # Accumulate the delta to get the absolute position
                steer_position += delta
                # Clamp the position to the known limits of the device
                steer_position = max(STEER_MIN, min(STEER_MAX, steer_position))
            last_steer_raw = current_steer_raw

            # --- 2. Pedal Processing ---
            # Gas is inverted (255=off, 0=full), so we flip it.
            gas_value = 255 - data[GAS_BYTE_INDEX]
            # Brake is normal (0=off, 255=full).
            brake_value = data[BRAKE_BYTE_INDEX]

            # --- 3. Display Output ---
            # Use carriage return to update the line in-place
            print(f"{steer_position:10} | {gas_value:5} | {brake_value:5}  ", end='\r')

    except KeyboardInterrupt:
        print("\nStopped.")
    except IOError:
        print("\nError: Device not found or could not be read.")
        print(f"Ensure a device with VID=0x{TARGET_VENDOR_ID:04x} and PID=0x{TARGET_PRODUCT_ID:04x} is connected.")
    finally:
        if device:
            device.close()

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    list_devices()
    sniff_data()
