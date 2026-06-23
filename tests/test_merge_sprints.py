from pathlib import Path
import tempfile
import unittest

import pandas as pd

from scripts import merge_sprints


def write_items(batch_dir: Path, rows: list[dict[str, str]]) -> None:
    batch_dir.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(batch_dir / "items.csv", index=False, encoding="utf-8-sig")


class MergeSprintsTest(unittest.TestCase):
    def test_default_selection_uses_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "source_sprints"
            write_items(input_dir / "clean-a", [{"source_system": "a", "procedure_number": "P-1"}])
            write_items(input_dir / "probe-a", [{"source_system": "a", "procedure_number": "P-2"}])
            allowlist = root / "allowlist.csv"
            allowlist.write_text(
                "batch_name,source_system,status,include_in_default_merge,notes\n"
                "clean-a,a,current,1,\n"
                "probe-a,a,probe,0,\n",
                encoding="utf-8",
            )

            selected = merge_sprints.select_batch_names(
                input_dir=input_dir,
                allowlist_file=allowlist,
            )

            self.assertEqual(selected, ["clean-a"])

    def test_probe_batch_requires_explicit_unsafe_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "source_sprints"
            write_items(input_dir / "probe-a", [{"source_system": "a", "procedure_number": "P-1"}])
            allowlist = root / "allowlist.csv"
            allowlist.write_text(
                "batch_name,source_system,status,include_in_default_merge,notes\n",
                encoding="utf-8",
            )

            with self.assertRaises(SystemExit):
                merge_sprints.select_batch_names(
                    input_dir=input_dir,
                    allowlist_file=allowlist,
                    explicit_batches=["probe-a"],
                )

            selected = merge_sprints.select_batch_names(
                input_dir=input_dir,
                allowlist_file=allowlist,
                explicit_batches=["probe-a"],
                include_unsafe=True,
            )
            self.assertEqual(selected, ["probe-a"])

    def test_cross_source_dedupe_reports_keep_and_drop(self) -> None:
        frame_a = pd.DataFrame(
            [
                {
                    "source_system": "sberbank_ast",
                    "procedure_number": "P-1",
                    "lot_number": "1",
                    "sprint_batch": "ast",
                }
            ]
        )
        frame_b = pd.DataFrame(
            [
                {
                    "source_system": "eis",
                    "procedure_number": "P-1",
                    "lot_number": "1",
                    "sprint_batch": "eis",
                },
                {
                    "source_system": "b2b_center",
                    "procedure_number": "P-2",
                    "lot_number": "1",
                    "sprint_batch": "b2b",
                },
            ]
        )

        final, duplicates = merge_sprints.merge_frames([frame_a, frame_b])

        self.assertEqual(len(final), 2)
        self.assertEqual(len(duplicates), 2)
        self.assertEqual(duplicates["dedupe_action"].tolist(), ["keep", "drop"])
        self.assertEqual(duplicates["duplicate_group_size"].tolist(), [2, 2])


if __name__ == "__main__":
    unittest.main()
