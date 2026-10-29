"""Fetch a deterministic research sample from the CC BY 4.0 HIIG barrier dataset.

Only selected ZIP members are downloaded, CRC checked and hashed. The full archive
MD5 is recorded from Zenodo, NOT claimed as verified by this partial acquisition.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image

RECORD = 'https://zenodo.org/api/records/6382090'
SIZE = 7972407510
MD5 = 'd96051ca1339d1c1afa9ac736eabd058'
URL = RECORD + '/files/wm_barriers_data.zip/content'


class RangeFile(io.RawIOBase):
    def __init__(self):
        self.position = 0
        self.downloaded = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else SIZE + offset
        if not 0 <= self.position <= SIZE:
            raise ValueError('Invalid archive offset')
        return self.position

    def read(self, size=-1):
        size = min(size if size >= 0 else SIZE - self.position, SIZE - self.position)
        if size == 0:
            return b''
        if not 0 < size <= 16_000_000:
            raise ValueError('Unexpectedly large member/index read')
        end = self.position + size - 1
        request = urllib.request.Request(URL, headers={'Range': f'bytes={self.position}-{end}',
                                                        'User-Agent': 'VisionAssist-research'})
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 206 or response.headers.get('Content-Range') != f'bytes {self.position}-{end}/{SIZE}':
                raise ValueError('Server did not return the exact requested archive range')
            data = response.read(size + 1)
        if len(data) != size:
            raise ValueError('Incomplete archive range')
        self.position += size
        self.downloaded += size
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new output directory')
    with urllib.request.urlopen(RECORD, timeout=30) as response:
        metadata = json.load(response)
    source = next(f for f in metadata['files'] if f['key'] == 'wm_barriers_data.zip')
    if metadata['metadata']['license']['id'] != 'cc-by-4.0' or source['size'] != SIZE or source['checksum'] != 'md5:' + MD5:
        raise ValueError('Published license or source identity changed; review required')
    remote = RangeFile()
    with zipfile.ZipFile(remote) as archive:
        info = archive.getinfo('wm_annotations.xml')
        if info.file_size > 3_000_000:
            raise ValueError('Unexpected annotation size')
        xml = archive.read(info)  # ZipFile verifies the member CRC.
        if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
            raise ValueError('Unexpected XML declarations')
        annotations = ET.fromstring(xml)
        images = annotations.findall('image')
        if len(images) != 5538:
            raise ValueError('Unexpected published image count')
        counts = Counter(box.get('label') for image in images for box in image.findall('box'))
        curb_count = sum(box.get('label') == 'step' and
                         any(a.get('name') == 'type' and a.text == 'curb' for a in box.findall('attribute'))
                         for image in images for box in image.findall('box'))
        order = lambda image: hashlib.sha256(image.get('name').encode()).hexdigest()
        positives = sorted([i for i in images if any(b.get('label') == 'stair' for b in i.findall('box'))], key=order)[:4]
        negatives = sorted([i for i in images if not any(b.get('label') in ('stair', 'step') for b in i.findall('box'))], key=order)[:4]
        selected = positives + negatives
        if len(selected) != 8:
            raise ValueError('Insufficient sample strata')
        args.output.mkdir(parents=True)
        (args.output / 'zenodo-record.json').write_text(json.dumps(metadata, indent=2), encoding='utf8')
        (args.output / 'wm_annotations.xml').write_bytes(xml)
        records = []
        for index, image in enumerate(selected):
            entry = image.get('name')
            member = archive.getinfo(entry)
            if not 0 < member.file_size < 10_000_000:
                raise ValueError('Unexpected image size')
            content = archive.read(member)
            with Image.open(io.BytesIO(content)) as decoded:
                width, height = decoded.size
                decoded.load()
            if (width, height) != (int(image.get('width')), int(image.get('height'))):
                raise ValueError('Image/annotation dimensions differ')
            filename = f'{index:02d}.jpg'
            (args.output / filename).write_bytes(content)
            boxes = []
            for box in image.findall('box'):
                bounds = [float(box.get(k)) for k in ('xtl', 'ytl', 'xbr', 'ybr')]
                x1, y1, x2, y2 = bounds
                if not 0 <= x1 < x2 <= width or not 0 <= y1 < y2 <= height:
                    raise ValueError('Invalid published box')
                boxes.append(dict(label=box.get('label'), box=bounds,
                                  attributes={a.get('name'): a.text for a in box.findall('attribute')}))
            records.append(dict(path=filename, archive_entry=entry, width=width, height=height,
                                sha256=hashlib.sha256(content).hexdigest(), crc32=f'{member.CRC:08x}',
                                stratum='stair' if index < 4 else 'no_annotated_stair_or_step', boxes=boxes))
            print(f'Fetched {index + 1}/8: {entry}', flush=True)
    report = dict(source='https://doi.org/10.5281/zenodo.6382090', license='CC BY 4.0',
                  attribution='Jakob Stolberg; collectors Christopher Richters and Sami Nenno; HIIG, 2022',
                  archive_url=URL, archive_bytes=SIZE, publisher_archive_md5=MD5,
                  full_archive_checksum_verified=False, selected_member_crcs_verified=True,
                  downloaded_bytes=remote.downloaded, annotation_sha256=hashlib.sha256(xml).hexdigest(),
                  annotation_image_count=len(images), annotation_counts=dict(counts), curb_boxes=curb_count,
                  selection='First four by SHA256 of source member name in each stratum; no model-based selection',
                  records=records, limitations=[
                      'Eight-image execution sample, not a representative evaluation or training split.',
                      'Negative means no published stair/step annotation, not independently reviewed hazard-free.',
                      'Source uses visible-region boxes and wheelchair-accessibility annotation conventions.',
                      'Step heights are annotator estimates, not measured distance ground truth.',
                      'Source locations and overlap with model pretraining are not established.'])
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({k: report[k] for k in ('downloaded_bytes', 'annotation_counts', 'curb_boxes')}, indent=2))


if __name__ == '__main__':
    main()
