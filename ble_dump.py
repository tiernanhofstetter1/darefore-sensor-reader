import asyncio
from datetime import datetime
from bleak import BleakScanner, BleakClient

DEVICE_NAME = "Darefore HR2"


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


async def main():
    print(f"[{ts()}] Scanning for '{DEVICE_NAME}' (15s)...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15.0)
    if device is None:
        print("Device not found.")
        return

    async with BleakClient(
        device,
        winrt=dict(use_cached_services=False),
    ) as client:
        print(f"[{ts()}] Connected: {client.is_connected}")
        try:
            paired = await client.pair()
            print(f"[{ts()}] Pair result: {paired}")
        except Exception as e:
            print(f"[{ts()}] Pair failed: {e}")
        await asyncio.sleep(20)  # give Windows plenty of time to finish GATT discovery

        services = client.services
        if services is None or len(list(services)) == 0:
            print("No services resolved.")
            return

        for service in services:
            print(f"\nService {service.uuid}  ({service.description})")
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(f"  Characteristic {char.uuid}  props=[{props}]  handle={char.handle}")


asyncio.run(main())
