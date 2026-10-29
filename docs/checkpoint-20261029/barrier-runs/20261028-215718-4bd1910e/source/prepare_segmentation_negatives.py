"""Create annotation-defined negative masks from fixed RDD training/validation splits.

No box is converted into a foreground mask. Test images are used only to reject exact
cross-split duplicates, never for fitting or checkpoint selection.
"""
import argparse
import hashlib
import io
import json
import pathlib
import xml.etree.ElementTree as ET
import zipfile
import cv2
import numpy as np
from PIL import Image

RDD_SHA = '28eab0aa85638855e1907e63b175be2305a0accd018c54603037d3fb8cab963a'
MANIFEST_SHA = '24e131448dbdc5341d7af8caf5694eaf201812030dd0efcf37e01940120c8cf3'


def file_sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for name in ('archive', 'manifest', 'output'):
        parser.add_argument('--'+name, type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new preparation directory')
    if file_sha(args.archive) != RDD_SHA or file_sha(args.manifest) != MANIFEST_SHA:
        raise ValueError('RDD archive or fixed split manifest differs')
    manifest = json.loads(args.manifest.read_text(encoding='utf8'))
    selected = [r for r in manifest['records'] if not r['boxes'] and not r['ignored']
        and (r['split'] == 'validation' or (r['split'] == 'train' and r['used_for_training']))]
    if {split:sum(r['split']==split for r in selected) for split in ('train','validation')} != {'train':1993,'validation':1086}:
        raise ValueError('Unexpected annotation-defined negative counts')
    cv2.setNumThreads(2)
    args.output.mkdir(parents=True)
    records, image_hashes = [], {}
    for split in ('train','val'):
        (args.output/split).mkdir()
    with zipfile.ZipFile(args.archive) as archive:
        # Test bytes are read solely for source-image duplication protection.
        for record in manifest['records']:
            if record['split'] == 'test':
                digest = hashlib.sha256(archive.read(record['image'])).hexdigest()
                image_hashes[digest] = 'test'
        for index, record in enumerate(selected):
            split = 'train' if record['split']=='train' else 'val'
            image_bytes = archive.read(record['image'])
            digest = hashlib.sha256(image_bytes).hexdigest()
            if digest in image_hashes:
                raise ValueError('Duplicate source image in preparation or test partition')
            image_hashes[digest] = split
            annotation_path = f"India/train/annotations/xmls/{record['id']}.xml"
            annotation_bytes = archive.read(annotation_path)
            xml = ET.fromstring(annotation_bytes)
            if any(obj.findtext('name') == 'D40' for obj in xml.findall('object')):
                raise ValueError('Source XML contains a pothole label; cannot assign empty mask')
            with Image.open(io.BytesIO(image_bytes)) as image:
                if image.size != (720,720) or image.size != (record['width'],record['height']):
                    raise ValueError('Unexpected RDD dimensions')
                rgb = cv2.resize(np.asarray(image.convert('RGB')), (320,320), interpolation=cv2.INTER_AREA)
            target = args.output/split/(record['id']+'.npz')
            np.savez_compressed(target, images=rgb[None], masks=np.zeros((1,320,320),np.uint8))
            records.append(dict(id='rdd:'+record['id'], split=split,
                samples=[dict(source_image=record['image'], source_image_sha256=digest,
                    source_annotation=annotation_path, source_annotation_sha256=hashlib.sha256(annotation_bytes).hexdigest(),
                    resized_foreground_pixels=0)],
                negative_annotation_verified=True,
                training_arrays=dict(path=target.relative_to(args.output).as_posix(), sha256=file_sha(target))))
            if index % 250 == 0:
                print(f'Prepared {index+1}/{len(selected)} annotation-defined negatives', flush=True)
    summary = dict(kind='rdd_annotated_negatives', source_sha256=RDD_SHA, split_manifest_sha256=MANIFEST_SHA,
        source='https://doi.org/10.6084/m9.figshare.21431547.v1',
        license_note='Figshare CC BY 4.0; upstream project also declares CC BY-SA 4.0. Retain both source notices.',
        training_images=1993, validation_images=1086, test_images_exported=0,
        no_exact_cross_split_duplicates=True,
        annotation_rule='Source XML has no D40 object, including difficult objects; binary pothole mask is all zero.',
        limitations=['Annotation-defined negative, not independently reviewed as pothole-free.',
            'Other road-damage labels are not potholes; this mask does not label general terrain safety.',
            'Original grouped split retained; geographic independence is not established.',
            'Only negative images from this domain enter mask training; positive RDD boxes are not pixel masks.'])
    (args.output/'manifest.json').write_text(json.dumps(dict(summary=summary,records=records),indent=2),encoding='utf8')
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__ == '__main__':
    main()
