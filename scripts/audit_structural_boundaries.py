"""Independent retained-output audit for authored #149 structural campaigns."""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


COUNTERS = {"userCpuNs", "systemCpuNs", "workingSetBytes", "peakWorkingSetBytes", "privateCommitBytes", "readOperations", "writeOperations", "otherOperations", "readTransferBytes", "writeTransferBytes", "otherTransferBytes"}
MONOTONIC = COUNTERS - {"workingSetBytes", "privateCommitBytes"}


def audit_encoded(cell, path):
    data = Path(path).read_bytes()
    def number(at,width,order="big"):
        assert 0 <= at <= len(data)-width
        return int.from_bytes(data[at:at+width],order)
    boxes = []
    def walk(start,end,parent=None,depth=0):
        at=start
        while at<end:
            size=number(at,4); kind=data[at+4:at+8]
            assert size>=8 and at+size<=end
            index=len(boxes); boxes.append((at,at+size,kind,parent,depth))
            children=at+size
            if kind in (b"moov",b"trak",b"mdia",b"minf",b"stbl",b"dinf"): children=at+8
            elif kind==b"uuid":
                assert size>=24
                uuid=data[at+8:at+24].hex()
                if uuid=="85c0b687820f11e08111f4ce462b6a48": children=at+24
                if uuid=="eaf42b5e1c984b88b9fbb7dc406e4d16": children=at+32
            walk(children,at+size,index,depth+1)
            at+=size
        assert at==end
    walk(0,len(data))
    assert len(data)==cell["length"] and len(boxes)==cell["boxes"]
    cmt=next(b for b in boxes if b[2]==b"CMT4")
    base=cmt[0]+8; offset=number(base+4,4,"little"); directories=[]
    while offset:
        at=base+offset; count=number(at,2,"little")
        assert at+count*12+6<=cmt[1] and at not in [d[0] for d in directories]
        directories.append([at,len(directories),count])
        offset=number(at+2+12*count,4,"little")
    assert directories==cell["cmt4Directories"]
    stsd=next(b for b in boxes if b[2]==b"stsd" and data[b[0]+20:b[0]+24]==b"CTMD")
    tables=[b for b in boxes if b[3]==stsd[3]]
    stsz=next(b[0] for b in tables if b[2]==b"stsz")
    co64=next(b[0] for b in tables if b[2]==b"co64")
    assert number(stsz+16,4)==number(co64+12,4)==1
    at=number(co64+16,8); end=at+number(stsz+12,4)
    assert any(b[2]==b"mdat" and b[0]+8<=at<=end<=b[1] for b in boxes)
    records=[]
    while at<end:
        size=number(at,4,"little")
        assert size>=12 and at+size<=end and number(at+4,2,"little")==5
        records.append([at,size]); at+=size
    assert at==end and records==cell["timedRecordExtents"]
    scope=cell["scope"]
    actual={"boxes":len(boxes),"bmff-depth":max(b[4] for b in boxes),
            "tiff-depth":directories[-1][1],"entries-per-cmt":sum(d[2] for d in directories),"timed-records":len(records)}[scope]
    assert actual==cell["denominator"]
    return records


