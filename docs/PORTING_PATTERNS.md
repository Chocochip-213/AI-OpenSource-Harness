# Colab Porting Patterns — Battle-Tested Strategies

> Verified across 6+ real porting projects. Each strategy includes when to use it,
> code examples, and known pitfalls discovered during actual Colab testing.

## Strategy Selection Flowchart

```
Model has dependencies → Check colab-runtimes/SUMMARY.md
                              │
                    ┌─────────┴──────────┐
                    │                    │
              Versions match?      Versions differ?
                    │                    │
              [1. Direct pip]    Has C extensions?
                                     │
                              ┌──────┴──────┐
                              │             │
                             No            Yes
                              │             │
                    [2. Runtime Rollback   Does conda solve it?
                     or Selective Pin]         │
                                        ┌─────┴─────┐
                                        │           │
                                       Yes          No
                                        │           │
                                [3. Conda       [4. Shim +
                                 Isolation]      Patch]
```

---

## 1. Direct pip (Simplest)

**When**: Model deps are close to or match Colab stock versions.

**Process**:
1. Check `colab-runtimes/SUMMARY.md` for pre-installed versions
2. Only `pip install` packages that are missing or need a specific version
3. Avoid touching: numpy, scipy, Pillow, matplotlib, torch (keep Colab defaults)

**Example** (SAM3D Body — mostly Colab-compatible):
```bash
# Only pin what upstream truly requires
pip install networkx==3.2.1
pip install pytorch-lightning einops timm
# Do NOT: pip install numpy==1.x torch==2.x (use Colab's)
```

