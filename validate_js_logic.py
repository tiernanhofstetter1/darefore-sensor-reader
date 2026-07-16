import csv

CADENCE_BYTE_OFFSET = 9
MIN_ABSOLUTE_RANGE = 40
HYSTERESIS_FRACTION = 0.25
REFRACTORY_MS = 250
STALE_MS = 1500
CROSSING_WINDOW_MS = 8000
RANGE_WINDOW = 60
MIN_CROSSINGS_TO_REPORT = 3
MAX_INTERVAL_DEVIATION_FRACTION = 0.4
F0F0_DEFAULT_REFERENCE = 0x02


def run(filename):
    raw_buffer = []
    state = None
    last_crossing_ms = float("-inf")
    crossing_timestamps = []

    results = []
    with open(filename) as f:
        reader = csv.reader(f)
        next(reader)
        for t_s, hexstr in reader:
            now = float(t_s) * 1000.0
            b = bytes.fromhex(hexstr)
            if len(b) <= CADENCE_BYTE_OFFSET:
                continue
            if b[1] == F0F0_DEFAULT_REFERENCE:
                continue

            raw = b[CADENCE_BYTE_OFFSET]
            raw_buffer.append(raw)
            if len(raw_buffer) > RANGE_WINDOW:
                raw_buffer.pop(0)

            recent_min, recent_max = min(raw_buffer), max(raw_buffer)
            rng = recent_max - recent_min

            if rng >= MIN_ABSOLUTE_RANGE:
                mid = (recent_min + recent_max) / 2
                margin = rng * HYSTERESIS_FRACTION
                high_threshold = mid + margin
                low_threshold = mid - margin

                if state is None:
                    state = 'high' if raw > mid else 'low'
                elif state == 'low' and raw >= high_threshold:
                    if now - last_crossing_ms >= REFRACTORY_MS:
                        last_crossing_ms = now
                        crossing_timestamps.append(now)
                    state = 'high'
                elif state == 'high' and raw <= low_threshold:
                    state = 'low'

            crossing_timestamps = [t for t in crossing_timestamps if now - t <= CROSSING_WINDOW_MS]

            if now - last_crossing_ms > STALE_MS:
                crossing_timestamps = []
                results.append((now, 0))
                continue

            if len(crossing_timestamps) < MIN_CROSSINGS_TO_REPORT:
                results.append((now, None))
                continue

            recent = crossing_timestamps[-4:]
            if len(recent) >= 3:
                intervals = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
                mean_interval = sum(intervals) / len(intervals)
                max_dev = max(abs(iv - mean_interval) for iv in intervals)
                if max_dev > mean_interval * MAX_INTERVAL_DEVIATION_FRACTION:
                    results.append((now, 0))
                    continue

            span_ms = crossing_timestamps[-1] - crossing_timestamps[0]
            if span_ms <= 0:
                results.append((now, None))
                continue
            steps_per_ms = (len(crossing_timestamps) - 1) / span_ms
            cad = round(steps_per_ms * 60000)
            results.append((now, cad))

    return results


for fname in ["f0f0_capture_still.csv", "f0f0_capture_walk.csv", "f0f0_capture_walk2.csv"]:
    print(f"\n=== {fname} ===")
    results = run(fname)
    non_null = [c for t, c in results if c is not None]
    zero_count = sum(1 for c in non_null if c == 0)
    print(f"{len(results)} total, {len(non_null)} non-null, {zero_count} zeros")
    print("last 15 cadence values:", [c for t, c in results[-15:]])
    print("max cadence seen:", max(non_null) if non_null else None)