def audit_resources(attempt, request_id):
    elapsed = attempt["elapsedNs"]
    assert type(elapsed) is int and elapsed > 0
    assert datetime.fromisoformat(attempt["startedUtc"]).utcoffset() is not None
    assert attempt["errorClass"] is None
    telemetry = attempt["telemetry"]
    assert type(telemetry["pid"]) is int and telemetry["pid"] > 0
    assert request_id.startswith(f"req-{telemetry['pid']}-")
    assert telemetry["valid"] is True and telemetry["membership"] == "direct-only-observed"
    assert telemetry["observedDescendantPids"] == [] and telemetry["errors"] == []
    assert telemetry["stopReason"] is None
    assert telemetry["requestedIntervalMs"] == 1 and telemetry["maxSamples"] == 2048
    samples = telemetry["samples"]
    assert 2 <= len(samples) <= 2048
    assert samples[0]["final"] is False and samples[-1]["final"] is True
    previous_end = overhead = 0
    previous_values = None
    for index, sample in enumerate(samples):
        begin, end = sample["beginOffsetNs"], sample["endOffsetNs"]
        assert type(begin) is int and type(end) is int and previous_end <= begin <= end <= elapsed
        assert sample["final"] is (index == len(samples)-1)
        values = sample["values"]
        assert set(values) == COUNTERS | {"physicalIoBytes"}
        assert sample["errors"] == {"physicalIoBytes": "not instrumented; logical transfers are not device traffic"}
        assert values["physicalIoBytes"] is None
        assert all(type(values[k]) is int and values[k] >= 0 for k in COUNTERS)
        assert values["peakWorkingSetBytes"] >= values["workingSetBytes"]
        if previous_values:
            assert all(values[k] >= previous_values[k] for k in MONOTONIC)
        previous_values, previous_end = values, end
        overhead += end-begin
    assert telemetry["observerWallNs"] == overhead
    for key in ("workingSetBytes", "privateCommitBytes"):
        assert telemetry["sampledMaxima"][key] == max(s["values"][key] for s in samples)
        assert telemetry["sampledMaxima"][key] > 0


