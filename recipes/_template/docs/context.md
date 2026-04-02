# Context

## Architecture
<!-- Input → [stages] → Output
Example:
  Photo → [VLM Caption] → [Preprocessing] → [Diffusion Model] → Output Image
-->

## Dependencies
| Package | Upstream Ver | Colab Stock | Strategy |
|---------|-------------|-------------|----------|
|         |             |             |          |

<!-- Strategy values:
  - keep     — Colab default matches or is compatible
  - pin      — Specific version required (document why)
  - upgrade  — pip install newer than Colab stock
  - downgrade+patch — Older version needed, apply compat patch
  - shim     — Build fails, use torch-native substitute (e.g. flash-attn → SDPA)
  - conda    — Requires conda isolation (C extension conflict)
  - skip     — Not needed for inference (e.g. training-only dep)

  Check colab-runtimes/SUMMARY.md before deciding.
-->

## Key Decisions
<!-- Record every major decision with context + outcome.
Format:

### Decision title
- **Context**: What problem led to this decision
- **Options considered**: What alternatives were evaluated
- **Choice**: What was chosen and why
- **Outcome**: Result (PASS/FAIL, metrics, trade-offs)

Example:
### Florence-2 → Qwen2.5-VL replacement
- **Context**: Florence-2 lm_head weight tying broken on transformers 5.x
- **Options**: MiaoshouAI (max 4.49), florence-community (dtype bug), Qwen2.5-VL (native 5.x)
- **Choice**: Qwen2.5-VL-3B — native transformers 5.x, flash attention 2, bf16
- **Outcome**: Better captioning quality + no version constraint
-->

## Discovered Issues
| Error | Root Cause | Fix | Verified |
|-------|-----------|-----|----------|
|       |           |     |          |

<!-- Document every error encountered during Colab testing.
Include errors that were RESOLVED — they help future porters.
Check docs/COMMON_ERRORS.md first; add new entries there if generalizable.
-->

## Risks
| Risk | Prob | Mitigation |
|------|------|------------|
|      |      |            |

---
> Record decisions here as they happen. Every decision should have a "why" — not just "what."
> Failed experiments are as valuable as successes. Document what didn't work and why.
