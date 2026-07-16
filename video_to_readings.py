"""
Usage: python video_to_readings.py <path_to_screen_recording.mp4>

Extracts frames from the video, OCRs each one using Windows' built-in OCR,
reconstructs the (possibly line-wrapped) hex readings in on-screen order,
deduplicates consecutive repeats, and prints a clean ordered list.

Timestamps shown in the app are NOT reliable via OCR (small gray text), so
we rely on frame order + on-screen top-to-bottom order (newest first) instead.
"""
import asyncio
import glob
import os
import re
import subprocess
import sys

from winrt.windows.media.ocr import OcrEngine
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.storage import StorageFile, FileAccessMode

FFMPEG = None
FRAMES_DIR = "frames_tmp"
FPS = 30

PREFIX_RE = re.compile(r"^(0x|0X|ox|oX|Ox|OX|ex|eX|Ex|EX)([0-9A-Za-z]{15,45})$")
CONTINUATION_RE = re.compile(r"^[0-9A-Za-z]{2,20}$")

CONFUSION_MAP = str.maketrans({
    "O": "0", "o": "0", "Q": "0",
    "I": "1", "l": "1", "i": "1",
    "S": "5", "s": "5",
    "Z": "2", "z": "2",
    "G": "6", "g": "6",
    "T": "7",
})


def clean_hex(s):
    s = s.upper().translate(CONFUSION_MAP)
    return s if re.fullmatch(r"[0-9A-F]+", s) else None


def find_ffmpeg():
    for candidate in glob.glob(
        os.path.expanduser("~") + r"\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\ffmpeg.exe"
    ):
        return candidate
    return "ffmpeg"


def extract_frames(video_path):
    os.makedirs(FRAMES_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(FRAMES_DIR, "*.png")):
        os.remove(f)
    cmd = [FFMPEG, "-i", video_path, "-vf", f"fps={FPS}", os.path.join(FRAMES_DIR, "frame_%05d.png")]
    subprocess.run(cmd, check=True, capture_output=True)
    return sorted(glob.glob(os.path.join(FRAMES_DIR, "*.png")))


async def ocr_lines(path, engine):
    file = await StorageFile.get_file_from_path_async(os.path.abspath(path))
    stream = await file.open_async(FileAccessMode.READ)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    result = await engine.recognize_async(bitmap)
    return [line.text.strip() for line in result.lines]


def extract_hex_readings(lines):
    """Return hex readings found in this frame, top-to-bottom (newest first)."""
    readings = []
    i = 0
    while i < len(lines):
        m = PREFIX_RE.match(lines[i])
        if not m:
            i += 1
            continue
        parts = [m.group(2)]
        j = i + 1
        while j < len(lines) and CONTINUATION_RE.match(lines[j]) and not PREFIX_RE.match(lines[j]):
            parts.append(lines[j])
            j += 1
        full = clean_hex("".join(parts))
        if full:
            readings.append(full)
        i = j if j > i + 1 else i + 1
    return readings


async def main():
    global FFMPEG
    if len(sys.argv) < 2:
        print("Usage: python video_to_readings.py <video_path>")
        return
    FFMPEG = find_ffmpeg()

    print(f"Extracting frames at {FPS}fps...")
    frames = extract_frames(sys.argv[1])
    print(f"{len(frames)} frames to OCR")

    engine = OcrEngine.try_create_from_user_profile_languages()

    ordered = []  # list of hex strings, in chronological order (oldest first)
    last_seen = None
    for i, frame in enumerate(frames):
        lines = await ocr_lines(frame, engine)
        readings = extract_hex_readings(lines)  # newest first, on screen
        # reverse to oldest-first within this frame, then append any that are new
        for hx in reversed(readings):
            if hx != last_seen:
                ordered.append(hx)
                last_seen = hx
        if i % 50 == 0:
            print(f"  ...{i}/{len(frames)} frames processed, {len(ordered)} readings so far")

    # collapse immediate repeats (same value appearing in consecutive frames)
    collapsed = []
    for hx in ordered:
        if not collapsed or collapsed[-1] != hx:
            collapsed.append(hx)

    print(f"\n{len(collapsed)} readings (frame-order, oldest first):\n")
    lengths = {}
    for hx in collapsed:
        lengths[len(hx)] = lengths.get(len(hx), 0) + 1
        print(f'    "{hx}",')

    print("\nLength distribution:", lengths)


asyncio.run(main())
