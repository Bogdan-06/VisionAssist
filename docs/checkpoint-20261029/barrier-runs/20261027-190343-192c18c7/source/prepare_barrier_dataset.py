"""Audit real barrier photographs and create duplicate-grouped research splits.

Source boxes remain boxes. No segmentation masks or metric heights are invented.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageDraw

from fetch_barrier_sample import SIZE, MD5

XML_SHA = '9a19dc3a95acd01c30e1a40320de49e19a3d5fe5b1b9c7253f045aa2e590930c'
SEED = 4217


def annotations(xml):
    if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
        raise ValueError('Unexpected XML declarations')
    records = []
    names = set()
    for image in ET.fromstring(xml).findall('image'):
        name = image.get('name')
        if name in names:
            raise ValueError('Duplicate annotation image name')
        names.add(name)
        width, height = int(image.get('width')), int(image.get('height'))
        if min(width, height) < 1:
            raise ValueError('Invalid annotated image size')
        boxes = []
        for box in image.findall('box'):
            label = box.get('label')
            if label not in ('step', 'stair', 'ramp', 'grab_bar'):
                raise ValueError(f'Unknown source label: {label}')
            attributes = {a.get('name'): a.text for a in box.findall('attribute')}
            coords = [float(box.get(k)) for k in ('xtl', 'ytl', 'xbr', 'ybr')]
            x1, y1, x2, y2 = coords
            if not all(map(math.isfinite, coords)) or not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                raise ValueError(f'Invalid source box: {name}')
            target = 'stairs' if label == 'stair' else None
            if label == 'step':
                if attributes.get('type') not in ('curb', 'doorstep', 'other'):
                    raise ValueError('Step subtype is missing or unknown')
                target = 'curb' if attributes['type'] == 'curb' else 'step'
            boxes.append(dict(source_label=label, target_class=target, box=coords,
                              attributes=attributes, occluded=box.get('occluded') == '1'))
        records.append(dict(image=name, width=width, height=height, task_id=image.get('task_id'), boxes=boxes))
    return sorted(records, key=lambda r: r['image'])


def phash(image):
    gray = np.asarray(image.convert('L').resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32)
    low = cv2.dct(gray)[:8, :8].reshape(-1)
    bits = low > np.median(low[1:])
    bits[0] = False
    return int.from_bytes(np.packbits(bits).tobytes(), 'big')


class Groups:
    def __init__(self, count):
        self.parent = list(range(count))

    def find(self, index):
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def join(self, a, b):
        a, b = self.find(a), self.find(b)
        self.parent[max(a, b)] = min(a, b)


def label_signature(record):
    return sorted((b['target_class'], tuple(b['box'])) for b in record['boxes'] if b['target_class'])


def prepare(archive, records, output, previously_seen):
    groups = Groups(len(records))
    exact = defaultdict(list)
    exclusions = []
    for index, record in enumerate(records):
        content = archive.read(record['image'])  # CRC checked by ZipFile.
        with Image.open(io.BytesIO(content)) as source:
            orientation = int(source.getexif().get(274, 1))
            image = source.convert('RGB')  # Source coordinate convention; no silent EXIF rotation.
        if image.size != (record['width'], record['height']):
            raise ValueError(f'Image/annotation dimensions differ: {record["image"]}')
        record.update(sha256=hashlib.sha256(content).hexdigest(),
                      decoded_rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
                      exif_orientation=orientation, phash=f'{phash(image):016x}')
        if orientation != 1:
            record['excluded_reason'] = 'Nontrivial EXIF orientation requires coordinate review'
            exclusions.append(dict(image=record['image'], reason=record['excluded_reason']))
        exact[(image.width, image.height, record['decoded_rgb_sha256'])].append(index)
        if index % 200 == 0:
            print(f'Decoded and hashed {index+1}/{len(records)} images', flush=True)
    exact_duplicates = []
    for indices in exact.values():
        if len(indices) == 1:
            continue
        first = indices[0]
        conflict = any(label_signature(records[i]) != label_signature(records[first]) for i in indices[1:])
        for index in indices[1:]:
            groups.join(first, index)
        exact_duplicates.append(dict(images=[records[i]['image'] for i in indices], target_annotation_conflict=conflict))
        for index in indices if conflict else indices[1:]:
            reason = 'Conflicting target boxes on identical decoded image' if conflict else 'Exact decoded duplicate'
            records[index]['excluded_reason'] = reason
            exclusions.append(dict(image=records[index]['image'], reason=reason))
    hashes = np.array([int(r['phash'], 16) for r in records], dtype=np.uint64)
    ratios = np.array([r['width']/r['height'] for r in records])
    near = []
    for index in range(len(records)-1):
        distances = np.bitwise_count(hashes[index+1:] ^ hashes[index])
        candidates = np.flatnonzero(distances <= 4) + index + 1
        for other in candidates:
            other = int(other)
            if abs(ratios[index]-ratios[other])/max(ratios[index],ratios[other]) > .01:
                continue
            groups.join(index, other)
            if records[index]['decoded_rgb_sha256'] != records[other]['decoded_rgb_sha256']:
                near.append(dict(a=records[index]['image'], b=records[other]['image'],
                                 hamming=int(distances[other-index-1])))
    near.sort(key=lambda item: (item['hamming'], item['a'], item['b']))
    # Any examples displayed for this audit are kept out of the proposed validation/test splits.
    review = []
    for category in ('stairs', 'curb', 'step', 'no_target'):
        candidates = [r for r in records if not r.get('excluded_reason') and
                      ((not any(b['target_class'] for b in r['boxes'])) if category == 'no_target' else
                       any(b['target_class'] == category for b in r['boxes']))]
        candidates.sort(key=lambda r: hashlib.sha256(r['image'].encode()).hexdigest())
        selected = [r for r in candidates if r['image'] not in review][:2]
        review.extend(r['image'] for r in selected)
    displayed = set(review) | {p[k] for p in near[:12] for k in ('a','b')}
    previously_seen |= displayed
    members = defaultdict(list)
    for index, record in enumerate(records):
        members[groups.find(index)].append(record)
    for cluster in members.values():
        group = min(r['image'] for r in cluster)
        forced = any(r['image'] in previously_seen for r in cluster)
        bucket = int(hashlib.sha256(f'{SEED}:{group}'.encode()).hexdigest()[:8],16) % 100
        split = 'train' if forced or bucket < 70 else 'validation' if bucket < 85 else 'test'
        for record in cluster:
            record.update(group=group, reviewed_group_forced_train=forced,
                          split='excluded' if record.get('excluded_reason') else split)
    # Exact/near groups must not cross any active fitting/evaluation partition.
    for cluster in members.values():
        if len({r['split'] for r in cluster if r['split'] != 'excluded'}) > 1:
            raise ValueError('Duplicate group crosses a split')
    statistics = {}
    for split in ('train', 'validation', 'test', 'excluded'):
        selected = [r for r in records if r['split'] == split]
        counts = Counter(b['target_class'] for r in selected for b in r['boxes'] if b['target_class'])
        statistics[split] = dict(images=len(selected), target_boxes=dict(counts),
            no_target_images=sum(not any(b['target_class'] for b in r['boxes']) for r in selected),
            annotation_tasks=dict(Counter(r['task_id'] for r in selected)))
    for split in ('train', 'validation', 'test'):
        if any(statistics[split]['target_boxes'].get(c,0) == 0 for c in ('stairs','curb','step')):
            raise ValueError('A target class is absent from a proposed split')
    by_name = {r['image']: r for r in records}
    sheet = Image.new('RGB',(1024,640),'white')
    for index, name in enumerate(review):
        record = by_name[name]
        image = Image.open(io.BytesIO(archive.read(name))).convert('RGB')
        image.thumbnail((256,280))
        draw = ImageDraw.Draw(image)
        sx,sy=image.width/record['width'],image.height/record['height']
        for box in record['boxes']:
            color={'stairs':'orange','curb':'blue','step':'green'}.get(box['target_class'])
            if color:
                x1,y1,x2,y2=box['box']; draw.rectangle([x1*sx,y1*sy,x2*sx,y2*sy],outline=color,width=2)
        x,y=index%4*256,index//4*320
        sheet.paste(image,(x,y)); ImageDraw.Draw(sheet).text((x+2,y+282),name,fill='black')
    sheet.save(output/'label-review.png')
    if near:
        sheet=Image.new('RGB',(800,180*min(12,len(near))),'white')
        for row,pair in enumerate(near[:12]):
            for column,key in enumerate(('a','b')):
                image=Image.open(io.BytesIO(archive.read(pair[key]))).convert('RGB'); image.thumbnail((390,150))
                sheet.paste(image,(column*400,row*180))
                ImageDraw.Draw(sheet).text((column*400+2,row*180+152),f'{pair[key]} d={pair["hamming"]}',fill='black')
        sheet.save(output/'near-duplicate-review.png')
    return dict(splits=statistics, exact_duplicate_groups=exact_duplicates, near_duplicate_pairs=near,
                total_groups=len(members), largest_group=max(map(len,members.values())), exclusions=exclusions,
                reviewed_images_forced_into_training=sorted(previously_seen), records=records)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','output','previous-sample-manifest'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new preparation directory')
    provenance=json.loads(args.archive.with_suffix('.provenance.json').read_text())
    if provenance['bytes']!=SIZE or provenance['publisher_md5']!=MD5 or provenance['license']!='CC BY 4.0':
        raise ValueError('Unexpected source provenance')
    with args.archive.open('rb') as stream:
        source_sha=hashlib.file_digest(stream,'sha256').hexdigest()
    if args.archive.stat().st_size!=SIZE or source_sha!=provenance['sha256']:
        raise ValueError('Archive source identity check failed')
    sample=json.loads(args.previous_sample_manifest.read_text())
    if sample['source']!='https://doi.org/10.5281/zenodo.6382090':
        raise ValueError('Unexpected earlier sample source')
    seen={r['archive_entry'] for r in sample['records']}
    args.output.mkdir(parents=True)
    with zipfile.ZipFile(args.archive) as archive:
        xml=archive.read('wm_annotations.xml')
        if hashlib.sha256(xml).hexdigest()!=XML_SHA:
            raise ValueError('Annotation identity changed')
        records=annotations(xml)
        image_names={name for name in archive.namelist() if name.endswith('.jpg')}
        if len(records)!=5538 or {r['image'] for r in records}!=image_names or not seen<=image_names:
            raise ValueError('Image/annotation inventory differs')
        result=prepare(archive,records,args.output,seen)
    result.update(source_sha256=source_sha, annotation_sha256=XML_SHA, source=provenance['source'],
                  license=provenance['license'], classes=['stairs','curb','step'], seed=SEED,
                  split_rule='SHA256(seed:duplicate-group-anchor) 70/15/15; displayed/previously reviewed groups forced to train',
                  near_duplicate_rule='63-bit DCT pHash Hamming <=4 and aspect-ratio difference <=1%; transitive grouping',
                  no_cross_split_detected_duplicates=True,
                  limitations=[
                      'Similarity grouping does not prove geographic, source-session or all-near-duplicate independence.',
                      'Source visible-barrier convention may omit unseen descending stairs and is wheelchair-oriented.',
                      'Heights and widths remain subjective source attributes, never distance ground truth.',
                      'Source boxes are not segmentation masks; no pixel ground truth is created.',
                      'Negative images are annotation-defined, not independently reviewed hazard-free scenes.',
                      'Research splits are provisional; no trained runtime or warning eligibility is established.'])
    (args.output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    summary={k:v for k,v in result.items() if k not in ('records','near_duplicate_pairs','exact_duplicate_groups','exclusions')}
    summary.update(exact_duplicate_groups=len(result['exact_duplicate_groups']),near_duplicate_pairs=len(result['near_duplicate_pairs']),
                   excluded_images=len({e['image'] for e in result['exclusions']}),
                   manifest_sha256=hashlib.sha256((args.output/'manifest.json').read_bytes()).hexdigest())
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    main()
