import unittest

from purchase_analysis.clients.eis import EisEntityCandidate, build_customer_filter_value


class EisPayloadTest(unittest.TestCase):
    def test_build_customer_filter_value(self) -> None:
        candidate = EisEntityCandidate(
            search_term="Сбербанк",
            code="18950000008",
            name='ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК РОССИИ"',
            fz94id="18950000008",
            fz223id="",
            inn="7707083893",
            kpp="773601001",
            ogrn="1027700132195",
            draft_id="-1",
        )
        expected = (
            '18950000008:ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК РОССИИ"'
            "zZ18950000008zZ18950000008zZzZ7707083893zZ-1zZ773601001zZ1027700132195"
        )
        self.assertEqual(build_customer_filter_value(candidate), expected)


if __name__ == "__main__":
    unittest.main()
