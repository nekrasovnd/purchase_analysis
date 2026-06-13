import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from purchase_analysis.documents import extract_text_from_document, mask_pii


DOC_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Поставка офисных стульев</w:t></w:r></w:p>
    <w:p><w:r><w:t>Контакт: test@example.com, +7 999 123-45-67</w:t></w:r></w:p>
  </w:body>
</w:document>
"""


class DocumentExtractionTest(unittest.TestCase):
    def test_mask_pii(self) -> None:
        masked, count = mask_pii("mail a@b.ru phone +7 999 123-45-67")
        self.assertIn("[EMAIL]", masked)
        self.assertIn("[PHONE]", masked)
        self.assertEqual(count, 2)

    def test_extract_docx_text_masks_pii(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sample.docx"
            with ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", DOC_XML)
            result = extract_text_from_document(path)
            self.assertEqual(result.extraction_method, "docx_xml")
            self.assertIn("Поставка офисных стульев", result.text)
            self.assertIn("[EMAIL]", result.text)
            self.assertIn("[PHONE]", result.text)
            self.assertEqual(result.pii_findings_count, 2)


if __name__ == "__main__":
    unittest.main()
