"""Read-only binding to separately pinned installed components; no acquisition.

Absolute operational paths are derived locally and must remain in private reports.
The old profile preserves historical source references, never new qualification.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "0111-warning-jpeg"
ORIGINAL_PROFILE_CANONICAL_SHA256 = "885ae7003d6272ac4527b23b5471467f2546beeaa87bf5877f73214c7997011e"
COMPONENT_PROFILE_CANONICAL_SHA256 = "04e8673816a10605df35cf9a631cdce59b79d8e77e01216b199a3dcc6ef3626a"
PROFILE_ID = "0075-baseline-interleaved-rgb-zero-padding-v2"
SETTINGS = {
    "inputBytes": 32 * 1024 * 1024, "dimension": 8192,
    "packedRgbBytes": 256 * 1024 * 1024,
    "captureBytesPerStream": 16384, "childDeadlineSeconds": 120,
    "api": "tjDecompress2", "flags": 8192, "pixelFormat": "RGB",
    "extentPolicy": "single baseline 8-bit Huffman interleaved scan; no restart; all-zero suffix length 0 through 32 bytes inclusive",
}


class RuntimeRefusal(RuntimeError):
    """No native decoder access is permitted after a binding refusal."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_identity(path):
    data = Path(path).read_bytes()
    return {"byteLength": len(data), "sha256": digest(data)}


def canonical_digest(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def original_profile():
    profile = json.loads((ORIGINAL / "profile.json").read_text(encoding="utf-8"))
    if canonical_digest(profile) != ORIGINAL_PROFILE_CANONICAL_SHA256:
        raise RuntimeRefusal("original component profile differs")
    for path, expected in ((ORIGINAL / "qualify.py", profile["runtime"]["recipeSha256"]),
                           (HERE.parent / "0107-jpeg-validator/qualify.py",
                            profile["runtime"]["authoredRecipeSha256"])):
        if digest(path.read_bytes()) != expected:
            raise RuntimeRefusal("original qualification recipe differs")
    return profile


def component_profile():
    profile = json.loads((HERE / "component-profile.json").read_text(encoding="utf-8"))
    if canonical_digest(profile) != COMPONENT_PROFILE_CANONICAL_SHA256:
        raise RuntimeRefusal("current installed component profile differs")
    # Preserve the historical recipes as reviewed source references, not claims
    # that changed installed binaries reproduce the previous observation.
    original_profile()
    return profile


def _check(path, expected):
    if file_identity(path) != expected:
        raise RuntimeRefusal("installed component identity differs")


def _inside(root, relative):
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root.resolve(strict=True)):
        raise RuntimeRefusal("component escapes bundle")
    return path


class VerifiedRuntime:
    def __init__(self, root, original):
        self.root = root
        self.profile = original
        self.library_path = _inside(root, "native/libheif/libheif/bin/turbojpeg.dll")

    def load_library(self):
        """Caller grants/stage checks must precede this native-load seam."""
        # Match the reviewed current deterministic closure without pixel generation.
        import importlib.metadata
        from PIL import Image, JpegImagePlugin, features, _imaging, _imagingmath
        # Runtime and ABI were checked before these imports.
        library = C.CDLL(str(self.library_path))
        self.assert_loaded_closure()
        return library

    def assert_loaded_closure(self):
        expected = self.profile["loadedNonOsModules"]
        actual = loaded_components(self.root)
        if actual != expected:
            raise RuntimeRefusal("loaded non-OS module closure differs")
        return actual

    def identity(self):
        """Public-safe generic identities; no absolute operational locations."""
        return {"componentProfileCanonicalSha256": COMPONENT_PROFILE_CANONICAL_SHA256,
                "componentProfile": self.profile, "abi": "Windows-x64-LLP64-CPython-3.12.14"}


