"""Prepare published training/validation masks and audit cross-split duplication.

Test clips are decoded only for the duplication audit; their arrays are not exported
for fitting. No random frame split: every clip retains its published partition.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import math
import pathlib
import re
import tempfile
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageDraw

from prepare_masked_videos import SOURCE_BYTES, SOURCE_SHA256

SIZE = 320
COUNTS = {'train': 372, 'val': 124, 'test': 123}


def archive_pairs(archive):
    pairs = {split: {} for split in COUNTS}
    names = set()
    for info in archive.infolist():
        if info.filename in names:
            raise ValueError('Duplicate archive entry')
        names.add(info.filename)
        path = pathlib.PurePosixPath(info.filename)
        if path.is_absolute() or '..' in path.parts or '\\' in info.filename or ':' in info.filename:
            raise ValueError('Unsafe archive path')
        found = re.fullmatch(r'pothole_video/(train|val|test)/(rgb|mask)/(\d+)\.mp4', info.filename)
        if not found:
            continue
        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
            raise ValueError('Symbolic link video')
        if not 0 < info.file_size <= 100_000_000:
            raise ValueError('Unexpected video size')
        split, kind, identity = found.groups()
        pair = pairs[split].setdefault(identity, {})
        if kind in pair:
            raise ValueError('Duplicate paired video')
        pair[kind] = info
    identities = set()
    for split, clips in pairs.items():
        if len(clips) != COUNTS[split] or any(set(pair) != {'rgb', 'mask'} for pair in clips.values()):
            raise ValueError(f'Unexpected {split} clip count/pairing')
        if identities.intersection(clips):
            raise ValueError('Same clip identity appears in multiple partitions')
        identities.update(clips)
    return pairs


def sha(value):
    return hashlib.sha256(value).hexdigest()


def decode_pair(paths):
    captures = [cv2.VideoCapture(str(path)) for path in paths]
    try:
        if not all(c.isOpened() for c in captures):
            raise ValueError('Cannot open paired video')
        fps = [c.get(cv2.CAP_PROP_FPS) for c in captures]
        counts = [int(c.get(cv2.CAP_PROP_FRAME_COUNT)) for c in captures]
        if not all(math.isfinite(v) and v > 0 for v in fps) or abs(fps[0]-fps[1]) > 1e-6 or counts[0] != counts[1]:
            raise ValueError('Paired metadata differs')
        images, masks, samples = [], [], []
        index, next_sample = 0, 0.
        while True:
            ok_rgb, rgb = captures[0].read()
            ok_mask, mask = captures[1].read()
            if ok_rgb != ok_mask:
                raise ValueError('Paired streams end differently')
            if not ok_rgb:
                break
            if rgb.shape != mask.shape or rgb.shape[:2] != (1080, 1080):
                raise ValueError('Unexpected paired dimensions')
            stamp = index / fps[0] * 1000
            if stamp + 1e-6 >= next_sample:
                binary = (cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY) >= 128).astype(np.uint8)
                # Resize only after full-resolution binarization, with nearest-neighbour labels.
                resized_mask = cv2.resize(binary, (SIZE, SIZE), interpolation=cv2.INTER_NEAREST)
                images.append(cv2.cvtColor(cv2.resize(rgb, (SIZE, SIZE), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
                masks.append(resized_mask)
                samples.append(dict(frame=index, timestamp_ms=stamp, rgb_decoded_sha256=sha(rgb.tobytes()),
                    mask_binary_sha256=sha(binary.tobytes()), foreground_pixels=int(binary.sum()),
                    resized_foreground_pixels=int(resized_mask.sum())))
                next_sample = stamp + 400
            index += 1
        if index != counts[0] or not samples or not any(s['foreground_pixels'] for s in samples):
            raise ValueError('Truncated/empty/unlabelled clip requires review')
        return np.stack(images), np.stack(masks), samples, index, fps[0]
    finally:
        for capture in captures:
            capture.release()


def cross_split_duplicates(records, key):
    groups = defaultdict(list)
    for record in records:
        if key == 'video':
            groups[record['files']['rgb']['sha256']].append(dict(split=record['split'], clip=record['id']))
        else:
            for sample in record['samples']:
                groups[sample['rgb_decoded_sha256']].append(dict(split=record['split'], clip=record['id'], frame=sample['frame']))
    return [dict(sha256=digest, occurrences=items) for digest, items in groups.items()
            if len({item['split'] for item in items}) > 1]


def closest_cross_split(records, thumbnails):
    # This is a visual review aid, NOT proof that similar images share a source.
    small = np.stack([cv2.resize(cv2.cvtColor(v, cv2.COLOR_RGB2GRAY), (32, 32),
                               interpolation=cv2.INTER_AREA) for v in thumbnails]).astype(np.float32)
    pairs = []
    for first in range(len(records)):
        scores = np.mean(np.abs(small[first+1:] - small[first]), axis=(1, 2))
        for offset in np.argsort(scores):
            second = first + 1 + int(offset)
            if records[first]['split'] != records[second]['split']:
                pairs.append((float(scores[offset]), first, second))
                break
    return sorted(pairs)[:20]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new preparation directory')
    with args.archive.open('rb') as source:
        if args.archive.stat().st_size != SOURCE_BYTES or hashlib.file_digest(source, 'sha256').hexdigest() != SOURCE_SHA256:
            raise ValueError('Published archive checksum mismatch')
    cv2.setNumThreads(2)
    records, thumbnails = [], []
    args.output.mkdir(parents=True)
    with zipfile.ZipFile(args.archive) as archive, tempfile.TemporaryDirectory(prefix='visionassist-mask-') as scratch:
        pairs = archive_pairs(archive)
        for split, clips in pairs.items():
            if split != 'test':
                (args.output / split).mkdir()
            for identity, pair in sorted(clips.items()):
                paths, files = [], {}
                for kind in ('rgb', 'mask'):
                    info = pair[kind]
                    data = archive.read(info)  # zipfile checks CRC; data only, never executed.
                    if len(data) != info.file_size:
                        raise ValueError('Archive length mismatch')
                    path = pathlib.Path(scratch) / (kind + '.mp4')
                    path.write_bytes(data)
                    paths.append(path)
                    files[kind] = dict(archive_entry=info.filename, sha256=sha(data), bytes=len(data))
                images, masks, samples, count, fps = decode_pair(paths)
                record = dict(id=identity, split=split, files=files, decoded_frames=count,
                              fps=fps, samples=samples, training_arrays=None)
                if split != 'test':
                    target = args.output / split / (identity + '.npz')
                    np.savez_compressed(target, images=images, masks=masks)
                    with target.open('rb') as source:
                        digest = hashlib.file_digest(source, 'sha256').hexdigest()
                    record['training_arrays'] = dict(path=target.relative_to(args.output).as_posix(), sha256=digest)
                records.append(record)
                thumbnails.append(images[len(images)//2])
                if len(records) % 25 == 0:
                    print(f'Decoded {len(records)}/619 clips', flush=True)
    video_duplicates = cross_split_duplicates(records, 'video')
    frame_duplicates = cross_split_duplicates(records, 'frame')
    closest = closest_cross_split(records, thumbnails)
    review = []
    montage = Image.new('RGB', (640, 180 * min(8, len(closest))), 'white')
    draw = ImageDraw.Draw(montage)
    for row, (difference, first, second) in enumerate(closest):
        review.append(dict(mean_gray_difference_0_255=difference,
                           first=dict(split=records[first]['split'], clip=records[first]['id']),
                           second=dict(split=records[second]['split'], clip=records[second]['id'])))
        if row < 8:
            for column, index in enumerate((first, second)):
                montage.paste(Image.fromarray(thumbnails[index]).resize((160, 160)), (column*320, row*180))
                draw.text((column*320+164, row*180+5), f"{records[index]['split']} {records[index]['id']}\nMAE {difference:.2f}", fill='black')
    montage.save(args.output / 'closest-split-pairs.png')
    summary = dict(source='https://data.mendeley.com/datasets/5bwfg4v4cd/3',
        doi='10.17632/5bwfg4v4cd.3', license='CC BY 4.0', source_sha256=SOURCE_SHA256,
        authors=['Muhammad Ihsan', 'Agus Harjoko', 'Muhammad Alfian Amrizal'],
        preparation=dict(size=SIZE, sample_interval_ms=400, rgb_resize='area',
            mask='grayscale >=128 at original resolution, then nearest-neighbour resize',
            opencv=cv2.__version__, numpy=np.__version__, test_arrays_exported=False),
        partitions={split: dict(clips=sum(r['split']==split for r in records),
            sampled_frames=sum(len(r['samples']) for r in records if r['split']==split),
            foreground_pixels=sum(s['resized_foreground_pixels'] for r in records if r['split']==split for s in r['samples']))
            for split in COUNTS},
        cross_split_video_duplicates=video_duplicates, cross_split_sampled_frame_duplicates=frame_duplicates,
        closest_cross_split_pairs=review,
        exact_duplicate_audit_passed=not (video_duplicates or frame_duplicates),
        limitations=['Published clip partitions preserved; capture locations/source sequences are not established as disjoint.',
            'Near-neighbour grayscale differences are a manual review aid, not a reliable leakage classifier.',
            'Only sampled frames were checked for exact decoded-frame duplication.',
            'Test partition has already been used for detector development evaluation; not an untouched safety test.',
            'Road close-up masks cannot establish walking safety, curb/stair classes or distances.'])
    (args.output / 'manifest.json').write_text(json.dumps(dict(summary=summary, records=records), indent=2), encoding='utf8')
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
    print(json.dumps({key: summary[key] for key in ('partitions', 'exact_duplicate_audit_passed')}), flush=True)
    if not summary['exact_duplicate_audit_passed']:
        raise ValueError('Cross-split exact duplicates require review before training')


if __name__ == '__main__':
    main()
