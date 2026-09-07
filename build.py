#!/usr/bin/env python3
"""Build BlueJ FRI Edition from an official BlueJ Windows standalone ZIP."""
from __future__ import annotations
import argparse, shutil, sys, tempfile, urllib.error, urllib.request, urllib.parse, zipfile
from pathlib import Path
from typing import NoReturn

ROOT=Path(__file__).resolve().parent; DATA=ROOT/'data'; DST=ROOT/'dst'; DST_BLUEJ=DST/'bluej'; CACHE=ROOT/'.cache'/'bluej'
BLUEJ_VERSION_FILE=DATA/'bluej-version.txt'; FRI_VERSION_FILE=DATA/'bluejfri-version.txt'; DEFS_APPEND_FILE=DATA/'bluej.defs.append'; SETUP_TEMPLATE=DATA/'setup.iss'; EXTENSION_URLS_FILE=DATA/'extensions2.urls'
GITHUB_RELEASE_BASE='https://github.com/k-pet-group/BlueJ-Greenfoot/releases/download'

def fail(message:str)->NoReturn: print(f'ERROR: {message}',file=sys.stderr); raise SystemExit(1)
def read_version(path:Path, parts:int, label:str)->str:
    if not path.is_file(): fail(f'Missing {label} version file: {path}')
    v=path.read_text(encoding='utf-8').strip(); p=v.split('.')
    if len(p)!=parts or not all(x.isdigit() for x in p): fail(f"Invalid {label} version '{v}'")
    return v
def release_url(v:str)->str: return f'{GITHUB_RELEASE_BASE}/BLUEJ-RELEASE-{v}/BlueJ-windows-{v}.zip'
def download_file(url:str,destination:Path,force:bool=False)->None:
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.is_file() and not force: print(f'Using cached archive: {destination}'); return
    tmp=destination.with_suffix(destination.suffix+'.part'); tmp.unlink(missing_ok=True); print(f'Downloading:\n  {url}')
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'BlueJFRI-build/1.0'})
        with urllib.request.urlopen(req,timeout=60) as r,tmp.open('wb') as out: shutil.copyfileobj(r,out,length=1024*1024)
    except (urllib.error.URLError,OSError) as exc: tmp.unlink(missing_ok=True); fail(f'Could not download file: {exc}')
    tmp.replace(destination)
def safe_extract_zip(archive:Path,destination:Path)->None:
    destination=destination.resolve()
    try:
        with zipfile.ZipFile(archive) as zf:
            for m in zf.infolist():
                try: (destination/m.filename).resolve().relative_to(destination)
                except ValueError: fail(f'Unsafe path in ZIP: {m.filename}')
            zf.extractall(destination)
    except zipfile.BadZipFile as exc: fail(f'Downloaded file is not a valid ZIP: {exc}')
def is_bluej_root(p:Path)->bool: return all(x.is_file() for x in (p/'BlueJ.exe',p/'lib'/'bluej.defs',p/'lib'/'english'/'labels',p/'LICENSE.txt'))
def find_bluej_root(extracted:Path)->Path:
    if is_bluej_root(extracted): return extracted
    c=[e.parent for e in extracted.rglob('BlueJ.exe') if is_bluej_root(e.parent)]
    if len(c)==1: print(f'=== BlueJ distribution root: {c[0].relative_to(extracted)}'); return c[0]
    if not c: fail('Could not find a complete BlueJ distribution in the downloaded ZIP')
    fail('Several complete BlueJ distributions were found in the ZIP')
def remove_non_english_languages(lib:Path)->list[str]:
    removed=[]
    for item in sorted(lib.iterdir(),key=lambda p:p.name.lower()):
        if item.is_dir() and item.name.lower()!='english' and (item/'labels').is_file(): shutil.rmtree(item); removed.append(item.name)
    return removed
def overlay_directory(src:Path,dst:Path)->None:
    if not src.exists(): return
    if not src.is_dir(): fail(f'Expected directory: {src}')
    dst.mkdir(parents=True,exist_ok=True); shutil.copytree(src,dst,dirs_exist_ok=True)
