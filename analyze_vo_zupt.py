import csv
import struct
import math
import statistics
import sys

INPUT_FILE = sys.argv[1]
GROUND_TRUTH_CM = float(sys.argv[2])

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

baseline = [(ax, ay, az) for t, ax, ay, az in decoded if t < 3]
mean_ax = statistics.mean(v[0] for v in baseline)
mean_ay = statistics.mean(v[1] for v in baseline)
mean_az = statistics.mean(v[2] for v in baseline)
axes = {'ax': mean_ax, 'ay': mean_ay, 'az': mean_az}
vertical_axis = max(axes, key=lambda k: abs(axes[k]))
gravity_value = axes[vertical_axis]
axis_index = {'ax': 1, 'ay': 2, 'az': 3}[vertical_axis]

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

vo_values = []
for i in range(len(stance_starts) - 1):
    t_start = stance_starts[i]
    t_end = stance_starts[i + 1]
    segment = [(t, [ax, ay, az][axis_index-1] - gravity_value) for t, ax, ay, az in decoded if t_start <= t < t_end]
    if len(segment) < 4:
        continue

    # integrate velocity with NO reset across the whole stride
    velocity = 0.0
    velocities = [0.0]
    prev_t, _ = segment[0]
    for t, a in segment[1:]:
        dt = t - prev_t
        velocity += a * dt
        velocities.append(velocity)
        prev_t = t

    # zero-velocity update: we know velocity should be ~0 at the end too, so
    # subtract a linearly-growing correction across the stride to enforce that,
    # instead of letting all the drift sit uncorrected until the next reset
    n = len(velocities)
    end_error = velocities[-1]
    corrected_velocities = [v - (end_error * i / (n - 1)) for i, v in enumerate(velocities)]

    # integrate corrected velocity to get position
    position = 0.0
    positions = [0.0]
    prev_t = segment[0][0]
    for i in range(1, n):
        t = segment[i][0]
        dt = t - prev_t
        position += corrected_velocities[i] * dt
        positions.append(position)
        prev_t = t

    vo_cm = (max(positions) - min(positions)) * 100
    vo_values.append(vo_cm)

if vo_values:
    print(f"{INPUT_FILE}: {len(vo_values)} strides, ground truth={GROUND_TRUTH_CM}cm")
    mean_vo = statistics.mean(vo_values)
    median_vo = statistics.median(vo_values)
    print(f"mean={mean_vo:.1f}cm  median={median_vo:.1f}cm  "
          f"ratio(mean)={mean_vo/GROUND_TRUTH_CM:.2f}x  ratio(median)={median_vo/GROUND_TRUTH_CM:.2f}x")
else:
    print("No VO values computed.")
