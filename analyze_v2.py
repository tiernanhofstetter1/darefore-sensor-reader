import re

readings = []
with open("ocr_output_v2.txt") as f:
    for line in f:
        m = re.search(r'"([0-9A-F]+)"', line)
        if m and len(m.group(1)) == 40:
            readings.append(bytes.fromhex(m.group(1)))

n = len(readings)
num_bytes = 20
print(f"{n} clean readings, {num_bytes} bytes each\n")

# also 2-byte little-endian combos for the columns that look like paired fields
def count_peaks(vals, min_prominence=3):
    peaks = 0
    for i in range(1, len(vals) - 1):
        if vals[i] > vals[i - 1] and vals[i] >= vals[i + 1]:
            # check prominence against local window
            lo = max(0, i - 5)
            hi = min(len(vals), i + 6)
            local_min = min(vals[lo:hi])
            if vals[i] - local_min >= min_prominence:
                peaks += 1
    return peaks

for b in range(num_bytes):
    vals = [r[b] for r in readings]
    if max(vals) == min(vals):
        continue
    peaks = count_peaks(vals)
    print(f"byte {b:02d}: min={min(vals):3d} max={max(vals):3d} range={max(vals)-min(vals):3d}  peaks={peaks}")

print("\n--- 16-bit little-endian pairs (bytes i,i+1) ---")
for b in range(num_bytes - 1):
    vals = [r[b] | (r[b+1] << 8) for r in readings]
    if max(vals) == min(vals):
        continue
    peaks = count_peaks(vals, min_prominence=50)
    print(f"bytes {b:02d}-{b+1:02d}: min={min(vals):6d} max={max(vals):6d} range={max(vals)-min(vals):6d}  peaks={peaks}")


def smooth(vals, window):
    out = []
    for i in range(len(vals)):
        lo = max(0, i - window // 2)
        hi = min(len(vals), i + window // 2 + 1)
        out.append(sum(vals[lo:hi]) / (hi - lo))
    return out


print("\n--- smoothed (window=15) peak counts, all byte positions ---")
for b in range(num_bytes):
    raw = [r[b] for r in readings]
    if max(raw) == min(raw):
        continue
    sm = smooth(raw, 15)
    peaks = count_peaks(sm, min_prominence=2)
    print(f"byte {b:02d}: smoothed peaks={peaks}")

print("\n--- smoothed (window=15) peak counts, 16-bit LE pairs ---")
for b in range(num_bytes - 1):
    raw = [r[b] | (r[b + 1] << 8) for r in readings]
    if max(raw) == min(raw):
        continue
    sm = smooth(raw, 15)
    peaks = count_peaks(sm, min_prominence=20)
    print(f"bytes {b:02d}-{b+1:02d}: smoothed peaks={peaks}")
