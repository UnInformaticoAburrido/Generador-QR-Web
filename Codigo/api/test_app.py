"""Pruebas de contrato, límites y lectura real con un decodificador independiente."""

import base64
from io import BytesIO
import json
import unittest

from PIL import Image
import zxingcpp

from app import app


class QRTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def generate(self, text):
        return self.client.post("/api/qr", json={"text": text})

    def assert_round_trip(self, text):
        response = self.generate(text)
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        png = base64.b64decode(data["png"].split(",", 1)[1])
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        result = zxingcpp.read_barcode(Image.open(BytesIO(png)))
        self.assertIsNotNone(result, "El PNG debe poder leerse como un QR")
        self.assertEqual(result.text, text)
        svg = base64.b64decode(data["svg"].split(",", 1)[1])
        self.assertIn(b"<svg", svg)
        self.assertEqual(data["characters"], len(text))
        self.assertEqual(data["bytes"], len(text.encode("utf-8")))
        self.assertEqual(data["error_correction"], "L")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        return data

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_text_round_trip(self):
        for text in ["https://example.com/qr?x=1&y=2", "0000123", "  Hola\nMundo  ", "   ", "¡Hola, España! 👋 中文 العربية", '<script>alert("hola")</script>']:
            with self.subTest(text=text):
                self.assert_round_trip(text)

    def test_exact_capacity(self):
        for character, limit, mode in [("1", 7089, "numeric"), ("A", 4296, "alphanumeric"), ("a", 2953, "byte"), ("é", 1476, "byte"), ("😀", 738, "byte")]:
            with self.subTest(mode=mode, character=character):
                data = self.assert_round_trip(character * limit)
                self.assertEqual(data["version"], 40)
                self.assertEqual(data["mode"], mode)
                overflow = self.generate(character * (limit + 1))
                self.assertEqual(overflow.status_code, 422)
                self.assertIn("no cabe", overflow.get_json()["error"])

    def test_invalid_input(self):
        for payload in [{}, {"text": None}, {"text": 123}, {"text": []}, {"text": ""}, [], "hola"]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/api/qr", json=payload).status_code, 400)
        self.assertEqual(self.client.post("/api/qr", data="hola").status_code, 415)
        self.assertEqual(self.client.post("/api/qr", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.generate("\ud800").status_code, 400)

    def test_oversized_request(self):
        response = self.generate("a" * (128 * 1024))
        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.get_json())

    def test_escaped_digits_at_capacity(self):
        payload = '{"text":"' + "\\u0031" * 7089 + '"}'
        self.assertEqual(len(json.loads(payload)["text"]), 7089)
        self.assertEqual(self.client.post("/api/qr", data=payload, content_type="application/json").status_code, 200)


if __name__ == "__main__":
    unittest.main()
