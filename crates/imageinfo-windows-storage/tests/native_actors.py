"""Authored Windows mapping/ADS actors; retains all fixture artifacts and audit.

Run after building --example guard_probe, with explicit --probe and --output.
No source media, privilege, VM, crash, power, or source-security operations.
"""
import argparse
import ctypes as c
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--probe", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = args.output.resolve()
root.mkdir(parents=True, exist_ok=False)
k = c.WinDLL("kernel32", use_last_error=True)
k.CreateFileW.argtypes = [c.c_wchar_p, c.c_uint32, c.c_uint32, c.c_void_p, c.c_uint32, c.c_uint32, c.c_void_p]
k.CreateFileW.restype = c.c_void_p
k.CreateFileMappingW.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32, c.c_wchar_p]
k.CreateFileMappingW.restype = c.c_void_p
k.MapViewOfFile.argtypes = [c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32, c.c_size_t]
k.MapViewOfFile.restype = c.c_void_p
k.UnmapViewOfFile.argtypes = [c.c_void_p]
k.UnmapViewOfFile.restype = c.c_int
k.CloseHandle.argtypes = [c.c_void_p]
k.CloseHandle.restype = c.c_int
invalid = c.c_void_p(-1).value

def start(path):
    child = subprocess.Popen([str(args.probe.resolve()), str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return child, child.stdout.readline().strip()

source = root / "mapped-source.bin"
original = b"authored mapping source"
source.write_bytes(original)
file = k.CreateFileW(str(source), 0xC0000000, 7, None, 3, 0, None)
assert file not in (None, invalid)
mapping = view = None
try:
    mapping = k.CreateFileMappingW(file, None, 4, 0, 0, None)
    assert mapping
    view = k.MapViewOfFile(mapping, 2, 0, 0, 0)
    assert view
    assert k.CloseHandle(file)
    file = None
    child, acquisition = start(source)
    existing = subprocess.run([str(args.probe.resolve()), str(source), "--existing-access"], capture_output=True, text=True, timeout=10)
    assert existing.returncode == 0 and not existing.stderr
    existing_acquisition = existing.stdout.strip()
    assert existing_acquisition == "acquisition-refused:Some(32)", existing_acquisition
    # Mutation after the original file handle is closed but mapping remains.
    c.c_ubyte.from_address(view).value = ord("X")
    later, stderr = child.communicate("continue\n", timeout=10)
    assert child.returncode == 0 and not stderr
    assert acquisition == "acquisition-refused:Some(32)", acquisition
finally:
    if view:
        assert k.UnmapViewOfFile(view)
    if mapping:
        assert k.CloseHandle(mapping)
    if file:
        assert k.CloseHandle(file)
assert source.read_bytes() == b"X" + original[1:]

plain = root / "plain-source.bin"
plain.write_bytes(b"authored plain source")
child, held = start(plain)
assert held == "guard-acquired", held
ads = k.CreateFileW(str(plain) + ":actor", 0x40000000, 7, None, 1, 0, None)
ads_error = c.get_last_error()
if ads not in (None, invalid):
    assert k.CloseHandle(ads)
after, stderr = child.communicate("continue\n", timeout=10)
assert child.returncode == 0 and not stderr
if ads not in (None, invalid):
    assert after.strip() == "check-conflict", after
else:
    assert after.strip() == "check-matched", after
assert plain.read_bytes() == b"authored plain source"
report = {"mappingAcquisition": acquisition, "mappedOriginalHandleClosed": True,
          "existingAccessMappingAcquisition": existing_acquisition,
          "mappingRetainedAudit": "matched-authored-edit", "adsCreated": ads not in (None, invalid),
          "adsError": ads_error, "adsCheckpoint": after.strip(), "sourceDefaultBytesPreserved": True}
(root / "audit.private.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("mapping acquisition and ADS checkpoint actors/audits passed")