def verify_runtime(manifest_path=None):
    """Hash the existing components before PIL/TurboJPEG imports or native load."""
    if (sys.platform != "win32" or platform.machine().upper() != "AMD64" or
            sys.version_info[:3] != (3, 12, 14) or
            C.sizeof(C.c_ulong) != 4 or C.sizeof(C.c_void_p) != 8):
        raise RuntimeRefusal("reviewed Windows x64 CPython ABI required")
    profile = component_profile()
    python = Path(sys.executable).resolve(strict=True).parent
    root = python.parent
    package = python / "Lib/site-packages/PIL"
    distribution = package.parent / "pillow-12.3.0.dist-info"
    paths = {
        "python-executable": Path(sys.executable), "python-runtime": python / "python312.dll",
        "python-notices": python / "LICENSE.txt", "pillow-init": package / "__init__.py",
        "pillow-jpeg-plugin": package / "JpegImagePlugin.py", "pillow-image-file": package / "ImageFile.py",
        "pillow-image": package / "Image.py", "pillow-native-decoder": package / "_imaging.cp312-win_amd64.pyd",
        "pillow-metadata": distribution / "METADATA", "pillow-notices": distribution / "licenses/LICENSE",
        "pillow-sbom": distribution / "sboms/pillow-12.3.0.cdx.json",
    }
    expected = profile["components"]
    if paths.keys() != expected.keys():
        raise RuntimeRefusal("encoder component set differs")
    for name, path in paths.items():
        _check(path, expected[name])
    for relative, identity in profile["loadedNonOsModules"].items():
        _check(_inside(root, relative), identity)
    manifest = _inside(root, "native/libheif/manifest.json")
    if (digest(manifest.read_bytes()) != profile["manifest"]["sha256"] or
            json.loads(manifest.read_text(encoding="utf-8")) != profile["manifest"]["package"]):
        raise RuntimeRefusal("package manifest differs")
    verified = VerifiedRuntime(root, profile)
    if manifest_path is not None:
        manifest_identity = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        if manifest_identity != verified.identity():
            raise RuntimeRefusal("caller runtime manifest differs")
    return verified


def verify_encoder():
    """Controls callback, called before any Pillow import."""
    return verify_runtime()


def loaded_components(root):
    """Enumerate the current process, excluding Windows-owned modules only."""
    if sys.platform != "win32":
        raise RuntimeRefusal("Windows module enumeration required")
    kernel, psapi = C.WinDLL("kernel32", use_last_error=True), C.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = W.HANDLE
    psapi.EnumProcessModules.argtypes = [W.HANDLE, C.POINTER(W.HMODULE), W.DWORD, C.POINTER(W.DWORD)]
    psapi.EnumProcessModules.restype = W.BOOL
    psapi.GetModuleFileNameExW.argtypes = [W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD]
    psapi.GetModuleFileNameExW.restype = W.DWORD
    handles, needed = (W.HMODULE * 2048)(), W.DWORD()
    process = kernel.GetCurrentProcess()
    if (not psapi.EnumProcessModules(process, handles, C.sizeof(handles), C.byref(needed)) or
            needed.value > C.sizeof(handles) or needed.value % C.sizeof(W.HMODULE)):
        raise RuntimeRefusal("module inventory failed or exceeded bound")
    osroot = Path(os.environ["SystemRoot"]).resolve(strict=True)
    rows = {}
    for handle in handles[:needed.value // C.sizeof(W.HMODULE)]:
        buffer = C.create_unicode_buffer(32768)
        count = psapi.GetModuleFileNameExW(process, handle, buffer, len(buffer))
        if not count or count >= len(buffer):
            raise RuntimeRefusal("module path inventory failed")
        path = Path(buffer.value).resolve(strict=True)
        if path.is_relative_to(osroot):
            continue
        if not path.is_relative_to(root):
            raise RuntimeRefusal("unexpected non-OS module outside bundle")
        relative = path.relative_to(root).as_posix()
        if relative in rows:
            raise RuntimeRefusal("duplicate module identity")
        rows[relative] = file_identity(path)
    return rows
