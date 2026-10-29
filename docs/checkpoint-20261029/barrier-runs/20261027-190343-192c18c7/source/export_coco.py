"""Export the existing reviewed split to COCO for a pretrained detector comparison.

No resplitting, label inference or image conversion. The test split is deliberately not exported.
Dataset stays outside the Android/source distribution. Standard library only.
"""
import argparse
import hashlib
import json
import pathlib
import zipfile


def select_records(manifest, split):
    if split not in ('train', 'validation'):
        raise ValueError('Only training and validation exports are allowed')
    selected = []
    for record in manifest['records']:
        used = record.get('used_for_training', False)
        if used and record['split'] != 'train':
            raise ValueError('Optimization image outside the training split')
        if record['split'] == split and (used if split == 'train' else not record['ignored']):
            if record['ignored']:
                raise ValueError('Ignored annotations need an explicit detector-specific policy')
            selected.append(record)
    if not selected:
        raise ValueError('Empty export')
    if len({r['id'] for r in selected}) != len(selected):
        raise ValueError('Duplicate image IDs')
    return selected


def annotations_for(record, image_id, first_annotation_id):
    result = []
    for box in record['boxes']:
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= record['width'] and 0 <= y1 < y2 <= record['height']):
            raise ValueError('Invalid annotation bounds')
        result.append(dict(id=first_annotation_id+len(result), image_id=image_id, category_id=1,
                           bbox=[x1,y1,x2-x1,y2-y1], area=(x2-x1)*(y2-y1), iscrowd=0))
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('dataset','manifest','output'):
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf8'))
    with args.dataset.open('rb') as stream:
        digest = hashlib.file_digest(stream,'sha256').hexdigest()
    if digest != manifest['source_sha256']:
        raise ValueError('Dataset hash differs from the frozen manifest')
    if args.output.exists():
        raise ValueError('Output already exists; use a new directory to preserve provenance')
    selections = {split:select_records(manifest,split) for split in ('train','validation')}
    if {r['group'] for r in selections['train']} & {r['group'] for r in selections['validation']}:
        raise ValueError('Source groups cross the split')
    args.output.mkdir(parents=True)
    counts = {}
    with zipfile.ZipFile(args.dataset) as archive:
        for split, records in selections.items():
            folder = args.output/split
            (folder/'images').mkdir(parents=True)
            images, annotations = [], []
            for image_id, record in enumerate(records):
                name = record['id']+'.jpg'
                if pathlib.Path(name).name != name or '/' in name or '\\' in name:
                    raise ValueError('Unsafe image identifier')
                original = archive.read(record['image'])
                if f'{archive.getinfo(record["image"]).CRC:08x}' != record['crc32']:
                    raise ValueError('Image CRC differs from manifest')
                (folder/'images'/name).write_bytes(original)
                images.append(dict(id=image_id,file_name=name,width=record['width'],height=record['height']))
                annotations.extend(annotations_for(record,image_id,len(annotations)))
            document = dict(images=images,annotations=annotations,
                            categories=[dict(id=0,name='background'),dict(id=1,name='pothole')])
            (folder/'labels.json').write_text(json.dumps(document),encoding='utf8')
            counts[split] = dict(images=len(images),boxes=len(annotations),
                                 negatives=sum(not r['boxes'] for r in records))
    provenance = dict(source_sha256=digest,manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                      classes=['pothole'],counts=counts,test_images_exported=False,image_folder='images',
                      source='https://doi.org/10.6084/m9.figshare.21431547.v1',
                      license='Release CC BY 4.0; author repository images CC BY-SA 4.0; retain both notices.',
                      transformations='Original JPEG bytes; VOC-derived xyxy boxes converted to COCO xywh only.')
    (args.output/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf8')
    print(json.dumps(provenance,indent=2))


if __name__ == '__main__':
    main()
