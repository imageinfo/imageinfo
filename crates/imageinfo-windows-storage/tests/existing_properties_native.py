"""Finite authored Windows #196 refusal audit. Retains every artifact.

Build --example existing_properties_probe first. Run with --probe and a fresh
--output below private evidence. Only authored files are changed by fixture/actor
setup. No privilege adjustment, real media, cleanup or publication occurs.
"""
import argparse
import csv
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument("--probe", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
assert os.name == "nt"
output = a.output.resolve()
output.mkdir(parents=True, exist_ok=False)
probe = a.probe.resolve()
k = c.WinDLL("kernel32", use_last_error=True)
s = c.WinDLL("advapi32", use_last_error=True)
invalid = c.c_void_p(-1).value
READ_CONTROL = 0x20000

def api(dll, name, args, result=w.BOOL):
    f = getattr(dll, name)
    f.argtypes, f.restype = args, result
    return f

create = api(k, "CreateFileW", [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, c.c_void_p], c.c_void_p)
close = api(k, "CloseHandle", [c.c_void_p])
local_free = api(k, "LocalFree", [c.c_void_p], c.c_void_p)
get_info = api(k, "GetFileInformationByHandle", [c.c_void_p, c.c_void_p])
get_basic = api(k, "GetFileInformationByHandleEx", [c.c_void_p, c.c_int, c.c_void_p, w.DWORD])
get_security = api(s, "GetKernelObjectSecurity", [c.c_void_p, w.DWORD, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)])
to_sddl = api(s, "ConvertSecurityDescriptorToStringSecurityDescriptorW", [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_void_p), c.POINTER(w.DWORD)])
from_sddl = api(s, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [w.LPCWSTR, w.DWORD, c.POINTER(c.c_void_p), c.POINTER(w.DWORD)])
set_security = api(s, "SetFileSecurityW", [w.LPCWSTR, w.DWORD, c.c_void_p])
set_kernel_security = api(s, "SetKernelObjectSecurity", [c.c_void_p, w.DWORD, c.c_void_p])
set_time = api(k, "SetFileTime", [c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p])
create_link = api(k, "CreateHardLinkW", [w.LPCWSTR, w.LPCWSTR, c.c_void_p])
set_attributes = api(k, "SetFileAttributesW", [w.LPCWSTR, w.DWORD])
write_file = api(k, "WriteFile", [c.c_void_p, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p])
read_file = api(k, "ReadFile", [c.c_void_p, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p])

class Info(c.Structure):
    _fields_ = [("attributes", w.DWORD), ("creation", w.FILETIME), ("access", w.FILETIME),
                ("write", w.FILETIME), ("volume", w.DWORD), ("size_high", w.DWORD),
                ("size_low", w.DWORD), ("links", w.DWORD), ("index_high", w.DWORD), ("index_low", w.DWORD)]

class Basic(c.Structure):
    _fields_ = [("creation", c.c_int64), ("access", c.c_int64), ("write", c.c_int64),
                ("change", c.c_int64), ("attributes", w.DWORD)]

class Stream(c.Structure):
    _fields_ = [("size", c.c_int64), ("name", w.WCHAR * 296)]

first_stream = api(k, "FindFirstStreamW", [w.LPCWSTR, c.c_int, c.c_void_p, w.DWORD], c.c_void_p)
next_stream = api(k, "FindNextStreamW", [c.c_void_p, c.c_void_p])
find_close = api(k, "FindClose", [c.c_void_p])

def checked(ok):
    if not ok:
        raise c.WinError(c.get_last_error())
    return ok

def opened(path, access, flags=0x02200000):
    h = create(str(path), access, 7, None, 3, flags, None)
    if h in (None, invalid):
        raise c.WinError(c.get_last_error())
    return h

def descriptor(text):
    result = c.c_void_p()
    checked(from_sddl(text, 1, c.byref(result), None))
    return result

def security(handle, flags):
    n = w.DWORD()
    get_security(handle, flags, None, 0, c.byref(n))
    err = c.get_last_error()
    if not n.value:
        return {"unavailableError": err}
    assert n.value <= 65536
    buf = c.create_string_buffer(n.value)
    if not get_security(handle, flags, buf, n.value, c.byref(n)):
        return {"unavailableError": c.get_last_error()}
    text = c.c_void_p()
    checked(to_sddl(buf, 1, flags, c.byref(text), None))
    try:
        return {"bytes": bytes(buf[:n.value]).hex(), "sddl": c.wstring_at(text)}
    finally:
        local_free(text)

