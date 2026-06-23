import json
import unittest

from scripts import merge_aliases


class MergeAliasesTest(unittest.TestCase):
    def test_merge_aliases_updates_json_aliases_only_in_memory(self) -> None:
        rows = [
            {
                "entity_key": "demo",
                "entity_name": "ООО Демо",
                "aliases": json.dumps(["Demo"], ensure_ascii=False),
            }
        ]

        changed, messages = merge_aliases.merge_aliases(
            rows,
            {"demo": ["Demo", "Демо Тест"]},
        )

        self.assertEqual(changed, 1)
        self.assertEqual(len(messages), 1)
        self.assertEqual(json.loads(rows[0]["aliases"]), ["Demo", "Демо Тест"])

    def test_candidate_alias_value_ignores_identifier_fields(self) -> None:
        self.assertEqual(
            merge_aliases.candidate_alias_value(
                {"field_name": "kpp", "proposed_value": "770101001"}
            ),
            "",
        )
        self.assertEqual(
            merge_aliases.candidate_alias_value(
                {"field_name": "official_name", "proposed_value": "ООО Демо"}
            ),
            "ООО Демо",
        )

    def test_candidate_name_requires_explicit_flag(self) -> None:
        row = {"candidate_name": "Филиал ПАО Сбербанк", "decision": "accept"}

        self.assertEqual(merge_aliases.candidate_alias_value(row), "")
        self.assertEqual(
            merge_aliases.candidate_alias_value(row, include_candidate_name=True),
            "Филиал ПАО Сбербанк",
        )


if __name__ == "__main__":
    unittest.main()
