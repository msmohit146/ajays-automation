import cv2
import numpy as np
import subprocess

# Load
img = cv2.imread("images/[SCANS]_ Ajay Srinivisan_ 14th August/1989-1996- Newest @top/1990/1990.jpg")
if img is None:
    print("Failed to load image")
    exit(1)

print(f"Original image shape: {img.shape}")

# Preprocess - aggressive for text extraction
img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
img_proc = cv2.convertScaleAbs(img_gray, alpha=2.0, beta=40)
img_proc = cv2.GaussianBlur(img_proc, (1,1), 0)

# Threshold
_, img_thresh = cv2.threshold(img_proc, 120, 255, cv2.THRESH_BINARY)

# Save preprocessed
import os
tmpdir = os.environ.get("TEMP", "C:\\temp")
os.makedirs(tmpdir, exist_ok=True)
preproc_path = os.path.join(tmpdir, "1990_preprocessed.jpg")
output_path = os.path.join(tmpdir, "1990_test_ocr")

cv2.imwrite(preproc_path, img_thresh)
print(f"Preprocessed image saved to {preproc_path}")

# Test with Tesseract
result = subprocess.run([
    "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    preproc_path,
    output_path,
    "-l", "eng",
    "--psm", "3"
], capture_output=True, text=True)

print(f"Tesseract exit code: {result.returncode}")
print(f"Stderr: {result.stderr[:500] if result.stderr else 'none'}")

# Check output
output_txt = output_path + ".txt"
try:
    with open(output_txt, "r") as f:
        text = f.read()
        print(f"OCR output length: {len(text)}")
        print(f"First 800 chars:\n{text[:800]}")
except Exception as e:
    print(f"No output file: {e}")
