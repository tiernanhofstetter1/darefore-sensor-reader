import csv

rows = []
with open("f0f0_capture.csv") as f:
    reader = csv.reader(f)
    next(reader)
    for t, hexstr in reader:
        b = bytes.fromhex(hexstr)
        rows.append((float(t), b))

print(f"{len(rows)} total readings over {rows[-1][0]:.1f}s ({len(rows)/rows[-1][0]:.1f}/sec average)\n")

# check reference byte distribution
from collections import Counter
ref_counts = Counter(b[1] for t, b in rows if len(b) > 1)
print("Reference byte (byte 1) distribution:", ref_counts)

fast = [(t, b) for t, b in rows if len(b) > 9 and b[1] != 0x02]
print(f"\n{len(fast)} 'fast stream' readings (byte1 != 0x02)")
if fast:
    span = fast[-1][0] - fast[0][0]
    print(f"Fast stream spans {span:.2f}s -> {len(fast)/span:.1f}/sec average rate\n")

times = [t for t, b in fast]
vals = [b[9] for t, b in fast]

print("byte9 sample values (first 30):", vals[:30])
print(f"byte9 overall min={min(vals)} max={max(vals)}\n")


def smooth_by_time(times, vals, window_s):
    out = []
    n = len(times)
    lo = 0
    for i in range(n):
        while times[lo] < times[i] - window_s / 2:
            lo += 1
        hi = lo
        while hi < n and times[hi] <= times[i] + window_s / 2:
            hi += 1
        out.append(sum(vals[lo:hi]) / (hi - lo))
    return out


def count_peaks(vals, min_prominence):
    peaks = 0
    idxs = []
    for i in range(1, len(vals) - 1):
        if vals[i] > vals[i - 1] and vals[i] >= vals[i + 1]:
            lo = max(0, i - 20)
            hi = min(len(vals), i + 21)
            local_min = min(vals[lo:hi])
            if vals[i] - local_min >= min_prominence:
                peaks += 1
                idxs.append(i)
    return peaks, idxs


prom = (max(vals) - min(vals)) * 0.15
print(f"prominence threshold: {prom:.1f}\n")
print("window(s)  peaks  implied_steps/min")
for w in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0]:
    sm = smooth_by_time(times, vals, w)
    peaks, idxs = count_peaks(sm, prom)
    span = times[-1] - times[0]
    per_min = peaks / span * 60 if span > 0 else 0
    print(f"{w:6.1f}    {peaks:4d}   {per_min:6.1f}")
