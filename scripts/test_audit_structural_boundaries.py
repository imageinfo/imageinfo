"""Authored acceptance and corruption controls; no process measurement."""
import copy
import unittest
from audit_structural_boundaries import audit_resources, COUNTERS


def authored_attempt():
    values = {name:100 for name in COUNTERS}
    values["physicalIoBytes"] = None
    samples = [{"beginOffsetNs":begin,"endOffsetNs":begin+10,"final":final,
                "values":copy.deepcopy(values),"errors":{"physicalIoBytes":"not instrumented; logical transfers are not device traffic"}}
               for begin,final in ((10,False),(100,True))]
    return {"elapsedNs":200,"startedUtc":"2026-10-17T12:00:00+00:00","errorClass":None,
            "telemetry":{"pid":123,"valid":True,"membership":"direct-only-observed",
                         "observedDescendantPids":[],"errors":[],"stopReason":None,
                         "requestedIntervalMs":1,"maxSamples":2048,"samples":samples,
                         "observerWallNs":20,"sampledMaxima":{"workingSetBytes":100,"privateCommitBytes":100}}}


class Resources(unittest.TestCase):
    def test_valid_authored_endpoints(self):
        audit_resources(authored_attempt(),"req-123-authored")

    def test_missing_elapsed(self):
        a=authored_attempt(); del a["elapsedNs"]
        with self.assertRaises((AssertionError,KeyError)): audit_resources(a,"req-123-authored")

    def test_corruptions_are_rejected(self):
        def mutate(field,value):
            def apply(a): a["telemetry"][field]=value
            return apply
        def sample(field,value):
            def apply(a): a["telemetry"]["samples"][-1][field]=value
            return apply
        controls=[
            mutate("samples",[{}]), mutate("pid",124), mutate("errors",["counter-setup"]),
            mutate("observedDescendantPids",[456]), mutate("stopReason","telemetry-limit"),
            mutate("observerWallNs",0), mutate("sampledMaxima",{"workingSetBytes":999,"privateCommitBytes":100}),
            sample("final",False), sample("endOffsetNs",201), sample("beginOffsetNs",0),
            sample("values",{}), sample("errors",{"cpu":"failed"}),
            lambda a:a["telemetry"]["samples"][-1]["values"].update(userCpuNs=None),
            lambda a:a["telemetry"]["samples"][-1]["values"].update(readTransferBytes=99),
            lambda a:a["telemetry"]["samples"][-1]["values"].update(physicalIoBytes=0),
            lambda a:a.update(elapsedNs=0),
        ]
        for index,change in enumerate(controls):
            with self.subTest(control=index):
                a=authored_attempt(); change(a)
                with self.assertRaises((AssertionError,KeyError,TypeError)):
                    audit_resources(a,"req-123-authored")


if __name__ == "__main__":
    unittest.main()
