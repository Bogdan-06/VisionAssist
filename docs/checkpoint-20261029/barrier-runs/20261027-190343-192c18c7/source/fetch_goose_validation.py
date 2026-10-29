"""Acquire the official labelled GOOSE validation archive for curb-data inspection.

No weights/code are downloaded or executed. The training split is not downloaded here.
"""
import argparse
import hashlib
import json
import pathlib
import urllib.request

URL = 'https://goose-dataset.de/storage/goose_2d_val.zip'
EXPECTED_BYTES = 2857251081
EXPECTED_ETAG = '"67d9a658-aa4e3109"'
# Pinned from the first HTTPS acquisition, not a publisher-supplied checksum.
EXPECTED_SHA256 = '9fed0dacfef36fa18c866dc724e63ea7a42796244fdd998bc91330555ed071d1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output/'goose_2d_val.zip'
    partial = args.output/'goose_2d_val.zip.part'
    if target.exists() or partial.exists(): raise ValueError('Inspect existing download before retrying')
    with urllib.request.urlopen(urllib.request.Request(URL, method='HEAD'), timeout=30) as response:
        headers = dict(response.headers)
        if int(response.headers['Content-Length']) != EXPECTED_BYTES or response.headers['ETag'] != EXPECTED_ETAG:
            raise ValueError('Official archive version changed; review metadata before downloading')
    digest = hashlib.sha256(); written = 0; last_report = 0
    request = urllib.request.Request(URL, headers={'If-Match': EXPECTED_ETAG})
    with urllib.request.urlopen(request, timeout=60) as response, partial.open('xb') as stream:
        if response.status != 200 or response.headers['ETag'] != EXPECTED_ETAG:
            raise ValueError('Response differs from inspected archive')
        while chunk := response.read(1024*1024):
            written += len(chunk)
            if written > EXPECTED_BYTES: raise ValueError('Download exceeds declared size')
            stream.write(chunk); digest.update(chunk)
            if written-last_report >= 100*1024*1024:
                print(f'{written}/{EXPECTED_BYTES} bytes', flush=True); last_report = written
    if written != EXPECTED_BYTES: raise ValueError('Incomplete archive')
    actual_hash = digest.hexdigest()
    if actual_hash != EXPECTED_SHA256: raise ValueError('Archive differs from the reviewed local version')
    partial.rename(target)
    report = dict(url=URL, source='https://goose-dataset.de/docs/setup/',
        license='CC BY-SA 4.0', license_url='https://creativecommons.org/licenses/by-sa/4.0/',
        attribution='Peter Mortimer, Raphael Hagmanns, Miguel Granero, Thorsten Luettel, Janko Petereit, Hans-Joachim Wuensche',
        paper='https://arxiv.org/abs/2310.16788', bytes=written, sha256=actual_hash,
        server_headers=headers, split='validation', use='curb annotation inspection; not training',
        checksum_scope='Locally computed SHA-256; no publisher-provided cryptographic checksum found. HTTPS origin, size and ETag checked; inspect ZIP CRCs separately.')
    (args.output/'provenance.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(dict(bytes=written,sha256=actual_hash)),flush=True)


if __name__ == '__main__': main()
