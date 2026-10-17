"""Offline authored-evidence reconciliation; never runs a reader or benchmark."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/performance/read-limits/evidence-supplement.v1.json"
PROJECTIONS = {
    "64": ["/limits"],
    "146": ["/campaign", "/lifetimeSummary", "/cells"],
    "147": ["/denominators", "/cells", "/closeControls"],
    "148": ["/denominator", "/cells"],
    "149": ["/outcome", "/inconsistentObservation", "/validOnlyOverallRanges", "/cases"],
    "150": ["/denominators", "/trials"],
}
EXPECTED_LIMITS = {
    "metadata_bytes": (8388608, 268435456), "block_bytes": (1048576, 8388608),
    "boxes": (4096, 65536), "depth": (16, 64), "entries": (4096, 65536),
    "records": (4096, 65536),
}
DIMENSIONS = {
    "source_length": "bytes", "metadata_reads": "bytes", "block_request": "bytes",
    "boxes": "boxes", "bmff_depth": "parent-path components",
    "tiff_depth": "directory links from zero", "entries": "entries per CMT parse",
    "records": "records per track sample", "output": "UTF-8 bytes",
    "cpu": "process CPU ns", "working_set": "bytes", "private_commit": "bytes",
    "logical_io": "operations and transfer bytes", "physical_io": "unavailable",
    "retained_ids": "UTF-8 bytes and admitted request count", "frames": "UTF-8 bytes including LF/CRLF",
    "elapsed": "ns or explicitly labelled ms", "observer": "ns",
    "scratch": "unmeasured filesystem allocated bytes", "workers": "unselected count",
    "deadlines": "research watchdog ms only", "filters": "named workload stratum",
    "queues": "unsupported", "storage_cache": "declared uncontrolled stratum",
    "unsupported": "unavailable capability",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pointer(value, path):
    for key in path.lstrip("/").split("/"):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def validate(ledger, read_bytes=None):
    read_bytes = read_bytes or (lambda path: (ROOT / path).read_bytes())
    require(ledger["ticket"] == 152 and ledger["schemaVersion"] == 1, "identity")
    require(ledger["adoption"] == "none; historical proposal remains unadopted", "adoption")
    require(ledger["privateCameraEvidenceUsed"] is False, "private source")
    require(set(ledger["evidence"]) == {"64", "146", "147", "148", "149", "150"}, "sources")
    sources = {}
    for ticket, item in ledger["evidence"].items():
        require(item["path"].startswith("docs/performance/") and ".." not in item["path"], "public path")
        raw = read_bytes(item["path"])
        require(hashlib.sha256(raw).hexdigest() == item["sha256"], "source identity " + ticket)
        sources[ticket] = json.loads(raw.decode("utf-8"))
        require([x["pointer"] for x in item["distributions"]] == PROJECTIONS[ticket], "projection coverage")
        for projection in item["distributions"]:
            require(projection["value"] == pointer(sources[ticket], projection["pointer"]), "distribution " + ticket)
    proposal = sources["64"]
    require(proposal["status"] == "proposed-not-adopted", "proposal status")
    require(len(proposal["limits"]) == 6, "six constants")
    for row in proposal["limits"]:
        default, hard = EXPECTED_LIMITS[row["name"]]
        require(row["implementedDefault"] == row["proposedDefault"] == row["proposedOperatingCeiling"] == default, "constant")
        require(row["implementedHardCeiling"] == hard, "hard constant")
    a, b, c, d, e = (sources[str(n)] for n in range(146, 151))
    require(a["campaign"]["totalReadResults"] == 960 + 256 + 1 == sum(x["readResults"] for x in a["cells"]), "session denominator")
    require(len(a["cells"]) == a["campaign"]["attemptedCells"] == 16, "session cells")
    require(sum(x["stdoutBytes"] for x in a["cells"]) == a["campaign"]["totalStdoutBytes"], "session bytes")
    require(b["denominators"]["attempts"] == 8 + 40 + 2 == 50, "consumer denominator")
    require(sum(x["samples"] for x in b["cells"]) == b["denominators"]["eligibleSamples"] == 40, "consumer samples")
    require(c["denominator"]["attempts"] == len(c["cells"]) == 6, "byte cells")
    require(sum(x["status"] == "OK" for x in c["cells"]) == 4, "byte successes")
    require(d["outcome"]["attempts"] == sum(x["attempted"] for x in d["cases"]) == 45, "structure denominator")
    require(d["outcome"]["nativeSuccesses"] == 30 and d["outcome"]["expectedRefusals"] == 15, "native outcomes")
    require(d["outcome"]["strictResourceAudit"] == "failed", "failed resource audit")
    require(d["outcome"]["strictResourceValidAttempts"] == sum(x["strictResourceValidAttempts"] for x in d["cases"]) == 44, "valid-only denominator")
    require(d["outcome"]["strictResourceInvalidAttempts"] == 1, "invalid retained")
    bad = d["inconsistentObservation"]
    require(bad["workingSetBytes"] - bad["peakWorkingSetBytes"] == bad["currentExceedsReportedPeakBytes"] == 4096, "memory pair")
    require(e["denominators"]["attempted"] == 18 + 180 == 198, "observer denominator")
    require(sum(x["pairedTelemetryMinusElapsed"]["count"] for x in e["trials"]) == 90, "paired denominator")
    rows = ledger["dimensions"]
    require(len(rows) == len(DIMENSIONS) and {x["name"] for x in rows} == set(DIMENSIONS), "dimension coverage")
    for row in rows:
        require(row["unit"] == DIMENSIONS[row["name"]], "unit " + row["name"])
        for key in ("scope", "distribution", "boundary", "failureOverride", "unknown", "disposition"):
            require(isinstance(row[key], str) and row[key].strip(), "missing " + key)
        require(row["disposition"] in {"retain implemented boundary; no policy adoption", "separate review; no numeric bound selected", "unsupported; not tunable"}, "disposition")
        require(all(ref in sources for ref in row["evidence"]), "dimension source")
    return sources


def main():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    validate(ledger)
    # Deliberate independent reconciliation failures; no native/media execution.
    controls = []
    for mutate in (
        lambda x: x.update(adoption="adopted"),
        lambda x: x.update(privateCameraEvidenceUsed=True),
        lambda x: x["dimensions"].pop(),
        lambda x: x["dimensions"][0].update(unit="MiB"),
        lambda x: x["dimensions"][0].update(scope=""),
        lambda x: x["evidence"]["149"].update(sha256="0" * 64),
        lambda x: x["evidence"]["149"]["distributions"][0].update(value={}),
        lambda x: x["evidence"]["146"].update(distributions=[]),
    ):
        damaged = copy.deepcopy(ledger)
        mutate(damaged)
        try:
            validate(damaged)
        except (ValueError, KeyError, TypeError):
            controls.append(True)
        else:
            raise ValueError("corruption accepted")
    print(f"read-limits supplement: 6 bound sources, {len(DIMENSIONS)} unit/scope rows, denominator arithmetic and {len(controls)} rejection controls passed")


if __name__ == "__main__":
    main()
