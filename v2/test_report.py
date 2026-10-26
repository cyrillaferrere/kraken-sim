"""Report routine tests."""
import unittest
from pathlib import Path
from check_report import validate_report


class ReportTests(unittest.TestCase):
    def test_template_has_all_sections(self):
        text = (Path(__file__).resolve().parent / "reports" / "TEMPLATE.md").read_text(encoding="utf-8")
        self.assertTrue(validate_report(text, template=True))

    def test_unfinished_report_is_rejected(self):
        text = (Path(__file__).resolve().parent / "reports" / "TEMPLATE.md").read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            validate_report(text)

    def test_missing_sections_rejected(self):
        with self.assertRaises(ValueError):
            validate_report("BTC 1 USD")


if __name__ == "__main__":
    unittest.main()
