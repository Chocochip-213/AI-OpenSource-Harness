#!/usr/bin/env python3
"""Promote MCP-side notebook edits back into `notebook_manifest.yaml`.

Flow used by the `/colab-mcp-sync` skill:

  1. Claude (via MCP) fetches the current notebook state from the live Colab
     runtime and writes it to
       outputs/mcp-sessions/<recipe>/latest-cells.json
     The file is a JSON array of cells:
       [
         {"name": "A) GPU Check", "type": "code", "source": "...", "cell_id": "opt"},
         {"name": "## Setup", "type": "markdown", "source": "..."},
         ...
       ]

  2. This script loads that file and the recipe's notebook_manifest.yaml,
     aligns cells by name (falling back to index), and prints a unified diff
     plus a summary of adds / modifications / removals. No file is mutated
     without the --apply flag.

  3. With --apply, the manifest is rewritten atomically. A backup is saved
     to recipes/<name>/notebook_manifest.yaml.sync-<ISO>.bak.

Usage:
    python scripts/colab_mcp_sync.py <recipe>                     # dry-run
    python scripts/colab_mcp_sync.py <recipe> --apply              # mutate manifest
    python scripts/colab_mcp_sync.py <recipe> --cells-file PATH    # override input
    python scripts/colab_mcp_sync.py <recipe> --session SESSION_ID # specific session

Exit codes:
    0  no changes / changes applied
    3  diff found (dry-run) — review before re-running with --apply
    1  input error (missing files, invalid JSON/YAML)
"""
from __future__ import annotations

import argparse
import difflib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Windows Git Bash / cmd default to cp949; force UTF-8 so em-dashes and
# unicode diff markers don't crash the script mid-print.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

try:
    import yaml  # pyproject.toml declares this
except ImportError:
    print("ERROR: PyYAML required. Install with: uv sync  (or: pip install pyyaml)", file=sys.stderr)
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent


def cells_from_live(data: Any) -> list[dict]:
    """Normalize the `latest-cells.json` payload to the list-of-dict format."""
    if isinstance(data, dict):
        data = data.get("cells", data)
    if not isinstance(data, list):
        raise ValueError("latest-cells.json must be a list of cells or {cells: [...]}.")
    out = []
    for i, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise ValueError(f"cell #{i} is not an object")
        out.append({
            "name": raw.get("name") or raw.get("title") or f"cell-{i}",
            "type": (raw.get("type") or raw.get("cell_type") or "code").lower(),
            "source": raw.get("source") if isinstance(raw.get("source"), str)
                      else "".join(raw.get("source") or []),
            "cell_id": raw.get("cell_id") or raw.get("id"),
        })
    return out


def cells_from_manifest(manifest: dict) -> list[dict]:
    raw_cells = manifest.get("cells") or []
    out = []
    for i, raw in enumerate(raw_cells):
        if not isinstance(raw, dict):
            continue
        out.append({
            "name": raw.get("name") or raw.get("title") or f"cell-{i}",
            "type": (raw.get("type") or "code").lower(),
            "source": raw.get("source") if isinstance(raw.get("source"), str)
                      else "".join(raw.get("source") or []),
            "cell_id": raw.get("cell_id"),
        })
    return out


