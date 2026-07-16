import re

readings = []
with open("ocr_output_v2.txt") as f:
    for line in f:
        m = re.search(r'"([0-9A-F]+)"', line)
        if m and len(m.group(1)) == 40:
            readings.append(bytes.fromhex(m.group(1)))

n = len(readings)
raw = [r[9] for r in readings]


def smooth(vals, window):
    csum = [0]
    for v in vals:
        csum.append(csum[-1] + v)
    out = []
    for i in range(len(vals)):
        lo = max(0, i - window // 2)
        hi = min(len(vals), i + window // 2 + 1)
        out.append((csum[hi] - csum[lo]) / (hi - lo))
    return out


def find_peak_indices(vals, min_prominence):
    peaks = []
    for i in range(1, len(vals) - 1):
        if vals[i] > vals[i - 1] and vals[i] >= vals[i + 1]:
            lo = max(0, i - 20)
            hi = min(len(vals), i + 21)
            local_min = min(vals[lo:hi])
            if vals[i] - local_min >= min_prominence:
                peaks.append(i)
    return peaks


prom = (max(raw) - min(raw)) * 0.15

print("window  peaks")
for w in [90, 100, 110, 120, 130, 140, 150, 160]:
    sm = smooth(raw, w)
    p = find_peak_indices(sm, prom)
    print(f"{w:4d}    {len(p)}")

# use window=120 and show where the peaks fall (as fraction of total sequence)
sm = smooth(raw, 120)
peaks = find_peak_indices(sm, prom)
print(f"\nAt window=120: {len(peaks)} peaks total, {n} readings total")
print("Peak positions as % through the sequence:")
pct = [round(100 * p / n, 1) for p in peaks]
print(pct)

# expected phase boundaries based on reported timing: 20s upright, 15s leaning, 5s upright (40s total activity)
b1 = 20 / 40 * 100
b2 = (20 + 15) / 40 * 100
print(f"\nExpected phase boundaries (if readings ~uniform over 40s activity): 0-{b1:.0f}% upright(35 steps), {b1:.0f}-{b2:.0f}% leaning(25 steps), {b2:.0f}-100% upright(10 steps)")

phase1 = sum(1 for p in pct if p < b1)
phase2 = sum(1 for p in pct if b1 <= p < b2)
phase3 = sum(1 for p in pct if p >= b2)
print(f"Peaks in phase1: {phase1} (expected ~35)")
print(f"Peaks in phase2: {phase2} (expected ~25)")
print(f"Peaks in phase3: {phase3} (expected ~10)")
