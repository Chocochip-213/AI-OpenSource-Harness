# Skill: colab-debugging

## When Active
Triggered on install failures, import errors, package conflicts, CUDA/GPU issues.

## Diagnosis Steps
1. Check `requirements_opt1.txt` / `requirements_opt2.txt` for version pins.
2. Cross-reference with Colab's pre-installed packages (torch, transformers, numpy).
3. Look for conflicting specifiers across files (`grep -r "torch" recipes/<name>/`).
4. For GPU issues: verify CUDA toolkit version compatibility.

## Colab Environment Reference
| Resource | Free Tier | Pro Tier |
|----------|-----------|----------|
| Python   | 3.10-3.11 | 3.10-3.11 |
| GPU      | T4 (15GB) | A100/V100 |
| RAM      | 12GB      | 25-50GB |
| Disk     | ~100GB    | ~200GB |

## Common Fixes
- **torch version conflict**: Pin `torch>=2.1,<2.5` for Colab CUDA 12.x.
- **OOM**: Add `torch.cuda.empty_cache()` between inference steps.
- **ImportError**: Ensure install cell runs before import cell in notebook.

## Escalation
Use the `compat-debugger` agent for complex multi-package resolution.