def align(manifest_cells: list[dict], live_cells: list[dict]) -> list[tuple[str, dict | None, dict | None]]:
    """Return list of (op, manifest_cell, live_cell) tuples.

    Alignment strategy: prefer cell_id match, then exact name match, then
    index order. Remaining cells on either side become add/remove.
    """
    ops: list[tuple[str, dict | None, dict | None]] = []
    m_by_id = {c["cell_id"]: c for c in manifest_cells if c.get("cell_id")}
    l_by_id = {c["cell_id"]: c for c in live_cells if c.get("cell_id")}

    m_by_name: dict[str, dict] = {}
    for c in manifest_cells:
        m_by_name.setdefault(c["name"], c)
    l_by_name: dict[str, dict] = {}
    for c in live_cells:
        l_by_name.setdefault(c["name"], c)

    matched_m: set[int] = set()
    matched_l: set[int] = set()

    # Pass 1 — cell_id
    for i_l, lc in enumerate(live_cells):
        cid = lc.get("cell_id")
        if cid and cid in m_by_id:
            mc = m_by_id[cid]
            i_m = manifest_cells.index(mc)
            if i_m in matched_m or i_l in matched_l:
                continue
            op = "same" if mc["source"] == lc["source"] and mc["type"] == lc["type"] else "modify"
            ops.append((op, mc, lc))
            matched_m.add(i_m); matched_l.add(i_l)

    # Pass 2 — exact name
    for i_l, lc in enumerate(live_cells):
        if i_l in matched_l:
            continue
        mc = m_by_name.get(lc["name"])
        if mc is None:
            continue
        i_m = manifest_cells.index(mc)
        if i_m in matched_m:
            continue
        op = "same" if mc["source"] == lc["source"] and mc["type"] == lc["type"] else "modify"
        ops.append((op, mc, lc))
        matched_m.add(i_m); matched_l.add(i_l)

    # Pass 3 — adds (live cells not matched)
    for i_l, lc in enumerate(live_cells):
        if i_l not in matched_l:
            ops.append(("add", None, lc))

    # Pass 4 — removes (manifest cells not matched)
    for i_m, mc in enumerate(manifest_cells):
        if i_m not in matched_m:
            ops.append(("remove", mc, None))

    return ops


def unified_diff(label: str, old: str, new: str) -> str:
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"{label} (manifest)",
        tofile=f"{label} (live)",
        n=2,
    )
    return "".join(diff)


def print_report(ops, *, verbose: bool) -> dict[str, int]:
    counts = {"same": 0, "modify": 0, "add": 0, "remove": 0}
    for op, mc, lc in ops:
        counts[op] = counts.get(op, 0) + 1
        if op == "same":
            continue
        if op == "modify":
            name = lc["name"]
            print(f"\n--- MODIFY: {name}")
            print(unified_diff(name, mc["source"], lc["source"]).rstrip() or "(no text diff — metadata only)")
        elif op == "add":
            print(f"\n--- ADD: {lc['name']} ({lc['type']})")
            if verbose:
                print(lc["source"][:400] + ("…" if len(lc["source"]) > 400 else ""))
        elif op == "remove":
            print(f"\n--- REMOVE: {mc['name']} ({mc['type']})")
    return counts


def rebuild_manifest(manifest: dict, live_cells: list[dict]) -> dict:
    """Produce a new manifest dict where `cells` reflects the live sequence.
    Top-level keys other than `cells` are preserved as-is.
    """
    new_cells = []
    for c in live_cells:
        entry = {
            "name": c["name"],
            "type": c["type"],
            "source": c["source"],
        }
        if c.get("cell_id"):
            entry["cell_id"] = c["cell_id"]
        new_cells.append(entry)
    new = dict(manifest)
    new["cells"] = new_cells
    return new


def atomic_write_yaml(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=100)
    tmp.replace(path)


