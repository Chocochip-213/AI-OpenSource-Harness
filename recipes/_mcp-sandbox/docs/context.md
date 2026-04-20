# Context — _mcp-sandbox

## Architecture
Browser → Colab runtime (T4) ← colab-mcp server (uvx, Python 3.13) ← Claude Code (stdio).

No model weights. The notebook does:
1. Preflight (GPU + VRAM assert — auto-injected by generate_notebook.py)
2. `import torch`
3. `torch.randn(1024, 1024, device="cuda") @ torch.randn(1024, 1024, device="cuda")`
4. Print result shape + max abs value

## Dependencies
| Package | Upstream Ver | Colab Stock (2025.07) | Strategy |
|---------|-------------|-----------------------|----------|
| torch | (sandbox) | 2.6.0+cu124 | keep |

No other deps — sandbox imports only torch from Colab's stock.

## Key Decisions
_Filled in as Phase 2 execution surfaces real behavior._

## Discovered Issues
| Error | Root Cause | Fix | Verified |
|-------|-----------|-----|----------|
|       |           |     |          |

Expected classes of surprise to watch for:
- `claude mcp list` shows `disconnected` until first tool call (by design — stdio)
- `open_colab_browser_connection` 60s timeout if browser not signed into Colab
- T4 requested, L4/V100 allocated (peak hours) → preflight assert warns, does not fail
- Dynamic tool list arrives with names we did not predict (actual names are set by
  the Colab browser frontend JS, not the Python MCP server we analyzed)

## Risks
| Risk | Prob | Mitigation |
|------|------|------------|
| uvx v1.0.2 fails to install on first run | medium | `uv cache clean` + `uvx --reinstall` |
| Browser profile not signed into Colab | medium | Sign in manually, retry |
| `claude` process binds to old `.mcp.json` (not our new one) | low | Confirm `claude mcp list` output before proceeding |

## Decision Log (reversals allowed)
| Date | Decision / Reversal | Reason |
|------|---------------------|--------|
| 2026-04-20 | Created sandbox recipe for Phase 2 E2E validation | End of Phase 1 (enforcement complete) required real-handshake proof before any real model ports |

## Artifact Locations
| Path | Contents | Gitignored? |
|------|----------|-------------|
| `outputs/notebooks/_mcp-sandbox.ipynb` | Generated sandbox notebook | Yes |
| `outputs/mcp-sessions/_mcp-sandbox/<session>.jsonl` | Per-call MCP session log | Yes |
| `outputs/mcp-sessions/_mcp-sandbox/latest-cells.json` | Live-cell dump for /colab-mcp-sync | Yes |
