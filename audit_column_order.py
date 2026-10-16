import argparse
import csv
import hashlib
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "archive.db"
IMAGE_DIR = BASE_DIR / "images"
TESSERACT_EXE = (
    os.environ.get("TESSERACT_CMD")
    or shutil.which("tesseract")
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


@dataclass
class TextLine:
    left: int
    top: int
    right: int
    bottom: int
    text: str

    @property
    def center_x(self):
        return (self.left + self.right) / 2

    @property
    def center_y(self):
        return (self.top + self.bottom) / 2

    @property
    def height(self):
        return max(1, self.bottom - self.top)


def image_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tesseract_lines(image_path, article_ids):
    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")

    with tempfile.TemporaryDirectory() as temp_dir:
        normalized_path = Path(temp_dir) / "scan.png"
        image.save(normalized_path)
        environment = os.environ.copy()
        environment["OMP_THREAD_LIMIT"] = "1"
        result = subprocess.run(
            [TESSERACT_EXE, str(normalized_path), "stdout", "-l", "eng", "--psm", "1", "tsv"],
            capture_output=True,
            check=True,
            timeout=120,
            env=environment,
        )

    rows = csv.DictReader(result.stdout.decode("utf-8", errors="replace").splitlines(), delimiter="\t")
    grouped = {}
    confidence = []
    for row in rows:
        if row.get("level") != "5" or not row.get("text", "").strip():
            continue
        key = (row["block_num"], row["par_num"], row["line_num"])
        left = int(row["left"])
        top = int(row["top"])
        right = left + int(row["width"])
        bottom = top + int(row["height"])
        confidence_value = float(row["conf"])
        if confidence_value >= 0:
            confidence.append(confidence_value)
        line = grouped.get(key)
        if line is None:
            grouped[key] = TextLine(left, top, right, bottom, row["text"].strip())
        else:
            line.left = min(line.left, left)
            line.top = min(line.top, top)
            line.right = max(line.right, right)
            line.bottom = max(line.bottom, bottom)
            line.text += " " + row["text"].strip()

    lines = list(grouped.values())
    if not lines:
        return {
            "article_ids": article_ids,
            "path": str(image_path.relative_to(BASE_DIR)),
            "width": image.width,
            "height": image.height,
            "line_count": 0,
            "column_count": 0,
            "side_switches": 0,
            "near_row_switches": 0,
            "mean_confidence": 0,
            "flag": "no_text",
        }

    x_centers = sorted(line.center_x for line in lines)
    candidate_gaps = [
        (x_centers[index + 1] - x_centers[index], index)
        for index in range(len(x_centers) - 1)
    ]
    largest_gap, gap_index = max(candidate_gaps, default=(0, 0))
    column_count = 1
    split_x = None
    if largest_gap >= max(image.width * 0.10, image.height * 0.025):
        possible_split = (x_centers[gap_index] + x_centers[gap_index + 1]) / 2
        left_count = sum(line.center_x < possible_split for line in lines)
        right_count = len(lines) - left_count
        if left_count >= 8 and right_count >= 8:
            column_count = 2
            split_x = possible_split

    side_switches = 0
    near_row_switches = 0
    if column_count == 2 and split_x is not None:
        labels = [line.center_x >= split_x for line in lines]
        median_line_height = sorted(line.height for line in lines)[len(lines) // 2]
        near_row_threshold = max(median_line_height * 1.5, image.height * 0.025)
        for previous, current, previous_y, current_y in zip(
            labels, labels[1:],
            [line.center_y for line in lines],
            [line.center_y for line in lines[1:]],
        ):
            if previous != current:
                side_switches += 1
                if abs(current_y - previous_y) <= near_row_threshold:
                    near_row_switches += 1

    if column_count == 2 and near_row_switches >= 4:
        flag = "possible_row_interleaving"
    elif column_count == 2 and near_row_switches >= 2:
        flag = "review_column_transitions"
    else:
        flag = "no_order_warning"

    return {
        "article_ids": article_ids,
        "path": str(image_path.relative_to(BASE_DIR)),
        "width": image.width,
        "height": image.height,
        "line_count": len(lines),
        "column_count": column_count,
        "side_switches": side_switches,
        "near_row_switches": near_row_switches,
        "mean_confidence": round(sum(confidence) / len(confidence), 1) if confidence else 0,
        "flag": flag,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit Tesseract line order for possible column interleaving.")
    parser.add_argument("--sample", type=int, default=0, help="Audit only this many unique images for detector testing.")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", default="column_order_audit.csv")
    args = parser.parse_args()

    if not os.path.isfile(TESSERACT_EXE):
        raise FileNotFoundError(f"Tesseract executable not found: {TESSERACT_EXE}")

    import sqlite3

    with sqlite3.connect(DB_PATH) as connection:
        database_rows = connection.execute(
            "SELECT id, file_path FROM articles ORDER BY id"
        ).fetchall()

    paths_by_hash = {}
    errors = []
    for article_id, stored_path in database_rows:
        image_path = Path(stored_path)
        if not image_path.is_absolute():
            image_path = BASE_DIR / image_path
        if not image_path.is_file():
            errors.append((article_id, stored_path, "image_missing"))
            continue
        try:
            digest = image_digest(image_path)
        except OSError as error:
            errors.append((article_id, stored_path, str(error)))
            continue
        paths_by_hash.setdefault(digest, {"path": image_path, "article_ids": []})["article_ids"].append(article_id)

    unique_images = list(paths_by_hash.values())
    if args.sample:
        unique_images = unique_images[:args.sample]
    print(
        f"Auditing {len(unique_images)} unique images from {len(database_rows)} database rows "
        f"with {args.workers} workers",
        flush=True,
    )

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(read_tesseract_lines, item["path"], item["article_ids"]): item
            for item in unique_images
        }
        for index, future in enumerate(as_completed(futures), 1):
            try:
                results.append(future.result())
            except Exception as error:
                item = futures[future]
                errors.append((item["article_ids"], str(item["path"]), str(error)))
            if index % 50 == 0:
                print(f"Audited {index}/{len(unique_images)}; errors={len(errors)}", flush=True)

    results.sort(key=lambda result: result["path"].casefold())
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = BASE_DIR / output_path
    columns = [
        "article_ids", "path", "width", "height", "line_count", "column_count",
        "side_switches", "near_row_switches", "mean_confidence", "flag",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as report:
        writer = csv.DictWriter(report, fieldnames=columns)
        writer.writeheader()
        for result in results:
            result["article_ids"] = ",".join(map(str, result["article_ids"]))
            writer.writerow(result)

    counts = {}
    for result in results:
        counts[result["flag"]] = counts.get(result["flag"], 0) + 1
    print(f"Report: {output_path}")
    print(f"Unique images audited: {len(results)}")
    print(f"Flags: {counts}")
    print(f"Path/OCR errors: {len(errors)}")
    for error in errors[:20]:
        print("ERROR", error)


if __name__ == "__main__":
    main()
