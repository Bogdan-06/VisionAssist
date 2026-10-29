"""Download the published CC BY 4.0 barrier ZIP with bounded, resumable ranges."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import http.client
import json
from pathlib import Path
import time
import urllib.request
import urllib.error
import zipfile

from fetch_barrier_sample import RECORD, SIZE, MD5, URL

CHUNK = 64 * 1024 * 1024


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf8')
    temporary.replace(path)


def download_chunk_once(index, partial):
    start = index * CHUNK
    size = min(CHUNK, SIZE - start)
    end = start + size - 1
    request = urllib.request.Request(URL, headers={'Range': f'bytes={start}-{end}',
                                                   'User-Agent': 'VisionAssist-research'})
    digest = hashlib.sha256()
    received = 0
    with urllib.request.urlopen(request, timeout=60) as response, partial.open('r+b') as target:
        if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{SIZE}':
            raise ValueError('Server did not return the exact requested range')
        target.seek(start)
        while received < size:
            block = response.read(min(1024 * 1024, size - received))
            if not block:
                raise EOFError('Incomplete download range')
            target.write(block)
            digest.update(block)
            received += len(block)
        if response.read(1):
            raise ValueError('Range response exceeded requested length')
        target.flush()
    return str(index), digest.hexdigest()


def download_chunk(index, partial, attempts=5):
    """Restart only the failed range; integrity/identity errors remain fatal."""
    for attempt in range(attempts):
        try:
            return download_chunk_once(index, partial)
        except urllib.error.HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt + 1 == attempts:
                raise
        except (EOFError, TimeoutError, ConnectionError, urllib.error.URLError,
                http.client.IncompleteRead, http.client.RemoteDisconnected):
            if attempt + 1 == attempts:
                raise
        delay = min(30, 2 ** (attempt + 1))
        print(f'Range {index} interrupted; retry {attempt + 2}/{attempts} in {delay}s', flush=True)
        time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Final output already exists; inspect its provenance before reuse')
    with urllib.request.urlopen(RECORD, timeout=30) as response:
        metadata = json.load(response)
    source = next(f for f in metadata['files'] if f['key'] == 'wm_barriers_data.zip')
    if metadata['metadata']['license']['id'] != 'cc-by-4.0' or source['size'] != SIZE or source['checksum'] != 'md5:' + MD5:
        raise ValueError('Published license/source identity changed; review required')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix('.part')
    checkpoint = args.output.with_suffix('.download.json')
    completed = {}
    if partial.exists() or checkpoint.exists():
        if not partial.exists() or not checkpoint.exists() or partial.stat().st_size != SIZE:
            raise ValueError('Incomplete download metadata; do not overwrite unrelated partial files')
        previous = json.loads(checkpoint.read_text())
        if previous['url'] != URL or previous['bytes'] != SIZE or previous['chunk_bytes'] != CHUNK:
            raise ValueError('Partial download belongs to a different source')
        with partial.open('rb') as stream:
            for index, expected in previous['completed_chunks'].items():
                start = int(index) * CHUNK
                if not 0 <= start < SIZE:
                    raise ValueError('Invalid saved chunk index')
                stream.seek(start)
                content = stream.read(min(CHUNK, SIZE - start))
                if hashlib.sha256(content).hexdigest() == expected:
                    completed[index] = expected
    else:
        with partial.open('xb') as stream:
            stream.truncate(SIZE)
    started = time.monotonic()
    state = dict(url=URL, bytes=SIZE, publisher_md5=MD5, chunk_bytes=CHUNK,
                 completed_chunks=completed, state='downloading')
    save(checkpoint, state)
    count = (SIZE + CHUNK - 1) // CHUNK
    print(f'Fetching reviewed CC BY 4.0 source: {SIZE:,} bytes, {len(completed)}/{count} verified chunks present.', flush=True)
    futures = []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(download_chunk, index, partial) for index in range(count) if str(index) not in completed]
            try:
                for future in as_completed(futures):
                    index, digest = future.result()
                    completed[index] = digest
                    state['elapsed_seconds'] = time.monotonic() - started
                    save(checkpoint, state)
                    print(f'Downloaded and hashed {len(completed)}/{count} chunks', flush=True)
            except BaseException:
                for future in futures:
                    future.cancel()
                raise
        state['state'] = 'verifying_full_archive'
        save(checkpoint, state)
        md5, sha = hashlib.md5(), hashlib.sha256()
        with partial.open('rb') as stream:
            while block := stream.read(8 * 1024 * 1024):
                md5.update(block)
                sha.update(block)
        if md5.hexdigest() != MD5:
            raise ValueError('Full archive MD5 does not match the publisher')
        print('Full publisher MD5 passed; checking ZIP CRCs...', flush=True)
        with zipfile.ZipFile(partial) as archive:
            names = archive.namelist()
            if len(names) != 5540 or len(set(names)) != len(names) or archive.testzip() is not None:
                raise ValueError('Archive member count, uniqueness or CRC check failed')
        partial.replace(args.output)
        report = dict(source='https://doi.org/10.5281/zenodo.6382090', license='CC BY 4.0',
                      attribution='Jakob Stolberg; collectors Christopher Richters and Sami Nenno; HIIG, 2022',
                      bytes=SIZE, publisher_md5=MD5, sha256=sha.hexdigest(), zip_crcs_passed=True,
                      members=5540, url=URL, metadata=metadata)
        save(args.output.with_suffix('.provenance.json'), report)
        state['state'] = 'completed'
        state['sha256'] = sha.hexdigest()
        state['elapsed_seconds'] = time.monotonic() - started
        save(checkpoint, state)
        print(json.dumps({k: report[k] for k in ('bytes', 'publisher_md5', 'sha256', 'zip_crcs_passed')}, indent=2))
    except BaseException as error:
        state['state'] = 'failed'
        state['error'] = str(error)
        save(checkpoint, state)
        raise


if __name__ == '__main__':
    main()