def default_cells_file(recipe: str, session: str | None) -> Path:
    base = REPO_ROOT / "outputs" / "mcp-sessions" / recipe
    if session:
        return base / f"{session}.cells.json"
    # Newest session wins
    latest = base / "latest-cells.json"
    if latest.exists():
        return latest
    candidates = sorted(base.glob("*.cells.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]
    return latest  # caller will emit a friendly error below


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("recipe", help="Recipe name (folder under recipes/)")
    ap.add_argument("--apply", action="store_true",
                    help="Apply changes to notebook_manifest.yaml (default: dry-run)")
    ap.add_argument("--cells-file", type=Path,
                    help="Path to JSON dump of live cells. "
                         "Default: outputs/mcp-sessions/<recipe>/latest-cells.json "
                         "or newest *.cells.json in that directory.")
    ap.add_argument("--session", help="Specific session id (file: <session>.cells.json)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Print full source for added cells")
    ap.add_argument("--no-regen", action="store_true",
                    help="Skip the post-apply `generate_notebook.py <recipe>` call. "
                         "Default: --apply automatically regenerates the .ipynb so "
                         "manifest and notebook stay in lock-step (otherwise the "
                         "sync only updates the YAML and the .ipynb drifts).")
    args = ap.parse_args()

    recipe_dir = REPO_ROOT / "recipes" / args.recipe
    manifest_path = recipe_dir / "notebook_manifest.yaml"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found", file=sys.stderr)
        return 1

    cells_file = args.cells_file or default_cells_file(args.recipe, args.session)
    if not cells_file.exists():
        print(
            f"ERROR: {cells_file} not found.\n"
            f"Have Claude (while MCP-connected) dump the live notebook cells to this path "
            f"first — the /colab-mcp-sync skill describes the exact MCP tool call.",
            file=sys.stderr,
        )
        return 1

    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f) or {}
        with open(cells_file, encoding="utf-8") as f:
            live_raw = json.load(f)
    except Exception as e:
        print(f"ERROR reading inputs: {e}", file=sys.stderr)
        return 1

    try:
        live = cells_from_live(live_raw)
        local = cells_from_manifest(manifest)
    except Exception as e:
        print(f"ERROR normalizing cells: {e}", file=sys.stderr)
        return 1

    ops = align(local, live)
    print(f"# /colab-mcp-sync — {args.recipe}")
    print(f"# manifest: {manifest_path.relative_to(REPO_ROOT)}")
    print(f"# live: {cells_file.relative_to(REPO_ROOT)} ({len(live)} cells)")
    counts = print_report(ops, verbose=args.verbose)
    total_changes = counts["modify"] + counts["add"] + counts["remove"]
    print(
        f"\nSummary: same={counts['same']} modify={counts['modify']} "
        f"add={counts['add']} remove={counts['remove']}"
    )

    if total_changes == 0:
        print("No changes to promote. Manifest already matches live notebook.")
        return 0

    if not args.apply:
        print(
            "\nDry-run complete. Re-run with --apply to write the changes back "
            f"to {manifest_path.relative_to(REPO_ROOT)}."
        )
        return 3

    # --apply: write with a backup
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = manifest_path.with_suffix(manifest_path.suffix + f".sync-{ts}.bak")
    shutil.copy2(manifest_path, backup)
    new_manifest = rebuild_manifest(manifest, live)
    atomic_write_yaml(manifest_path, new_manifest)
    print(f"\nApplied. Backup: {backup.relative_to(REPO_ROOT)}")

    # Post-apply: regenerate the .ipynb so manifest and notebook stay in
    # lock-step. Without this, the next `generate_notebook.py` run (or the
    # next Colab upload) would silently undo all the edits we just promoted.
    # `--no-regen` exists for the rare case where the user wants to inspect
    # the manifest diff first before regenerating.
    if args.no_regen:
        print("Skipped notebook regeneration (--no-regen). "
              f"Run `uv run python tools/generate_notebook.py {args.recipe}` "
              "manually to refresh outputs/notebooks/.")
        return 0
    import subprocess
    print(f"\nRegenerating notebook (use --no-regen to skip)...")
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "generate_notebook.py"), args.recipe],
        capture_output=True, text=True,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        print(f"WARN: notebook regeneration failed (exit={proc.returncode}). "
              f"Manifest WAS updated; .ipynb may be stale. "
              f"Re-run `uv run python tools/generate_notebook.py {args.recipe}` "
              "after fixing the cause.", file=sys.stderr)
        return 0  # don't fail the sync — manifest is already on disk
    return 0


if __name__ == "__main__":
    sys.exit(main())
