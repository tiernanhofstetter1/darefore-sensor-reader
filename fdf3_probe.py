import asyncio
from datetime import datetime
from bleak import BleakScanner, BleakClient

DEVICE_NAME = "Darefore HR2"

FDF3_NOTIFY = "6b200002-ff4e-4979-8186-fb7ba486fcd7"
FDF3_WRITE = "6b200001-ff4e-4979-8186-fb7ba486fcd7"
F0F0_NOTIFY = "34800002-7185-4d5d-b431-630e7050e8f0"
F0F0_WRITE = "34800001-7185-4d5d-b431-630e7050e8f0"
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"

# (label, bytes)
CANDIDATES = [
    ("single 00", bytes([0x00])),
    ("single 01", bytes([0x01])),
    ("single 02", bytes([0x02])),
    ("single 03", bytes([0x03])),
    ("single 04", bytes([0x04])),
    ("single 05", bytes([0x05])),
    ("single ff", bytes([0xFF])),
    ("01 00", bytes([0x01, 0x00])),
    ("01 01", bytes([0x01, 0x01])),
    ("00 01", bytes([0x00, 0x01])),
    ("ascii start", b"start"),
    ("ascii GET", b"GET"),
    ("ascii SUBSCRIBE", b"SUBSCRIBE"),
    ("movesense-style SUBSCRIBE /Meas/RunningDynamics", bytes([0x01, 0x09]) + b"/Meas/RunningDynamics"),
    ("movesense-style GET /RunningDynamics", bytes([0x04, 0x09]) + b"/RunningDynamics"),
    ("movesense-style SUBSCRIBE /Darefore/RD", bytes([0x01, 0x09]) + b"/Darefore/RD"),
    ("hello 0x00 0x00 0x00 0x00", bytes([0x00, 0x00, 0x00, 0x00])),
    ("counter-like 01 00 00 00", bytes([0x01, 0x00, 0x00, 0x00])),
]


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def make_handler(label):
    def handler(_, data: bytearray):
        print(f"[{ts()}]   <-- {label} notify: {data.hex(' ')}")
    return handler


async def main():
    print(f"[{ts()}] Scanning for '{DEVICE_NAME}' (15s)...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15.0)
    if device is None:
        print("Device not found. Make sure it's powered on, nearby, and disconnected from your phone.")
        return

    async with BleakClient(device, winrt=dict(use_cached_services=False)) as client:
        print(f"[{ts()}] Connected: {client.is_connected}")

        for uuid, label in [
            (FDF3_NOTIFY, "FDF3"),
            (F0F0_NOTIFY, "F0F0"),
            (HR_MEASUREMENT, "HR"),
        ]:
            try:
                await client.start_notify(uuid, make_handler(label))
                print(f"[{ts()}] Subscribed to {label}")
            except Exception as e:
                print(f"[{ts()}] Could not subscribe to {label}: {e}")

        print(f"\n[{ts()}] Listening passively for 5s...\n")
        await asyncio.sleep(5)

        for label, payload in CANDIDATES:
            print(f"[{ts()}] Writing [{label}] = {payload.hex(' ')!r} (write-with-response)")
            try:
                await client.write_gatt_char(FDF3_WRITE, payload, response=True)
                print(f"[{ts()}]   write acknowledged (no GATT-level error)")
            except Exception as e:
                print(f"[{ts()}]   write REJECTED: {type(e).__name__}: {e}")
            await asyncio.sleep(2.0)

        print(f"\n[{ts()}] Done. Listening passively for 10 more seconds...\n")
        await asyncio.sleep(10)
        print(f"[{ts()}] Finished.")


asyncio.run(main())
