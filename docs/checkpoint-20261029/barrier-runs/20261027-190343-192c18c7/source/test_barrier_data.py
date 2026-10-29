"""Offline regressions for download recovery and barrier split integrity.

Synthetic images exercise data plumbing only; they are never training/evaluation data.
Run: python -m unittest discover -s tools/ground -p test_barrier_data.py -v
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

import numpy as np
from PIL import Image, ImageEnhance

import fetch_barrier_archive as download
import prepare_barrier_dataset as preparation
import export_barrier_coco as coco
from evaluate_barrier_detector import class_counts, metrics


class Response(io.BytesIO):
    status = 206

    def __init__(self, content, content_range='bytes 8-15/20'):
        super().__init__(content)
        self.headers = {'Content-Range': content_range}


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'source.part'
        self.path.write_bytes(b'x' * 20)
        for name, value in [('CHUNK', 8), ('SIZE', 20)]:
            patcher = patch.object(download, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_truncated_range_restarts_and_preserves_neighbors(self):
        with patch.object(download.urllib.request, 'urlopen', side_effect=[
                Response(b'bad'), Response(b'12345678')]) as request, \
                patch.object(download.time, 'sleep') as sleep:
            index, digest = download.download_chunk(1, self.path)
        self.assertEqual(self.path.read_bytes(), b'x' * 8 + b'12345678' + b'x' * 4)
        self.assertEqual((index, digest), ('1', hashlib.sha256(b'12345678').hexdigest()))
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_incorrect_content_range_is_not_retried(self):
        with patch.object(download.urllib.request, 'urlopen', return_value=
                Response(b'12345678', 'bytes 0-7/20')) as request:
            with self.assertRaisesRegex(ValueError, 'exact requested range'):
                download.download_chunk(1, self.path)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(self.path.read_bytes(), b'x' * 20)

    def test_retry_limit_and_http_error_classification(self):
        transient = urllib.error.HTTPError(download.URL, 503, 'Unavailable', {}, None)
        with patch.object(download.urllib.request, 'urlopen', side_effect=transient) as request, \
                patch.object(download.time, 'sleep'):
            with self.assertRaises(urllib.error.HTTPError):
                download.download_chunk(1, self.path)
        self.assertEqual(request.call_count, 5)
        permanent = urllib.error.HTTPError(download.URL, 403, 'Forbidden', {}, None)
        with patch.object(download.urllib.request, 'urlopen', side_effect=permanent) as request:
            with self.assertRaises(urllib.error.HTTPError):
                download.download_chunk(1, self.path)
        self.assertEqual(request.call_count, 1)

    def test_oversized_response_and_last_short_chunk(self):
        with patch.object(download.urllib.request, 'urlopen', return_value=Response(b'123456789')):
            with self.assertRaisesRegex(ValueError, 'exceeded'):
                download.download_chunk(1, self.path)
        with patch.object(download.urllib.request, 'urlopen', return_value=Response(b'last', 'bytes 16-19/20')):
            self.assertEqual(download.download_chunk(2, self.path)[1], hashlib.sha256(b'last').hexdigest())
        self.assertEqual(self.path.read_bytes()[-4:], b'last')


class AnnotationTests(unittest.TestCase):
    @staticmethod
    def xml(box):
        return ('<annotations><image name="images/a.jpg" width="100" height="80">'
                + box + '</image></annotations>').encode()

    def test_distinct_target_types_and_ignored_source_labels(self):
        boxes = ''.join(f'<box label="{label}" xtl="1" ytl="2" xbr="30" ybr="40">'
                        f'<attribute name="type">{kind}</attribute></box>'
                        for label, kind in [('stair', ''), ('step', 'curb'),
                                            ('step', 'doorstep'), ('step', 'other'), ('ramp', '')])
        record = preparation.annotations(self.xml(boxes))[0]
        self.assertEqual([b['target_class'] for b in record['boxes']], ['stairs', 'curb', 'step', 'step', None])
        self.assertEqual(record['boxes'][2]['attributes']['type'], 'doorstep')

    def test_malformed_labels_boxes_and_xml_are_rejected(self):
        for label, kind, x2 in [('unknown', '', '30'), ('step', '', '30'),
                                ('stair', '', 'nan'), ('stair', '', '101'), ('stair', '', '0')]:
            with self.subTest(label=label, kind=kind, x2=x2), self.assertRaises(ValueError):
                preparation.annotations(self.xml(f'<box label="{label}" xtl="1" ytl="2" xbr="{x2}" ybr="40">'
                                                  f'<attribute name="type">{kind}</attribute></box>'))
        with self.assertRaises(ValueError):
            preparation.annotations(b'<!DOCTYPE annotations []><annotations/>')


class SplitIntegrityTests(unittest.TestCase):
    def test_exact_conflicts_near_duplicates_review_and_orientation(self):
        rng = np.random.default_rng(18)
        records, contents = [], {}

        def add(index, image, category, orientation=None, encoded=None):
            name = f'images/{index:04}.jpg'
            if encoded is None:
                stream = io.BytesIO()
                exif = Image.Exif()
                if orientation is not None:
                    exif[274] = orientation
                image.save(stream, format='JPEG', quality=95, exif=exif)
                encoded = stream.getvalue()
            contents[name] = encoded
            boxes = [dict(target_class=category, box=[2., 3., 40., 35.])] if category else []
            records.append(dict(image=name, width=64, height=48, boxes=boxes, task_id='synthetic-test'))

        for i in range(160):
            add(i, Image.fromarray(rng.integers(25, 230, (48, 64, 3), dtype=np.uint8)),
                ['stairs', 'curb', 'step', None][i % 4])
        add(160, None, 'stairs', encoded=contents['images/0000.jpg'])
        add(161, None, 'stairs', encoded=contents['images/0001.jpg'])  # Conflicting identical image.
        base = Image.open(io.BytesIO(contents['images/0002.jpg'])).convert('RGB')
        add(162, ImageEnhance.Brightness(base).enhance(1.02), 'step')
        add(163, Image.fromarray(rng.integers(0, 256, (48, 64, 3), dtype=np.uint8)), None, orientation=6)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with zipfile.ZipFile(path / 'images.zip', 'w') as archive:
                for name, content in contents.items():
                    archive.writestr(name, content)
            with zipfile.ZipFile(path / 'images.zip') as archive:
                result = preparation.prepare(archive, copy.deepcopy(records), path, {'images/0000.jpg'})
            by_name = {r['image']: r for r in result['records']}
            self.assertEqual(by_name['images/0160.jpg']['excluded_reason'], 'Exact decoded duplicate')
            for name in ('images/0001.jpg', 'images/0161.jpg'):
                self.assertEqual(by_name[name]['excluded_reason'], 'Conflicting target boxes on identical decoded image')
            self.assertEqual(by_name['images/0163.jpg']['split'], 'excluded')
            self.assertEqual(by_name['images/0000.jpg']['split'], 'train')
            self.assertEqual(by_name['images/0002.jpg']['group'], by_name['images/0162.jpg']['group'])
            groups = {}
            for record in result['records']:
                if record['split'] != 'excluded':
                    groups.setdefault(record['group'], set()).add(record['split'])
            self.assertTrue(all(len(splits) == 1 for splits in groups.values()))
            for name in result['reviewed_images_forced_into_training']:
                self.assertIn(by_name[name]['split'], ('train', 'excluded'))
            for split in ('train', 'validation', 'test'):
                self.assertEqual(set(result['splits'][split]['target_boxes']), {'stairs', 'curb', 'step'})
            self.assertTrue((path / 'label-review.png').exists())
            self.assertTrue((path / 'near-duplicate-review.png').exists())
            result['classes'] = coco.CLASSES
            selected = coco.selections(result)
            with zipfile.ZipFile(path / 'images.zip') as archive:
                counts, files = coco.export(archive, selected, path / 'coco')
            exported_names = set()
            for split in ('train', 'validation'):
                labels = path / 'coco' / split / 'labels.json'
                document = json.loads(labels.read_text())
                self.assertEqual(files[split]['labels_sha256'], hashlib.sha256(labels.read_bytes()).hexdigest())
                self.assertEqual({c['id']: c['name'] for c in document['categories']},
                                 {0: 'background', 1: 'stairs', 2: 'curb', 3: 'step'})
                self.assertEqual(counts[split]['images'], len(selected[split]))
                self.assertGreater(counts[split]['negatives'], 0)
                for image in document['images']:
                    name = image['source_image']
                    exported_names.add(name)
                    self.assertEqual((path / 'coco' / split / 'images' / image['file_name']).read_bytes(), contents[name])
                    self.assertEqual(by_name[name]['split'], split)
                for annotation in document['annotations']:
                    self.assertEqual(annotation['bbox'], [2., 3., 38., 32.])
                    self.assertNotIn('segmentation', annotation)
            self.assertFalse(exported_names & {r['image'] for r in result['records'] if r['split'] in ('test', 'excluded')})
            tampered = copy.deepcopy(result)
            test_record = next(r for r in tampered['records'] if r['split'] == 'test')
            test_record['group'] = by_name['images/0000.jpg']['group']
            with self.assertRaisesRegex(ValueError, 'cross fitting/evaluation'):
                coco.selections(tampered)
            tampered = copy.deepcopy(selected)
            tampered['train'][0]['sha256'] = '0' * 64
            with zipfile.ZipFile(path / 'images.zip') as archive, self.assertRaisesRegex(ValueError, 'bytes differ'):
                coco.export(archive, tampered, path / 'corrupt')


class ClassMetricTests(unittest.TestCase):
    def test_wrong_class_duplicate_and_score_order(self):
        truth = [dict(target_class='stairs', box=[0, 0, 10, 10])]
        predictions = [dict(score=.2, box=[0, 0, 10, 10], **{'class': 'stairs'}),
                       dict(score=.9, box=[0, 0, 10, 10], **{'class': 'curb'})]
        result = class_counts(predictions, truth, .5)
        self.assertEqual(result, {'stairs': (0, 0, 1), 'curb': (0, 1, 0), 'step': (0, 0, 0)})
        predictions += [dict(score=.8, box=[0, 0, 10, 10], **{'class': 'stairs'})]
        self.assertEqual(class_counts(predictions, truth, .1)['stairs'], (1, 1, 0))
        self.assertEqual(class_counts(predictions, truth, .5)['stairs'], (1, 0, 0))
        self.assertIsNone(metrics((0, 0, 0))['recall'])
        self.assertIsNone(metrics((0, 0, 0))['precision'])


if __name__ == '__main__':
    unittest.main()