def exact_bytes(path):
    # Python's ordinary open omits delete sharing and would conflict with the
    # retained DELETE actor. Observe with explicit all-share read access.
    h = opened(path, 0x80000000)
    try:
        buf, n = c.create_string_buffer(65537), w.DWORD()
        checked(read_file(h, buf, 65537, c.byref(n), None))
        assert n.value <= 65536
        data = bytes(buf[:n.value])
    finally:
        checked(close(h))
    return {"length": len(data), "hex": data.hex(), "sha256": hashlib.sha256(data).hexdigest()}

def streams(path):
    item = Stream()
    h = first_stream(str(path), 0, c.byref(item), 0)
    if h in (None, invalid):
        return {"unavailableError": c.get_last_error()}
    result = {}
    try:
        while True:
            name = item.name
            data_path = str(path) if name == "::$DATA" else str(path) + name
            result[name] = exact_bytes(data_path)
            assert result[name]["length"] == item.size
            if not next_stream(h, c.byref(item)):
                assert c.get_last_error() == 38  # ERROR_HANDLE_EOF
                break
    finally:
        checked(find_close(h))
    return result

def inventory(root):
    result = {}
    for path in [root] + sorted(root.iterdir()):
        h = opened(path, READ_CONTROL | 0x80)
        try:
            info, basic = Info(), Basic()
            checked(get_info(h, c.byref(info)))
            checked(get_basic(h, 0, c.byref(basic), c.sizeof(basic)))
            record = {
                "volume": info.volume, "fileId": (info.index_high << 32) | info.index_low,
                "links": info.links, "attributes": info.attributes,
                "creation": basic.creation, "write": basic.write,
                "accessObserved": basic.access, "changeObserved": basic.change,
                "ownerGroupDacl": security(h, 7), "label": security(h, 0x10),
                "sacl": security(h, 8),
                "reparseTag": getattr(path.lstat(), "st_reparse_tag", 0),
            }
            if path.is_file() and not record["reparseTag"]:
                record["streams"] = streams(path)
                assert "unavailableError" not in record["streams"]
            result[path.name if path != root else "."] = record
        finally:
            checked(close(h))
    return result

def stable(observation):
    return {name: {k: v for k, v in row.items() if k not in ("accessObserved", "changeObserved")}
            for name, row in observation.items()}

sid_csv = subprocess.run(["whoami.exe", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, check=True)
sid = list(csv.reader(sid_csv.stdout.splitlines()))[0][1]
assert sid.startswith("S-1-")
records = []

def run(label, setup=None, policy="update", expected_mtime=None):
    root = output / label
    root.mkdir()
    target, candidate = root / "target.bin", root / "candidate.bin"
    target.write_bytes(b"authored original target\n")
    candidate.write_bytes(b"authored changed candidate\n")
    handles = []
    actor = {}
    try:
        if setup:
            setup(root, handles, actor)
        before = inventory(root)
        if label == "03-noncanonical-acl-owner":
            acl = before["target.bin"]["ownerGroupDacl"]["sddl"]
            assert f"O:{sid}" in acl
            assert acl.index("(A;") < acl.index("(D;")
        if label == "08-mandatory-label":
            assert "(ML;;NW;;;LW)" in before["target.bin"]["label"]["sddl"]
        if expected_mtime is not None:
            assert before["target.bin"]["write"] == expected_mtime
        reply = subprocess.run([str(probe), str(candidate), str(target), policy], capture_output=True, text=True, timeout=15)
        assert reply.returncode == 0 and not reply.stderr
        assert reply.stdout.strip() == "EXISTING_TARGET_STRICT_PROPERTIES_UNSUPPORTED"
        after = inventory(root)
        assert stable(before) == stable(after), label
        record = {"case": label, "policy": policy, "actor": actor, "result": reply.stdout.strip(),
                  "before": before, "after": after, "strictNoEffectsInventoryMatched": True}
        records.append(record)
        (output / f"{label}.private.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    finally:
        for h in handles:
            checked(close(h))

def set_mtime(root, handles, actor):
    h = opened(root / "target.bin", 0x100)
    handles.append(h)
    time = c.c_uint64(132000000000000000)
    checked(set_time(h, None, None, c.byref(time)))
    actor.update(access="FILE_WRITE_ATTRIBUTES", preopened=True, actualSetter="SetFileTime")

def noncanonical(root, handles, actor):
    text = f"O:{sid}D:P(A;;FA;;;{sid})(D;;SD;;;WD)"
    sd = descriptor(text)
    try:
        # Owner is observed and retained, never reassigned. Ordinary ownership
        # supplies WRITE_DAC, not a promise of WRITE_OWNER or ownership privilege.
        checked(set_security(str(root / "target.bin"), 4 | 0x80000000, sd))
    finally:
        local_free(sd)
    actor.update(noncanonicalDacl="explicit allow before explicit deny", owner="actual creator SID retained")

def stream_data(root, handles, actor):
    Path(str(root / "target.bin") + ":authored").write_bytes(b"stream A: exact private authored bytes\x00\xff")
    actor.update(namedStreamContent=True)

def readonly(root, handles, actor):
    checked(set_attributes(str(root / "target.bin"), 0x21))
    actor.update(readonly=True)

def hardlink(root, handles, actor):
    os.link(root / "target.bin", root / "alias.bin")
    actor.update(actualHardlink=True)

def reparse(root, handles, actor):
    # Ordinary-token directory junction, not a privileged symbolic-link request.
    (root / "referent").mkdir()
    reply = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(root / "junction"), str(root / "referent")], capture_output=True, text=True)
    assert reply.returncode == 0, reply.stderr
    # Replace only authored setup name before the boundary is invoked.
    (root / "target.bin").unlink()
    (root / "junction").rename(root / "target.bin")
    actor.update(actualDirectoryReparse=True)

