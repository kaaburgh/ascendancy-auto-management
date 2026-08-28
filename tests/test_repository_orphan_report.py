import json
import tempfile
import unittest
from pathlib import Path

from scripts import report_repository_orphans as orphan_report


class RepositoryOrphanReportTests(unittest.TestCase):
    def _root(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "scripts").mkdir()
        (root / "tools").mkdir()
        (root / "tests").mkdir()
        (root / "docs" / "experiments").mkdir(parents=True)
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        self.addCleanup(temp.cleanup)
        return root

    def test_new_schema_constant_without_producer_is_reported(self):
        root = self._root()
        (root / "scripts" / "example.py").write_text(
            'UNUSED_SCHEMA = "ascendancy.example/v1"\n', encoding="utf-8"
        )
        report = orphan_report.detect(root)
        self.assertEqual(
            report["schema_orphans"],
            [
                {
                    "id": "ascendancy.example/v1",
                    "path": "scripts/example.py",
                    "symbol": "UNUSED_SCHEMA",
                }
            ],
        )

    def test_schema_written_to_document_is_not_reported(self):
        root = self._root()
        (root / "scripts" / "example.py").write_text(
            'OUTPUT_SCHEMA = "ascendancy.example/v1"\n'
            'def emit():\n    return {"schema": OUTPUT_SCHEMA}\n',
            encoding="utf-8",
        )
        self.assertEqual(orphan_report.detect(root)["schema_orphans"], [])

    def test_imported_module_and_standalone_cli_are_not_reported(self):
        root = self._root()
        (root / "scripts" / "library.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "scripts" / "consumer.py").write_text(
            "import scripts.library\n", encoding="utf-8"
        )
        (root / "tools" / "cli.py").write_text(
            'if __name__ == "__main__":\n    pass\n', encoding="utf-8"
        )
        self.assertEqual(orphan_report.detect(root)["module_orphans"], [])

    def test_unlinked_experiment_is_reported(self):
        root = self._root()
        path = root / "docs" / "experiments" / "E1.md"
        path.write_text("# E1\n", encoding="utf-8")
        self.assertEqual(
            orphan_report.detect(root)["experiment_orphans"],
            [{"path": "docs/experiments/E1.md"}],
        )
        (root / "ROADMAP.md").write_text(
            "See [E1](docs/experiments/E1.md).\n", encoding="utf-8"
        )
        self.assertEqual(orphan_report.detect(root)["experiment_orphans"], [])

    def test_allowlist_requires_non_empty_reason(self):
        root = self._root()
        path = root / "allowlist.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": orphan_report.ALLOWLIST_SCHEMA,
                    "entries": {"module:scripts/example.py": ""},
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "non-empty reason"):
            orphan_report.load_allowlist(path)


if __name__ == "__main__":
    unittest.main()
