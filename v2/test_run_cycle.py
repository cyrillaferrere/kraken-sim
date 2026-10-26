"""Unattended V2 routine tests: fail-closed and atomic candidate staging."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from run_cycle import stage_candidate
from test_engine_preflight import NOW, plan, market, state


class RoutineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = [self.root / n for n in ("plan.json", "market.json", "verified.json", "candidate.json")]
        for path, obj in zip(self.paths, (plan(), market(), state())):
            path.write_text(json.dumps(obj), encoding="utf-8")

    def test_stages_candidate_atomically_without_touching_state(self):
        before = self.paths[2].read_bytes()
        result = stage_candidate(*self.paths, now=NOW)
        self.assertEqual(result["status"], "STAGED")
        self.assertEqual(self.paths[2].read_bytes(), before)
        candidate = json.loads(self.paths[3].read_text())
        self.assertEqual(candidate["mode"], "PAPER")
        self.assertEqual(len(candidate["orders"]), 1)

    def test_refuses_overwrite(self):
        stage_candidate(*self.paths, now=NOW)
        with self.assertRaises(FileExistsError):
            stage_candidate(*self.paths, now=NOW)

    def test_missing_verified_portfolio_rejects_without_output(self):
        self.paths[2].write_text(json.dumps({"data_source": None}), encoding="utf-8")
        with self.assertRaises(Exception):
            stage_candidate(*self.paths, now=NOW)
        self.assertFalse(self.paths[3].exists())

    def test_rejects_stale_snapshot_without_output(self):
        m = market()
        m["ts"] = "2026-10-25T11:40:00Z"
        self.paths[1].write_text(json.dumps(m), encoding="utf-8")
        with self.assertRaises(Exception):
            stage_candidate(*self.paths, now=NOW)
        self.assertFalse(self.paths[3].exists())

    def test_never_overwrites_live_state(self):
        with self.assertRaises(ValueError):
            stage_candidate(*self.paths[:3], self.paths[2], now=NOW)
        with self.assertRaises(ValueError):
            stage_candidate(*self.paths[:3], self.root / "state.json", now=NOW)


if __name__ == "__main__":
    unittest.main()
