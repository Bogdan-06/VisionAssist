"""Fetch one published RDD2022 country archive, verifying the outer ZIP member CRC.

Only reads public HTTP byte ranges. No credentials, mirrors or executable model downloads.
Source metadata: https://api.figshare.com/v2/articles/21431547
"""
import argparse, hashlib, io, json, pathlib, struct, urllib.request, zipfile, zlib

ARTICLE = 'https://api.figshare.com/v2/articles/21431547'
class RemoteArchive(io.RawIOBase):
    def __init__(self, url, size): self.url, self.size, self.position = url, size, 0
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.position
    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        return self.position
    def read(self, size=-1):
        size = min(size if size >= 0 else self.size-self.position, self.size-self.position)
        if size <= 0: return b''
        if size > 16_000_000: raise ValueError('Index read unexpectedly large')
        start = self.position; self.position += size
        with open_range(self.url, start, size) as response: data = response.read(size)
        if len(data) != size: raise ValueError('Incomplete archive index')
        return data

def open_range(url, start, count):
    request = urllib.request.Request(url, headers={'Range': f'bytes={start}-{start+count-1}'})
    response = urllib.request.urlopen(request, timeout=90)
    if response.status != 206 or not response.headers.get('Content-Range', '').startswith(f'bytes {start}-'):
        response.close(); raise RuntimeError('Public server did not honor the requested byte range')
    return response

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--country', choices=['India', 'Czech', 'China_MotorBike', 'China_Drone', 'Japan', 'United_States', 'Norway'], default='India')
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    metadata = json.load(urllib.request.urlopen(ARTICLE, timeout=30))
    print('Published dataset:', metadata['title'], '| metadata license:', metadata['license']['name'], flush=True)
    source = next(item for item in metadata['files'] if item['name'].endswith('.zip'))
    remote = RemoteArchive(source['download_url'], source['size'])
    with zipfile.ZipFile(remote) as archive: info = archive.getinfo(f'RDD2022/{args.country}.zip')
    if info.compress_type != zipfile.ZIP_STORED: raise RuntimeError('Country member is no longer stored without compression')
    remote.seek(info.header_offset); header = remote.read(30)
    if header[:4] != b'PK\x03\x04': raise RuntimeError('Invalid member header')
    name_size, extra_size = struct.unpack_from('<HH', header, 26)
    offset = info.header_offset + 30 + name_size + extra_size
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists(): raise FileExistsError('Output already exists; verify its manifest before reusing it')
    partial = args.output.with_suffix('.part')
    digest = hashlib.sha256(); crc = 0; count = 0
    with open_range(source['download_url'], offset, info.file_size) as response, partial.open('wb') as out:
        while data := response.read(1024*1024):
            out.write(data); digest.update(data); crc = zlib.crc32(data, crc); count += len(data)
    if count != info.file_size or crc != info.CRC: raise RuntimeError('Country ZIP length/CRC verification failed')
    partial.replace(args.output)
    manifest = {'article': ARTICLE, 'doi': metadata['doi'], 'license': metadata['license'],
        'outer_file_id': source['id'], 'outer_size': source['size'], 'member': info.filename,
        'bytes': count, 'crc32': f'{crc:08x}', 'sha256': digest.hexdigest()}
    args.output.with_suffix('.provenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2), flush=True)

if __name__ == '__main__': main()
