"""Export verified barrier training/validation boxes for detector training.

Original JPEG bytes and explicit class labels are preserved. Test and excluded
images are never copied into the training export. No segmentation masks are made.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import zipfile

CLASSES = ['stairs', 'curb', 'step']


def selections(manifest):
    if manifest['classes'] != CLASSES:
        raise ValueError('Unexpected target class order')
    groups = defaultdict(set)
    names = set()
    for record in manifest['records']:
        name = record['image']
        if name in names:
            raise ValueError('Duplicate image name')
        names.add(name)
        split = record['split']
        if split not in ('train', 'validation', 'test', 'excluded'):
            raise ValueError('Unknown split')
        if split == 'excluded':
            continue
        if record.get('excluded_reason') or record['exif_orientation'] != 1:
            raise ValueError('Unreviewed or excluded image assigned to an active split')
        groups[record['group']].add(split)
    if any(len(value) != 1 for value in groups.values()):
        raise ValueError('Duplicate groups cross fitting/evaluation splits')
    result = {s: [r for r in manifest['records'] if r['split'] == s] for s in ('train', 'validation')}
    if not all(result.values()):
        raise ValueError('Empty fitting split')
    return result


def export(archive, selected, destination):
    counts, files = {}, {}
    for split, records in selected.items():
        if split not in ('train', 'validation'):
            raise ValueError('Test/excluded export is not permitted')
        folder = destination / split
        (folder / 'images').mkdir(parents=True, exist_ok=False)
        images, annotations, image_hashes, filenames = [], [], {}, set()
        for image_id, record in enumerate(records):
            if record['split'] != split:
                raise ValueError('Record assigned to the wrong export split')
            name = PurePosixPath(record['image']).name
            if not name.endswith('.jpg') or '\\' in name or name in filenames:
                raise ValueError('Invalid or duplicate output filename')
            filenames.add(name)
            content = archive.read(record['image'])
            digest = hashlib.sha256(content).hexdigest()
            if digest != record['sha256']:
                raise ValueError('Image bytes differ from audited preparation')
            image_hashes[name] = digest
            (folder / 'images' / name).write_bytes(content)
            images.append(dict(id=image_id, file_name=name, width=record['width'], height=record['height'],
                               source_image=record['image'], source_group=record['group']))
            for box in record['boxes']:
                category = box['target_class']
                if category is None:
                    continue
                if category not in CLASSES:
                    raise ValueError('Unexpected target label')
                x1, y1, x2, y2 = box['box']
                if not all(map(math.isfinite, box['box'])) or not (
                        0 <= x1 < x2 <= record['width'] and 0 <= y1 < y2 <= record['height']):
                    raise ValueError('Invalid source box')
                annotations.append(dict(id=len(annotations), image_id=image_id, category_id=CLASSES.index(category)+1,
                                        bbox=[x1, y1, x2-x1, y2-y1], area=(x2-x1)*(y2-y1), iscrowd=0))
        document = dict(images=images, annotations=annotations,
                        categories=[dict(id=i, name=c) for i, c in enumerate(['background']+CLASSES)])
        labels = folder / 'labels.json'
        labels.write_text(json.dumps(document), encoding='utf8')
        hashes = folder / 'image-sha256.json'
        hashes.write_text(json.dumps(image_hashes, indent=2), encoding='utf8')
        box_counts = Counter(CLASSES[a['category_id']-1] for a in annotations)
        counts[split] = dict(images=len(images), boxes=len(annotations), boxes_by_class=dict(box_counts),
                             negatives=len(images)-len({a['image_id'] for a in annotations}))
        files[split] = dict(labels_sha256=hashlib.sha256(labels.read_bytes()).hexdigest(),
                            image_hashes_sha256=hashlib.sha256(hashes.read_bytes()).hexdigest())
    return counts, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'prepared', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new export directory')
    manifest_path = args.prepared / 'manifest.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    summary = json.loads((args.prepared / 'summary.json').read_text(encoding='utf8'))
    if manifest_sha != summary['manifest_sha256']:
        raise ValueError('Prepared manifest changed since the audit')
    manifest = json.loads(manifest_bytes)
    if manifest['source'] != 'https://doi.org/10.5281/zenodo.6382090' or manifest['license'] != 'CC BY 4.0':
        raise ValueError('Unexpected dataset source/license')
    selected = selections(manifest)
    with args.archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != manifest['source_sha256']:
        raise ValueError('Archive differs from audited source')
    args.output.mkdir(parents=True)
    with zipfile.ZipFile(args.archive) as archive:
        counts, files = export(archive, selected, args.output)
    provenance = dict(source=manifest['source'], license=manifest['license'],
                      attribution='Jakob Stolberg; collectors Christopher Richters and Sami Nenno; HIIG, 2022',
                      source_sha256=digest, manifest_sha256=manifest_sha, classes=CLASSES, counts=counts,
                      files=files, test_images_exported=False, image_folder='images',
                      transformations='Original JPEG bytes; source xyxy boxes converted to COCO xywh. No masks.',
                      limitations=manifest['limitations'],
                      exporter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (args.output / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf8')
    print(json.dumps(provenance, indent=2), flush=True)


if __name__ == '__main__':
    main()