def audit(directory):
    if not __debug__:
        raise ValueError("audit requires Python assertion checks; omit -O")
    root = Path(directory)
    record = json.loads((root / "record.json").read_text(encoding="utf-8"))
    assert record["schemaVersion"] == 1 and record["ticket"] == 149
    assert type(record["repeats"]) is int and 1 <= record["repeats"] <= 10
    assert record["limits"] == {"timeoutMs":10000,"captureBytesPerPipe":4194304,"telemetryIntervalMs":1}
    scripts = Path(__file__).resolve().parent
    for key, name in (("driverSha256","structural_boundary_campaign.py"),("sharedDriverSha256","read_benchmark.py"),("telemetryDriverSha256","read_telemetry.py")):
        assert digest(scripts/name) == record[key]
    assert digest(record["pythonExecutable"]) == record["pythonSha256"]
    assert record["complete"] and record["binaryUnchanged"]
    assert digest(record["binary"]) == record["binarySha256"]
    assert digest(record["manifest"]) == record["manifestSha256"]
    manifest = json.loads(Path(record["manifest"]).read_text(encoding="utf-8"))
    assert len(record["cases"]) == len(manifest) == 15
    messages = {"boxes": "Box count limit exceeded", "bmff-depth": "Box nesting limit exceeded",
                "tiff-depth": "IFD depth limit exceeded", "entries-per-cmt": "TIFF entry limit exceeded",
                "timed-records": "Timed record limit exceeded"}
    assert {c["id"] for c in manifest} == {s+"-"+v for s in messages for v in ("below","at","above")}
    results = []
    for cell, case in zip(manifest, record["cases"]):
        assert case["expectation"] == cell and case["id"] == cell["id"]
        assert case["sourceUnchanged"] and digest(case["input"]) == cell["sha256"]
        assert case["inputSha256"] == cell["sha256"]
        assert case["argv"] == [record["binary"],"metadata","read","--tag","Make","--output","json","--",case["input"]]
        scope, label = cell["id"].rsplit("-", 1)
        default = 16 if scope.endswith("depth") else 4096
        assert cell["default"] == default
        assert cell["denominator"] == default + {"below": -1, "at": 0, "above": 1}[label]
        refusal = messages[scope] if label == "above" else None
        assert cell["refusal"] == refusal
        records = audit_encoded(cell,case["input"])
        requests = json.loads(Path(record["manifest"]).with_name(cell["id"] + ".requests.json").read_text(encoding="utf-8"))
        assert len(requests) == cell["requests"] and requests[-1] == cell["lastRequest"]
        assert sum(r["requested"] for r in requests) == cell["logicalRequestedBytes"]
        assert all(r["requested"] == r["returned"] and r["offset"] + r["returned"] <= cell["length"] for r in requests)
        if scope == "timed-records" and refusal:
            boundary=records[4096][0]
            assert not any(r["offset"]==boundary for r in requests)
            assert requests[-1]["offset"]==records[4095][0]+12 and requests[-1]["returned"]==12
        assert len(case["attempts"]) == record["repeats"]
        for index, attempt in enumerate(case["attempts"]):
            assert attempt["index"] == index
            assert attempt["stdoutFile"] == f"{cell['id']}-{index}.stdout"
            assert attempt["stderrFile"] == f"{cell['id']}-{index}.stderr"
            stdout = (root / attempt["stdoutFile"]).read_bytes()
            stderr = (root / attempt["stderrFile"]).read_bytes()
            assert hashlib.sha256(stdout).hexdigest() == attempt["stdoutSha256"]
            assert hashlib.sha256(stderr).hexdigest() == attempt["stderrSha256"]
            assert attempt["outcome"] == "exited" and not attempt["censored"]
            assert len(stdout) == attempt["stdoutBytes"] <= 4194304
            assert len(stderr) == attempt["stderrBytes"] <= 4194304
            assert attempt["stdoutCapturedBytes"] == len(stdout) and attempt["stderrCapturedBytes"] == len(stderr)
            value = json.loads(stdout)
            assert value["schemaVersion"] == 1
            request_id = value["requestId"]
            assert value["request"]["requestId"] == request_id and value["request"]["operation"] == "metadata read"
            summary = value["summary"]
            assert summary["requestId"] == request_id
            assert summary["outputComplete"] and summary["selectionComplete"] and not summary["interrupted"]
            assert summary["artifacts"] == [] and len(value["files"]) == 1
            f = value["files"][0]
            assert f["requestId"] == request_id and f["path"] == case["input"] and f["inputId"] == "input-0"
            assert f["effects"] == {"publicationMayHaveOccurred": False, "changed": False, "cleanupPending": False, "recoveryIds": [], "notes": []}
            if refusal:
                assert attempt["exitCode"] == summary["exitStatus"] == 1
                assert f["state"] == "failed" and f["snapshot"] is None
                assert len(f["issues"]) == 1 and f["issues"][0]["code"] == "LIMIT_EXCEEDED"
                assert f["issues"][0]["message"] == refusal
                assert stderr.decode("utf-8").startswith("LIMIT_EXCEEDED: " + refusal)
            else:
                assert attempt["exitCode"] == summary["exitStatus"] == 0 and not stderr
                assert f["state"] == "read" and len(f["issues"]) == 1 and f["issues"][0]["code"] == "COVERAGE_PARTIAL"
                snapshot = f["snapshot"]
                assert len(snapshot["occurrences"]) == 1
                occurrence = snapshot["occurrences"][0]
                assert occurrence["tag"]["name"] == "Make"
                assert occurrence["values"]["normalized"] == {"state":"present","value":{"kind":"string","text":"Canon"}}
            audit_resources(attempt,request_id)
        measurements=[]
        for attempt in case["attempts"]:
            telemetry=attempt["telemetry"]
            final=telemetry["samples"][-1]["values"]
            measurements.append({"elapsedNs":attempt["elapsedNs"],"cpuNs":final["userCpuNs"]+final["systemCpuNs"],
                                 "lifetimePeakWorkingSetBytes":final["peakWorkingSetBytes"],
                                 "sampledMaxWorkingSetBytes":telemetry["sampledMaxima"]["workingSetBytes"],
                                 "sampledMaxPrivateCommitBytes":telemetry["sampledMaxima"]["privateCommitBytes"],
                                 "readOperations":final["readOperations"],"writeOperations":final["writeOperations"],
                                 "logicalReadBytes":final["readTransferBytes"],"logicalWriteBytes":final["writeTransferBytes"]})
        results.append({"id": cell["id"], "attempts": len(case["attempts"]), "logicalRequestedBytes": cell["logicalRequestedBytes"], "measurements":measurements, "verdict": "pass"})
    return {"ticket": 149, "verdict": "pass", "cases": results,
            "limits": "finite authored default boundaries; direct sampled process counters; cache uncontrolled; no hard-envelope saturation or physical I/O claim"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record-dir", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    result = audit(args.record_dir)
    with Path(args.output).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
