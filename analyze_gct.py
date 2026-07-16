import csv
import struct
import math

rows = []
with open("f0f0_capture_gct.csv") as f:
    reader = csv.reader(f)
    next(reader)
    for t, hexstr in reader:
        b = bytes.fromhex(hexstr)
        rows.append((float(t), b))

fast = [(t, b) for t, b in rows if len(b) >= 18 and b[1] != 0x02]
print(f"{len(fast)} readings over {fast[-1][0]-fast[0][0]:.1f}s\n")

decoded = []
for t, b in fast:
    ax = struct.unpack_from('<f', b, 6)[0]
    ay = struct.unpack_from('<f', b, 10)[0]
    az = struct.unpack_from('<f', b, 14)[0]
    mag = math.sqrt(ax*ax + ay*ay + az*az)
    decoded.append((t, ax, ay, az, mag))

# print a dense slice during the slow-jog phase to see the waveform shape
print("--- magnitude during slow jog phase (t=6 to t=9) ---")
for t, ax, ay, az, mag in decoded:
    if 6.0 <= t <= 9.0:
        print(f"t={t:6.3f}  mag={mag:6.2f}  ax={ax:7.2f} ay={ay:7.2f} az={az:7.2f}")
