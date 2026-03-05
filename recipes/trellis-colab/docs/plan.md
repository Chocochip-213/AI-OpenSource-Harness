# Plan

## Goal
Build a TRELLIS.2-focused Colab recipe incrementally, using strict checkpoints.
Each checkpoint must be validated locally first, then verified on Colab when GPU/runtime evidence is required.

## Scope
In scope:
- CP0 recipe scaffold and SSOT docs
- CP1 Colab bootstrap and runtime diagnostics
- CP2 TRELLIS minimum inference PoC
- CP3 output artifact validation
- CP4 post-process MVP (optimization-first subset)
- CP5 notebook-manifest integration
- CP6 repeatable runbook and handoff checklist

Out of scope for initial passes:
- Full production backend integration
- Full WebAR runtime implementation
- Fine-tuning TRELLIS models

## Approach
1. Use `../TrellisDocs` as planning/research source.
2. Keep this recipe docs triad as implementation SSOT.
3. Execute one checkpoint at a time.
4. For each checkpoint:
   - Agent local pre-check
   - User Colab run (if runtime/GPU proof required)
   - Gate decision to proceed
5. Update `tasks.md` immediately after each checkpoint.

## Success Criteria
- Every checkpoint has explicit pass/fail criteria.
- Colab-only checkpoints include user-provided evidence:
  - executed cells
  - tail logs
  - output file listing
  - screenshot(s) when needed
- Final notebook can be executed end-to-end in Colab with documented fallback steps.
