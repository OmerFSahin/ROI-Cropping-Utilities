from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import nrrd


def find_scan_and_mask(folder: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """Find .nrrd files containing 'scan' and 'mask' in filenames."""
    scan, mask = None, None
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() == ".nrrd":
            name = p.name.lower()
            if "scan" in name:
                scan = p
            elif "mask" in name:
                mask = p
    return scan, mask


def crop_to_roi_with_margin(scan: np.ndarray, mask: np.ndarray, margin: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    """Crop scan+mask to bounding box of non-zero mask voxels, expanded by margin."""
    if scan.shape != mask.shape:
        raise ValueError("Scan and mask must have the same shape.")
    if margin < 0:
        raise ValueError("margin must be >= 0")

    fg = np.where(mask != 0)
    if fg[0].size == 0:
        raise ValueError("Mask has no non-zero voxels; cannot crop.")

    min_coords = [int(ax.min()) for ax in fg]
    max_coords = [int(ax.max()) for ax in fg]

    min_coords = [max(m - margin, 0) for m in min_coords]
    max_coords = [min(M + margin, dim - 1) for M, dim in zip(max_coords, mask.shape)]

    slices = tuple(slice(mi, ma + 1) for mi, ma in zip(min_coords, max_coords))
    return scan[slices], mask[slices]


def process_dataset(input_dir: Path, output_dir: Path, margin: int, scan_dtype: str = "float32") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    patient_folders = [p for p in sorted(input_dir.iterdir()) if p.is_dir()]
    if not patient_folders:
        raise FileNotFoundError(f"No patient folders found under: {input_dir}")

    for patient in patient_folders:
        scan_path, mask_path = find_scan_and_mask(patient)
        if scan_path is None or mask_path is None:
            print(f"[SKIP] {patient.name}: scan/mask .nrrd not found")
            continue

        scan, scan_header = nrrd.read(str(scan_path))
        mask, mask_header = nrrd.read(str(mask_path))

        scan = scan.astype(np.dtype(scan_dtype), copy=False)

        try:
            cropped_scan, cropped_mask = crop_to_roi_with_margin(scan, mask, margin=margin)
        except ValueError as e:
            print(f"[SKIP] {patient.name}: {e}")
            continue

        out_patient = output_dir / patient.name
        out_patient.mkdir(parents=True, exist_ok=True)

        nrrd.write(str(out_patient / f"{scan_path.stem}_cropped.nrrd"), cropped_scan, header=scan_header)
        nrrd.write(str(out_patient / f"{mask_path.stem}_cropped.nrrd"), cropped_mask, header=mask_header)

        print(f"[OK] {patient.name} -> {out_patient}")


def main() -> int:
    p = argparse.ArgumentParser(description="Crop NRRD scan+mask pairs to ROI defined by mask foreground.")
    p.add_argument("--input-dir", type=Path, default=Path("data/input"))
    p.add_argument("--output-dir", type=Path, default=Path("data/output"))
    p.add_argument("--margin", type=int, default=10)
    p.add_argument("--scan-dtype", type=str, default="float32")
    args = p.parse_args()

    process_dataset(args.input_dir, args.output_dir, args.margin, scan_dtype=args.scan_dtype)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
