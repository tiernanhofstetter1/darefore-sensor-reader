import asyncio
import os
from PIL import Image, ImageDraw
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.storage import StorageFile, FileAccessMode


async def ocr_image(path):
    file = await StorageFile.get_file_from_path_async(path)
    stream = await file.open_async(FileAccessMode.READ)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    engine = OcrEngine.try_create_from_user_profile_languages()
    result = await engine.recognize_async(bitmap)
    return result.text


async def main():
    from PIL import ImageFont
    img_path = os.path.abspath("ocr_test.png")
    img = Image.new("RGB", (1200, 220), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("consola.ttf", 34)
        print("loaded consola.ttf")
    except Exception as e:
        print("fallback font, reason:", e)
        font = ImageFont.load_default(size=34)
    d.text((20, 20), "16:21:16.393", fill="black", font=font)
    d.text((20, 70), "0x0302880557010000FE00B7E70100347B320401", fill="black", font=font)
    img.save(img_path)

    text = await ocr_image(img_path)
    print("OCR RESULT:", repr(text))
    print("Saved test image to:", img_path)


asyncio.run(main())
