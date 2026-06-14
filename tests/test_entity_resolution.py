from pathlib import Path
import unittest

from purchase_analysis.entity_resolution import (
    build_search_terms,
    classify_entity_match,
    load_entity_scope,
    split_multi,
)


ROOT_DIR = Path(__file__).resolve().parents[1]


class EntityResolutionTest(unittest.TestCase):
    def test_split_multi_dedupes_values(self) -> None:
        self.assertEqual(split_multi("Сбербанк; Сбербанк | Домклик"), ["Сбербанк", "Домклик"])

    def test_load_scope_preserves_enriched_identity_fields(self) -> None:
        entities = load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
        self.assertEqual(len(entities), 26)
        inns = [entity.inn for entity in entities]
        self.assertTrue(all(inns))
        self.assertEqual(len(inns), len(set(inns)))
        sberbank = next(entity for entity in entities if entity.entity_id == "sberbank_russia")
        self.assertEqual(sberbank.inn, "7707083893")
        self.assertEqual(sberbank.ogrn, "1027700132195")
        self.assertIn("773601001", sberbank.kpp_list)
        self.assertIn("Сбербанк", sberbank.brand_aliases)

    def test_build_search_terms_uses_identifiers_and_aliases(self) -> None:
        entity = next(
            item
            for item in load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
            if item.entity_id == "domclick"
        )
        terms = build_search_terms(entity, source_system="eis")
        self.assertIn("7736249247", terms)
        self.assertIn("1157746652150", terms)
        self.assertIn("Домклик", terms)
        self.assertEqual(len(terms), len({term.casefold() for term in terms}))

    def test_identifier_matches_are_accepted_for_safe_roles(self) -> None:
        entity = next(
            item
            for item in load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
            if item.entity_id == "sberbank_ast"
        )
        by_inn = classify_entity_match(entity, candidate_inn="7707308480", role="Заказчик")
        by_ogrn = classify_entity_match(entity, candidate_ogrn="1027707000441", role="customer")
        self.assertTrue(by_inn.accepted)
        self.assertEqual(by_inn.reason, "inn_exact")
        self.assertTrue(by_ogrn.accepted)
        self.assertEqual(by_ogrn.reason, "ogrn_exact")

    def test_name_only_match_goes_to_review_not_core(self) -> None:
        entity = next(
            item
            for item in load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
            if item.entity_id == "sberbank_leasing"
        )
        decision = classify_entity_match(
            entity,
            candidate_name='АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК ЛИЗИНГ"',
            role="customer",
        )
        self.assertTrue(decision.needs_review)
        self.assertEqual(decision.reason, "exact_name_without_identifier")

    def test_unsafe_roles_are_rejected_even_with_matching_identifier(self) -> None:
        entity = next(
            item
            for item in load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
            if item.entity_id == "sberbank_russia"
        )
        decision = classify_entity_match(entity, candidate_inn="7707083893", role="operator")
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "unsafe_core_role")


if __name__ == "__main__":
    unittest.main()
