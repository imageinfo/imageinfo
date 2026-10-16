"""Check the finite #0121 source inventory; never runs tools or reads media."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs/legacy-compatibility/native-token-inventory.v1.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path)
    args = parser.parse_args()
    data = json.loads(PATH.read_text(encoding="utf-8"))
    expected = {"families": 32, "cliOptionHeadings": 87, "apiMethods": 39,
                "apiOptions": 102, "setNewValueOptions": 12,
                "apiDocumentedOptionHeadings": 97, "apiRegistryEntries": 99}
    assert data["counts"] == expected, "closed denominator changed"
    for key in expected.keys() - {"apiDocumentedOptionHeadings", "apiRegistryEntries"}:
        assert len(data[key]) == expected[key], key
    mappings = json.loads((ROOT / "docs/inventory/canon-eos-r5-cr3.v1.json").read_text(encoding="utf-8"))["mappings"]
    assert [r["id"] for r in data["families"]] == [f"MAP-{i:03}" for i in range(1, 33)]
    for row, source in zip(data["families"], mappings):
        assert row["surveyedForms"] == source["upstreamForms"]
        assert row["family"] == source["family"]
        assert row["adoptedDifference"] is False
    for key in ("families", "cliOptionHeadings", "apiMethods", "apiOptions", "setNewValueOptions"):
        for row in data[key]:
            assert row["residual"] in {"current-RAW-unresolved", "deferred-breadth"}
    for key, field in [("apiOptions", "name"), ("apiMethods", "heading"), ("cliOptionHeadings", "syntax")]:
        values = [r[field] for r in data[key]]
        assert len(set(values)) == len(values), f"duplicate {key}"
    for name, expected_hash in data["nativeSourceSha256"].items():
        assert digest(ROOT / name) == expected_hash, f"review and refresh native source: {name}"
    cli = (ROOT / "src/cli.rs").read_text(encoding="utf-8")
    longs = {"--" + x for x in re.findall(r'\.long\("([^"]+)"\)', cli)}
    native = data["native"]
    listed = set(native["commonOptions"])
    for options in native["leafOptions"].values():
        listed.update(options)
    assert listed == longs, "native option denominator drift"
    wire = (ROOT / "src/reader/wire.rs").read_text(encoding="utf-8")
    names = re.findall(r'"([^"]+)"', section(wire, "pub const NAMES: &[&str] = &[", "];"))
    assert native["selectors"] == names
    ledger = (ROOT / "docs/legacy-compatibility/surface-ledger.md").read_text(encoding="utf-8")
    for row in data["apiMethods"]:
        assert "`" + row["heading"].split()[0] + "`" in ledger
    assert sum(r["documentedHeading"] for r in data["apiOptions"]) == 97
    assert sum(r["registryEntry"] for r in data["apiOptions"]) == 99
    if args.upstream_root:
        upstream = args.upstream_root
        for name, record in data["upstream"]["sources"].items():
            assert digest(upstream / name) == record["sha256"], name
        pod = (upstream / "lib/Image/ExifTool.pod").read_text(encoding="utf-8")
        methods = re.findall(r"^=head2 (.+)$", section(pod, "=head1 METHODS", "=head1 CHARACTER ENCODINGS"), re.M)
        assert methods == [r["heading"] for r in data["apiMethods"]]
        opts = re.findall(r"^=item (\S+)$", section(pod, "=item Option Parameters:", "=item Return Values:"), re.M)
        assert {x.replace("[+]", "") for x in opts} == {r["name"] for r in data["apiOptions"] if r["documentedHeading"]}
        pm = (upstream / "lib/Image/ExifTool.pm").read_text(encoding="utf-8")
        registry = re.findall(r"^    \[ '([^']+)'", section(pm, "my @availableOptions = (", "\n);"), re.M)
        assert set(registry) == {r["name"] for r in data["apiOptions"] if r["registryEntry"]}
        setters = re.findall(r"^=item (\S+)$", section(pod, "=item SetNewValue Options:", "=item Return Values:"), re.M)
        assert setters == [r["name"] for r in data["setNewValueOptions"]]
        application = (upstream / "exiftool").read_text(encoding="utf-8")
        headings = re.findall(r"^=item (.*(?:\n(?!\n|=)[^\n]+)*)", section(application, "=head2 Option Details", "=head1 WINDOWS UNICODE"), re.M)
        def plain(value):
            value = value.replace("E<lt>", "<").replace("E<gt>", ">")
            while re.search(r"[BICFL]<([^<>]*)>", value):
                value = re.sub(r"[BICFL]<([^<>]*)>", r"\1", value)
            return value.replace("\n", " ")
        assert [plain(x) for x in headings] == [r["syntax"] for r in data["cliOptionHeadings"]]
    print("native token inventory: 32 MAP / 39 methods / 87 CLI headings / 102 API options / 12 setter options checked")


if __name__ == "__main__":
    main()
