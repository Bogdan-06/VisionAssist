"""Narrow vision-only compatibility patch for an isolated Model Maker 0.2.1.4 venv.

Removes eager imports of unused text/other tasks and preserves labelled negative images.
No tokenizer, model, loss, prediction, or TensorFlow operation is replaced or mocked.
NLP text tasks are unavailable afterward.
Upstream Apache-2.0 copyright/license headers remain intact. Original files are retained.
"""
import hashlib
import importlib.metadata
import pathlib
import sys
import sysconfig


def main():
    if sys.prefix == sys.base_prefix or sys.platform not in ('win32','linux'):
        raise RuntimeError('Use a dedicated Windows or Linux virtual environment')
    if importlib.metadata.version('mediapipe-model-maker') != '0.2.1.4':
        raise RuntimeError('Unexpected Model Maker version')
    if importlib.metadata.version('tf-models-official') != '2.15.0':
        raise RuntimeError('Unexpected Model Garden version')
    site = pathlib.Path(sysconfig.get_paths()['purelib'])
    patches = [
        ('mediapipe_model_maker/__init__.py',
         '04e52987c43aa289f8e9e2a91340db60c8738f5ab9e2e1b1ec45557e2857a451',
         ('from mediapipe_model_maker.python.vision import image_classifier',
          'from mediapipe_model_maker.python.vision import gesture_recognizer',
          'from mediapipe_model_maker.python.text import text_classifier',
          'from mediapipe_model_maker.python.vision import face_stylizer')),
        ('official/nlp/modeling/layers/__init__.py',
         'cea4af51ebd00ca96bd27ba367dc2db3679e55ca202f303c70416969280fb87d',
         ('from official.nlp.modeling.layers.text_layers import ',)),
        ('mediapipe_model_maker/python/vision/object_detector/dataset_util.py',
         '8010ae7cd0e218d02ec65a9a6a0636504e72e61b7c5177d189ce5f96bb6380d3', ()),
    ]
    for relative, expected, prefixes in patches:
        path = site/relative
        backup = path.with_suffix('.py.visionassist-original')
        source = backup.read_bytes() if backup.exists() else path.read_bytes()
        if hashlib.sha256(source).hexdigest() != expected:
            raise RuntimeError(f'Unrecognized upstream source: {relative}')
        lines = source.decode('utf8').splitlines(keepends=True)
        modified_text = ''.join(line for line in lines if not any(line.startswith(p) for p in prefixes))
        if relative.endswith('/dataset_util.py'):
            skip = "      if not data['xmin']:\n        # Skip examples which have no annotations\n        continue\n"
            if modified_text.count(skip) != 1:
                raise RuntimeError('Unrecognized COCO negative-image handling')
            modified_text = modified_text.replace(skip,'      # VisionAssist: retain explicitly labelled negative images.\n')
            for coordinate in ('xmin','xmax','ymin','ymax'):
                old=f"tfrecord_lib.convert_to_feature(data['{coordinate}'])"
                if modified_text.count(old)!=1: raise RuntimeError('Unrecognized coordinate serialization')
                modified_text=modified_text.replace(old,f"tfrecord_lib.convert_to_feature(data['{coordinate}'], 'float_list')")
            old="          data['category_id']\n"
            if modified_text.count(old)!=1: raise RuntimeError('Unrecognized label serialization')
            modified_text=modified_text.replace(old,"          data['category_id'], 'int64_list'\n")
        modified = modified_text.encode('utf8')
        if backup.exists() and path.read_bytes() != modified:
            previous=hashlib.sha256(path.read_bytes()).hexdigest()
            if previous!='a3a00e6692dd5f96c5cfa583e590856197f5992bd4484d7225c12f46dc6be71f':
                raise RuntimeError(f'Existing local modifications: {relative}')
        if not backup.exists():
            backup.write_bytes(source)
        path.write_bytes(modified)
        print(relative,hashlib.sha256(modified).hexdigest())


if __name__ == '__main__': main()
