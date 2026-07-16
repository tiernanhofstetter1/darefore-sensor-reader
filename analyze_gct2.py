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
    mag = math.sqrt(ax*ax + ay*ay + az*az)
    decoded.append((t, mag))

THRESHOLD = 8.0
MIN_STANCE_MS = 80   # ignore blips shorter than this (noise, not a real stance)
MAX_STANCE_MS = 500  # real GCT is never this long -- flag as a bad detection, don't average it in

def find_stances(data):
    stances = []
    rejected = 0
    in_stance = False
    start = None
    for t, mag in data:
        above = mag > THRESHOLD
        if above and not in_stance:
            in_stance = True
            start = t
        elif not above and in_stance:
            in_stance = False
            duration_ms = (t - start) * 1000
            if duration_ms < MIN_STANCE_MS:
                continue
            if duration_ms > MAX_STANCE_MS:
                rejected += 1
                continue
            stances.append((start, t, duration_ms))
    return stances, rejected

PHASES = [("baseline", 0, 3), ("slow_jog", 3, 15), ("pause", 15, 18), ("fast_step", 18, 30)]

for name, lo, hi in PHASES:
    segment = [(t, m) for t, m in decoded if lo <= t < hi]
    if not segment:
        continue
    stances, rejected = find_stances(segment)
    reject_note = f"  ({rejected} rejected as implausible)" if rejected else ""
    if stances:
        durations = [d for _, _, d in stances]
        print(f"{name:10s} ({lo}-{hi}s): {len(stances)} stances, "
              f"mean GCT={statistics.mean(durations):6.1f}ms  "
              f"median={statistics.median(durations):6.1f}ms  "
              f"min={min(durations):6.1f}  max={max(durations):6.1f}{reject_note}")
    else:
        print(f"{name:10s} ({lo}-{hi}s): no stances detected{reject_note}")
