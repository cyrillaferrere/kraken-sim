"""V1.2 manual deploy workflow security contract; no run is triggered."""
import re
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WF=(ROOT/".github"/"workflows"/"sim_v12.yml").read_text(encoding="utf8")
HOST="github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"
class TestWorkflowSecurity(unittest.TestCase):
    def test_manual_only_without_cron(self):
        self.assertIn("workflow_dispatch:",WF)
        self.assertNotRegex(WF,r"(?m)^\s*schedule:")
        self.assertIn("contents: read",WF)
        self.assertNotIn("contents: write",WF)
        self.assertNotIn("git push --force",WF)
        self.assertNotIn("git push -f ",WF)
    def test_secret_only_in_publisher(self):
        jobs=WF.split("\n  publish:",1)
        self.assertEqual(len(jobs),2)
        self.assertNotIn("secrets.PREPROD_DEPLOY_KEY",jobs[0])
        self.assertEqual(jobs[1].count("secrets.PREPROD_DEPLOY_KEY"),1)
        self.assertIn("V12_REVIEWED_CODE_SHA",WF)
        self.assertIn("cancel-in-progress: false",WF)
    def test_ssh_host_not_trust_on_first_use(self):
        self.assertIn(HOST,WF)
        self.assertNotIn("ssh-keyscan",WF)
        self.assertIn("StrictHostKeyChecking=yes",WF)
        self.assertIn("trap 'rm -f",WF)
    def test_state_branch_only(self):
        self.assertIn("HEAD:state-v12",WF)
        self.assertNotIn("HEAD:main",WF)
        self.assertNotIn("kraken-sim-state.git",WF)
if __name__=="__main__": unittest.main()
