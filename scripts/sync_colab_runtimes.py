#!/usr/bin/env python3
"""
Sync Colab runtime package snapshots from googlecolab/backend-info.

Clones (or fetches) the upstream repo, parses README.md for version→commit mappings,
extracts pip-freeze and os-info for each runtime version, and writes structured
JSON + Markdown summary to colab-runtimes/.

Usage:
    python scripts/sync_colab_runtimes.py [--output-dir colab-runtimes]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

UPSTREAM_URL = "https://github.com/googlecolab/backend-info.git"

# Packages that matter most for AI/ML Colab porting
KEY_PACKAGES = [
    "torch", "torchvision", "torchaudio",
    "numpy", "scipy", "pillow",
    "transformers", "diffusers", "accelerate",
    "huggingface-hub", "huggingface_hub", "safetensors",
    "xformers", "flash-attn", "flash_attn",
    "spconv", "spconv-cu120", "spconv-cu124", "spconv-cu126", "spconv-cu128",
    "tensorflow", "jax", "jaxlib",
    "triton", "opencv-python", "opencv-python-headless",
    "gradio", "peft", "bitsandbytes",
    "onnxruntime", "onnxruntime-gpu",
]


def clone_or_fetch(work_dir: Path) -> Path:
    """Clone upstream repo (bare) into work_dir, return repo path."""
    repo_path = work_dir / "backend-info.git"
    if repo_path.exists():
        subprocess.run(["git", "fetch", "--all"], cwd=repo_path, check=True,
                       capture_output=True)
    else:
        subprocess.run(
            ["git", "clone", "--bare", UPSTREAM_URL, str(repo_path)],
            check=True, capture_output=True,
        )
    return repo_path


def git_show(repo: Path, ref: str, path: str) -> str | None:
    """Read a file at a specific ref from the bare repo."""
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=repo, capture_output=True, text=True, check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None


def git_ls_tree(repo: Path, ref: str) -> list[str]:
    """List files at a ref."""
    result = subprocess.run(
        ["git", "ls-tree", "--name-only", ref],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip().split("\n")


def parse_readme_versions(repo: Path) -> dict[str, str]:
    """Parse README.md to extract version→commit SHA mapping.

    Returns: {"2026.01": "bd8aaa4...", "2025.10": "7a0599e...", ...}
    Also adds "latest" key pointing to main HEAD.
    """
    readme = git_show(repo, "main", "README.md")
    if not readme:
        return {}

    versions: dict[str, str] = {}

    # Pattern: ### 2026.01 ... [GitHub commit](https://...tree/<sha>)
    blocks = re.split(r"###\s+(\d{4}\.\d{2})", readme)
    # blocks[0] is preamble, then alternating: version, content, version, content...
    for i in range(1, len(blocks) - 1, 2):
        version = blocks[i].strip()
        content = blocks[i + 1]
        sha_match = re.search(
            r"github\.com/googlecolab/backend-info/tree/([0-9a-f]{40})", content
        )
        if sha_match:
            versions[version] = sha_match.group(1)

    # Also get main HEAD as "latest"
    result = subprocess.run(
        ["git", "rev-parse", "main"], cwd=repo,
        capture_output=True, text=True, check=True,
    )
    versions["latest"] = result.stdout.strip()

    return versions


def parse_pip_freeze(text: str) -> dict[str, str]:
    """Parse pip freeze output into {package_name: version_or_url}."""
    packages: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Format 1: package==version
        if "==" in line and "@" not in line:
            name, version = line.split("==", 1)
            packages[name.lower().replace("-", "_")] = version

        # Format 2: package @ https://...whl (URL install)
        elif " @ " in line:
            name = line.split(" @ ")[0].strip()
            url = line.split(" @ ")[1].strip()
            # Extract version from URL, including +cuXXX suffix
            # URL-encoded: %2B = +, so match both
            whl_match = re.search(
                r"(\d+\.\d+\.\d+(?:[%+]2[Bb]\w+|\+\w+)?)", url
            )
            if whl_match:
                version = whl_match.group(1).replace("%2B", "+")
            else:
                version = url
            packages[name.lower().replace("-", "_")] = version

    return packages


def parse_os_info(text: str) -> dict[str, str]:
    """Parse os-info.txt into structured dict."""
    info: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "Ubuntu" in line:
            info["ubuntu"] = line
        elif "Python" in line:
            info["python"] = line.replace("Python ", "")
        elif line.startswith("R version"):
            info["r"] = line
        elif "julia" in line.lower():
            info["julia"] = line.replace("julia version ", "")
    return info


def extract_runtime(repo: Path, ref: str) -> dict:
    """Extract all info for a single runtime version at given ref."""
    files = git_ls_tree(repo, ref)

    # Determine GPU pip-freeze file (naming changed between versions)
    gpu_freeze_file = "pip-freeze.gpu.txt" if "pip-freeze.gpu.txt" in files else "pip-freeze.txt"
    gpu_osinfo_file = "os-info-gpu.txt" if "os-info-gpu.txt" in files else "os-info.txt"

    # Parse GPU packages
    freeze_text = git_show(repo, ref, gpu_freeze_file) or ""
    all_packages = parse_pip_freeze(freeze_text)

    # Extract key packages
    key_pkgs: dict[str, str] = {}
    for pkg in KEY_PACKAGES:
        normalized = pkg.lower().replace("-", "_")
        if normalized in all_packages:
            key_pkgs[pkg] = all_packages[normalized]

    # Parse OS info
    os_text = git_show(repo, ref, gpu_osinfo_file) or ""
    os_info = parse_os_info(os_text)

    # Also grab CPU freeze if separate file exists
    has_separate_gpu = "pip-freeze.gpu.txt" in files
    cpu_count = None
    if has_separate_gpu:
        cpu_text = git_show(repo, ref, "pip-freeze.txt") or ""
        cpu_count = len(parse_pip_freeze(cpu_text))

    return {
        "os": os_info,
        "gpu_freeze_file": gpu_freeze_file,
        "total_packages": len(all_packages),
        "cpu_packages": cpu_count,
        "key_packages": key_pkgs,
        "all_packages": all_packages,
    }


def generate_summary_md(runtimes: dict) -> str:
    """Generate a Markdown comparison table of key packages across runtimes."""
    # Sort versions: latest first, then descending
    sorted_versions = []
    for v in runtimes:
        if v == "latest":
            continue
        sorted_versions.append(v)
    sorted_versions.sort(reverse=True)

    lines = [
        "# Colab Runtime Package Versions",
        "",
        "> Auto-generated by `scripts/sync_colab_runtimes.py`",
        f"> Source: [{UPSTREAM_URL}]({UPSTREAM_URL})",
        "",
        "## Runtime Overview",
        "",
    ]

    # OS info table
    header = "| | " + " | ".join(sorted_versions) + " |"
    separator = "|---|" + "|".join(["---"] * len(sorted_versions)) + "|"
    lines.extend([header, separator])

    for field in ["ubuntu", "python", "julia"]:
        row = f"| {field.title()} | "
        row += " | ".join(
            runtimes.get(v, {}).get("os", {}).get(field, "-")
            for v in sorted_versions
        )
        row += " |"
        lines.append(row)

    pkg_count_row = "| GPU Packages | " + " | ".join(
        str(runtimes.get(v, {}).get("total_packages", "-"))
        for v in sorted_versions
    ) + " |"
    lines.append(pkg_count_row)
    lines.append("")

    # Key packages table
    lines.extend([
        "## Key AI/ML Packages",
        "",
        "| Package | " + " | ".join(sorted_versions) + " |",
        "|---|" + "|".join(["---"] * len(sorted_versions)) + "|",
    ])

    # Collect all key packages that exist in any version
    all_key = set()
    for v in sorted_versions:
        all_key.update(runtimes.get(v, {}).get("key_packages", {}).keys())

    # Sort with priority packages first
    priority = ["torch", "torchvision", "numpy", "scipy", "transformers",
                "diffusers", "accelerate", "xformers", "jax", "tensorflow"]
    ordered = [p for p in priority if p in all_key]
    ordered += sorted(all_key - set(ordered))

    for pkg in ordered:
        row = f"| `{pkg}` | "
        cells = []
        for v in sorted_versions:
            ver = runtimes.get(v, {}).get("key_packages", {}).get(pkg, "-")
            cells.append(ver)
        row += " | ".join(cells) + " |"
        lines.append(row)

    lines.extend([
        "",
        "## Usage for AI Porting",
        "",
        "When porting an open-source AI model to Colab, check this table to:",
        "",
        "1. **Identify conflicts** - Compare model requirements with Colab's pre-installed versions",
        "2. **Choose runtime** - Pick the runtime version that best matches your model's dependencies",
        "3. **Plan workarounds** - Know which packages need `pip install --upgrade` or conda isolation",
        "",
        "### Example: Checking PyTorch compatibility",
        "",
        "```python",
        "# If your model needs torch 2.6.0+cu124:",
        "#   -> Use runtime 2025.07 (has torch 2.6.0+cu124 natively)",
        "#   -> On 2026.01 (torch 2.10.0+cu128), you'd need conda isolation",
        "```",
        "",
        "### Runtime Rollback",
        "",
        "Colab supports pinning notebooks to past runtime versions.",
        "In Colab: **Runtime > Change runtime type > Runtime version**",
        "",
        "This is often the easiest fix for dependency conflicts.",
        "",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Sync Colab runtime info")
    parser.add_argument(
        "--output-dir", default="colab-runtimes",
        help="Output directory for parsed data (default: colab-runtimes)",
    )
    parser.add_argument(
        "--repo-cache", default=None,
        help="Path to cache the bare clone (default: temp dir)",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    output_dir = project_root / args.output_dir

    # Clone/fetch upstream
    if args.repo_cache:
        work_dir = Path(args.repo_cache)
        work_dir.mkdir(parents=True, exist_ok=True)
        repo = clone_or_fetch(work_dir)
        cleanup = False
    else:
        tmp = tempfile.mkdtemp(prefix="colab-sync-")
        work_dir = Path(tmp)
        repo = clone_or_fetch(work_dir)
        cleanup = True

    try:
        # Parse version→commit from README
        versions = parse_readme_versions(repo)
        if not versions:
            print("ERROR: Could not parse any versions from README.md")
            return 1

        print(f"Found {len(versions)} runtime versions: {', '.join(versions.keys())}")

        # Extract data for each version
        runtimes: dict[str, dict] = {}
        for version, sha in versions.items():
            if version == "latest":
                continue
            print(f"  Extracting {version} ({sha[:8]})...")
            runtimes[version] = extract_runtime(repo, sha)
            runtimes[version]["commit_sha"] = sha

        # Write output
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Full JSON (all packages per version)
        full_data = {
            "source": UPSTREAM_URL,
            "runtimes": {},
        }
        for version, data in sorted(runtimes.items(), reverse=True):
            full_data["runtimes"][version] = {
                "commit_sha": data["commit_sha"],
                "os": data["os"],
                "total_gpu_packages": data["total_packages"],
                "key_packages": data["key_packages"],
            }

        with open(output_dir / "runtimes.json", "w", encoding="utf-8") as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)

        # 2. Per-version directories with full package lists
        for version, data in runtimes.items():
            ver_dir = output_dir / version
            ver_dir.mkdir(parents=True, exist_ok=True)

            # Full package list as JSON
            with open(ver_dir / "packages.json", "w", encoding="utf-8") as f:
                json.dump({
                    "commit_sha": data["commit_sha"],
                    "os": data["os"],
                    "total_packages": data["total_packages"],
                    "packages": data["all_packages"],
                }, f, indent=2, ensure_ascii=False)

            # Key packages only (quick reference)
            with open(ver_dir / "key-packages.json", "w", encoding="utf-8") as f:
                json.dump(data["key_packages"], f, indent=2, ensure_ascii=False)

        # 3. Summary markdown
        summary_md = generate_summary_md(runtimes)
        sync_header = (
            f"<!-- Last synced: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
            f"by scripts/sync_colab_runtimes.py -->\n"
        )
        with open(output_dir / "SUMMARY.md", "w", encoding="utf-8") as f:
            f.write(sync_header + summary_md)

        # 4. AI-consumable context file (compact, for CLAUDE.md or context packs)
        sync_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        latest_ver = sorted(runtimes.keys(), reverse=True)[0] if runtimes else "?"
        context_lines = [
            "# Colab Runtime Quick Reference (auto-generated)",
            "",
            f"> **Last synced**: {sync_ts} (UTC) — latest runtime in this snapshot: `{latest_ver}`",
            "> Colab updates runtimes ~monthly. If `{today} - Last synced > 30d`, re-run:",
            "> `python scripts/sync_colab_runtimes.py`",
            "",
        ]
        for version in sorted(runtimes.keys(), reverse=True):
            d = runtimes[version]
            os_info = d["os"]
            kp = d["key_packages"]
            context_lines.append(f"## {version}")
            context_lines.append(f"- Python {os_info.get('python', '?')}, {os_info.get('ubuntu', '?')}")
            for pkg in ["torch", "numpy", "transformers", "diffusers", "xformers", "jax", "tensorflow"]:
                if pkg in kp:
                    context_lines.append(f"- {pkg}=={kp[pkg]}")
            context_lines.append("")

        with open(output_dir / "quick-reference.md", "w", encoding="utf-8") as f:
            f.write("\n".join(context_lines))

        print(f"\nOutput written to {output_dir}/")
        print(f"  runtimes.json        - overview ({len(runtimes)} versions)")
        print(f"  SUMMARY.md           - human-readable comparison")
        print(f"  quick-reference.md   - compact AI-consumable reference")
        for v in sorted(runtimes.keys(), reverse=True):
            print(f"  {v}/packages.json  - full package list")

    finally:
        if cleanup:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
