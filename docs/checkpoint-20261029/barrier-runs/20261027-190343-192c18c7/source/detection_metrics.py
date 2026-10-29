"""Framework-independent box matching shared by the two detector evaluations."""


def iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection/union if union > 0 else 0.


def match(detections, boxes, ignored, threshold):
    matched = set(); tp = fp = 0
    for detection in detections:
        if detection['score'] < threshold: continue
        candidates = [(iou(detection['box'], box), i) for i, box in enumerate(boxes) if i not in matched]
        overlap, index = max(candidates, default=(0., -1))
        if overlap >= .5: tp += 1; matched.add(index)
        elif not any(iou(detection['box'], box) >= .5 for box in ignored): fp += 1
    return tp, fp, len(boxes)-tp
