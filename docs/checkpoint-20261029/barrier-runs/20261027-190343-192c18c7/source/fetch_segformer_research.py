"""Fetch a pinned official stair-label checkpoint for local research/evaluation only.

NVIDIA's linked license restricts use to research/evaluation. No Android packaging,
remote repository code, pickle weights or automatic inference is performed here.
"""
import argparse
import hashlib
import json
import pathlib
import struct
import urllib.request

REVISION = '489d5cd81a0b59fab9b7ea758d3548ebe99677da'
LICENSE_REVISION = '1022b45ddb0d18c6288683d60139ac9b1e83a5f2'
BASE = f'https://huggingface.co/nvidia/segformer-b0-finetuned-ade-512-512/resolve/{REVISION}/'
FILES = {
    'README.md': (3189, 'a0fbaa9434d2c61a704150a0f61e64e538ee105f'),
    'config.json': (6884, 'ba9e66725a3c53aeff1e9fede9ed14e6800f76d5'),
    'preprocessor_config.json': (271, '731939640bb201ce03c59a5b2d6bc1ee4f4162b3'),
    'model.safetensors': (15036944, '6ae39addd01de6b1b8bde2cf677d43a5cd733424b8d186de3f95d1c51fee23f9'),
}


def fetch(url, maximum):
    request = urllib.request.Request(url, headers={'User-Agent':'VisionAssist-research'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(maximum+1)
    if len(data)>maximum:
        raise ValueError('Download exceeds expected length')
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new research-only directory')
    license_url = f'https://raw.githubusercontent.com/NVlabs/SegFormer/{LICENSE_REVISION}/LICENSE'
    license_bytes = fetch(license_url, 10000)
    license_text = license_bytes.decode('utf8')
    if 'research or evaluation purposes only' not in license_text or 'NVIDIA Source Code License for SegFormer' not in license_text:
        raise ValueError('Unexpected license text; review required')
    args.output.mkdir(parents=True)
    (args.output/'LICENSE').write_bytes(license_bytes)
    entries = []
    for name,(length,digest) in FILES.items():
        data = fetch(BASE+name, length)
        if len(data)!=length:
            raise ValueError('Unexpected file length')
        actual = (hashlib.sha256(data).hexdigest() if name.endswith('.safetensors') else
                  hashlib.sha1(b'blob '+str(len(data)).encode()+b'\x00'+data).hexdigest())
        if actual != digest:
            raise ValueError('Publisher file digest mismatch')
        (args.output/name).write_bytes(data)
        entries.append(dict(name=name, bytes=length, sha256=hashlib.sha256(data).hexdigest(),
                            publisher_digest=digest, source=BASE+name))
    config = json.loads((args.output/'config.json').read_text(encoding='utf8'))
    expected = {'53':'stairs','59':'stairway','121':'step'}
    if any(config['id2label'].get(key)!=value for key,value in expected.items()) or len(config['id2label'])!=150:
        raise ValueError('Unexpected semantic classes')
    # Inspect safetensors metadata as bounded JSON, without loading tensor libraries.
    with (args.output/'model.safetensors').open('rb') as stream:
        header_length = struct.unpack('<Q',stream.read(8))[0]
        if not 0<header_length<1_000_000:
            raise ValueError('Unexpected tensor header length')
        header = json.loads(stream.read(header_length))
    tensors = {key:value for key,value in header.items() if key!='__metadata__'}
    classifier = tensors.get('decode_head.classifier.weight')
    if not classifier or classifier['shape'] != [150,256,1,1] or classifier['dtype'] != 'F32':
        raise ValueError('Unexpected classifier tensor')
    payload_bytes = FILES['model.safetensors'][0]-8-header_length
    for tensor in tensors.values():
        start,end = tensor['data_offsets']
        if not 0<=start<=end<=payload_bytes:
            raise ValueError('Tensor offsets exceed payload')
    report = dict(model='nvidia/segformer-b0-finetuned-ade-512-512', revision=REVISION,
        use='Acquired for local noncommercial research/evaluation only; not bundled in Android or cleared for general app use',
        license_source=license_url, license_sha256=hashlib.sha256(license_bytes).hexdigest(),
        license_restriction='NVIDIA SegFormer license section 3.3: research or evaluation purposes only',
        class_ids=expected, curb_class=False, tensors=len(tensors), files=entries,
        training_provenance='Model card: ImageNet-1k encoder pretraining and ADE20K fine-tuning',
        limitations=['Semantic classes are not calibrated hazard events or measured distances.',
            'No accuracy, phone runtime or camera performance has been established by this acquisition.',
            'Do not map sidewalk to curb or ordinary image semantics to surface geometry.',
            'Retain NVIDIA license; this model is not cleared for general-use or commercial app distribution.'])
    (args.output/'provenance.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    main()
