from pathlib import Path
import tempfile
import unittest

import pandas as pd

from purchase_analysis import source_sprint

ROOT_DIR = Path(__file__).resolve().parents[1]


class SourceSprintTest(unittest.TestCase):
    def test_normalize_item_row_maps_legacy_columns(self) -> None:
        row = source_sprint.normalize_item_row(
            {
                "source": "rts_tender",
                "title": "Test purchase",
                "url": "https://example.test/procedure/1",
                "amount": "10 000",
                "stage": "Active",
                "date_published": "01.02.2025",
                "company_name": "Customer",
                "company_inn": "7707083893",
                "procedure_number": "P-1",
            }
        )

        self.assertEqual(row["source_system"], "rts_tender")
        self.assertEqual(row["subject"], "Test purchase")
        self.assertEqual(row["detail_url"], "https://example.test/procedure/1")
        self.assertEqual(row["price_text"], "10 000")
        self.assertEqual(row["status"], "Active")
        self.assertEqual(row["published_at"], "01.02.2025")
        self.assertEqual(row["customer_name"], "Customer")
        self.assertEqual(row["customer_inn"], "7707083893")
        self.assertEqual(row["lot_number"], "1")

    def test_dedupe_items_frame_uses_procedure_and_lot(self) -> None:
        frame = pd.DataFrame(
            [
                {"source_system": "a", "procedure_number": "P-1", "lot_number": "1"},
                {"source_system": "a", "procedure_number": "P-1", "lot_number": "1"},
                {"source_system": "a", "procedure_number": "P-1", "lot_number": "2"},
            ]
        )

        deduped, duplicates = source_sprint.dedupe_items_frame(frame)

        self.assertEqual(len(deduped), 2)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(set(deduped["lot_number"]), {"1", "2"})

    def test_write_items_csv_preserves_standard_column_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "items.csv"
            written = source_sprint.write_items_csv(
                path,
                [{"source": "etpgpb", "procedure_number": "P-1", "title": "Subject"}],
            )

            self.assertTrue(path.exists())
            self.assertEqual(written.columns[:3].tolist(), ["source_system", "platform_section", "entity_name"])
            self.assertEqual(written.loc[0, "source_system"], "etpgpb")
            self.assertEqual(written.loc[0, "subject"], "Subject")

    def test_write_items_csv_writes_header_for_empty_batches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "items.csv"
            written = source_sprint.write_items_csv(path, [])

            self.assertTrue(path.exists())
            self.assertTrue(written.empty)
            self.assertEqual(written.columns.tolist(), source_sprint.STANDARD_ITEM_COLUMNS)

    def test_manifest_and_allowlist_agree_on_default_batches(self) -> None:
        allowlist = source_sprint.load_source_sprint_allowlist(
            ROOT_DIR / "configs" / "source_sprints_allowlist.csv"
        )
        manifest = source_sprint.load_source_sprint_manifest(
            ROOT_DIR / "configs" / "source_sprints_manifest.csv"
        )

        default_allowlist = {
            entry.batch_name
            for entry in allowlist
            if entry.include_in_default_merge
        }
        default_manifest = {
            entry.batch_name
            for entry in manifest
            if entry.include_in_default_merge
        }

        self.assertEqual(
            default_allowlist,
            {
                "ast-full-2024-2025-finalcheck",
                "b2b_center_prompt2_full_scope_2026-06-18",
                "eis-prompt2-full-scope-2026-06-22",
            },
        )
        self.assertEqual(default_allowlist, default_manifest)
        self.assertTrue(all(entry.item_rows > 0 for entry in manifest if entry.include_in_default_merge))


if __name__ == "__main__":
    unittest.main()
