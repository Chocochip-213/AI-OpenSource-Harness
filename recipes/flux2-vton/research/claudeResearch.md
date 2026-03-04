# Size control for FLUX.2 Klein 9B virtual try-on

**Garment size differentiation in diffusion-based VTON is fundamentally a spatial-geometric problem, not a semantic one — every working solution in the literature controls size through mask manipulation and garment scaling, never through text prompts alone.** The fal VTON LoRA's "always fitted" behavior is not a bug but an inherent consequence of how all current VTON models are trained: on single-fit datasets where each garment appears in exactly one size per person. Six peer-reviewed papers from 2023–2025 confirm this and demonstrate concrete size control mechanisms, several of which can be adapted to FLUX.2 Klein 9B without retraining. The most immediately actionable path is a **two-pass pipeline** combining the existing LoRA for quality generation with mask dilation + latent-space masking for spatial size control.

---

## Why text prompts cannot control garment size

The impossibility of prompt-based size control is structural, not a limitation of prompt phrasing. In the fal VTON LoRA, the garment image is fed as a concatenated reference through FLUX.2's multimodal Qwen3-8B encoder — vision tokens from the garment image provide **far stronger spatial conditioning** than any text tokens describing size. The LoRA was trained on paired data where garments always appear "well-fitted," so the learned mapping from garment→output is invariant to size-related vocabulary. FLUX.2 Klein's text conditioning tensor has shape `[1, 512, 12288]` with only ~67 active tokens, while the reference latent occupies a separate `[1, 128, H, W]` channel that dominates spatial layout decisions.

The COTTON paper (ICCV 2023) states this explicitly: *"Previous works are conditioned on the clothing image by only considering the shape of the clothes without the scale information. Thus, given a clothing image, it is impossible for previous works to change the clothing size."* The SV-VTON paper (April 2025) further demonstrates that **models trained with tight masks generate tight-fitting results** — standard VTON datasets create an inescapable single-fit bias. CLIP-family and language model text encoders lack spatial precision for garment boundaries; as the MGD paper notes, *"text can convey specific attributes like style, color, and patterns of a garment, but may not provide sufficient information about its spatial characteristics."*

---

## The mask dilation strategy validated by six papers

**Mask size is the primary lever for garment size control across all working VTON size-control systems.** SV-VTON, SiCo, FitControler, COTTON, FitDiT, and PromptDresser all converge on the same core mechanism: manipulate the spatial mask that defines where the garment can appear, and the diffusion model fills the expanded or contracted region accordingly.

**SV-VTON** (arXiv 2504.00562, April 2025) provides the most detailed implementation. Its Multi-size Mask Generation Module uses morphological operations on a keypoint-derived base mask: iterative dilation controls garment looseness while closing operations refine boundaries. A parameter **λ** scales sizes: λ=1 for tight-fit, λ=2 for one size up, λ=3 for two sizes up. Gaussian smoothing (5×5 kernel) produces natural edges. The paper demonstrates **5–10% sizing error** against international garment standards, validated across three diffusion backbones (ReferenceNet, StableVITON, DCI-VTON). Crucially, SV-VTON controls two factors simultaneously — **mask size AND garment image proportion** — because adjusting both together produces the most realistic differentiation.

**FitControler** (arXiv 2512.24016, December 2025) takes a more principled approach with a learnable **fit-aware layout generator** that redraws the body-garment segmentation map conditioned on discrete fit labels (slim/regular/loose for tops; tapered/straight for bottoms). Its **multi-scale fit injector** delivers layout features to the VTON backbone via a ControlNet-style interface. Trained on the Fit4Men dataset (13,000 annotated body-garment pairs), it produces clearly distinguishable slim/regular/loose outputs. The key design insight is using a **rectangular mask** rather than body-fitted one to eliminate "garment shape leakage" — the tendency for models to reproduce the original garment's silhouette.