def label(root, handles, actor):
    # Fixture-only explicit owner rights; do not infer WRITE_OWNER from being
    # owner. This is authored setup, not a source-security production shortcut.
    owner_acl = descriptor(f"D:P(A;;FA;;;{sid})")
    try:
        checked(set_security(str(root / "target.bin"), 4 | 0x80000000, owner_acl))
    finally:
        local_free(owner_acl)
    sd = descriptor("S:(ML;;NW;;;LW)")
    try:
        checked(set_security(str(root / "target.bin"), 0x10, sd))
    finally:
        local_free(sd)
    actor.update(actualMandatoryLabel="low integrity", privilegeAdjustment=False)

def security_actor(root, handles, actor):
    h = opened(root / "target.bin", 0x40000)
    handles.append(h)
    sd = descriptor(f"D:P(A;;FA;;;{sid})(A;;FR;;;WD)")
    try:
        checked(set_kernel_security(h, 4 | 0x80000000, sd))
    finally:
        local_free(sd)
    actor.update(access="WRITE_DAC", preopened=True, actualSetter="SetKernelObjectSecurity")

def stream_actor(root, handles, actor):
    stream_data(root, handles, actor)
    h = opened(str(root / "target.bin") + ":authored", 0x40000000)
    handles.append(h)
    changed = b"stream B: exact private authored bytes\x00\xff"
    n = w.DWORD()
    checked(write_file(h, changed, len(changed), c.byref(n), None))
    assert n.value == len(changed)
    actor.update(access="GENERIC_WRITE on named stream", preopened=True, actualSetter="WriteFile", sameLengthEdit=True)

def link_actor(root, handles, actor):
    h = opened(root / "target.bin", 0x10000 | 0x100)
    handles.append(h)
    # Win32 hard-link creation is name based. Keep the actor's real DELETE /
    # attribute-capable handle live, and state the distinction in evidence.
    checked(create_link(str(root / "actor-alias.bin"), str(root / "target.bin"), None))
    actor.update(access="DELETE | FILE_WRITE_ATTRIBUTES", preopened=True,
                 actualSetter="CreateHardLinkW (name based, not the retained handle)", actualAlias=True)

run("01-update-mtime", set_mtime, expected_mtime=132000000000000000)
run("02-preserve-mtime", set_mtime, "preserve", 132000000000000000)
run("03-noncanonical-acl-owner", noncanonical)
run("04-exact-stream-content", stream_data)
run("05-readonly", readonly)
run("06-extra-hardlink", hardlink)
run("07-reparse", reparse)
run("08-mandatory-label", label)
run("09-sacl-unobservable", lambda r, h, x: x.update(sacl="not acquired; no privilege adjustment; unsupported before query"))
run("10-preopened-security", security_actor)
run("11-preopened-stream-writer", stream_actor)
run("12-preopened-link-actor", link_actor)
report = {"schema": "imageinfo-existing-target-refusal-native-v1", "cases": records,
          "scope": "actual production refusal; no positive preservation/exclusion/recovery qualification",
          "accessAndChangeTimes": "observed; not a preservation promise; omitted from equality predicate",
          "sacl": "access errors remain explicit; no complete SACL observation or recovery claim",
          "artifactsRetained": True, "privilegeAdjustment": False}
(output / "audit.private.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"{len(records)} authored native strict-refusal inventories matched; artifacts retained")
