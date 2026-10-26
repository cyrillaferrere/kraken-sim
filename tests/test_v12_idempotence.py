import tempfile,unittest
from v12_isolation import connect,record_cycle
class TestIdempotence(unittest.TestCase):
    def test_duplicate_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with connect(tmp) as db:
                self.assertTrue(record_cycle(db,"slot1","2026-10-25T00:00:00Z"))
                self.assertFalse(record_cycle(db,"slot1","2026-10-25T00:05:00Z"))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM cycles").fetchone()[0],1)
if __name__=="__main__": unittest.main()
