import asyncio
from datetime import datetime

from bleak import BleakScanner
from winrt.windows.devices.bluetooth import BluetoothLEDevice, BluetoothCacheMode
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattReliableWriteTransaction,
    GattClientCharacteristicConfigurationDescriptorValue,
    GattCommunicationStatus,
)
from winrt.windows.storage.streams import DataWriter

DEVICE_NAME = "Darefore HR2"
FDF3_SERVICE = "0000fdf3-0000-1000-8000-00805f9b34fb"
FDF3_NOTIFY = "6b200002-ff4e-4979-8186-fb7ba486fcd7"
FDF3_WRITE = "6b200001-ff4e-4979-8186-fb7ba486fcd7"


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def make_buffer(data: bytes):
    writer = DataWriter()
    writer.write_bytes(bytes(data))
    return writer.detach_buffer()


def on_value_changed(sender, args):
    reader_bytes = bytes(args.characteristic_value)
    print(f"[{ts()}]   <-- NOTIFY: {reader_bytes.hex(' ')}")


async def main():
    print(f"[{ts()}] Scanning for '{DEVICE_NAME}' (15s)...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15.0)
    if device is None:
        print("Device not found.")
        return

    addr_int = int(device.address.replace(":", "").replace("-", ""), 16)
    ble_device = await BluetoothLEDevice.from_bluetooth_address_async(addr_int)
    if ble_device is None:
        print("Could not get BluetoothLEDevice.")
        return

    print(f"[{ts()}] Got BluetoothLEDevice, discovering services (uncached)...")
    services_result = await ble_device.get_gatt_services_for_uuid_with_cache_mode_async(
        __import__("uuid").UUID(FDF3_SERVICE), BluetoothCacheMode.UNCACHED
    )
    if services_result.status != GattCommunicationStatus.SUCCESS or len(services_result.services) == 0:
        print(f"Could not get FDF3 service: {services_result.status}")
        return
    service = services_result.services[0]

    chars_result = await service.get_characteristics_async()
    notify_char = None
    write_char = None
    for c in chars_result.characteristics:
        if str(c.uuid) == FDF3_NOTIFY:
            notify_char = c
        elif str(c.uuid) == FDF3_WRITE:
            write_char = c

    if notify_char is None or write_char is None:
        print("Could not find both characteristics.")
        return

    print(f"[{ts()}] Subscribing to notify...")
    notify_char.add_value_changed(on_value_changed)
    cccd_status = await notify_char.write_client_characteristic_configuration_descriptor_async(
        GattClientCharacteristicConfigurationDescriptorValue.NOTIFY
    )
    print(f"[{ts()}] CCCD write status: {cccd_status}")

    await asyncio.sleep(2)

    # --- Try the formal Reliable Write transaction ---
    for payload in [bytes([0x01]), bytes([0x00, 0x01]), b"start"]:
        print(f"\n[{ts()}] Queuing RELIABLE WRITE of {payload.hex(' ')!r}...")
        transaction = GattReliableWriteTransaction()
        transaction.write_value(write_char, make_buffer(payload))
        try:
            result = await transaction.commit_async()
            print(f"[{ts()}] Reliable write commit status: {result}")
        except Exception as e:
            print(f"[{ts()}] Reliable write FAILED: {type(e).__name__}: {e}")
        await asyncio.sleep(2)

    print(f"\n[{ts()}] Listening a bit more...")
    await asyncio.sleep(5)
    print(f"[{ts()}] Done.")


asyncio.run(main())
