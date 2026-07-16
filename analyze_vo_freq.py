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

print(f"{INPUT_FILE}: {len(decoded)} readings, ground truth={GROUND_TRUTH_CM}cm")

# vertical axis from standing baseline
baseline = [(ax, ay, az) for t, ax, ay, az in decoded if t < 3]
mean_ax = statistics.mean(v[0] for v in baseline)
mean_ay = statistics.mean(v[1] for v in baseline)
mean_az = statistics.mean(v[2] for v in baseline)
axes = {'ax': mean_ax, 'ay': mean_ay, 'az': mean_az}
vertical_axis = max(axes, key=lambda k: abs(axes[k]))
gravity_value = axes[vertical_axis]
idx = {'ax': 1, 'ay': 2, 'az': 3}[vertical_axis]
print(f"vertical axis: {vertical_axis}")

# stance detection for stride boundaries (also gives us stride frequency directly)
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

moving = [s for s in stance_starts if s >= 3]
if len(moving) < 2:
    print("Not enough strides detected.")
    sys.exit()

intervals = [b - a for a, b in zip(moving, moving[1:])]
mean_interval = statistics.mean(intervals)
frequency_hz = 1 / mean_interval
print(f"{len(moving)} strides, mean interval={mean_interval*1000:.0f}ms, frequency={frequency_hz:.2f}Hz")

# dynamic (gravity-removed) vertical acceleration, RMS amplitude during movement
dynamic = [[ax, ay, az][idx-1] - gravity_value for t, ax, ay, az in decoded if t >= 3]
rms = math.sqrt(sum(d*d for d in dynamic) / len(dynamic))
peak_amplitude = rms * math.sqrt(2)  # RMS -> peak, assuming roughly sinusoidal

omega = 2 * math.pi * frequency_hz
vo_m = peak_amplitude / (omega * omega)
vo_cm = vo_m * 100

print(f"RMS accel={rms:.2f} m/s^2, peak amplitude={peak_amplitude:.2f} m/s^2")
print(f"Computed VO: {vo_cm:.1f}cm  (ground truth: {GROUND_TRUTH_CM}cm, ratio={vo_cm/GROUND_TRUTH_CM:.2f}x)")
