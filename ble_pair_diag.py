import asyncio
from datetime import datetime
from bleak import BleakScanner
from winrt.windows.devices.bluetooth import BluetoothLEDevice
from winrt.windows.devices.enumeration import DevicePairingKinds

DEVICE_NAME = "Darefore HR2"


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


async def main():
    print(f"[{ts()}] Scanning for '{DEVICE_NAME}' (15s)...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15.0)
    if device is None:
        print("Device not found.")
        return

    addr_int = int(device.address.replace(":", "").replace("-", ""), 16)
    print(f"[{ts()}] Address: {device.address} ({addr_int})")

    ble_device = await BluetoothLEDevice.from_bluetooth_address_async(addr_int)
    if ble_device is None:
        print("Could not get BluetoothLEDevice from address.")
        return

    info = ble_device.device_information
    pairing = info.pairing
    print(f"[{ts()}] IsPaired: {pairing.is_paired}")
    print(f"[{ts()}] CanPair: {pairing.can_pair}")
    print(f"[{ts()}] ProtectionLevel: {pairing.protection_level}")

    custom = pairing.custom
    print(f"[{ts()}] Requesting pairing (ConfirmOnly ceremony)...")
    result = await custom.pair_async(DevicePairingKinds.CONFIRM_ONLY)
    print(f"[{ts()}] Pairing status: {result.status}")


asyncio.run(main())
