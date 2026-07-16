"""
Paste readings from the 0xF0F0 notify channel below (timestamp, hex string),
oldest or newest first -- order doesn't matter, this sorts them.

Format: one entry per line/tuple: ("HH:MM:SS.mmm", "hex string without 0x")
"""

SAMPLES = [
    ("15:53:56.245", "03028B0629013700" "1C01A5FE5300337FBF" "0301"),
    ("15:53:54.745", "0302E606290136001E01B8FE4300327FBF0301"),
    ("15:53:54.145", "0302E6062901340020016CFE4300317FBD0301"),
    ("15:53:52.766", "030200000F010000000015FF09003172A90301"),
    ("15:53:52.166", "0302000000000000000059FF09003270C00201"),
    ("15:54:00.775", "030240061D013C000501FBFE6400327FD50301"),
    ("15:54:00.238", "0302400618013B00060104FF6400317FD60301"),
    ("15:53:58.768", "0302300627013A000A01F4FE5500317FD30301"),
    ("15:53:58.255", "0302300624013A000F01D8FE5500347FCC0301"),
    ("15:53:56.755", "03028B06110139001601A5FE5300347FBF0301"),
    ("15:54:06.325", "0302600624013B0009018DFE5700337FCE0301"),
    ("15:54:04.766", "03025D0614013C000901D4FE6600337FCE0301"),
    ("15:54:04.315", "03025D0618013C0008010AFF6600337FC60301"),
    ("15:54:02.816", "0302550614013D000701EAFE6B00347FD50301"),
    ("15:54:02.246", "0302550618013C000601FFFE6B00317FD50301"),
]


def parse_ts(ts):
    h, m, rest = ts.split(":")
    s, ms = rest.split(".")
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def main():
    if not SAMPLES:
        print("Add samples to the SAMPLES list at the top of this file, then re-run.")
        return

    rows = []
    for ts, hexstr in SAMPLES:
        hexstr = hexstr.replace(" ", "").replace("0x", "")
        if len(hexstr) != 38:
            print(f"SKIPPING {ts}: expected 38 hex chars, got {len(hexstr)} -> {hexstr}")
            continue
        rows.append((parse_ts(ts), ts, bytes.fromhex(hexstr)))

    rows.sort(key=lambda r: r[0])

    n = len(rows)
    if n < 3:
        print("Need at least 3 valid samples to analyze.")
        return

    num_bytes = len(rows[0][2])

    print(f"{n} samples, {num_bytes} bytes each\n")
    header = "time".ljust(14) + " " + " ".join(f"{i:02d}" for i in range(num_bytes))
    print(header)
    for t0, ts, b in rows:
        print(ts.ljust(14), " ".join(f"{x:02X}" for x in b))

    print("\n--- per-byte analysis ---")
    for i in range(num_bytes):
        vals = [b[i] for (_, _, b) in rows]
        if len(set(vals)) == 1:
            continue  # constant, ignore

        # count sign changes around the mean (oscillation indicator)
        mean = sum(vals) / len(vals)
        signs = [1 if v > mean else -1 for v in vals]
        flips = sum(1 for a, b_ in zip(signs, signs[1:]) if a != b_)

        # estimate crossing rate in Hz using elapsed time
        elapsed_s = (rows[-1][0] - rows[0][0]) / 1000.0
        crossing_hz = (flips / 2) / elapsed_s if elapsed_s > 0 else 0
        est_per_min = crossing_hz * 60

        print(
            f"byte {i:02d}: min={min(vals):3d} max={max(vals):3d} "
            f"range={max(vals)-min(vals):3d} sign-flips={flips:2d} "
            f"-> if periodic: ~{est_per_min:.0f} cycles/min"
        )


if __name__ == "__main__":
    main()
