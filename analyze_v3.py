import re

readings = []
with open("ocr_output_v2.txt") as f:
    for line in f:
        m = re.search(r'"([0-9A-F]+)"', line)
        if m and len(m.group(1)) == 40:
            readings.append(bytes.fromhex(m.group(1)))

n = len(readings)
num_bytes = 20
print(f"{n} clean readings, {num_bytes} bytes each")
print("Total steps performed: 70 (35 + 25 + 10) over ~40s of activity\n")


def smooth(vals, window):
    out = []
    csum = [0]
    for v in vals:
        csum.append(csum[-1] + v)
    for i in range(len(vals)):
        lo = max(0, i - window // 2)
        hi = min(len(vals), i + window // 2 + 1)
        out.append((csum[hi] - csum[lo]) / (hi - lo))
    return out


def count_peaks(vals, min_prominence):
    peaks = 0
    for i in range(1, len(vals) - 1):
        if vals[i] > vals[i - 1] and vals[i] >= vals[i + 1]:
            lo = max(0, i - 20)
            hi = min(len(vals), i + 21)
            local_min = min(vals[lo:hi])
            if vals[i] - local_min >= min_prominence:
                peaks += 1
    return peaks


windows = [15, 30, 50, 80, 120, 180, 250]

signals = {}
for b in range(num_bytes):
    raw = [r[b] for r in readings]
    if max(raw) != min(raw):
        signals[f"byte{b:02d}"] = (raw, (max(raw) - min(raw)) * 0.15)
for b in range(num_bytes - 1):
    raw = [r[b] | (r[b + 1] << 8) for r in readings]
    if max(raw) != min(raw):
        signals[f"pair{b:02d}-{b+1:02d}"] = (raw, (max(raw) - min(raw)) * 0.15)

header = "signal".ljust(10) + " ".join(f"w={w:<4d}" for w in windows)
print(header)
for name, (raw, prom) in signals.items():
    row = [name.ljust(10)]
    for w in windows:
        sm = smooth(raw, w)
        p = count_peaks(sm, prom)
        row.append(f"{p:<6d}")
    print(" ".join(row))
