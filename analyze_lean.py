import re
import sys
import statistics

fname = sys.argv[1] if len(sys.argv) > 1 else "ocr_lean_v1.txt"

readings = []
with open(fname) as f:
    for line in f:
        m = re.search(r'"([0-9A-F]+)"', line)
        if m and len(m.group(1)) == 40:
            readings.append(bytes.fromhex(m.group(1)))

n = len(readings)
num_bytes = 20
num_segments = 10
seg_len = n // num_segments

print(f"{n} readings, split into {num_segments} segments of ~{seg_len} readings each\n")

candidates = []
for b in range(num_bytes):
    seg_means = []
    seg_stds = []
    for s in range(num_segments):
        chunk = [r[b] for r in readings[s * seg_len:(s + 1) * seg_len]]
        seg_means.append(statistics.mean(chunk))
        seg_stds.append(statistics.pstdev(chunk))
    overall_range = max(seg_means) - min(seg_means)
    avg_std = statistics.mean(seg_stds)
    # a good "steady level" candidate: big swing between segment means, but low noise within each segment
    if overall_range > 5 and avg_std < overall_range * 0.5:
        candidates.append((b, overall_range, avg_std, seg_means))

candidates.sort(key=lambda c: -c[1] / (c[2] + 1))

print("Best candidates (big segment-to-segment shifts, low within-segment noise):\n")
for b, rng, std, means in candidates[:8]:
    means_str = " ".join(f"{m:6.1f}" for m in means)
    print(f"byte {b:02d}  range={rng:6.1f}  avg_std={std:5.1f}   segment means: {means_str}")

print("\n--- all bytes, for reference ---")
for b in range(num_bytes):
    seg_means = []
    for s in range(num_segments):
        chunk = [r[b] for r in readings[s * seg_len:(s + 1) * seg_len]]
        seg_means.append(statistics.mean(chunk))
    means_str = " ".join(f"{m:6.1f}" for m in seg_means)
    print(f"byte {b:02d}: {means_str}")
