import csv
import struct
import math
import statistics

rows = []
with open("f0f0_capture_vo3.csv") as f:
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

print(f"{len(decoded)} readings over {decoded[-1][0]-decoded[0][0]:.1f}s\n")

# figure out which axis is "vertical" using the standing-still baseline (t<3)
baseline = [(ax, ay, az) for t, ax, ay, az in decoded if t < 3]
mean_ax = statistics.mean(v[0] for v in baseline)
mean_ay = statistics.mean(v[1] for v in baseline)
mean_az = statistics.mean(v[2] for v in baseline)
print(f"baseline means: ax={mean_ax:.2f} ay={mean_ay:.2f} az={mean_az:.2f}")

axes = {'ax': mean_ax, 'ay': mean_ay, 'az': mean_az}
vertical_axis = max(axes, key=lambda k: abs(axes[k]))
gravity_value = axes[vertical_axis]
print(f"using '{vertical_axis}' as vertical axis (baseline value {gravity_value:.2f})\n")

axis_index = {'ax': 1, 'ay': 2, 'az': 3}[vertical_axis]

# stance detection (same as GCT) using magnitude, to get per-stride reset points
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

print(f"{len(stance_starts)} stride starts detected: {[round(s,2) for s in stance_starts[:10]]}...\n")

# double-integrate vertical accel between consecutive stance starts (reset each time)
vo_values = []
for i in range(len(stance_starts) - 1):
    t_start = stance_starts[i]
    t_end = stance_starts[i + 1]
    raw_segment = [(t, [ax, ay, az][axis_index-1]) for t, ax, ay, az in decoded if t_start <= t < t_end]
    if len(raw_segment) < 3:
        continue
    # detrend: remove this stride's own mean, forcing it to be exactly zero-mean
    # (a fixed global gravity value leaves a small residual bias that, after
    # double integration, blows up into a large fake displacement)
    seg_mean = statistics.mean(a for t, a in raw_segment)
    segment = [(t, a - seg_mean) for t, a in raw_segment]
    velocity = 0.0
    position = 0.0
    positions = [0.0]
    prev_t, prev_a = segment[0]
    for t, a in segment[1:]:
        dt = t - prev_t
        velocity += a * dt
        position += velocity * dt
        positions.append(position)
        prev_t, prev_a = t, a
    vo_cm = (max(positions) - min(positions)) * 100  # meters -> cm
    vo_values.append(vo_cm)

if vo_values:
    print(f"{len(vo_values)} stride VO estimates:")
    print([round(v, 1) for v in vo_values])
    print(f"\nmean={statistics.mean(vo_values):.1f}cm  median={statistics.median(vo_values):.1f}cm  "
          f"min={min(vo_values):.1f}  max={max(vo_values):.1f}")
else:
    print("No VO values computed.")
