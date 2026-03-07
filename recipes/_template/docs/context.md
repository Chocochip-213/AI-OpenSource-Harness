# Context

## Architecture

<!-- Model/pipeline architecture overview -->

## Dependencies

<!-- Check colab-runtimes/runtimes.json for actual Colab stock versions -->
| Package | Upstream | Colab Stock | Strategy |
|---------|----------|-------------|----------|
| Python | <!-- e.g. 3.10 --> | <!-- check runtimes.json --> | <!-- direct / conda --> |
| PyTorch | <!-- e.g. 2.6.0/cu124 --> | <!-- check runtimes.json --> | <!-- keep stock / pip --> |
| CUDA | <!-- e.g. 12.4 --> | <!-- check nvidia-smi on Colab --> | <!-- host toolkit --> |
| <!-- key dep --> | <!-- version --> | <!-- version --> | <!-- pip / patch --> |

## Colab Compatibility

### Install Strategy
<!-- Direct pip (lightweight) or conda isolation (heavy/native ext) -->

### Known Conflicts
<!-- Package version conflicts with Colab's pre-installed packages -->

### Fallback Backends
<!-- e.g., ATTN_BACKEND=xformers, SPARSE_CONV_BACKEND=spconv -->

### Lazy Imports
<!-- Imports deferred to avoid missing-package crashes -->

## Key Decisions

<!-- Record every decision with rationale:
### Decision: [what]
- **Context**: [why this came up]
- **Options**: [what was considered]
- **Choice**: [what was chosen and why]
-->

## Discovered Issues

<!-- Errors found during Colab testing:
| Error | Root Cause | Fix |
|-------|-----------|-----|
-->

## Risks

| Risk | Prob | Impact | Mitigation |
|------|------|--------|------------|
| <!-- risk --> | <!-- H/M/L --> | <!-- impact --> | <!-- mitigation --> |

## References

- <!-- [Upstream repo](https://github.com/...) -->
- <!-- [Issue #N](https://github.com/.../issues/N) -->

---

> **Rule**: When a decision is made during implementation, add it to "Key Decisions" with the reasoning.
