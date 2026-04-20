---
name: colab-debugging
description: Use when a Colab cell fails with ImportError, ModuleNotFoundError, RuntimeError, pip install failure, CUDA version mismatch, OOM / illegal memory access, C extension build failure (spconv/nvdiffrast/flash-attn), .so ABI conflict, xformers/diffusers version conflicts, or when user says "doesn't work in Colab" / "코랩 안 돼". Checks colab-runtimes/runtimes.json for pre-installed package versions before recommending pins. Considers runtime rollback, selective downgrade, SDPA shim, and conda isolation strategies in that order of simplicity. Delegates complex multi-package conflicts to compat-debugger sub-agent.
allowed-tools: Read Grep Glob Bash
---

# Skill: colab-debugging

## When Active
Triggered on install failures, import errors, package conflicts, CUDA/GPU issues in Colab.

## Diagnosis Steps
1. **Identify Colab runtime version**: Check which runtime the user is on (Runtime > Change runtime type > Runtime version). Refer to `colab-runtimes/runtimes.json` for pre-installed package versions.
2. **Compare upstream requirements vs Colab stock**: Does the model need a specific torch/CUDA version? Check `colab-runtimes/<version>/packages.json` for exact versions.
3. **Check recipe requirements**: Review `requirements_opt1.txt` / `requirements_opt2.txt` for version pins and potential conflicts.
4. **Identify conflict type**: Is it a Python version issue? CUDA version mismatch? C extension (.so) conflict? Package version incompatibility?
5. **Consider runtime rollback**: Colab supports past runtimes. If the model's torch version matches an older runtime, suggest rollback before attempting complex fixes.

## Conflict Types to Investigate
| Symptom | Possible Cause | Investigation |
|---------|---------------|---------------|
| `ImportError` after pip install | C extension (.so) linked to wrong lib version | Check if pre-loaded .so conflicts with pip-installed version |
| `illegal memory access` | CUDA/torch version mismatch | Compare `nvidia-smi` CUDA vs torch CUDA build |
| `ModuleNotFoundError` | Package not installed or wrong Python | Verify `sys.executable` and install target match |
| Build failure (`pip install --no-build-isolation`) | Missing build deps or ABI mismatch | Check CUDA toolkit, compiler version, torch ABI |
| OOM / Killed | VRAM or RAM exhaustion | Check model size vs GPU VRAM (T4=15GB, L4=24GB, A100=40/80GB) |

## Strategy Options (verify each in Colab before confirming)
- **Direct pip**: Simplest. Works when model deps are close to Colab stock versions.
- **Runtime rollback**: Change runtime version to one with matching torch/Python.
- **Conda isolation (condacolab)**: For heavy native extension models. Untested combos may fail.
- **Environment variable overrides**: `ATTN_BACKEND`, `SPARSE_CONV_BACKEND` etc. to skip hard-to-build deps.
- **Lazy import patches**: Defer imports of unavailable C extensions until actually needed.

## Key Reference
- `colab-runtimes/SUMMARY.md` — Side-by-side package comparison across runtime versions
- `colab-runtimes/<version>/packages.json` — Full package list for a specific runtime
- Upstream: https://github.com/googlecolab/backend-info

## Escalation
Use the `compat-debugger` agent for complex multi-package resolution.