**SiCo** (arXiv 2408.02803, August 2024) maps standard size charts (XXS through XXL) to mask dimensions using body measurements, then uses SD + IP-Adapter + Canny ControlNet to inpaint garments within the sized mask. User studies with 48 participants showed significant improvement in size perception accuracy.

For FLUX.2 Klein 9B, the mask dilation approach is directly portable as preprocessing — no model retraining required. OpenCV morphological operations are all that's needed:

```python
import cv2
import numpy as np

def generate_sized_mask(base_mask, size_level):
    """size_level: 0=fitted, 1=M-to-L, 2=L-to-XL, 3=XL-to-2XL"""
    kernel = np.ones((5, 5), np.uint8)
    dilated = cv2.dilate(base_mask, kernel, iterations=size_level * 3)
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel, iterations=size_level)
    smoothed = cv2.GaussianBlur(closed, (5, 5), 0)
    return (smoothed > 127).astype(np.uint8) * 255
```

---

## Injecting masks into FLUX.2 Klein 9B without official support

The `Flux2KleinPipeline` in diffusers has **no `mask_image` parameter** — Issue #13005 requesting inpaint support remains open with no PR submitted. However, two concrete workarounds exist that bypass this limitation entirely.

**The `callback_on_step_end` hook** is the lowest-complexity approach (~20 lines of code). FLUX.2 Klein's pipeline exposes this callback, which fires after each denoising step and provides access to the current latent tensor. By blending the denoised latents with the original image latents using a mask, you achieve manual inpainting:

```python
def mask_inpaint_callback(pipe, step, timestep, callback_kwargs):
    latents = callback_kwargs["latents"]
    # mask_latent: 1 in garment region, 0 elsewhere (latent-space resolution)
    # init_latents: VAE-encoded original person image + noise at current timestep
    init_latents_proper = pipe.scheduler.scale_noise(image_latents, timestep, noise)
    latents = init_latents_proper * (1 - mask_latent) + latents * mask_latent
    callback_kwargs["latents"] = latents
    return callback_kwargs
```

The mask must be downscaled to latent dimensions (÷8 for the FLUX.2 VAE, so 1024×1024 becomes 128×128). During the transformer forward pass, FLUX.2 reshapes latents to `[batch, (H//2)*(W//2), channels*4]`, so the mask needs compatible reshaping.

**Subclassing `Flux2KleinPipeline`** into a custom `Flux2KleinInpaintPipeline` is the more robust option (~200 lines), following the exact pattern from `FluxInpaintPipeline`. This adds proper `mask_image` and `image` parameters, handles mask preparation in `prepare_latents`, and performs the blend operation inside the denoising loop with correct noise scheduling.

---

## The recommended two-pass pipeline architecture

The highest-confidence approach combines the fal VTON LoRA's quality with spatial size control in a **two-pass architecture**:

**Pass 1 — Quality generation.** Run FLUX.2 Klein 9B + fal VTON LoRA normally with `[person_image, garment_image, person_image]` input. This produces a high-quality, well-fitted try-on result. The LoRA does what it does best: accurate garment texture, color, and identity preservation.

**Pass 2 — Size-aware refinement.** Segment the garment region from the Pass 1 output using SAM 3 or human parsing (SegFormer, Sapiens). Generate a **size-adjusted mask** using SV-VTON-style dilation (λ parameter maps to M/L/XL/2XL). Simultaneously, proportionally scale the garment reference image to match the target size. Re-inpaint the dilated mask region using either the `callback_on_step_end` latent masking approach or LanPaint's training-free inpainting with a prompt explicitly describing the target fit ("oversized baggy loose-fitting [garment], extra fabric draping, relaxed silhouette").

In ComfyUI, this workflow chains: **VTON LoRA generation → SAM 3 segmentation → GrowMaskWithBlur (dilation) → LanPaint KSampler (re-inpainting) → LanPaint Mask Blend (compositing)**. LanPaint is confirmed compatible with FLUX.2 Klein 9B, though with a caveat: performance degrades on distilled models, so using flux guidance of **1.0–2.0** and **20–50 LanPaint steps** is recommended.

