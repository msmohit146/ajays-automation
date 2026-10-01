import os
import re
import shutil
import subprocess

from PIL import Image, ImageOps


def find_tesseract():
    configured_path = os.environ.get("TESSERACT_CMD")
    if configured_path:
        return configured_path

    discovered_path = shutil.which("tesseract")
    if discovered_path:
        return discovered_path

    windows_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    return windows_path if os.path.isfile(windows_path) else None


def detect_rotation(image_path, tesseract_exe=None):
    """Return the clockwise correction angle reported by Tesseract OSD."""
    executable = tesseract_exe or find_tesseract()
    if not executable:
        return 0

    try:
        result = subprocess.run(
            [executable, image_path, "stdout", "--psm", "0"],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0

    output = result.stdout.decode("utf-8", errors="replace")
    output += result.stderr.decode("utf-8", errors="replace")
    rotation = re.search(r"^Rotate:\s*(\d+)", output, re.MULTILINE)
    confidence = re.search(r"^Orientation confidence:\s*([\d.]+)", output, re.MULTILINE)
    if not rotation or (confidence and float(confidence.group(1)) < 5):
        return 0
    return int(rotation.group(1)) % 360


def load_oriented_image(image_path, tesseract_exe=None):
    """Load a scan with EXIF and page orientation corrected, without changing the source."""
    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")

    rotation = detect_rotation(image_path, tesseract_exe)
    if rotation:
        image = image.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
    return image