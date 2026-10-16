"""Authored integrity controls for the small assisted-sign-in supplement."""
import hashlib
from pathlib import Path
import tempfile
import unittest

import audit_completion as completion


class SignInControls(unittest.TestCase):
    def setUp(self):
        scratch = completion.core.REPO/'.local'
        scratch.mkdir(exist_ok=True)
        self.storage = tempfile.TemporaryDirectory(dir=scratch,prefix='0110-completion-control-')
        self.assertTrue(Path(self.storage.name).resolve().is_relative_to(scratch.resolve()))
        self.addCleanup(self.storage.cleanup)
        self.folder = Path(self.storage.name).resolve()/'pre-context'
        self.folder.mkdir()
        (self.folder/'screen.png').write_bytes(b'authored screenshot hash control')
        self.proof = {'stage':'waiting-for-fresh-agent-readiness','controllerStillRunning':True,
            'measurementRequestsQueued':False,'bootstrapPerformed':False,'actorReplayed':False,
            'faultReplayed':False,'extraVmOffs':0,'pendingCell':'pre-context',
            'originalRequestCheckpoint':'before.private.json','screenshot':'screen.png',
            'screenshotSha256':hashlib.sha256((self.folder/'screen.png').read_bytes()).hexdigest(),
            'observedScreenUtc':'1970-01-01T00:00:02+00:00',
            'continuationObservedUtc':'1970-01-01T00:00:03+00:00',
            'authorization':'Parent authorized login-only continuation; no bootstrap/replacement/replay',
            'action':'Dismiss visible incorrect-password dialog, clear password field, enter retained fixture password; login only'}
        self.before = {'checkpoint':{'at':1}}
        self.after = {'readiness':{'challengeResult':{'at':4}}}

    def check(self, proof=None):
        return completion.sign_in(proof or self.proof,self.folder,self.before,self.after)

    def test_login_only_scope(self):
        self.assertTrue(self.check()['operatorAssistedSignIn'])

    def test_bootstrap_is_not_sign_in(self):
        self.proof['bootstrapPerformed'] = True
        with self.assertRaises(ValueError):
            self.check()

    def test_pending_job_claim_rejected(self):
        self.proof['measurementRequestsQueued'] = True
        with self.assertRaises(ValueError):
            self.check()

    def test_extra_fault_rejected(self):
        self.proof['extraVmOffs'] = 1
        with self.assertRaises(ValueError):
            self.check()

    def test_screenshot_hash_mismatch(self):
        self.proof['screenshotSha256'] = '0'*64
        with self.assertRaises(ValueError):
            self.check()

    def test_observation_before_fault_rejected(self):
        self.proof['observedScreenUtc'] = '1970-01-01T00:00:00+00:00'
        with self.assertRaises(ValueError):
            self.check()


if __name__ == '__main__':
    unittest.main()
