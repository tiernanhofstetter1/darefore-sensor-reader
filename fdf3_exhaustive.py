import asyncio
from datetime import datetime
from bleak import BleakScanner, BleakClient

DEVICE_NAME = "Darefore HR2"
FDF3_NOTIFY = "6b200002-ff4e-4979-8186-fb7ba486fcd7"
FDF3_WRITE = "6b200001-ff4e-4979-8186-fb7ba486fcd7"

got_response = asyncio.Event()
last_response = None


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def handler(_, data: bytearray):
    global last_response
    last_response = bytes(data)
    got_response.set()


async def main():
    print(f"[{ts()}] Scanning for '{DEVICE_NAME}' (15s)...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15.0)
    if device is None:
        print("Device not found.")
        return

    async with BleakClient(device, winrt=dict(use_cached_services=False)) as client:
        print(f"[{ts()}] Connected: {client.is_connected}")
        await client.start_notify(FDF3_NOTIFY, handler)
        await asyncio.sleep(1)

        hits = []
        for b in range(256):
            got_response.clear()
            payload = bytes([b])
            try:
                await client.write_gatt_char(FDF3_WRITE, payload, response=True)
            except Exception as e:
                print(f"[{ts()}] 0x{b:02X} write REJECTED: {type(e).__name__}: {e}")
                continue

            try:
                await asyncio.wait_for(got_response.wait(), timeout=0.4)
                print(f"[{ts()}] 0x{b:02X} -> RESPONSE: {last_response.hex(' ')}")
                hits.append((b, last_response.hex(' ')))
            except asyncio.TimeoutError:
                pass  # no response, move on

            if b % 32 == 0:
                print(f"[{ts()}]   ...tried up to 0x{b:02X}")

        print(f"\n[{ts()}] Done. {len(hits)} byte value(s) got a response: {hits}")


asyncio.run(main())
