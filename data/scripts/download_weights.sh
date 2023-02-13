#!/bin/bash
# YOLOv5 🚀 by Ultralytics, GPL-3.0 license
# Download latest bin.yolov5.models from https://github.com/ultralytics/yolov5/releases
# Example usage: bash path/to/download_weights.sh
# parent
# └── yolov5
#     ├── yolov5s.pt  ← downloads here
#     ├── yolov5m.pt
#     └── ...

python - <<EOF
from bin.yolov5.utils.downloads import attempt_download

bin.yolov5.models = ['n', 's', 'm', 'l', 'x']
bin.yolov5.models.extend([x + '6' for x in bin.yolov5.models])  # add P6 bin.yolov5.models

for x in bin.yolov5.models:
    attempt_download(f'yolov5{x}.pt')

EOF