**Key Rules**:
- **Never downgrade** numpy, scipy, Pillow on Colab (C extension ABI crash)
- **Never `pip install torch`** in base env (use Colab's pre-compiled version)
- Use `--no-deps` when installing packages that would pull in conflicting torch/numpy versions

**Pitfall**: `pip install package` may silently upgrade torch via transitive dependencies. Always check with `pip install --dry-run` first.

---

## 2. Runtime Rollback

**When**: Model needs a specific torch/Python version that exists in an older Colab runtime.

**Process**:
1. Check `colab-runtimes/SUMMARY.md` — which runtime has the needed versions?
2. In Colab: Runtime > Change runtime type > Runtime version
3. No code changes needed

**Example** (UniRig — needs Python 3.11 for condacolab + bpy):
```
Model needs: Python 3.11, torch 2.6.0+cu124
2026.01: Python 3.12, torch 2.9.0+cu126  ← FAIL (3.12 breaks condacolab)
2025.10: Python 3.12, torch 2.8.0+cu126  ← FAIL
2025.07: Python 3.11, torch 2.6.0+cu124  ← MATCH ✓
```

**Key Insight**: Runtime selection is **constraint-driven**, not "use latest". Older runtimes are often the correct choice.

**Pitfall**: User must manually select the runtime version in Colab UI. Document the required version prominently in Cell A of the notebook.

---

## 3. Conda Isolation (condacolab)

**When**: Native C extensions (spconv, cumm, nvdiffrast) fundamentally broken on Colab's base Python environment. Direct pip and runtime rollback both fail.

**Process**:
```python
# Cell A: GPU Check (run once, skip after restart)
import torch
assert torch.cuda.is_available(), "GPU required"
gpu_name = torch.cuda.get_device_name(0)
print(f"GPU: {gpu_name}")

# Cell B: condacolab Install (triggers kernel restart)
import shutil, os
if shutil.which("mamba") and os.path.exists("/usr/local/bin/python"):
    print("condacolab already installed, skipping")
else:
    # Pin to 0.1.x; check https://github.com/conda-incubator/condacolab for updates
    !pip install -q condacolab==0.1.10
    import condacolab
    condacolab.install()
    # ⚠️ Kernel restarts here. After restart, skip to Cell C.

# Cell C: Verify Conda Environment
import subprocess, sys

_MODEL_PYTHON = "/usr/local/bin/python"
os.environ["_MODEL_PYTHON"] = _MODEL_PYTHON

# Verify conda Python is active
result = subprocess.run([_MODEL_PYTHON, "--version"], capture_output=True, text=True)
print(f"Conda Python: {result.stdout.strip()}")

# Install deps in conda env
subprocess.run([_MODEL_PYTHON, "-m", "pip", "install",
    "torch==2.6.0+cu124", "--index-url", "https://download.pytorch.org/whl/cu124"
], check=True)
```

**Critical Pitfalls** (all verified):
- **Python 3.12**: condacolab fails. Use runtime 2025.07 (Python 3.11).
- **sys.executable**: Points to wrapper, not conda Python. Always use explicit path.
- **LD_LIBRARY_PATH**: Must include nvidia lib dirs for CUDA libraries.
- **Upstream scripts**: Patch all `python`/`pip` references to use `$_MODEL_PYTHON`.
- **Kernel restart**: condacolab requires restart. Design notebooks to skip Cells A+B on re-run.

**When NOT to use**: If only 1-2 packages conflict, try selective pinning first. Conda isolation adds 3-5 min setup time and significant notebook complexity.

---

## 4. Shim / Monkey-Patch

**When**: Build fails but a runtime-compatible substitute exists in PyTorch or another pre-installed package.

### flash-attn SDPA Shim (Complete Template)

```python
import sys, os, types
import torch.nn.functional as F

# 1. Remove stale flash_attn.py if exists (shadows package dir)
import glob
for f in glob.glob("/usr/local/lib/python*/site-packages/flash_attn.py"):
    os.remove(f)

# 2. Create shim package
flash_attn = types.ModuleType("flash_attn")
flash_attn.__spec__ = None

def _sdpa_replacement(*args, **kwargs):
    """Redirect flash attention to PyTorch native SDPA."""
    return F.scaled_dot_product_attention(*args, **kwargs)

flash_attn.flash_attn_varlen_qkvpacked_func = _sdpa_replacement

# 3. Create submodules (must cover all import surfaces)
modules_mod = types.ModuleType("flash_attn.modules")
mha_mod = types.ModuleType("flash_attn.modules.mha")

class MHA(torch.nn.Module):
    """Shim MHA that uses standard PyTorch attention."""
    def __init__(self, embed_dim, num_heads, *args, **kwargs):
        super().__init__()
        self.Wq = torch.nn.Linear(embed_dim, embed_dim)
        self.Wkv = torch.nn.Linear(embed_dim, 2 * embed_dim)
        self.out_proj = torch.nn.Linear(embed_dim, embed_dim)
        self.num_heads = num_heads
        # NOTE: Parameter names (Wq, Wkv, out_proj) must match checkpoint keys

    def forward(self, x, *args, **kwargs):
        # Stub — implement per-model attention pattern if needed.
        # This class primarily exists to define parameter names
        # matching checkpoint keys for weight loading.
        raise NotImplementedError("Implement forward() for your model's attention pattern")

mha_mod.MHA = MHA
modules_mod.mha = mha_mod
flash_attn.modules = modules_mod

# 4. Register in sys.modules
sys.modules["flash_attn"] = flash_attn
sys.modules["flash_attn.modules"] = modules_mod
sys.modules["flash_attn.modules.mha"] = mha_mod

# 5. Create .dist-info for importlib.metadata (transformers checks this)
import site
site_pkg = site.getsitepackages()[0]  # Adapts to Python version automatically
dist_dir = f"{site_pkg}/flash_attn-0.0.0.dist-info"
os.makedirs(dist_dir, exist_ok=True)
with open(f"{dist_dir}/METADATA", "w") as f:
    f.write("Metadata-Version: 2.1\nName: flash-attn\nVersion: 0.0.0\n")

# 6. Patch model config: flash_attention_2 → eager
config_path = "model/config.yaml"
with open(config_path) as f:
    config = f.read()
original = config
config = config.replace("flash_attention_2", "eager")
assert config != original, "Config patch failed — string not found"
with open(config_path, "w") as f:
    f.write(config)
```

**Why the shim needs 6 steps**:
1. Stale `.py` file shadows the package directory
2. Some code imports `flash_attn` directly
3. Some code imports `flash_attn.modules.mha.MHA` specifically
4. Python must resolve all three import paths
5. `transformers` checks `importlib.metadata.version('flash_attn')`
6. Model config hard-codes `flash_attention_2` as attention implementation

**Key Rule**: Shim parameter names (Wq, Wkv, out_proj) must EXACTLY match the checkpoint keys. Using `torch.nn.MultiheadAttention`'s default names will cause checkpoint loading to fail.

---

## 5. Selective Downgrade + Compatibility Patch

**When**: Model needs an older version of a specific package (e.g., diffusers 0.24), but the rest of the environment should stay at Colab defaults.

**Process**:
```bash
# Only downgrade the specific package
pip install diffusers==0.24.0

# Apply compatibility patches for API changes
python patches/fix_diffusers_compat.py
```

**Example Patch** (diffusers 0.24 on modern transformers):
```python
# patches/fix_diffusers_compat.py
import re, glob

PATCHES = [
    # CaptionProjection moved between diffusers versions
    (r'from diffusers\.models\.embeddings import CaptionProjection',
     'from diffusers.models import CaptionProjection'),
    # DualTransformer2DModel relocated
    (r'from diffusers\.models\.dual_transformer_2d import',
     'from diffusers.models import'),
    # Attention processor names changed (assignment context only)
    (r'^ADDED_KV_ATTENTION_PROCESSORS\s*=.*$',
     'ADDED_KV_ATTENTION_PROCESSORS = {}  # Removed in newer diffusers'),
]

site_dir = site.getsitepackages()[0]
for py_file in glob.glob(f"{site_dir}/diffusers/**/*.py", recursive=True):
    with open(py_file) as f:
        content = f.read()
    for pattern, replacement in PATCHES:
        content = re.sub(pattern, replacement, content)
    with open(py_file, 'w') as f:
        f.write(content)
```

**Key Rules**:
- Keep Colab torch/numpy untouched
- Only downgrade the one package that truly needs it
- Document every patch with the specific import that broke and why
- Patches should be idempotent (safe to run multiple times)

**What NOT to downgrade** (causes cascade failures):
- torch (breaks all CUDA-dependent packages)
- numpy (C extension ABI incompatibility)
- scipy, scikit-learn (dependency chains to jax/shap/giddy/spopt)

---

## 6. Fail-Fast Verification Pattern

**When**: Always. Every notebook should verify dependencies before running the actual pipeline.

**Process**: Add a verification cell immediately after dependency installation.

```python
#@title C) Verify Dependencies { run: "auto" }
import sys

REQUIRED = {
    "torch": lambda: __import__("torch").cuda.is_available(),
    "spconv": lambda: __import__("spconv.pytorch"),
    "bpy": lambda: __import__("bpy"),
    "transformers": lambda: __import__("transformers"),
}

failed = []
for name, check in REQUIRED.items():
    try:
        check()
        print(f"  {name}: OK")
    except Exception as e:
        print(f"  {name}: FAIL — {e}")
        failed.append(name)

if failed:
    print(f"\n{'='*50}")
    print(f"FATAL: {len(failed)} required package(s) missing: {', '.join(failed)}")
    print(f"Fix the installation cells above before continuing.")
    sys.exit(1)
else:
    print(f"\nAll {len(REQUIRED)} dependencies verified.")
```

**Why This Matters**: Without fail-fast, a missing dependency in Cell C causes a cryptic error in Cell F — after 30+ minutes of model loading and inference. Fail-fast catches it in 10 seconds.

---

## 7. Environment Variable Propagation for Subprocess

**When**: Using conda isolation or any setup where the notebook Python differs from subprocess Python.

```python
import os, subprocess

# Store verified Python path
_MODEL_PYTHON = "/usr/local/bin/python"
os.environ["_MODEL_PYTHON"] = _MODEL_PYTHON

# Patch upstream scripts that use bare `python` / `pip`
def patch_script(script_path):
    with open(script_path) as f:
        content = f.read()
    content = content.replace("python ", f"{_MODEL_PYTHON} ")
    content = content.replace("pip ", f"{_MODEL_PYTHON} -m pip ")
    with open(script_path, "w") as f:
        f.write(content)

# Use in subprocess calls
subprocess.run(
    [_MODEL_PYTHON, "inference.py", "--input", input_path],
    env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"},
    check=True
)
```

**Why**: Colab base Python != conda Python. Bare `python` in shell scripts resolves to the wrong interpreter, causing silent import failures.

---

## 8. Pipeline Caching (GPU Object Transplant)

**When**: Notebook cells re-run frequently during development. Model loading takes 20+ seconds.

```python
#@title F) Run Inference
import importlib

# Check for cached pipeline from previous cell runs
_cache_key = "_cached_pipeline"
if _cache_key in globals():
    print("Using cached pipeline (instant)")
    pipeline = globals()[_cache_key]
else:
    print("Loading pipeline from scratch...")
    pipeline = load_model()  # 20+ seconds
    globals()[_cache_key] = pipeline

# Run inference with (potentially patched) code
result = pipeline.predict(input_data)
```

**Benefit**: First run ~20s (full model load), subsequent runs <1s (code changes only, GPU model persisted).

---

## Decision Checklist for New Recipes

When starting a new porting project, evaluate in this order:

1. **Check `colab-runtimes/SUMMARY.md`** — Does any runtime have matching versions?
2. **Identify C extensions** — Does the model need spconv, nvdiffrast, custom CUDA kernels?
   - If yes and pip fails → conda isolation
3. **Identify build-heavy deps** — flash-attn, xformers, detectron2?
   - If build fails → check for shim (SDPA) or pre-built wheel
4. **Test on 2 runtimes** — Latest (2026.01) + fallback (2025.07)
5. **Document every failure** in `context.md` — even failed attempts help future porters
6. **Add fail-fast verification** — Cell after deps, before inference
7. **Design for re-runnability** — Pipeline caching, idempotent cells, skip-on-restart

---

## Anti-Patterns (What Doesn't Work)

| Anti-Pattern | Why It Fails | Instead |
|--------------|-------------|---------|
| `pip install numpy<2` on Colab | C extension ABI crash | Keep Colab default |
| `pip install torch==X` in base env | Breaks CUDA-dependent packages | Use Colab stock or conda |
| Building flash-attn from source | 10+ min build, then fails | SDPA shim |
| Single `pip install -r requirements.txt` | Cascade conflicts | Install one-by-one, check each |
| `str.replace()` without assert | Silent no-op on format change | Always assert after patch |
| Bare `python` in subprocess | Wrong interpreter in conda | Explicit `_MODEL_PYTHON` path |
| Test at end of pipeline | 30 min wasted on missing dep | Fail-fast after install cells |
| `snapshot_download(repo_id)` on a multi-variant HF repo | Pulls every variant + every precision — disk fills (flux2 FLUX.2-dev is 152 GB total) | `hf_hub_download(repo_id, filename="ae.safetensors")` for single files, or `allow_patterns=["*.bf16.safetensors"]` to filter |
| Trust upstream `scripts/cli.py` blindly | Often force-loads extras (moderation / upsampling / safety models) that bloat GPU/disk (flux2 klein-4b: cli force-loaded 15 GB Mistral Small for safety checks) | Audit `cli.py` imports + top-level dict registries (e.g. FLUX2_MODEL_INFO); if the CLI loads things you don't need, bypass it and call the library's sampling primitives directly. Save 20+ GB and 60+ s startup |
| Test artifact by URL parsing alone | URL returned ≠ content ready. A Gradio submit + SSE `complete` can still yield a dead file URL | Do the full round-trip: `GET <url>` → verify `Content-Type` + magic bytes (e.g. `b"\x89PNG"`) + size > threshold |
| Leave failed/debug cells in the live Colab notebook after replacing them | User sees two Gradio iframes / dead share URLs / noisy `/colab-mcp-sync` diffs, and state-from-top re-runs execute the broken version | `delete_cell` the failed one as soon as the replacement works. `colab-mcp` skill codifies this |
| Skip per-cell local backup during live MCP work | Single Colab tab close / runtime disconnect = all work lost (colab-mcp has NO save-to-Drive tool) | After every successful `run_code_cell`, CALL `get_cells(0,N)`. The PostToolUse hook `_mcp_session_log.py` then writes `latest-cells.json` + a timestamped snapshot atomically (widened 2026-04-20, pruned to last 20 on 2026-04-21). The write is deterministic; the `get_cells` call itself is still your responsibility — the hook can't fire a snapshot until you request the payload. |

---

## CLI Audit Checklist (before relying on upstream `cli.py`)

When porting a new model, treat the upstream CLI as a **reference**, not a
sacred entrypoint. Before wiring `cli.main()` into your notebook:

1. **Imports**: read the top of `scripts/cli.py`. Any `from <package>.<module> import X` that
   references something you don't need? (Safety check models, prompt upsampling clients, API
   dependencies.) If yes → bypass candidate.
2. **Registries**: look for top-level dicts (`MODEL_INFO`, `CONFIGS`, etc.). Does entering your
   model name trigger auto-loading of dependencies you don't want? (flux2 klein-4b loads dev
   Mistral Small unconditionally — 15 GB.)
3. **Interactive blocks**: `input()` loops will hang in Colab. Look for `while True:` with
   `try: line = input(...)`. Use `single_eval=True` or similar non-interactive flags if
   available; bypass entirely otherwise.
4. **Side-effecting imports**: `cli.py`'s `from X import Y` may trigger downloads or GPU allocations
   at import time. If `import cli` itself is slow, inspect why.
5. **Download strategy**: if the CLI calls `snapshot_download("big-repo")`, it likely pulls
   everything. Map out which specific files you actually need (via `huggingface_hub.list_repo_files`)
   and `hf_hub_download` them individually.

Rule of thumb: **if the CLI's "simplest usage" is > 50 lines of setup, you'll bypass it within
the first 2 debug cycles anyway. Do it upfront.**

---

> **Contributing**: When you discover a new pattern, add it here with:
> when to use, code example, verified results, and known pitfalls.
