import csv
import struct
import math
import statistics

import sys
INPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "f0f0_capture_speed.csv"

rows = []
with open(INPUT_FILE) as f:
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

GROUND_TRUTH_LENGTHS = float(sys.argv[2]) if len(sys.argv) > 2 else 3.75
GROUND_TRUTH_DISTANCE_M = GROUND_TRUTH_LENGTHS * 20 * 0.3048
GROUND_TRUTH_TIME_S = 22.0
GROUND_TRUTH_SPEED = GROUND_TRUTH_DISTANCE_M / GROUND_TRUTH_TIME_S
print(f"Ground truth: {GROUND_TRUTH_DISTANCE_M:.2f}m over {GROUND_TRUTH_TIME_S}s = {GROUND_TRUTH_SPEED:.3f} m/s\n")

baseline = [(ax, ay, az) for t, ax, ay, az in decoded if t < 3]
mean_ax = statistics.mean(v[0] for v in baseline)
mean_ay = statistics.mean(v[1] for v in baseline)
mean_az = statistics.mean(v[2] for v in baseline)
axes = {'ax': mean_ax, 'ay': mean_ay, 'az': mean_az}
vertical_axis = max(axes, key=lambda k: abs(axes[k]))
print(f"vertical axis: {vertical_axis} (baseline {axes[vertical_axis]:.2f})")

horizontal_axes = [k for k in ['ax', 'ay', 'az'] if k != vertical_axis]
print(f"horizontal axes: {horizontal_axes}\n")
idx = {'ax': 1, 'ay': 2, 'az': 3}

# stance detection (same as GCT/VO) for reset points
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

walking_starts = [s for s in stance_starts if 3 <= s < 25]
print(f"{len(walking_starts)} strides detected during walking phase\n")

# single-integrate horizontal-plane acceleration magnitude, per stride, reset each time
speed_estimates = []
for i in range(len(walking_starts) - 1):
    t_start = walking_starts[i]
    t_end = walking_starts[i + 1]
    segment = [(t, [ax, ay, az][idx[horizontal_axes[0]]-1], [ax, ay, az][idx[horizontal_axes[1]]-1])
               for t, ax, ay, az in decoded if t_start <= t < t_end]
    if len(segment) < 3:
        continue
    h1_mean = statistics.mean(s[1] for s in segment)
    h2_mean = statistics.mean(s[2] for s in segment)
    velocities = []
    v1 = v2 = 0.0
    prev_t = segment[0][0]
    for t, h1, h2 in segment[1:]:
        dt = t - prev_t
        v1 += (h1 - h1_mean) * dt
        v2 += (h2 - h2_mean) * dt
        velocities.append(math.sqrt(v1*v1 + v2*v2))
        prev_t = t
    if velocities:
        speed_estimates.append(max(velocities))

if speed_estimates:
    print(f"{len(speed_estimates)} per-stride speed estimates (m/s):")
    print([round(v, 2) for v in speed_estimates])
    print(f"\nmean={statistics.mean(speed_estimates):.2f} m/s  median={statistics.median(speed_estimates):.2f} m/s")
    print(f"Ground truth was: {GROUND_TRUTH_SPEED:.2f} m/s")
else:
    print("No speed estimates computed.")
