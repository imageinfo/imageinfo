"""Independent arithmetic/semantic audit of retained v2 records; no counter helper imports.

This checks internal consistency, never authenticity of arbitrary imported JSON.
"""
import argparse
import json
from pathlib import Path

COUNTERS = ("userCpuNs", "systemCpuNs", "readOperations", "writeOperations", "otherOperations",
            "readTransferBytes", "writeTransferBytes", "otherTransferBytes", "peakWorkingSetBytes")
ALL = set(COUNTERS) | {"workingSetBytes", "privateCommitBytes", "physicalIoBytes"}
GROUPS = {"cpu": {"userCpuNs", "systemCpuNs"},
          "memory": {"workingSetBytes", "privateCommitBytes", "peakWorkingSetBytes"},
          "logicalIo": {"readOperations", "writeOperations", "otherOperations", "readTransferBytes",
                        "writeTransferBytes", "otherTransferBytes"}}


def audit(record):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    require(record["schemaVersion"] == 2, "wrong record version")
    base = record["elapsedRecord"]
    require(record["purpose"] in ("metadata-read", "authored-child-qualification"), "unknown purpose")
    attempts, telemetry = base["attempts"], record["telemetry"]
    require(len(attempts) == len(telemetry) > 0, "attempt/telemetry count mismatch")
    cancelled = any(a["outcome"] == "cancelled" for a in attempts)
    require(not cancelled or base["status"] in ("cancelled", "invalid-measurement"), "cancellation status mismatch")
    require(base["status"] != "cancelled" or cancelled, "cancelled status without cancelled attempt")
    expected_count = base["configuration"]["warmups"] + base["configuration"]["repeats"]
    require(len(attempts) == expected_count or (
        len(attempts) < expected_count and base["status"] in ("cancelled", "invalid-measurement") and
        attempts[-1]["outcome"] == "cancelled"), "missing attempts without cancellation")
    for index, (a, t) in enumerate(zip(attempts, telemetry)):
        require(a["index"] == index, "attempt ordering")
        require(a["phase"] == ("warmup" if index < base["configuration"]["warmups"] else "sample"), "phase ordering")
        require(a["censored"] == (a["outcome"] in ("timeout", "output-limit", "consumer-error", "cancelled", "telemetry-limit")), "censor mismatch")
        require(a["elapsedNs"] > 0, "nonpositive elapsed duration")
        for pipe in ("stdout", "stderr"):
            require(0 <= a[pipe + "CapturedBytes"] <= min(a[pipe + "Bytes"], base["configuration"]["captureBytes"]), "capture bound")
        samples = t["samples"]
        require(len(samples) <= t["maxSamples"] == 2048, "sample bound")
        require(t["observedDescendantPids"] == sorted(set(t["observedDescendantPids"])), "duplicate/unsorted descendants")
        if t["observedDescendantPids"]:
            require(t["membership"] == "invalid-descendants", "descendants without invalid membership")
        totals = 0
        last_end = -1
        previous = {}
        for position, s in enumerate(samples):
            begin, end = s["beginOffsetNs"], s["endOffsetNs"]
            require(0 <= begin <= end <= a["elapsedNs"] and begin >= last_end, "sample timing alignment")
            last_end = end
            totals += end - begin
            require(not s["final"] or position == len(samples) - 1, "nonterminal final sample")
            require(set(s["values"]) == ALL, "missing/extra metric")
            values, errors = s["values"], s["errors"]
            require(values["physicalIoBytes"] is None and bool(errors.get("physicalIoBytes")), "physical I/O fabricated")
            for group, names in GROUPS.items():
                if group in errors or "counterRead" in errors:
                    require(all(values[n] is None for n in names), "failed counter fabricated values")
                else:
                    require(all(type(values[n]) is int and values[n] >= 0 for n in names), "counter missing without reason")
            for name in COUNTERS:
                value = values[name]
                if value is not None:
                    require(value >= previous.get(name, 0), "cumulative/high-water counter decreased")
                    previous[name] = value
            if values["workingSetBytes"] is not None:
                require(values["workingSetBytes"] <= values["peakWorkingSetBytes"], "RSS exceeds OS high-water")
        require(totals == t["observerWallNs"], "overhead arithmetic mismatch")
        require(not samples or samples[-1]["final"], "missing direct-exit sample")
        for metric in ("workingSetBytes", "privateCommitBytes"):
            maximum = max((s["values"][metric] for s in samples if s["values"][metric] is not None), default=None)
            require(t["sampledMaxima"][metric] == maximum, "sampled maximum arithmetic mismatch")
        calculated_valid = (bool(samples) and t["membership"] == "direct-only-observed" and not t["errors"]
                            and t["stopReason"] is None and all(not(set(s["errors"]) - {"physicalIoBytes"}) for s in samples))
        require(t["valid"] == calculated_valid, "validity contradicts counters/membership")
        if a["eligible"]:
            require(record["purpose"] == "metadata-read" and t["valid"] and a["phase"] == "sample" and a["correctness"] == "pass"
                    and a["outcome"] == "exited" and a["exitCode"] == 0
                    and base["sourceUnchanged"] and base["binaryUnchanged"], "invalid eligibility")
    return {"attempts": len(attempts), "telemetryValid": sum(t["valid"] for t in telemetry),
            "eligible": sum(a["eligible"] for a in attempts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    # 110 attempts x 2048 bounded samples, plus configurations. Not an unbounded importer.
    with args.record.open("rb") as stream:
        data = stream.read(256 * 1024 * 1024 + 1)
    if len(data) > 256 * 1024 * 1024:
        raise ValueError("audit record exceeds 256 MiB bound")
    print(json.dumps(audit(json.loads(data))))


if __name__ == "__main__":
    main()
