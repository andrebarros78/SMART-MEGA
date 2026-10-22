"""Fail-closed independent public corroboration; never API/official proof."""
from __future__ import annotations
import hashlib
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
import smart_public_result_capture as capture


HTML_A = b'''<html><head><title>Resultado da Mega Sena 3072: ter\xc3\xa7a-feira 20/10/2026</title></head><body><ul>
<li class="ball">2</li><li class="ball">6</li><li class="ball">9</li>
<li class="ball">16</li><li class="ball">31</li><li class="ball">40</li></ul></body></html>'''
HTML_B = b'''<html><head><title>Resultado da Mega-Sena 3072 \xe2\x80\x94 20/10/2026</title></head><body>
<div class="balls " aria-label="N\xc3\xbameros sorteados">
<span class="ball">02</span><span class="ball">06</span><span class="ball">09</span>
<span class="ball">16</span><span class="ball">31</span><span class="ball">40</span></div></body></html>'''


def client(url):
    if "megasena.com" in url and "resultadosdasloterias" not in url:
        return HTML_A, url
    return HTML_B, url


class TestCapture(unittest.TestCase):
    def test_two_sources_agree_and_result_has_low_authority(self):
        record = capture.capture(3072, fetcher=client,
                                 clock=datetime(2026, 10, 21, 12, tzinfo=timezone.utc))
        self.assertEqual(record["schema"], "SMART_PUBLIC_CORROBORATED_RESULT_BATCH_1")
        self.assertEqual(record["authority"], "TWO_PUBLIC_SOURCES_NOT_CAIXA_API_VERIFIED")
        self.assertFalse(record["raw_api_independently_verified"])
        self.assertFalse(record["scientific_certification_authorized"])
        self.assertEqual(record["results"][0]["listaDezenas"], ["02","06","09","16","31","40"])
        self.assertEqual(len(record["providers"]), 2)
        self.assertEqual(record["sha256"], capture.self_hash(record))

    def test_disagreement_fails_closed(self):
        def different(url):
            if "megasena.com" in url and "resultadosdasloterias" not in url:
                return HTML_A, url
            return HTML_B.replace(b'>40</span>', b'>41</span>'), url
        with self.assertRaisesRegex(ValueError, "disagree"):
            capture.capture(3072, fetcher=different)

    def test_future_result_forbidden(self):
        with self.assertRaisesRegex(ValueError, "future"):
            capture.capture(3072, fetcher=client,
                            clock=datetime(2026,10,19,11,tzinfo=timezone.utc))

    def test_redirect_to_other_host_forbidden(self):
        with self.assertRaisesRegex(ValueError, "redirect"):
            capture.capture(3072, fetcher=lambda u:(HTML_A,u.replace("https://","http://")))

    def test_stale_title_or_invalid_six_forbidden(self):
        with self.assertRaises(ValueError):
            capture.capture(3072, fetcher=lambda u:(HTML_A.replace(b"3072",b"3071"),u))

    def test_no_network_implicit_in_model_cycle(self):
        source = (Path(__file__).resolve().parent / "smart_cycle_completion.py").read_text()
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("urlopen(", source)

if __name__ == "__main__":
    unittest.main()