The critical technical question is whether Pass 2's re-inpainting will generate *genuinely oversized garment appearance* (wrinkles, fabric folds, draping) versus simply stretching the fitted garment into a larger mask. The SV-VTON results suggest that **combining mask dilation with garment image proportion adjustment** is what produces realistic size differentiation — either factor alone is insufficient.

---

## FLUX.2-specific spatial control tools that exist today

Three tools provide spatial influence within the FLUX.2 Klein ecosystem, though none were designed specifically for size control.

**ComfyUI-Flux2Klein-Enhancer** (github.com/capitan01R/ComfyUI-Flux2Klein-Enhancer) exposes the internal separation between text conditioning and reference latents. Its `ref_strength` parameter (0 = ignore reference, 1 = normal, >1 = stronger lock) can reduce the VTON LoRA's spatial dominance, potentially allowing prompt-based size cues to influence the output. Its `magnitude` parameter scales active embedding vectors, amplifying text influence. Lowering `ref_strength` to **0.6–0.8** while increasing `magnitude` to **1.3–1.5** with size-descriptive prompts may introduce slight looseness — worth testing as a zero-effort first experiment, though the effect is likely subtle.

**Regional prompting adapted from FLUX.1** (github.com/instantX-research/Regional-Prompting-FLUX) manipulates attention masks in MMDiT's joint attention layers. For FLUX.2, the attention structure is architecturally identical — text and image streams processed separately in double blocks, then concatenated for single blocks. The adaptation requires updating for Qwen3's token structure (`[1, 512, 12288]` vs FLUX.1's CLIP+T5 concatenation). By constraining garment-related text tokens to attend only to specific spatial regions, you could define the garment's spatial extent through attention masks rather than inpainting masks.

**The "ControlNet hack"** discovered by community members feeds preprocessed control images (canny edges, pose skeletons, depth maps) directly into Klein's reference image input rather than through a separate ControlNet model. Klein's edit capability interprets structural images as layout guidance. Creating a **custom silhouette map** showing the desired garment boundary at target size and feeding it as a reference could spatially guide generation. Reported results with pose guidance were accurate ("followed the pose perfectly"), but interaction with the VTON LoRA's training signal is unpredictable.

**No FLUX.2-compatible ControlNet or IP-Adapter exists.** All published ControlNets (XLabs, InstantX, Shakker-Labs, Jasperai) and IP-Adapters are hardcoded for FLUX.1's CLIP+T5 text encoder and `FluxTransformer2DModel`. FLUX.2 uses different text encoders (Qwen3/Mistral3), a different transformer (`Flux2Transformer2DModel` with bias-free layers and shared time/guidance modulation), and a new VAE (`AutoencoderKLFlux2`). The only FLUX.2 ControlNet found — **alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union** — targets the full 32B FLUX.2-dev model and has different block dimensions than Klein 9B.

---

## What retraining would unlock and whether it's worth it

If the two-pass pipeline proves insufficient for clear M-vs-2XL differentiation, training a **size-conditioned LoRA** is the most principled solution. MC-VTON demonstrates that FLUX can be LoRA-tuned for VTON with just **39.7M additional parameters** (0.33% of backbone) using separate G-LoRA (garment, rank 8) and MP-LoRA (masked person, rank 4). Extending this with a size conditioning token in the prompt format — "TRYON SIZE_LOOSE" or "TRYON SIZE_XL" — is technically feasible.

The critical bottleneck is **training data**. You need sets of {same person, same garment, multiple sizes} — this data barely exists. FitControler's Fit4Men dataset has only 13,000 pairs. SV-VTON's approach of generating synthetic size variants through mask manipulation could bootstrap training data: run your two-pass pipeline to generate M/L/XL/2XL variants, curate the best results, then use these as training pairs for a unified size-aware LoRA. fal's LoRA trainer accepts start/end image pairs in .zip format; **200+ curated sets** would likely be the minimum for robust size learning.

LoRA stacking (size LoRA on top of VTON LoRA) is supported in both ComfyUI and fal's API, with individual scale values per LoRA. General guidance is to lower each LoRA strength to **0.5–0.7** when stacking. However, two LoRAs modifying the same attention layers targeting the same garment region risk destructive interference. A single retrained LoRA incorporating both VTON and size conditioning is architecturally cleaner.

---

## Phased implementation roadmap

**Phase 1 (1–2 days): Zero-training quick experiments.** Test garment image pre-scaling (50%, 100%, 150%, 200% with padding) to check if the LoRA normalizes scale — measure output garment area with segmentation to confirm. Test Flux2Klein-Enhancer with reduced `ref_strength` (0.6) + increased `magnitude` (1.5) + size prompts. Test negative prompt with guidance scale raised to 2.0 ("not tight-fitting, not slim-fit, not bodycon"). Expected outcome: subtle or zero size differentiation, but these tests take minutes and establish the baseline.

**Phase 2 (3–5 days): Two-pass pipeline prototype.** Implement the full two-pass architecture in ComfyUI: VTON LoRA → SAM 3 segmentation → mask dilation (3/8/15/22 iterations for M/L/XL/2XL) → LanPaint re-inpainting. Alternatively, implement `callback_on_step_end` latent masking in Python. Test with garment-agnostic map expansion (rectangular mask instead of body-fitted). Combine mask dilation with proportional garment image scaling per SV-VTON's dual-factor approach. Expected outcome: **visible size differentiation** at XL and 2XL levels; subtle at M-to-L.

**Phase 3 (1–2 weeks): Pipeline refinement.** Add DWPose body measurements for programmatic dilation calibration (shoulder width, torso length → dilation amount). Implement SV-VTON's Edge Attention + U2-Net mask refinement for natural garment boundaries. Test attention mask manipulation via custom `AttentionProcessor` to constrain garment features to the target spatial region. Explore the "ControlNet hack" with size-adjusted silhouette maps as reference input.

**Phase 4 (2–4 weeks): Size-conditioned retraining.** Generate synthetic training data using the Phase 2/3 pipeline. Train a unified VTON + size LoRA on Klein 9B using fal's trainer or custom diffusers training loop. Target: size differentiation from a single prompt keyword without the two-pass overhead.

---

## Honest viability assessment for each approach

| Approach | Visible M→L? | Visible L→XL? | Visible XL→2XL? | Complexity | Retraining? |
|---|---|---|---|---|---|
| Prompt engineering alone | No | No | No | None | No |
| Garment image pre-scaling | Unlikely | Unlikely | Unlikely | Very low | No |
| Flux2Klein-Enhancer tuning | Marginal | Marginal | Marginal | Low | No |
| **Mask dilation + re-inpainting** | **Possible** | **Likely** | **Likely** | **Medium** | **No** |
| **Mask + garment proportion (SV-VTON)** | **Likely** | **Yes** | **Yes** | **Medium** | **No** |
| Attention mask manipulation | Possible | Possible | Likely | Medium-high | No |
| FitControler adaptation | Yes | Yes | Yes | High | Yes |
| Size-conditioned LoRA | Yes | Yes | Yes | High | Yes |

## Conclusion

The path to size-controllable VTON on FLUX.2 Klein 9B runs through **mask-based spatial control, not text conditioning**. The SV-VTON dual-factor approach — mask dilation combined with proportional garment image scaling — is the highest-confidence method that requires zero retraining and is validated across multiple diffusion backbones. FLUX.2's lack of a native inpaint pipeline is solvable today with the `callback_on_step_end` latent masking hook or a lightweight pipeline subclass. The two-pass architecture (quality generation → size-aware refinement) preserves the fal VTON LoRA's excellent garment fidelity while adding the spatial degree of freedom that size control demands. If this pipeline proves insufficient for fine-grained M-vs-L differentiation, the fallback is training a size-conditioned LoRA using synthetic data bootstrapped from the pipeline itself — creating a virtuous cycle where the preprocessing approach generates training data for the model-native solution.