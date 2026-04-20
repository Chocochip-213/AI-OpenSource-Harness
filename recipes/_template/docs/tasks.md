# Tasks

> **Strategy Fallback Tree**: Always start with v1 (Direct pip). If v1 fails in Colab,
> DO NOT delete v1 tasks — keep them checked/failed, add a new vN section below.
> The failure history guides the next porter (Ever trellis2: v1→v2 saved ~3 days).

## Setup
- [ ] Copy `_template` → `recipes/<name>/`
- [ ] `scripts/set_active_recipe.sh <name>` (writes `.claude/last_recipe.txt` + `.claude/.env`)
- [ ] Update `recipe.yaml` (`upstream.repo`, `upstream.ref` commit SHA, GPU, Python, runtime, `recipe_type`, `secrets`)
- [ ] Write `docs/plan.md` (goal, scope, target env, success criteria — fill ALL sections, not just Goal)
- [ ] Write `docs/context.md` **Dependencies** table (package × upstream ver × Colab stock × strategy)
- [ ] Check `colab-runtimes/SUMMARY.md` for best-matching runtime (minimize version drift)
- [ ] Check `docs/COMMON_ERRORS.md` for known issues with this model's deps
- [ ] Check `docs/PORTING_PATTERNS.md` — pick initial strategy (§1 Direct pip default)

## v1 — Direct pip (default, try first)
- [ ] `requirements_opt1.txt` — only packages NOT in Colab stock, pinned where version-sensitive
- [ ] `notebook_manifest.yaml` Cell A: GPU check + VRAM assert (fail fast if insufficient)
- [ ] `notebook_manifest.yaml` Cell B: `pip install` deltas only
- [ ] `notebook_manifest.yaml` Cell C: Fail-fast verification — import EVERY critical dep, assert CUDA, check VRAM
- [ ] `notebook_manifest.yaml` Cell D: Clone upstream at pinned SHA, apply any patches
- [ ] `notebook_manifest.yaml` Cell E: Load model (cache in `globals()` for cell re-run safety)
- [ ] `notebook_manifest.yaml` Cell F: Inference + save/download output
- [ ] `generate_notebook.py` succeeds (non-empty cells validated)
- [ ] Colab test: Cells A-C pass → if YES continue, if NO → record error in `context.md` Discovered Issues, go to v2
- [ ] Colab test: Full pipeline end-to-end
- [ ] Record metrics in `context.md` (cold-start time, VRAM peak, output quality, cost)

## v2 — Strategy Fallback (activate ONE when v1 fails — do not delete v1)

Pick based on the v1 failure mode. Strategies ordered simplest → hardest.

### v2a: Runtime Rollback (simplest — if model needs older torch/Python)
- [ ] Identify target runtime from `colab-runtimes/SUMMARY.md` (e.g. 2025.07 for Python 3.11)
- [ ] Add "Runtime > Change runtime type > <version>" instruction to Cell A markdown
- [ ] Re-test Cell B onwards on target runtime
- [ ] Document runtime requirement in `recipe.yaml` (`runtime.colab_version`)

### v2b: Selective Downgrade + Patch (one package, version-sensitive)
- [ ] Identify the ONE conflicting package (diffusers, transformers, etc.)
- [ ] `requirements_opt2.txt` with narrow pin
- [ ] Add compat-patch cell — `str.replace()` on upstream file
- [ ] **Always assert after replace** — `assert 'new_token' in content, 'patch failed — upstream changed'`
- [ ] Re-test fail-fast cell C

### v2c: Shim / Monkey-patch (build fails, native substitute exists)
- [ ] Read `docs/PORTING_PATTERNS.md` §4
- [ ] Identify failing build (flash-attn, xformers, nvdiffrast)
- [ ] Write shim covering ALL import surfaces (module, class, function, `__version__`)
- [ ] Create `.dist-info/METADATA` if `importlib.metadata.version()` is called
- [ ] Register safe globals via `torch.serialization.add_safe_globals([...])` for `torch.load` weights_only
- [ ] Verify fail-fast cell passes with shim

### v2d: Conda Isolation (last resort — multi-C-ext ABI conflict)
- [ ] Read `docs/PORTING_PATTERNS.md` §3
- [ ] Must use runtime 2025.07 (Python 3.11 + condacolab 0.1.x)
- [ ] Redesign Cell B: `!pip install -q condacolab` then `import condacolab; condacolab.install()`
- [ ] Add Cell C for conda env verification
- [ ] Patch upstream scripts for `_MODEL_PYTHON` environment variable
- [ ] Accept ~3-5 min setup overhead

## Validation (all strategies)
- [ ] `smoke_test.py` passes locally
- [ ] `generate_notebook.py` succeeds (non-blank notebook)
- [ ] Colab cells run sequentially without error (cold fresh runtime)
- [ ] Input → output verified with metrics
- [ ] Record every error encountered (even resolved) in `context.md` Discovered Issues
- [ ] Promote generalizable fixes to `docs/COMMON_ERRORS.md`
- [ ] Update `CLAUDE.md` Porting Patterns table if a new pattern emerged

## Colab MCP (live runtime) — only if `recipe.yaml:mcp.enabled: true`
- [ ] `scripts/set_active_recipe.sh <name>` + `source .claude/.env` before starting claude
- [ ] `/colab-mcp` opens the browser handshake; approve the Colab tab once
- [ ] Cell A (auto-injected preflight) passes — GPU matches `mcp.preferred_gpu`
- [ ] No `output over budget` warnings in `.claude/_hook_errors.log` (else raise `mcp.max_tool_output_tokens`)
- [ ] `.claude/_mcp_tool_calls.log` reviewed for unexpected calls
- [ ] **MCP edits promoted to manifest** via `/colab-mcp-sync` — dry-run → review → `--apply`
- [ ] `generate_notebook.py` re-run after `--apply`; output matches live notebook
- [ ] Colab tab closed cleanly at end of session

## Reversal & Re-judgement (Ever lesson: decisions change mid-porting)
<!-- If you initially judged "too hard to port" but later succeeded (or vice versa),
record the reversal here with a date. This prevents "we already decided that" circular loops.
Example:
  2026-03-15: Initially marked "inference works but pipeline integration infeasible".
  2026-03-22: Reversed — pipeline integration succeeded after shim-v2.
-->

---
> Check off IMMEDIATELY after each item (not at session end).
> `docs: session-end` commits finalize the progress snapshot.
> Decisions → `context.md`. Errors → `context.md` Discovered Issues table.
> When v1 fails → keep v1 checked as-is, add v2 section. Failure history is valuable.
