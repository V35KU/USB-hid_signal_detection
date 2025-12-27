import hid
import time

# configuration 
TARGET_VENDOR_ID = 0x06a31  # choose the correct usb device 
TARGET_PRODUCT_ID = 0xff32 
POLL_DELAY = 0.001  # use a smaller delay for smoother tracking and to save cpu

# R660 wheel/pedal byte mapping
# byte 0: Report ID. We only care about ID 0x07.
# byte 1: Steering (relative, 8-bit, 255, wraps)
# byte 3: Gas      (absolute, 8-bit, 255=off, 0=full)
# byte 4: Brake    (absolute, 8-bit, 255=off, 0=full)
# byte 5: ignore
# byte 6: buttons on wheel (ignore for now)
STEER_BYTE_INDEX = 1
REPORT_ID_BYTE_INDEX = 0
GAS_BYTE_INDEX = 3
BRAKE_BYTE_INDEX = 4

# full range 0 - 4090
STEER_MIN = -2045
STEER_MAX = 2045

##TODO 
# deadzone in the middle ~-2030 - 2050
##TODO also in the brake we have a weird problem with pedals

# device listing to see all HID devices connected
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

# data intepreter
def sniff_data():
    """
    Connects to the R660 wheel, reads its HID data, and interprets it into
    meaningful steering, gas, and brake values.
    """
    device = None
    try:
        # conneccts to our device using VIP/DIP
        # non-block to avoid freezing, send data or return nothing and continue
        device = hid.device()
        device.open(TARGET_VENDOR_ID, TARGET_PRODUCT_ID)
        device.set_nonblocking(1)

        print("Connected. Reading wheel and pedal data... (Ctrl+C to stop)")
        print(f"\n{'Steering':>10} | {'Gas':>5} | {'Brake':>5}")
        print("-" * 32)

        # state variables for steering reconstruction
        # +because steering is relative encoder (wraps) we need to know
        # the previus raw value, accumulate it in 'steer_position'
        last_steer_raw = None
        steer_position = 0

        while True:
            # read a data packet (8 bytes)
            data = device.read(8)
            if not data:
                time.sleep(POLL_DELAY)
                continue

            # The device sends multiple report types. The one with ID 0x07
            # contains the axis data we care about. Ignore all others,
            # because they are 'TRASH'
            if data[REPORT_ID_BYTE_INDEX] != 0x07:
                time.sleep(POLL_DELAY)
                continue

            # steering reconstruction
            current_steer_raw = data[STEER_BYTE_INDEX]
            if last_steer_raw is not None:
                # calculate delta(change), handling the 8-bit wrap-around.
                # if the jump is > 127 (half of 255), it's a wrap-around in one direction.
                # if the jump is < -127, it's a wrap-around in the other.
                delta = current_steer_raw - last_steer_raw
                if delta > 127:
                    delta -= 256
                elif delta < -127:
                    delta += 256

                # accumulate the delta to get the absolute position
                steer_position += delta
                # clamp the position to the known limits of the device
                steer_position = max(STEER_MIN, min(STEER_MAX, steer_position))
            last_steer_raw = current_steer_raw

            # pedal processing
            # gas and brake are inverted (255=off, 0=full), so we flip it.
            gas_value = 255 - data[GAS_BYTE_INDEX]
            brake_value = 255 - data[BRAKE_BYTE_INDEX]

            # output display
            # use carriage return to update the line in-place instead of printing shit-ton
            print(f"{steer_position:10} | {gas_value:5} | {brake_value:5}  ", end='\r')

    except KeyboardInterrupt:
        print("\nStopped.")
    except IOError:
        print("\nError: Device not found or could not be read.")
        print(f"Ensure a device with VID=0x{TARGET_VENDOR_ID:04x} and PID=0x{TARGET_PRODUCT_ID:04x} is connected.")
    finally:
        if device:
            device.close()

# main  
if __name__ == "__main__":
    list_devices()
    sniff_data()
