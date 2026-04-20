# Plan — _mcp-sandbox

## Goal
Prove that Claude Code + colab-mcp + live Colab runtime actually talks
end-to-end, before any real model porting depends on the integration.

The work is deliberately trivial — a torch matmul — so any failure is
attributable to the MCP pipeline, not to model-specific issues.

## Scope
**In scope**
- First `claude mcp list` output showing `colab-mcp` registered
- First `open_colab_browser_connection` handshake (browser popup)
- First `notifications/tools/list_changed` received after handshake
- One MCP-driven cell run that returns a non-trivial result (torch matmul)
- One `/colab-mcp-sync` round-trip (live → manifest)
- Collect every surprise into `docs/context.md` Discovered Issues

**Out of scope**
- Any real model weights, datasets, or GPU-intensive work
- `keepalive: true` (session intentionally short)
- Running on A100 (T4 is easier to allocate on the free tier)

## Target Environment

> These are the **sandbox minimums** — values chosen so Phase 2 validation
> works on a free Colab account. They are NOT a restriction. Colab's
> `Runtime > Change runtime type` lets the user pick any of
> `T4 / L4 / A100 / H100` (availability varies by tier). The preflight
> assert cell only fails if allocation is smaller than these minimums.

| Item | Minimum | Upgrades you can pick in Colab |
|------|---------|-------------------------------|
| GPU  | T4      | L4, A100, H100 (the matmul finishes in <1s on any of them) |
| VRAM | 8 GB    | Larger GPUs ship with 22–80 GB; preflight accepts anything ≥ 8 GB |
| Python | 3.11  | Also fine on 3.12 (runtimes 2025.10 / 2026.01 / 2026.04); the sandbox doesn't use anything runtime-specific |
| Colab Runtime | 2025.07 | Any current runtime works for torch matmul; 2025.07 is just the minimum tested |

If the allocated GPU is larger than T4, the auto-injected preflight cell
prints a `[warn]` about the mismatch with `mcp.preferred_gpu: T4` — that's
expected and informational, not a failure.

## Approach
1. `scripts/set_active_recipe.sh _mcp-sandbox` + `source .claude/.env`
2. Start `claude` (fresh process — required for `.mcp.json` to load)
3. `claude mcp list` — verify `colab-mcp` registered
4. `uv run python tools/generate_notebook.py _mcp-sandbox` — sanity check
5. Ask Claude: "Open the Colab connection and run the sandbox cells"
6. Approve browser popup
7. Watch `.claude/_mcp_tool_calls.log` + `outputs/mcp-sessions/_mcp-sandbox/*.jsonl`
   fill with real entries
8. Run `/colab-mcp-sync _mcp-sandbox` — dry-run then --apply
9. Collect findings into `docs/context.md`

## Success Criteria
- [ ] `claude mcp list` shows `colab-mcp` connected
- [ ] `open_colab_browser_connection` returns true (browser handshake)
- [ ] Cell A preflight passes (torch.cuda.is_available() == True)
- [ ] Cell B matmul returns expected shape
- [ ] `.claude/_mcp_tool_calls.log` has redacted entries for each call
- [ ] `outputs/mcp-sessions/_mcp-sandbox/<session>.jsonl` exists + has output records
- [ ] `/colab-mcp-sync _mcp-sandbox` dry-run reports a clean or reasonable diff
- [ ] No `DANGER` / secret leaks in the redacted logs
- [ ] Every surprise logged in `context.md` Discovered Issues
