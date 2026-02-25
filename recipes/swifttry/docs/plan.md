# Plan — SwiftTry

## Goal
Colab-ready inference recipe for **SwiftTry** (AAAI 2025): given a person video and a garment image, produce a try-on result video using diffusion-based video inpainting.

## Scope
**In scope**
- Video virtual try-on inference (`inference.py`)
- Automated weight download (5 HF repos + SD-Inpainting)
- Two install strategies: opt2_modern (default) / opt1_legacy (fallback)
- A100 notebook with user-configurable data paths

**Out of scope**
- Training (Stage 1 / Stage 2)
- Dataset redistribution (TikTokDress, VVT)
- Training (Stage 1 / Stage 2)와 데이터셋 전처리 파이프라인 (별도 도구)
- Image-only try-on (`inference_image.py`)

## Approach
1. Clone upstream at pinned commit SHA
2. Install deps via opt2_modern (keep Colab torch, install compatible diffusers stack)
3. Download weights via upstream `tools/download_weights.py` + separate SD-Inpainting snapshot
4. Symlink `weights/tiktokdress -> pretrained_sd_models/swift_try` to bridge config path mismatch
5. User provides DATA_DIR with pre-processed videos; notebook runs `inference.py`
6. User 모드: 업로드된 동영상/의류에 대해 DWPose + SegFormer 기반 자동 전처리 (포즈 추출, 마스크 생성)

## Success Criteria
- `install.sh` completes without error on fresh Colab A100 runtime
- `python tools/download_weights.py` downloads all 5 weight sets
- `python inference.py --data_dir ... --test_pairs ... --save_dir ...` produces output MP4s
- Notebook cells run top-to-bottom with only DATA_DIR edit required
