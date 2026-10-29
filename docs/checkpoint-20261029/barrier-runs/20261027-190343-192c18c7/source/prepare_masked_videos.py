"""Verify the published archive and extract only paired external test videos.

No archive scripts are executed. The train/validation partitions are not extracted or used.
"""
import argparse
import hashlib
import json
import pathlib
import re
import zipfile

SOURCE_SHA256='34a98a297f2e29c646cbdada37d820d2c8648e2ed5d15a28f72744d365fe9522'
SOURCE_BYTES=1025786813


def selected_pairs(archive):
    pairs={}
    for info in archive.infolist():
        if info.is_dir(): continue
        path=pathlib.PurePosixPath(info.filename)
        if '\\' in info.filename or ':' in info.filename or '..' in path.parts or path.is_absolute():
            raise ValueError('Unsafe archive path')
        found=re.search(r'(?:^|/)test/(rgb|mask)/([^/]+\.mp4)$',info.filename,re.IGNORECASE)
        if not found: continue
        kind,name=found.groups(); kind=kind.lower()
        if ((info.external_attr>>16)&0o170000)==0o120000:
            raise ValueError('Archive video is a symbolic link')
        if info.file_size<=0 or info.file_size>100_000_000: raise ValueError('Unexpected video size')
        identity=pathlib.PurePosixPath(name).stem.casefold()
        if name.startswith('.'): raise ValueError('Unexpected hidden video')
        pair=pairs.setdefault(identity,{})
        if kind in pair: raise ValueError('Duplicate video identifier')
        pair[kind]=info
    if len(pairs)!=123 or any(set(pair)!={'rgb','mask'} for pair in pairs.values()):
        raise ValueError(f'Expected 123 exact RGB/mask filename pairs; found {len(pairs)}')
    return pairs


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=pathlib.Path,required=True)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new extraction directory')
    with args.archive.open('rb') as stream:
        if args.archive.stat().st_size!=SOURCE_BYTES or hashlib.file_digest(stream,'sha256').hexdigest()!=SOURCE_SHA256:
            raise ValueError('Published archive size/checksum mismatch')
    with zipfile.ZipFile(args.archive) as archive:
        pairs=selected_pairs(archive)
        args.output.mkdir(parents=True)
        root=args.output.resolve()
        records=[]
        for index,(identity,pair) in enumerate(sorted(pairs.items())):
            record=dict(id=identity,files={})
            for kind,info in pair.items():
                relative=pathlib.Path(kind)/f'{index:03d}.mp4'
                target=args.output/relative
                if not target.resolve().is_relative_to(root): raise ValueError('Extraction escapes output')
                target.parent.mkdir(exist_ok=True)
                digest=hashlib.sha256(); written=0
                with archive.open(info) as source, target.open('xb') as destination:
                    while chunk:=source.read(1024*1024):
                        destination.write(chunk); digest.update(chunk); written+=len(chunk)
                if written!=info.file_size: raise ValueError('Extracted video length mismatch')
                record['files'][kind]=dict(path=relative.as_posix(),archive_entry=info.filename,
                    sha256=digest.hexdigest(),bytes=written)
            records.append(record)
    manifest=dict(dataset_doi='10.17632/5bwfg4v4cd.3',source_sha256=SOURCE_SHA256,
        authors=['Muhammad Ihsan','Agus Harjoko','Muhammad Alfian Amrizal'],license='CC BY 4.0',
        source='https://data.mendeley.com/datasets/5bwfg4v4cd/3',
        paper='https://doi.org/10.1016/j.dib.2024.110131',split='published test partition',
        use='external evaluation; no training',videos=len(records),records=records,
        limitations=['Short downward-facing phone clips, not walking-route trials.',
                    'Masks are semantic, with semi-manual tracking and acknowledged boundary uncertainty.',
                    'Published capture height is not a measured per-frame distance label.'])
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps(dict(videos=len(records),source_sha256=SOURCE_SHA256)),flush=True)


if __name__=='__main__': main()
