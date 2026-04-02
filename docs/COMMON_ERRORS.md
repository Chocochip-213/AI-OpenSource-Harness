# Common Errors — Colab Porting Reference

> Verified across 5 real porting projects (FLUX.2, SwiftTry, TRELLIS.2, UniRig, SAM3D Body).
> Each entry was encountered and resolved in actual Colab sessions.

## C Extension / Native Build Errors

### 1. cumm JIT Build Failure (spconv)

**Symptom**:
```
ImportError: cannot import name 'tensorview' from cumm
cumm JIT build: tensorview/pybind_utils.h not found
```

**Root Cause**: `cumm` wheel lacks prebuilt `.so` files. Its `__init__.py` always attempts JIT compilation, which fails because C++ headers are missing in the Colab environment.

**What Doesn't Work**:
- Downgrading `spconv-cu126` to `spconv-cu124` (same cumm error)
- Pre-installing `cumm` explicitly (JIT still triggers)

**Fix**: Conda isolation via `condacolab`. See [Porting Patterns: Conda Isolation](PORTING_PATTERNS.md#3-conda-isolation-condacolab).

**Verified on**: Colab 2026.01 (torch 2.9.0+cu126), 2025.07 (torch 2.6.0+cu124) with condacolab fix.

---

### 2. Pillow C Extension Mismatch

**Symptom**:
```
ImportError: cannot import name '_Ink' from 'PIL._typing'
```

**Root Cause**: `pip install Pillow==11.x` replaces the `.so` file but Colab's pre-loaded Python process still holds the old C extension in memory. In-process `.so` reload is impossible in CPython.

**Fix**: Do NOT pip-upgrade Pillow. Use Colab's stock version. If your code requires a specific Pillow API, write a thin wrapper.

---

### 3. numpy ABI Mismatch After Downgrade

**Symptom**:
```
SIGABRT / illegal instruction during numpy operation
ValueError: numpy dtype mismatch
```

**Root Cause**: Colab's torch is compiled against numpy 2.x ABI. Downgrading numpy to 1.x creates a binary incompatibility that causes crashes at the C level.

**Fix**: Never downgrade numpy on Colab. If upstream requires `numpy<2`, check if the code actually uses numpy 2-incompatible APIs (most code is forward-compatible). If truly incompatible, use conda isolation.

---

### 4. flash-attn Build Failure

**Symptom**:
```
error: command '/usr/local/cuda/bin/nvcc' failed
Building wheel for flash-attn (setup.py) ... error (takes 10+ minutes before failing)
```

**Root Cause**: Colab's CUDA toolkit is incomplete for building flash-attn from source. Compilation flags are incompatible.

**Fix**: Use SDPA (Scaled Dot-Product Attention) shim. See [Porting Patterns: Shim/Monkey-Patch](PORTING_PATTERNS.md#4-shim--monkey-patch).

---

### 5. xformers Torch Version Escalation

**Symptom**:
```
pip install xformers → silently upgrades torch to a different version (unwanted)
```

**Root Cause**: `xformers` has strict torch version pinning. Installing it can silently upgrade torch, breaking other dependencies.

**Fix**: Pin torch version when installing xformers:
```bash
pip install xformers torch==2.6.0+cu124 --index-url https://download.pytorch.org/whl/cu124
```
Or use the xformers version that matches your Colab torch (check `colab-runtimes/SUMMARY.md`).

---

## Import / Module Errors

### 6. Florence-2 Broken on transformers 5.x

**Symptom**:
```
RuntimeError: lm_head weight tying produces garbage output
# or
ImportError: cannot import Florence2 with trust_remote_code
```

**Root Cause**: Florence-2's `lm_head` weight tying mechanism is structurally broken when using transformers >= 5.0 (manually installed; Colab ships 4.57.x as of 2026.01). The `tie_weights()` function exists but isn't called during pipeline initialization, causing the projection head to use random weights.

**Affected variants**:
- `MiaoshouAI/Florence-2-*`: Only works with `transformers<=4.49`
- `florence-community/Florence-2-*`: `lm_head` dtype mismatch in 5.x

> Note: As of Colab 2026.01, the stock transformers is 4.57.x. This issue arises when manually installing `transformers>=5.0`.

**Fix**: Use `Qwen2.5-VL` or similar VLM that natively supports transformers 5.x.

---

### 7. Jupyter `notebook.utils` Import Conflict

**Symptom**:
```python
from notebook.utils import setup_function  # Gets Jupyter's notebook package, not yours
```

**Root Cause**: Colab has `notebook` (Jupyter) pre-installed. If your upstream repo also has a `notebook/` directory, Python resolves to Jupyter's package first.

**Fix**: Use explicit path import:
```python
import importlib.util
spec = importlib.util.spec_from_file_location(
    "my_utils", "/content/my-repo/notebook/utils.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
```

---

### 8. torch.load weights_only Error (PyTorch 2.6+)

**Symptom**:
```
UnpicklingError: Weights only load denies class 'box.Box'
```

**Root Cause**: PyTorch 2.6 changed `torch.load()` default to `weights_only=True`. Checkpoints containing non-tensor objects (e.g., `box.Box`, custom config classes) are blocked.

**Fix**:
```python
import torch
from box import Box  # or whatever class the checkpoint uses
torch.serialization.add_safe_globals([Box])
# Now torch.load works
```

---

### 9. importlib.metadata PackageNotFoundError for Shim Modules

**Symptom**:
```
PackageNotFoundError: No package metadata was found for flash_attn
```

**Root Cause**: `transformers` uses `importlib.metadata.version('flash_attn')` to auto-detect attention implementation. A shim module without `.dist-info` metadata causes this check to crash.

**Fix**: Create fake metadata:
```python
import os, site
site_dir = site.getsitepackages()[0]  # Adapts to Python version automatically
dist_info = "flash_attn-0.0.0.dist-info"
os.makedirs(f"{site_dir}/{dist_info}", exist_ok=True)
with open(f"{site_dir}/{dist_info}/METADATA", "w") as f:
    f.write("Metadata-Version: 2.1\nName: flash-attn\nVersion: 0.0.0\n")
```

---

### 10. Stale Module File Shadows Package Directory

**Symptom**:
```python
import flash_attn  # imports flash_attn.py file instead of flash_attn/ package directory
```

**Root Cause**: A leftover `flash_attn.py` file in `site-packages/` takes precedence over the `flash_attn/` package directory in Python's import resolution.

**Fix**: Delete the stale file before creating/installing the package:
```python
import os, glob, site
site_dir = site.getsitepackages()[0]
stale = os.path.join(site_dir, "flash_attn.py")
if os.path.exists(stale):
    os.remove(stale)
```

---

## CUDA / GPU Errors

### 11. libcusparseLt.so.0 Not Found

**Symptom**:
```
OSError: libcusparseLt.so.0: cannot open shared object file
```

**Root Cause**: In conda-isolated environments, `LD_LIBRARY_PATH` doesn't include nvidia's library paths. pip subprocess builds also lose this path.

**Fix**:
```python
import os, site
nvidia_lib = os.path.join(site.getsitepackages()[0], "nvidia")
lib_dirs = []
for pkg in os.listdir(nvidia_lib):
    lib_path = os.path.join(nvidia_lib, pkg, "lib")
    if os.path.isdir(lib_path):
        lib_dirs.append(lib_path)
os.environ["LD_LIBRARY_PATH"] = ":".join(lib_dirs) + ":" + os.environ.get("LD_LIBRARY_PATH", "")
```

---

### 12. torchvision::nms C++ Ops Not Registered

**Symptom**:
```
RuntimeError: operator torchvision::nms not found
```

**Root Cause**: In conda-isolated environments, `torchvision` may be installed without its C++ extensions registered in the current Python interpreter.

**Fix**: Uninstall and reinstall torchvision for the correct CUDA version:
```bash
pip uninstall torchvision -y
pip install torchvision --index-url https://download.pytorch.org/whl/cu124
```

---

### 13. CUDA Architecture Mismatch

**Symptom**:
```
CUDA error: no kernel image is available for execution on the device
```

**Root Cause**: Pre-compiled CUDA kernels target a different GPU architecture (e.g., sm_80 for A100 vs sm_120 for Blackwell).

**Fix**: Set `TORCH_CUDA_ARCH_LIST` before building:
```bash
export TORCH_CUDA_ARCH_LIST="8.0"  # A100
# or
export TORCH_CUDA_ARCH_LIST="8.0;8.6;9.0"  # Multi-arch
```

---

## condacolab-Specific Errors

### 14. condacolab Fails on Python 3.12

**Symptom**: `condacolab.install()` silently fails or hangs on Colab runtime 2026.01+.

**Root Cause**: condacolab 0.1.x is unmaintained; Python 3.12 compatibility was never added (GitHub issue #74).

**Fix**: Use Colab runtime **2025.07** (Python 3.11). Select via: Runtime > Change runtime type > Runtime version.

---

### 15. sys.executable Points to Wrong Python After condacolab

**Symptom**: After `condacolab.install()`, `sys.executable` still returns the original (non-conda) Python path.

**Root Cause**: condacolab creates a bash wrapper script at the original Python path. `sys.executable` reads the wrapper path, not the actual conda binary.

**Fix**: Use explicit path and store in env var:
```python
import os
_MODEL_PYTHON = "/usr/local/bin/python"
os.environ["_MODEL_PYTHON"] = _MODEL_PYTHON
# Use _MODEL_PYTHON for all subprocess calls
```

---

### 16. condacolab Cell Re-run After Kernel Restart

**Symptom**: Running Cell B (condacolab install) again after kernel restart re-triggers install, wasting time or causing errors.

**Root Cause**: condacolab checks for `mamba` in PATH to decide whether to skip. But the check may pass even when the install is incomplete.

**Fix**: Add explicit skip detection at the top of the install cell:
```python
import shutil
if shutil.which("mamba") and os.path.exists("/usr/local/bin/python"):
    print("condacolab already installed, skipping")
else:
    import condacolab
    condacolab.install()
```

---

## Diffusers / Model-Specific Errors

### 17. diffusers Private API Breakage (Version Downgrade)

**Symptom**:
```
ImportError: cannot import name 'CaptionProjection' from 'diffusers.models.embeddings'
ImportError: cannot import name 'DualTransformer2DModel'
```

**Root Cause**: Models pinned to older diffusers (e.g., 0.24) use internal APIs that were reorganized in newer versions.

**Fix**: Create a compatibility patch file:
```python
# patches/fix_diffusers_compat.py
import importlib, re

# Patch import paths that moved between diffusers versions
PATCHES = [
    (r'from diffusers\.models\..*CaptionProjection',
     'from diffusers.models import CaptionProjection'),
    (r'from diffusers\.models\..*DualTransformer2DModel',
     'from diffusers.models import DualTransformer2DModel'),
]

def patch_file(filepath):
    with open(filepath) as f:
        content = f.read()
    for pattern, replacement in PATCHES:
        content = re.sub(pattern, replacement, content)
    with open(filepath, 'w') as f:
        f.write(content)
```

---

### 18. FLUX.2 Prompt Weighting Ignored

**Symptom**: `(oversized:1.5)` or `(keyword:weight)` syntax has no effect.

**Root Cause**: FLUX.2 does not support prompt weighting syntax. Unlike Stable Diffusion, FLUX.2's text encoder treats the entire prompt as natural language.

**Fix**: Use natural language emphasis instead. Restructure prompts to front-load important concepts (decoder-only LLM positional bias means earlier words carry more weight).

---

### 19. FLUX.2 Negative Prompts Ignored

**Symptom**: Adding negative prompts causes the model to generate exactly what you tried to avoid.

**Root Cause**: FLUX.2's architecture does not support negative prompting. "Don't generate X" is interpreted as "generate X" by the text encoder.

**Fix**: Use positive framing: "plain undecorated surface" instead of "no logos".

---

### 20. BiRefNet meta tensor Error (accelerate + SwinTransformer)

**Symptom**:
```
RuntimeError: item() cannot be called on meta tensors
```

**Root Cause**: `accelerate`'s `init_empty_weights()` creates meta tensors. Models using `SwinTransformer` that call `.item()` during initialization crash.

**Fix**: Skip the preprocessing step that uses this model:
```python
pipeline = Pipeline.from_pretrained(model_id, preprocess_image=False)
# User provides RGBA cutout directly instead of relying on BiRefNet
```

---

## Notebook / Colab Environment Errors

### 21. PyOpenGL Display Server Missing

**Symptom**:
```
RuntimeError: No OpenGL context available
```

**Root Cause**: Colab has no X11 display server.

**Fix**:
```bash
!apt-get install -y libosmesa6-dev
```
```python
import os
os.environ['PYOPENGL_PLATFORM'] = 'osmesa'
```

---

### 22. Korean / Unicode Filenames in Colab Upload

**Symptom**: `cv2.imread()` returns `None` for uploaded files with Korean names.

**Root Cause**: OpenCV's file I/O doesn't handle non-ASCII paths reliably.

**Fix**: Rename to ASCII immediately after upload:
```python
import os, shutil
for f in uploaded.keys():
    safe_name = "input_image" + os.path.splitext(f)[1]
    shutil.move(f, safe_name)
```

---

### 23. Detectron2 Build Conflicts with Colab torch

**Symptom**: `pip install detectron2` tries to build from source and fails.

**Fix**: Install from specific commit with no build isolation:
```bash
# @a1ce2f9: verified compatible with torch 2.6-2.9 + cu124/cu126
# Check for newer compatible commits if using a different torch version
pip install 'git+https://github.com/facebookresearch/detectron2.git@a1ce2f9' \
  --no-build-isolation --no-deps
```
`--no-build-isolation` links against pre-installed torch; `--no-deps` skips dependency resolution.

---

## 3D / Mesh Export Errors

### 24. GLB "Dust" / Colorful Noise in 3D Export

**Symptom**: Exported GLB renders as scattered colorful dots instead of a solid mesh.

**Root Cause** (3 co-occurring issues):
1. xformers ABI mismatch (e.g., xformers 0.0.35 built for torch 2.10, running on torch 2.6)
2. Sampler parameters not explicitly passed (guidance_strength, guidance_rescale use wrong defaults)
3. Mesh decimation too aggressive (100K faces insufficient; need 300K+)

**Fix**:
- Force PyTorch native SDPA instead of xformers
- Pass all sampler parameters explicitly
- Set decimation to 300K+ faces

---

### 25. Vertex Fragmentation After Rigging

**Symptom**: Posed mesh shatters — vertices at the same position move differently.

**Root Cause**: Generated meshes (e.g., from Trellis) use per-face UV islands, creating ~83% duplicate vertices at the same position. When rigging tools assign different weights to co-located vertices, the mesh fragments when deformed.

**Fix**: Weight sync post-processing — group vertices by position, copy weights from the canonical vertex to all duplicates:
```python
import numpy as np
eps = 1e-4
keys = np.round(positions / eps).astype(np.int64)
# Hash → group → sync weights within each group
```

---

## Configuration / Pipeline Errors

### 26. Config Patch Silent Failure

**Symptom**: `str.replace()` on config file appears to work but model still uses old config.

**Root Cause**: Config format changed between versions (e.g., YAML key renamed). The replacement string doesn't match, `replace()` returns unchanged string silently.

**Fix**: Always assert after config patching:
```python
original = config_text
config_text = config_text.replace("flash_attention_2", "eager")
assert config_text != original, "Config patch failed — target string not found"
```

---

### 27. HuggingFace from_pretrained Interprets Local Path as Repo ID

**Symptom**:
```
OSError: <model-name> is not a valid git identifier
```

**Root Cause**: `from_pretrained("relative/path")` is interpreted as a HuggingFace Hub repo ID, not a local path.

**Fix**: Use `snapshot_download()` to get absolute local path first:
```python
from huggingface_hub import snapshot_download
local_path = snapshot_download("org/model-name")
model = Model.from_pretrained(local_path)
```

---

> **Contributing**: When you encounter a new Colab-specific error during porting, add it here with:
> symptom, root cause, what doesn't work, and the verified fix.