def external_extension_entries()->list[tuple[str,str]]:
    if not EXTENSION_URLS_FILE.exists(): return []
    entries=[]; seen=set()
    for n,raw in enumerate(EXTENSION_URLS_FILE.read_text(encoding='utf-8').splitlines(),1):
        url=raw.strip()
        if not url or url.startswith('#'): continue
        parsed=urllib.parse.urlparse(url)
        if parsed.scheme not in {'http','https'}: fail(f'Unsupported URL scheme on line {n}: {url}')
        name=Path(urllib.parse.unquote(parsed.path)).name
        if not name or name in {'.','..'}: fail(f'Could not determine extension filename from URL: {url}')
        if name in seen: fail(f"Duplicate external extension filename '{name}'")
        seen.add(name); entries.append((name,url))
    return entries
def install_external_extensions(dst:Path)->int:
    entries=external_extension_entries(); dst.mkdir(parents=True,exist_ok=True)
    local={p.name for p in (DATA/'extensions2').iterdir() if p.is_file()} if (DATA/'extensions2').is_dir() else set()
    for name,url in entries:
        if name in local: fail(f"Extension '{name}' is configured locally and externally")
        print(f'Downloading external extension: {name}'); download_file(url,dst/name,force=True)
    return len(entries)
def append_bluej_defs(path:Path)->int:
    if not DEFS_APPEND_FILE.is_file(): return 0
    additions=[x for x in DEFS_APPEND_FILE.read_text(encoding='utf-8').splitlines() if x.strip()]
    original=path.read_text(encoding='utf-8'); existing=set(original.splitlines()); additions=[x for x in additions if x not in existing]
    if not additions: return 0
    with path.open('a',encoding='utf-8',newline='\n') as h:
        if original and not original.endswith(('\n','\r')): h.write('\n')
        h.write('\n# BlueJ FRI Edition custom settings\n'); h.writelines(x.rstrip('\r\n')+'\n' for x in additions)
    return len(additions)
def generate_setup(fri_version:str)->Path:
    content=SETUP_TEMPLATE.read_text(encoding='utf-8')
    if '###VER###' not in content: fail('data/setup.iss does not contain ###VER###')
    out=DST/'setup.iss'; out.write_text(content.replace('###VER###',fri_version),encoding='utf-8',newline='\n'); return out
def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('--force-download',action='store_true'); args=ap.parse_args()
    bluej_version=read_version(BLUEJ_VERSION_FILE,3,'BlueJ'); fri_version=read_version(FRI_VERSION_FILE,4,'BlueJ FRI')
    if not fri_version.startswith(bluej_version+'.'): fail(f'BlueJ FRI version {fri_version} must start with {bluej_version}.')
    archive=CACHE/f'BlueJ-windows-{bluej_version}.zip'
    print('=== BlueJ FRI build ==='); print(f'BlueJ version: {bluej_version}'); print(f'FRI version:   {fri_version}')
    download_file(release_url(bluej_version),archive,force=args.force_download)
    if DST.exists(): shutil.rmtree(DST)
    DST.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='bluejfri-') as temp:
        extracted=Path(temp)/'extracted'; extracted.mkdir(); safe_extract_zip(archive,extracted); root=find_bluej_root(extracted); shutil.copytree(root,DST_BLUEJ)
    lib=DST_BLUEJ/'lib'; removed=remove_non_english_languages(lib); print(f'=== removed {len(removed)} non-English language packs')
    overlay_directory(DATA/'templates',lib/'english'/'templates'); overlay_directory(DATA/'extensions2',lib/'extensions2'); overlay_directory(DATA/'checkstyle',lib/'checkstyle')
    print(f'=== downloaded {install_external_extensions(lib/"extensions2")} external extension(s)'); print(f'=== appended {append_bluej_defs(lib/"bluej.defs")} bluej.defs line(s)')
    setup=generate_setup(fri_version); print(f'Build tree prepared successfully.\nInno Setup: {setup}\nExpected installer: {DST/"output"/f"BlueJFRI-{fri_version}.exe"}')
if __name__=='__main__': main()
