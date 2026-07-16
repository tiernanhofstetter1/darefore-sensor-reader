import csv
import statistics

rows = []
with open("f0f0_capture_tilt.csv") as f:
    reader = csv.reader(f)
    next(reader)
    for t, hexstr in reader:
        b = bytes.fromhex(hexstr)
        rows.append((float(t), b))

fast = [(t, b) for t, b in rows if len(b) > 17 and b[1] != 0x02]
print(f"{len(fast)} fast-stream readings over {fast[-1][0]-fast[0][0]:.1f}s\n")

PHASES = [("level_1", 0, 6), ("tilt_45", 6, 12), ("tilt_90", 12, 18), ("level_2", 18, 24)]
num_bytes = len(fast[0][1])

candidates = []
for idx in range(num_bytes):
    phase_means = []
    phase_stds = []
    for name, lo, hi in PHASES:
        vals = [b[idx] for t, b in fast if lo <= t < hi]
        if not vals:
            phase_means.append(None)
            phase_stds.append(None)
            continue
        phase_means.append(statistics.mean(vals))
        phase_stds.append(statistics.pstdev(vals))

    valid_means = [m for m in phase_means if m is not None]
    if len(valid_means) < 4:
        continue
    overall_range = max(valid_means) - min(valid_means)
    avg_std = statistics.mean(s for s in phase_stds if s is not None)
    if overall_range > 5 and avg_std < overall_range * 0.35:
        candidates.append((idx, overall_range, avg_std, phase_means))

candidates.sort(key=lambda c: -c[1] / (c[2] + 1))

print("Best candidates (byte index, stable plateaus per phase):\n")
for idx, rng, std, means in candidates[:10]:
    means_str = "  ".join(f"{name}={m:6.1f}" if m is not None else f"{name}=  N/A" for (name, _, _), m in zip(PHASES, means))
    print(f"byte {idx:02d}  range={rng:6.1f}  avg_std={std:5.1f}   {means_str}")

print("\n--- ALL bytes, unfiltered ---")
for idx in range(num_bytes):
    phase_means = []
    for name, lo, hi in PHASES:
        vals = [b[idx] for t, b in fast if lo <= t < hi]
        phase_means.append(statistics.mean(vals) if vals else None)
    means_str = "  ".join(f"{m:6.1f}" if m is not None else "   N/A" for m in phase_means)
    print(f"byte {idx:02d}: {means_str}")

print("\n--- 16-bit LE pairs ---")
pair_candidates = []
for idx in range(num_bytes - 1):
    phase_means = []
    phase_stds = []
    for name, lo, hi in PHASES:
        vals = [b[idx] | (b[idx+1] << 8) for t, b in fast if lo <= t < hi]
        if not vals:
            phase_means.append(None)
            phase_stds.append(None)
            continue
        phase_means.append(statistics.mean(vals))
        phase_stds.append(statistics.pstdev(vals))
    valid_means = [m for m in phase_means if m is not None]
    if len(valid_means) < 4:
        continue
    overall_range = max(valid_means) - min(valid_means)
    avg_std = statistics.mean(s for s in phase_stds if s is not None)
    if overall_range > 20 and avg_std < overall_range * 0.35:
        pair_candidates.append((idx, overall_range, avg_std, phase_means))

pair_candidates.sort(key=lambda c: -c[1] / (c[2] + 1))
for idx, rng, std, means in pair_candidates[:10]:
    means_str = "  ".join(f"{name}={m:7.1f}" if m is not None else f"{name}=  N/A" for (name, _, _), m in zip(PHASES, means))
    print(f"bytes {idx:02d}-{idx+1:02d}  range={rng:7.1f}  avg_std={std:6.1f}   {means_str}")
