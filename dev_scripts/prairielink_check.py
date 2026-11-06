'''
Hardware check, not used by the apps. Checks that the PrairieLink COM interface talks to the running Prairie View,
and shows what changes when a T-series ends by itself (frame limit). Prairie View must be running.
Every COM call prints its return value and how long it took.

Run from the repo root:
    uv run python -m dev_scripts.prairielink_check
        Connects, reads a few state values, disconnects. Does not scan.
    uv run python -m dev_scripts.prairielink_check --tseries D:\\some\\folder
        Also runs a T-series with the current Prairie View settings, saved in D:\\some\\folder\\prairielink_check-000.
        This opens the shutter. Set a frame limit in the T-series so it ends within a minute.
        Every second it prints the files in the T-series folder that changed and the state keys given with --keys.
        It sends -Abort when no file has changed for --quiet seconds, or after --max seconds.
'''
import argparse
import sys
import time
from pathlib import Path

import win32com.client

PREFIX = 'prairielink_check'
# (key, index) pairs read once after connecting
STATE_KEYS = (('directory', 1), ('directory', 4), ('fileIteration', 4),
              ('pixelsPerLine',), ('linesPerFrame',), ('framePeriod',), ('activeMode',))


def call(pl, method, *args, quiet=False):
    '''Call a PrairieLink COM method and print the result. Errors are printed, not raised.'''
    t = time.perf_counter()
    try:
        result = getattr(pl, method)(*args)
    except Exception as ex:
        result = f'ERROR {type(ex).__name__}: {ex}'
    if not quiet:
        print(f'{method}{args}: {result!r} ({time.perf_counter() - t:.3f} s)')
    return result


def snapshot(folder):
    '''{relative path: (size, mtime)} of the files in folder. Files can disappear while Prairie View converts them.'''
    files = {}
    for p in folder.rglob('*'):
        try:
            if p.is_file():
                st = p.stat()
                files[str(p.relative_to(folder))] = (st.st_size, st.st_mtime)
        except FileNotFoundError:
            pass
    return files


def xml_closed(folder):
    '''True if the T-series XML exists and ends with the closing PVScan tag.'''
    xml = folder / f'{folder.name}.xml'
    try:
        with open(xml, 'rb') as f:
            f.seek(max(0, xml.stat().st_size - 64))
            return b'</PVScan>' in f.read()
    except FileNotFoundError:
        return None


def watch(pl, folder, keys, quiet_s, max_s):
    t0 = time.time()
    last_change = t0
    prev = {}
    while True:
        time.sleep(1)
        now = time.time()
        snap = snapshot(folder) if folder.exists() else {}
        changed = sorted(n for n in snap.keys() | prev.keys() if snap.get(n) != prev.get(n))
        if changed:
            last_change = now
        t = time.perf_counter()
        states = [f'{k}={call(pl, "GetState", k, quiet=True)!r}' for k in keys]
        state_s = time.perf_counter() - t
        listed = ', '.join(changed[:3]) + (f' (+{len(changed) - 3})' if len(changed) > 3 else '')
        print(f'{now - t0:6.1f} s | {len(snap)} files, {sum(s for s, _ in snap.values()) / 1e6:.1f} MB | '
              f'xml closed: {xml_closed(folder)} | {" ".join(states)} ({state_s:.3f} s) | changed: {listed}')
        prev = snap
        if now - last_change > quiet_s:
            print(f'No file changed for {quiet_s} s.')
            return
        if now - t0 > max_s:
            print(f'Stopped after {max_s} s.')
            return


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tseries', help='folder to save a T-series in; without it, nothing is scanned')
    ap.add_argument('--keys', nargs='*', default=['activeMode'], help='state keys to read every second')
    ap.add_argument('--quiet', type=float, default=10, help='seconds without file changes before abort')
    ap.add_argument('--max', type=float, default=120, help='seconds before abort')
    args = ap.parse_args()

    if args.tseries is not None:
        save_path = Path(args.tseries)
        folder = save_path / f'{PREFIX}-000'
        if folder.exists():
            sys.exit(f'{folder} exists. Delete it or pick another folder.')

    pl = win32com.client.Dispatch('PrairieLink64.Application')
    if call(pl, 'Connect') is not True:
        sys.exit('Connect failed. Is Prairie View running?')
    for key in STATE_KEYS:
        call(pl, 'GetState', *key)

    if args.tseries is not None:
        # the same commands as RecorderGUI_CL
        call(pl, 'SendScriptCommands', f'-SetSavePath "{save_path}"')
        call(pl, 'SendScriptCommands', f'-SetFileName TSeries "{PREFIX}"')
        call(pl, 'SendScriptCommands', '-SetFileIteration TSeries 0')
        try:
            call(pl, 'SendScriptCommands', '-TSeries')
            watch(pl, folder, args.keys, args.quiet, args.max)
        finally:
            call(pl, 'SendScriptCommands', '-Abort')
        print(f'Files in {folder}:')
        for name, (size, mtime) in sorted(snapshot(folder).items()):
            print(f'  {time.strftime("%H:%M:%S", time.localtime(mtime))} {size:>14,} {name}')

    call(pl, 'Disconnect')


if __name__ == '__main__':
    main()
