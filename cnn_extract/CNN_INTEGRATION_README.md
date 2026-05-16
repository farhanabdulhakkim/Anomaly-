# CNN Extract

This folder contains the CNN pieces from the paddy anomaly detector, ready to copy into another repo.

## Core files

- `model.py` - current `PatchCNN` architecture, `PatchDataset`, `PATCH_SIZE=17`, `STRIDE=8`.
- `patch_cnn_model.pth` - trained PyTorch weights that match `model.py`.
- `anomaly.py` - video/frame inference pipeline. It loads `PatchCNN`, scans patches, writes overlays, and maps anomaly frames to GPS grid cells.
- `train_cnn.py` - training entry point using `PatchDataset` from `model.py`.
- `test_cnn.py` / `test2_cnn.py` - standalone CNN test/inference scripts.
- `requirements.txt` - original Python dependencies.
- `dataset/images`, `dataset/masks`, `dataset/ground_truth` - sample training/validation data copied from the project.

## Important integration note

Use `model.py` with `patch_cnn_model.pth` together. The weights were saved for the architecture where `PATCH_SIZE = 17`. The file `legacy_patch_all_in_one.py` is kept only as reference because it defines an older `PatchCNN` with `PATCH_SIZE = 25`, which does not match the included weight file.

## Minimal inference usage

```python
import cv2
import numpy as np
import torch
from model import PatchCNN, PATCH_SIZE, STRIDE

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
model = PatchCNN().to(DEVICE)
model.load_state_dict(torch.load("patch_cnn_model.pth", map_location=DEVICE))
model.eval()

frame = cv2.imread("your_frame.jpg")
h, w = frame.shape[:2]
pred_mask = np.zeros((h, w), dtype=np.uint8)

for y in range(0, h - PATCH_SIZE + 1, STRIDE):
    for x in range(0, w - PATCH_SIZE + 1, STRIDE):
        patch = frame[y:y + PATCH_SIZE, x:x + PATCH_SIZE]
        patch = (patch / 255.0).astype(np.float32)
        patch = np.transpose(patch, (2, 0, 1))
        tensor = torch.tensor(patch).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            pred = model(tensor).argmax(1).item()
        if pred == 1:
            c = PATCH_SIZE // 2
            cv2.circle(pred_mask, (x + c, y + c), 2, 1, -1)
```

## Runtime folders expected by scripts

Some scripts expect or create these paths relative to the repo root:

- `dataset/images/`
- `dataset/masks/`
- `dataset/tests/`
- `dataset/output/`
- `frames/`
- `output/`

Create them in the target repo or adjust the path constants before running.
