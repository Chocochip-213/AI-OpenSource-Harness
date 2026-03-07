# Context

## Architecture

<!-- Model/pipeline architecture overview -->

## Dependencies

| Package | Upstream | Colab Stock | Strategy |
|---------|----------|-------------|----------|
| Python | <!-- 3.10 --> | <!-- 3.11 --> | <!-- direct / conda --> |
| PyTorch | <!-- 2.6.0/cu124 --> | <!-- 2.6.0/cu124 --> | <!-- keep stock / pip --> |
| CUDA | <!-- 12.4 --> | <!-- 12.4 --> | <!-- host toolkit --> |
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
