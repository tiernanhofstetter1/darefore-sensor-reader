import asyncio
import time
from bleak import BleakScanner, BleakClient

DEVICE_NAME = "Darefore HR2"
F0F0_NOTIFY = "34800002-7185-4d5d-b431-630e7050e8f0"
F0F0_WRITE = "34800001-7185-4d5d-b431-630e7050e8f0"

SUBSCRIBE_FAST_ACCEL = bytes([0x01, 0x0B]) + b"/Meas/IMU6"

CAPTURE_SECONDS = 15
OUTPUT_FILE = "f0f0_capture_imu6_explore.csv"

rows = []
t0 = None


def handler(_, data: bytearray):
    global t0
    now = time.monotonic()
    if t0 is None:
        t0 = now
    rows.append((now - t0, bytes(data)))


async def main():
    print(f"Scanning for '{DEVICE_NAME}' (15s)...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15.0)
    if device is None:
        print("Device not found.")
        return

    async with BleakClient(device, winrt=dict(use_cached_services=False)) as client:
        print(f"Connected: {client.is_connected}")
        await client.start_notify(F0F0_NOTIFY, handler)
        await client.write_gatt_char(F0F0_WRITE, SUBSCRIBE_FAST_ACCEL)

        print(f"\nCapturing for {CAPTURE_SECONDS}s starting NOW!")
        print("  0-5s:   stand still (baseline)")
        print("  5-15s:  slowly twist/rotate the sensor by hand in different directions\n")
        for remaining in range(CAPTURE_SECONDS, 0, -5):
            print(f"  {remaining}s remaining...")
            await asyncio.sleep(5)

        print("Done capturing.")

    with open(OUTPUT_FILE, "w") as f:
        f.write("t_seconds,hex\n")
        for t, data in rows:
            f.write(f"{t:.4f},{data.hex()}\n")

    print(f"Wrote {len(rows)} readings to {OUTPUT_FILE}")


asyncio.run(main())
