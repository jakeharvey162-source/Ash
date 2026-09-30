import unittest
from unittest.mock import patch

from site_reference import _validate_public_url, _tokens


class SiteReferenceTests(unittest.TestCase):
    def test_rejects_localhost(self):
        with self.assertRaises(ValueError):
            _validate_public_url("http://localhost:8080")

    def test_rejects_private_ip(self):
        with self.assertRaises(ValueError):
            _validate_public_url("http://127.0.0.1")

    def test_accepts_public_https_hostname(self):
        with patch("site_reference.socket.getaddrinfo", return_value=[(2,1,6,"",("93.184.216.34",443))]):
            self.assertEqual(_validate_public_url("https://example.com/path"), "https://example.com/path")

    def test_extracts_design_tokens(self):
        colors, fonts, radii, spacing = _tokens("body{color:#112233;font-family:Inter,sans-serif;padding:24px}.card{border-radius:18px;gap:12px}")
        self.assertIn("#112233", colors)
        self.assertTrue(any("Inter" in x for x in fonts))
        self.assertIn("18px", radii)
        self.assertTrue(any(x in {"24px","12px"} for x in spacing))


if __name__ == "__main__":
    unittest.main()
