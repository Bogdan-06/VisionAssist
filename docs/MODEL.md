# Model and third-party provenance

## Bundled model

- EfficientDet-Lite0, float32, 320×320 input, version 1; 13,836,895 bytes.
- SHA-256: `40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58`
- [Official model file](https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float32/1/efficientdet_lite0.tflite)
- [Google model guide](https://ai.google.dev/edge/mediapipe/solutions/vision/object_detector)
- [MediaPipe Android integration guide](https://ai.google.dev/edge/mediapipe/solutions/vision/object_detector/android)
- Runtime: `com.google.mediapipe:tasks-vision:0.10.32`, CPU delegate. [MediaPipe source/license](https://github.com/google-ai-edge/mediapipe/tree/v0.10.32).
- Asset: `core/detection/src/main/assets/efficientdet_lite0.tflite`. Included uncompressed in
  the APK, with no runtime downloader. The model checksum is checked by instrumentation.

Google's model guide identifies EfficientDet-Lite0 as trained on COCO with 80 object classes.
The embedded `labels.txt` has 90 indexed entries: 80 named classes and 10 `???` placeholders.
[MODEL_LABELS.txt](MODEL_LABELS.txt) is extracted from that embedded metadata, preserving the
indices. Placeholder categories are excluded. The model is unmodified; retain its embedded
metadata and consult upstream model and dataset terms when redistributing it.

Supported named categories:

person, bicycle, car, motorcycle, airplane, bus, train, truck, boat, traffic light,
fire hydrant, stop sign, parking meter, bench, bird, cat, dog, horse, sheep, cow,
elephant, bear, zebra, giraffe, backpack, umbrella, handbag, tie, suitcase, frisbee,
skis, snowboard, sports ball, kite, baseball bat, baseball glove, skateboard,
surfboard, tennis racket, bottle, wine glass, cup, fork, knife, spoon, bowl, banana,
apple, sandwich, orange, broccoli, carrot, hot dog, pizza, donut, cake, chair, couch,
potted plant, bed, dining table, toilet, tv, laptop, mouse, remote, keyboard,
cell phone, microwave, oven, toaster, sink, refrigerator, book, clock, vase,
scissors, teddy bear, hair drier, toothbrush.

**Not supported:** potholes, stairs, curbs or poles. Traffic light recognition does not identify
its signal state. Object recognition does not determine whether an object blocks the user's
path. The score is a model confidence score, not a calibrated probability or safety guarantee.

Float32 was selected after testing int8 and SSD MobileNetV2 float32 on the same three public
fixtures at the same 0.5 score threshold. EfficientDet-Lite0 float32 recognized the bicycle,
car and dog in the overlapping-object scene, the bus and people in the street scene, and both
cats and dogs in the animal scene. Int8 missed the bicycle and misclassified two dogs as cats;
SSD MobileNetV2 missed the dogs. This small smoke comparison is not an accuracy benchmark.
Float32 adds about 9 MB relative to int8 and can cost more inference time. Target-device
latency and battery measurements remain necessary. Comparison output is preserved in the
validation evidence. Placeholder names are filtered from returned results in Kotlin.

## Processing and coordinate contract

1. CameraX binds Preview and YUV ImageAnalysis in one UseCaseGroup with a shared FILL_CENTER
   ViewPort and matching display rotation. The analysis target is 640×480 with supported-size
   fallback; actual sensor/output size is read from each ImageProxy.
2. A single executor loads the model before attaching the analyzer. KEEP_ONLY_LATEST and a
   125 ms sampling interval discard unnecessary work before bitmap conversion.
3. `ImageProxy.toBitmap()` converts the full buffer; bitmap pixels rotate by the frame's
   `rotationDegrees`. The model returns boxes in this upright bitmap's pixel coordinates.
4. ImageProxyTransformFactory uses rotation and the full buffer (`usingCropRect=false`).
   CoordinateTransform maps those coordinates to PreviewView's actual output transform,
   accounting for the shared crop, scaling and display rotation. It does not assume equal
   preview/analysis resolutions or multiply by an arbitrary view-width ratio.
5. Clip to the visible preview, discard invalid/offscreen rectangles, normalize by view size.
   Left/center/right is the midpoint of the visible rectangle split into image thirds.
6. The ViewModel clears results after 1,000 ms from analyzer receipt, or immediately on
   stop/error/rebinding. Receipt time is not a calibrated sensor timestamp or distance measure.

MediaPipe's synchronous IMAGE mode is intentional. The CameraX worker owns scheduling and
backpressure; MediaPipe has no additional async input queue. Initialization, inference and
close all run on that worker. `ObjectDetector.detect()` takes bitmap ownership: closing
MPImage recycles the bitmap. ImageProxy is always closed in `finally`, including skipped and
failed frames. Cancellation suppresses callbacks, and native close is queued after inference.

[CameraX transform reference](https://developer.android.com/reference/androidx/camera/view/transform/ImageProxyTransformFactory)
and [MediaPipe bitmap ownership implementation](https://github.com/google-ai-edge/mediapipe/blob/v0.10.32/mediapipe/java/com/google/mediapipe/framework/image/BitmapImageContainer.java)
provide the contracts used here.

## Test asset

The positive inference fixture is [cats_and_dogs.jpg](https://storage.googleapis.com/mediapipe-assets/cats_and_dogs.jpg)
from Google's MediaPipe test assets. It is included only under `src/androidTest/assets`, not
in the user-facing APK. Tests require real cat/dog detections and use the same bundled model.
The rendering image is generated from those real detections, never a simulated detection list.

Additional positive scene checks use test-only images from the upstream project repositories:

- [People and bus](https://raw.githubusercontent.com/ultralytics/assets/main/im/bus.jpg),
  SHA-256 `c02019c4979c191eb739ddd944445ef408dad5679acab6fd520ef9d434bfbc63`.
- [Dog, bicycle and vehicle](https://raw.githubusercontent.com/pjreddie/darknet/master/data/dog.jpg),
  SHA-256 `5a9522051c3cec2bbd2f6323fccba32e8fbf3ddcc2b3e2fd46b04c720bc6f866`.

These images are retained in the instrumentation test assets only, not the installed app's
production assets. Their originating projects and terms are linked above.
