import csv
import struct
import math
import statistics

rows = []
with open("f0f0_capture_gct.csv") as f:
    reader = csv.reader(f)
    next(reader)
    for t, hexstr in reader:
        b = bytes.fromhex(hexstr)
        rows.append((float(t), b))

fast = [(t, b) for t, b in rows if len(b) >= 18 and b[1] != 0x02]
decoded = []
for t, b in fast:
    ax = struct.unpack_from('<f', b, 6)[0]
    ay = struct.unpack_from('<f', b, 10)[0]
    az = struct.unpack_from('<f', b, 14)[0]
    decoded.append((t, ax, ay, az))

# stance detection (same as GCT) for stride boundaries
THRESHOLD = 8.0
stance_starts = []
in_stance = False
for t, ax, ay, az in decoded:
    mag = math.sqrt(ax*ax + ay*ay + az*az)
    above = mag > THRESHOLD
    if above and not in_stance:
        in_stance = True
        stance_starts.append(t)
    elif not above and in_stance:
        in_stance = False

# for each stride, find the peak (signed, not magnitude) ax and az during that stride
print("stride#  peak_ax   peak_az   (during slow_jog phase 3-15s)")
for i, t_start in enumerate(stance_starts):
    if not (3 <= t_start < 15):
        continue
    t_end = stance_starts[i+1] if i+1 < len(stance_starts) else t_start + 0.5
    segment = [(ax, az) for t, ax, ay, az in decoded if t_start <= t < t_end]
    if not segment:
        continue
    # peak = value with largest absolute magnitude, keeping its sign
    peak_ax = max(segment, key=lambda s: abs(s[0]))[0]
    peak_az = max(segment, key=lambda s: abs(s[1]))[1]
    print(f"{i:6d}   {peak_ax:7.2f}   {peak_az:7.2f}")
