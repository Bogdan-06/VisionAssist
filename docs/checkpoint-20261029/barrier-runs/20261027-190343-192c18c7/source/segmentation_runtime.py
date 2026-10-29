"""Desktop evaluation adapter for actual LiteRT segmentation candidates.

Component mean pixel probabilities are uncalibrated, not measured hazard likelihoods.
"""
import time
import cv2
import numpy as np

SIZE = 320


def prepare(rgb):
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) <= 0:
        raise ValueError('Expected nonempty uint8 RGB image')
    height, width = rgb.shape[:2]
    scale = min(SIZE/width, SIZE/height)
    rw, rh = max(1, round(width*scale)), max(1, round(height*scale))
    left, top = (SIZE-rw)//2, (SIZE-rh)//2
    canvas = np.full((SIZE, SIZE, 3), 114, np.uint8)
    canvas[top:top+rh, left:left+rw] = cv2.resize(rgb, (rw, rh), interpolation=cv2.INTER_AREA)
    return canvas.astype(np.float32)/127.5-1, (left, top, rw, rh, width, height)


def restore(output, transform):
    if output.shape != (80, 80) or not np.isfinite(output).all() or np.any(output < 0) or np.any(output > 1):
        raise ValueError('Invalid segmentation probability tensor')
    left, top, rw, rh, width, height = transform
    full = cv2.resize(output, (SIZE, SIZE), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(full[top:top+rh, left:left+rw], (width, height), interpolation=cv2.INTER_LINEAR)


def components(probability, threshold):
    if not 0 <= threshold <= 1:
        raise ValueError('Invalid pixel threshold')
    binary = (probability >= threshold).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    sums = np.bincount(labels.ravel(), weights=probability.ravel(), minlength=count)
    detections = []
    for index, (x, y, w, h, area) in enumerate(stats[1:], 1):
        detections.append(dict(box=[int(x), int(y), int(x+w), int(y+h)],
            score=float(sums[index]/area), area_pixels=int(area)))
    # Retain every region, including tiny false positives. No area tuning on evaluation data.
    return sorted(detections, key=lambda value: -value['score'])


class Segmenter:
    def __init__(self, model):
        import tensorflow as tf
        self.runtime_version = tf.__version__
        self.interpreter = tf.lite.Interpreter(model_path=str(model), num_threads=2)
        self.interpreter.allocate_tensors()
        inputs, outputs = self.interpreter.get_input_details(), self.interpreter.get_output_details()
        if (len(inputs) != 1 or len(outputs) != 1 or inputs[0]['shape'].tolist() != [1,320,320,3]
                or outputs[0]['shape'].tolist() != [1,80,80,1]
                or inputs[0]['dtype'] != np.float32 or outputs[0]['dtype'] != np.float32):
            raise ValueError('Unexpected segmentation model contract')
        self.input_index, self.output_index = inputs[0]['index'], outputs[0]['index']

    def predict(self, rgb):
        value, transform = prepare(rgb)
        self.interpreter.set_tensor(self.input_index, value[None])
        before = time.perf_counter()
        self.interpreter.invoke()
        elapsed = (time.perf_counter()-before)*1000
        output = self.interpreter.get_tensor(self.output_index)[0, ..., 0]
        return restore(output, transform), elapsed


def detection_scores(counts):
    tp, fp, fn = map(int, counts)
    return dict(tp=tp, fp=fp, fn=fn, precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None, f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
