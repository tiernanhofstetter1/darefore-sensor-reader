import csv

rows = []
with open("f0f0_capture.csv") as f:
    reader = csv.reader(f)
    next(reader)
    for t, hexstr in reader:
        b = bytes.fromhex(hexstr)
        rows.append((float(t), b))

fast = [(t, b) for t, b in rows if len(b) > 9 and b[1] != 0x02]
times = [t for t, b in fast]
vals = [b[9] for t, b in fast]

lo, hi = min(vals), max(vals)
mid = (lo + hi) / 2
print(f"byte9 range: {lo}-{hi}, midpoint threshold: {mid:.1f}\n")


def count_rising_edges(times, vals, threshold, refractory_s):
    count = 0
    last_time = -999
    above = vals[0] > threshold
    for i in range(1, len(vals)):
        now_above = vals[i] > threshold
        if now_above and not above and (times[i] - last_time) >= refractory_s:
            count += 1
            last_time = times[i]
        above = now_above
    return count


span = times[-1] - times[0]
print("refractory(s)  crossings  implied_steps/min")
for refractory in [0.1, 0.15, 0.2, 0.25, 0.3, 0.4]:
    c = count_rising_edges(times, vals, mid, refractory)
    print(f"{refractory:6.2f}       {c:4d}       {c/span*60:6.1f}")

# also show the actual sequence of crossing timestamps at a reasonable refractory
print("\nCrossing timestamps at refractory=0.25s:")
count = 0
last_time = -999
above = vals[0] > mid
crossing_times = []
for i in range(1, len(vals)):
    now_above = vals[i] > mid
    if now_above and not above and (times[i] - last_time) >= 0.25:
        crossing_times.append(times[i])
        last_time = times[i]
    above = now_above
print([round(t, 2) for t in crossing_times])
print(f"\nIntervals between crossings: {[round(b - a, 2) for a, b in zip(crossing_times, crossing_times[1:])]}")
