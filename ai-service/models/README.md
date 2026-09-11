# Models Directory

This directory is designated for local YOLO weight files (`.pt` or `.onnx`).

### Recommended Setup:
1. Place your custom trained road damage / pothole model here:
   ```
   ai-service/models/best.pt
   ```
2. Configure your `.env`:
   ```bash
   YOLO_MODEL_PATH=models/best.pt
   ```

### Default Fallback:
If no custom model is provided, the service defaults to `yolov8n.pt` (Ultralytics nano model), which automatically downloads on first run for general object detection (vehicles, pedestrians, traffic lights).

> [!NOTE]
> Large `.pt` files are excluded from source control via `.gitignore`.
