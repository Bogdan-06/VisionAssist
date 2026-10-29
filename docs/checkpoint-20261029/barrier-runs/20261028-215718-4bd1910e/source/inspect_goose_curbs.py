"""Audit real GOOSE curb labels; no model training or simulated detections."""
import argparse
import collections
import csv
import hashlib
import io
import json
import pathlib
import zipfile

import numpy as np
from PIL import Image

from fetch_goose_validation import EXPECTED_BYTES, EXPECTED_SHA256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive',type=pathlib.Path,required=True)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new output directory')
    with args.archive.open('rb') as stream:
        if args.archive.stat().st_size != EXPECTED_BYTES or hashlib.file_digest(stream,'sha256').hexdigest() != EXPECTED_SHA256:
            raise ValueError('Archive checksum differs from the reviewed acquisition')
    with zipfile.ZipFile(args.archive) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)): raise ValueError('Duplicate ZIP entries')
        for entry in archive.infolist():
            path = pathlib.PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename:
                raise ValueError('Unsafe ZIP path')
            if entry.file_size > 100_000_000: raise ValueError('Unexpectedly large entry')
        bad = archive.testzip()
        if bad is not None: raise ValueError('ZIP CRC failure: '+bad)
        mapping_bytes = archive.read('goose_label_mapping.csv')
        classes = list(csv.DictReader(io.StringIO(mapping_bytes.decode('utf8'))))
        class_names = {int(row['label_key']):row['class_name'] for row in classes}
        if set(class_names) != set(range(64)) or class_names[22] != 'curb':
            raise ValueError('Unexpected class taxonomy')
        masks = sorted(n for n in names if n.startswith('labels/val/') and n.endswith('_labelids.png'))
        images = {n for n in names if n.startswith('images/val/') and n.endswith('_windshield_vis.png')}
        if not masks or len(masks) != len(images): raise ValueError('Unbalanced RGB/mask counts')
        args.output.mkdir(parents=True)
        for name in ('LICENSE','CHANGELOG','goose_label_mapping.csv'):
            (args.output/name).write_bytes(archive.read(name))
        totals = np.zeros(64,dtype=np.int64); frame_counts = np.zeros(64,dtype=np.int64)
        records = []; seen = set(); sequences = collections.defaultdict(lambda:dict(frames=0,curb_frames=0,curb_pixels=0))
        for index,name in enumerate(masks):
            image_name = name.replace('labels/val/','images/val/',1).removesuffix('_labelids.png')+'_windshield_vis.png'
            if image_name not in images or image_name in seen: raise ValueError('Missing or repeated RGB pair')
            seen.add(image_name)
            mask_bytes = archive.read(name)
            with Image.open(io.BytesIO(mask_bytes)) as image:
                if image.mode != 'L': raise ValueError('Expected single-channel class IDs')
                labels = np.array(image)
                size = image.size
            if labels.max() >= 64: raise ValueError('Unknown class ID')
            with archive.open(image_name) as image_stream, Image.open(image_stream) as image:
                if image.size != size: raise ValueError('Image and mask dimensions differ')
            counts = np.bincount(labels.ravel(),minlength=64)
            totals += counts; frame_counts += counts>0
            sequence = pathlib.PurePosixPath(name).parts[2]
            curb_pixels = int(counts[22])
            sequences[sequence]['frames'] += 1
            sequences[sequence]['curb_frames'] += int(curb_pixels>0)
            sequences[sequence]['curb_pixels'] += curb_pixels
            records.append(dict(mask=name,image=image_name,sequence=sequence,width=size[0],height=size[1],
                mask_sha256=hashlib.sha256(mask_bytes).hexdigest(),curb_pixels=curb_pixels))
            if index%100 == 0: print(f'{index}/{len(masks)} masks',flush=True)
        if seen != images: raise ValueError('Unpaired RGB entries')
        positive = sorted((r for r in records if r['curb_pixels']),key=lambda r:r['curb_pixels'])
        # Median-area and largest-area positive samples; deterministic inspection, not a quality benchmark.
        examples = []
        if positive:
            for number,record in enumerate((positive[len(positive)//2], positive[-1])):
                for kind,entry in (('rgb',record['image']),('labelids',record['mask'])):
                    data = archive.read(entry)
                    (args.output/f'example-{number}-{kind}.png').write_bytes(data)
                with Image.open(io.BytesIO(archive.read(record['mask']))) as mask_image:
                    curb_mask = np.where(np.array(mask_image)==22,255,0).astype(np.uint8)
                Image.fromarray(curb_mask).save(args.output/f'example-{number}-curb-mask.png')
                examples.append(record)
        report = dict(source='https://goose-dataset.de/docs/setup/',license='CC BY-SA 4.0',
            source_sha256=EXPECTED_SHA256,source_bytes=EXPECTED_BYTES,zip_crc_checked_entries=len(names),
            split='published validation',rgb_mask_pairs=len(records),curb_frames=len(positive),
            frames_without_curb=len(records)-len(positive),curb_pixels=int(totals[22]),
            total_pixels=int(totals.sum()),curb_pixel_fraction=float(totals[22]/totals.sum()),
            curb_label_id=22,curb_is_instance_label=False,stairs_label_present=any('stair' in n for n in class_names.values()),
            class_pixel_counts={class_names[i]:int(totals[i]) for i in range(64)},
            class_frame_counts={class_names[i]:int(frame_counts[i]) for i in range(64)},
            sequences=dict(sequences),examples=examples,
            mapping_sha256=hashlib.sha256(mapping_bytes).hexdigest(),
            limitations=['Annotation coverage audit only; no detection accuracy or distance measurement.',
                'RGB headers and all class masks inspected; ZIP CRC checked for every entry, not full RGB decoding of every frame.',
                'No-curb means absent from these semantic labels, not a safe or hazard-free scene.',
                'Robotic-platform imagery has a viewpoint/domain gap to smartphone walking.',
                'Semantic curb labels lack per-instance heights or traversability ground truth.',
                'No training performed and no data or model added to Android assets.'])
        (args.output/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf8')
        (args.output/'inspection.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:report[k] for k in ('rgb_mask_pairs','curb_frames','frames_without_curb','curb_pixels','curb_pixel_fraction','stairs_label_present')}),flush=True)


if __name__ == '__main__': main()
