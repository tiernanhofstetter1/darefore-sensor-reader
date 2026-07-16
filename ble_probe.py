import asyncio
from datetime import datetime
from bleak import BleakScanner, BleakClient

DEVICE_NAME = "Darefore HR2"

FDF3_NOTIFY = "6b200002-ff4e-4979-8186-fb7ba486fcd7"
FDF3_WRITE = "6b200001-ff4e-4979-8186-fb7ba486fcd7"
MOVESENSE_NOTIFY = "34800002-7185-4d5d-b431-630e7050e8f0"
MOVESENSE_WRITE = "34800001-7185-4d5d-b431-630e7050e8f0"
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"

CANDIDATES = [
    bytes([0x00]), bytes([0x01]), bytes([0x02]), bytes([0x03]),
    bytes([0x04]), bytes([0x05]), bytes([0xFF]),
    bytes([0x01, 0x00]), bytes([0x01, 0x01]), bytes([0x00, 0x01]),
    b"start", b"START", b"go", b"GET", b"run",
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
        print("Device not found. Make sure it's powered on, nearby, and disconnected from your phone/other apps.")
        return

    async with BleakClient(device) as client:
        print(f"[{ts()}] Connected: {client.is_connected}")

        for uuid, label in [
            (FDF3_NOTIFY, "FDF3"),
            (MOVESENSE_NOTIFY, "MOVESENSE"),
            (HR_MEASUREMENT, "HR"),
        ]:
            try:
                await client.start_notify(uuid, make_handler(label))
                print(f"[{ts()}] Subscribed to {label} ({uuid})")
            except Exception as e:
                print(f"[{ts()}] Could not subscribe to {label}: {e}")

        print(f"\n[{ts()}] Listening passively for 5s before trying writes...\n")
        await asyncio.sleep(5)

        for payload in CANDIDATES:
            print(f"[{ts()}] Writing {payload.hex(' ')!r} to FDF3 write channel...")
            try:
                await client.write_gatt_char(FDF3_WRITE, payload, response=True)
            except Exception as e:
                print(f"[{ts()}]   write failed: {e}")
                continue
            await asyncio.sleep(1.5)

        print(f"\n[{ts()}] Done with write attempts. Listening passively for 10 more seconds...\n")
        await asyncio.sleep(10)
        print(f"[{ts()}] Finished.")


asyncio.run(main())
