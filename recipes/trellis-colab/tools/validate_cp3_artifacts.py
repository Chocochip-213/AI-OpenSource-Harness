#!/usr/bin/env python3
"""
CP3 artifact validator for TRELLIS Colab checkpoint flow.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
from typing import Any


def _add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    detail: str,
    required: bool = True,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "required": bool(required),
            "detail": detail,
        }
    )


def _load_json(path: pathlib.Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, f"missing: {path}"
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None, f"not-object JSON: {path}"
        return data, "ok"
    except Exception as e:  # pragma: no cover
        return None, f"json parse error: {e}"


def _glb_basic_integrity(path: pathlib.Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing: {path}"
    try:
        with path.open("rb") as f:
            header = f.read(12)
        if len(header) < 12:
            return False, "header too short"
        magic = header[:4]
        version = int.from_bytes(header[4:8], "little")
        total_len = int.from_bytes(header[8:12], "little")
        size = path.stat().st_size
        if magic != b"glTF":
            return False, f"bad magic: {magic!r}"
        if version != 2:
            return False, f"unexpected GLB version: {version}"
        if total_len > size:
            return False, f"declared length {total_len} exceeds file size {size}"
        return True, f"ok (version={version}, bytes={size})"
    except Exception as e:  # pragma: no cover
        return False, f"read error: {e}"


def validate_cp3(cp2_root: pathlib.Path, min_glb_mb: float) -> dict[str, Any]:
    cp2_input = cp2_root / "input"
    cp2_output = cp2_root / "output"
    cp2_report_path = cp2_output / "cp2_report.json"
    cp3_report_path = cp2_output / "cp3_validation.json"
    checks: list[dict[str, Any]] = []

    cp2_report, cp2_report_msg = _load_json(cp2_report_path)
    _add_check(checks, "cp2_report_exists_and_valid_json", cp2_report is not None, cp2_report_msg, required=True)

    cp2_status = None
    artifacts: dict[str, Any] = {}
    if cp2_report is not None:
        cp2_status = cp2_report.get("status")
        artifacts = cp2_report.get("artifacts", {}) if isinstance(cp2_report.get("artifacts"), dict) else {}

    allowed_cp2 = {"success", "partial_success_no_glb", "inference_ok"}
    _add_check(
        checks,
        "cp2_status_allowed",
        cp2_status in allowed_cp2,
        f"status={cp2_status!r}, allowed={sorted(allowed_cp2)}",
        required=True,
    )

    input_candidates = list(cp2_input.glob("*"))
    _add_check(
        checks,
        "input_image_present",
        len(input_candidates) > 0,
        f"count={len(input_candidates)} in {cp2_input}",
        required=True,
    )

    mesh_stats_path = pathlib.Path(str(artifacts.get("mesh_stats", cp2_output / "mesh_stats.json")))
    mesh_stats, mesh_msg = _load_json(mesh_stats_path)
    _add_check(checks, "mesh_stats_exists_and_valid_json", mesh_stats is not None, mesh_msg, required=True)

    vertex_count = None
    face_count = None
    if mesh_stats is not None:
        vertex_count = mesh_stats.get("vertex_count")
        face_count = mesh_stats.get("face_count")

    vc_ok = isinstance(vertex_count, int) and vertex_count > 0
    fc_ok = isinstance(face_count, int) and face_count > 0
    _add_check(checks, "mesh_vertex_count_positive", vc_ok, f"vertex_count={vertex_count!r}", required=True)
    _add_check(checks, "mesh_face_count_positive", fc_ok, f"face_count={face_count!r}", required=True)

    runtime_cfg = artifacts.get("runtime_pipeline_config")
    if runtime_cfg:
        runtime_cfg_path = pathlib.Path(str(runtime_cfg))
        _add_check(
            checks,
            "runtime_pipeline_config_exists",
            runtime_cfg_path.exists(),
            str(runtime_cfg_path),
            required=False,
        )

    glb_path_raw = artifacts.get("glb")
    glb_required = cp2_status == "success"
    if glb_path_raw:
        glb_path = pathlib.Path(str(glb_path_raw))
        glb_exists = glb_path.exists()
        _add_check(checks, "glb_exists", glb_exists, str(glb_path), required=glb_required)
        if glb_exists:
            size_mb = glb_path.stat().st_size / (1024 * 1024)
            _add_check(
                checks,
                "glb_size_minimum",
                size_mb >= min_glb_mb,
                f"size_mb={size_mb:.3f}, threshold={min_glb_mb:.3f}",
                required=glb_required,
            )
            glb_ok, glb_msg = _glb_basic_integrity(glb_path)
            _add_check(checks, "glb_basic_integrity", glb_ok, glb_msg, required=glb_required)
    else:
        _add_check(
            checks,
            "glb_missing_allowed",
            not glb_required,
            f"cp2_status={cp2_status!r}; glb required only when cp2_status='success'",
            required=glb_required,
        )

    required_checks = [c for c in checks if c["required"]]
    passed_required = [c for c in required_checks if c["passed"]]
    overall_pass = len(required_checks) == len(passed_required)

    report = {
        "cp2_root": str(cp2_root),
        "cp2_status": cp2_status,
        "overall_pass": overall_pass,
        "required_checks_total": len(required_checks),
        "required_checks_passed": len(passed_required),
        "checks": checks,
    }

    cp2_output.mkdir(parents=True, exist_ok=True)
    with cp3_report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


def _print_summary(report: dict[str, Any]) -> None:
    print("=== CP3 VALIDATION SUMMARY ===")
    print(f"cp2_status: {report.get('cp2_status')}")
    print(f"overall_pass: {report.get('overall_pass')}")
    print(f"required_checks: {report.get('required_checks_passed')}/{report.get('required_checks_total')}")
    print("")
    for row in report.get("checks", []):
        tag = "PASS" if row.get("passed") else "FAIL"
        req = "REQ" if row.get("required") else "OPT"
        print(f"[{tag}][{req}] {row.get('name')}: {row.get('detail')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CP2 output artifacts for CP3 gate.")
    parser.add_argument("--cp2-root", default="/content/trellis_cp_outputs/cp2")
    parser.add_argument("--min-glb-mb", type=float, default=0.05)
    args = parser.parse_args()

    cp2_root = pathlib.Path(args.cp2_root)
    report = validate_cp3(cp2_root, min_glb_mb=args.min_glb_mb)
    _print_summary(report)
    return 0 if report.get("overall_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
