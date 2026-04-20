"""Inference handler for {RECIPE_NAME}.

Single function `infer()` that loads the model lazily and returns the
prediction. This is the **canonical entry point** for both:

  1. The Gradio cell auto-injected by `tools/generate_notebook.py` when
     `recipe.yaml:mcp.serve_via_gradio: true` (Colab demo + Spring backend
     calls this via Gradio share URL).
  2. A local script `python -m exports.inference_handler` (only works if
     you have the GPU; the team plan is "GPU=Colab; local=compatibility-
     only, not actually run").

DO NOT add a web framework here. Gradio (Colab) and any future runtime
(FastAPI / Modal / TorchServe) wrap THIS function. Keep the surface
single-function so all wrappers stay trivial.
"""
from __future__ import annotations

import os
from typing import Any

# ---- Lazy globals — model is loaded once per process ----
_model: Any = None
_loaded: bool = False


def _load_model() -> Any:
    """Load model weights + any preprocessor. Called once.

    TODO recipe author: replace with the actual model load. Read paths
    from env vars rather than hardcoding so the same code works on Colab
    (weights from HuggingFace cache) and a future server (weights from
    `MODEL_WEIGHTS_DIR`).
    """
    global _model, _loaded
    if _loaded:
        return _model
    # Example placeholder:
    # import torch
    # from transformers import AutoModel, AutoProcessor
    # processor = AutoProcessor.from_pretrained(os.environ.get("MODEL_ID", "<hf-id>"))
    # model = AutoModel.from_pretrained(os.environ.get("MODEL_ID", "<hf-id>")).cuda().eval()
    # _model = (model, processor)
    _model = None  # <!-- FILL -->
    _loaded = True
    return _model


def infer(*args: Any, **kwargs: Any) -> Any:
    """Run a single prediction.

    Signature (positional args + return type) IS the API contract — keep
    it stable, or bump `recipe.yaml:version` when it changes. The Gradio
    cell + `gradio_api.schema.json` are generated from this signature.

    Recipe authors: replace this stub with real logic. Document the
    request/response shape in `model_card.md` and `gradio_api.schema.json`.
    """
    _ = _load_model()
    # <!-- FILL — replace with real inference -->
    # Example:
    #   model, processor = _model
    #   image = args[0]
    #   inputs = processor(image, return_tensors="pt").to("cuda")
    #   with torch.no_grad():
    #       result = model(**inputs)
    #   return {"prediction": result.logits.argmax(-1).item()}
    return {"echo": list(args), "kwargs": kwargs}


# ---- Local CLI (compatibility only — team plan: never actually run locally) ----
if __name__ == "__main__":
    import json
    import sys
    raw = sys.stdin.read().strip() or "{}"
    payload = json.loads(raw)
    args = payload.get("args", [])
    kwargs = payload.get("kwargs", {})
    print(json.dumps(infer(*args, **kwargs), default=str))
