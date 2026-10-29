"""Tests for tickets.py. Run from the campus_problem folder:

    python3 -m unittest -v
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import requests

import tickets

VALID = {"category": "Network", "urgency": "High", "steps": ["a", "b", "c", "d"]}


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def gemini_ok(content):
    return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": content}]}}]})


class HeuristicTests(unittest.TestCase):
    def test_network(self):
        result = tickets.heuristic_analysis("wifi", "wifi is slow")
        self.assertEqual((result["category"], result["urgency"]), ("Network", "Medium"))
        self.assertEqual(len(result["steps"]), 4)

    def test_authentication(self):
        result = tickets.heuristic_analysis("Login", "cannot sign in to my account")
        self.assertEqual((result["category"], result["urgency"]), ("Authentication", "High"))

    def test_hardware(self):
        self.assertEqual(tickets.heuristic_analysis("printer", "jammed")["category"], "Hardware")

    def test_default(self):
        result = tickets.heuristic_analysis("odd", "something strange")
        self.assertEqual((result["category"], result["urgency"]), ("General Hardware/Software", "Low"))


class ValidationTests(unittest.TestCase):
    def test_normalises_urgency_case(self):
        self.assertEqual(tickets.validate_analysis({**VALID, "urgency": "high"})["urgency"], "High")

    def test_rejects_bad_urgency(self):
        with self.assertRaises(ValueError):
            tickets.validate_analysis({**VALID, "urgency": "Urgent!!"})

    def test_rejects_non_dict_and_missing_fields(self):
        for bad in ([], "text", None, {"category": "x"}, {**VALID, "steps": "not a list"},
                    {**VALID, "steps": []}, {**VALID, "category": ""}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                tickets.validate_analysis(bad)

    def test_strips_terminal_escapes(self):
        result = tickets.validate_analysis({**VALID, "steps": ["\x1b[31mred\x1b[0m", "ok", "ok2"]})
        self.assertNotIn("\x1b", "".join(result["steps"]))

    def test_extract_json_variants(self):
        self.assertEqual(tickets.extract_json('{"a": 1}'), {"a": 1})
        self.assertEqual(tickets.extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(tickets.extract_json('Sure! {"a": 1} hope that helps'), {"a": 1})
        with self.assertRaises(ValueError):
            tickets.extract_json("no json here")


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "tickets.json")
        patcher = mock.patch.object(tickets, "TICKET_FILE", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_missing_file_is_empty_list(self):
        self.assertEqual(tickets.load_tickets(), [])

    def test_add_and_reload(self):
        ticket_id = tickets.add_ticket({"title": "t"})
        loaded = tickets.load_tickets()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["id"], ticket_id)
        self.assertEqual(len(str(ticket_id)), 10)

    def test_no_temp_files_left_behind(self):
        tickets.add_ticket({"title": "t"})
        leftovers = [n for n in os.listdir(self.tmp.name) if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_empty_file_is_ok(self):
        open(self.path, "w").close()
        self.assertEqual(tickets.load_tickets(), [])

    def test_corrupt_file_is_quarantined(self):
        with open(self.path, "w") as f:
            f.write("{not valid json")
        with quiet():
            self.assertEqual(tickets.load_tickets(), [])
        names = os.listdir(self.tmp.name)
        self.assertTrue(any(".corrupt-" in n for n in names))
        self.assertFalse(os.path.exists(self.path))

    def test_wrong_shape_is_quarantined(self):
        with open(self.path, "w") as f:
            json.dump({"oops": 1}, f)
        with quiet():
            self.assertEqual(tickets.load_tickets(), [])

    def test_ids_are_unique(self):
        ids = {tickets.add_ticket({"title": str(i)}) for i in range(25)}
        self.assertEqual(len(ids), 25)


class CascadeTests(unittest.TestCase):
    def run_cascade(self, choice, gemini, openrouter):
        with mock.patch.object(tickets, "analyze_with_gemini", gemini), \
             mock.patch.object(tickets, "analyze_with_openrouter", openrouter), quiet():
            return tickets.analyze_ticket("wifi", "wifi is slow", choice)

    def test_gemini_success_skips_openrouter(self):
        gemini = mock.Mock(return_value=VALID)
        openrouter = mock.Mock(return_value=VALID)
        result, source = self.run_cascade("3", gemini, openrouter)
        self.assertEqual(source, "gemini")
        openrouter.assert_not_called()

    def test_gemini_fails_openrouter_answers(self):
        gemini = mock.Mock(side_effect=tickets.ProviderError("503"))
        openrouter = mock.Mock(return_value=VALID)
        _, source = self.run_cascade("3", gemini, openrouter)
        self.assertEqual(source, "openrouter")
        gemini.assert_called_once()
        openrouter.assert_called_once()

    def test_malformed_output_moves_to_next_tier(self):
        gemini = mock.Mock(return_value={**VALID, "urgency": "Urgent!!"})
        openrouter = mock.Mock(return_value=VALID)
        _, source = self.run_cascade("3", gemini, openrouter)
        self.assertEqual(source, "openrouter")

    def test_everything_fails_uses_heuristic(self):
        gemini = mock.Mock(side_effect=tickets.ProviderError("down"))
        openrouter = mock.Mock(side_effect=tickets.ProviderError("down"))
        result, source = self.run_cascade("3", gemini, openrouter)
        self.assertEqual(source, "heuristic")
        self.assertEqual(result["category"], "Network")

    def test_manual_gemini_does_not_try_openrouter(self):
        gemini = mock.Mock(side_effect=tickets.ProviderError("down"))
        openrouter = mock.Mock(return_value=VALID)
        _, source = self.run_cascade("1", gemini, openrouter)
        self.assertEqual(source, "heuristic")
        openrouter.assert_not_called()

    def test_manual_openrouter_does_not_try_gemini(self):
        gemini = mock.Mock(return_value=VALID)
        openrouter = mock.Mock(return_value=VALID)
        _, source = self.run_cascade("2", gemini, openrouter)
        self.assertEqual(source, "openrouter")
        gemini.assert_not_called()


@mock.patch.dict(os.environ, {"GEMINI_API_KEY": "secret-test-key"})
class GeminiTests(unittest.TestCase):
    def test_retries_503_then_succeeds_and_key_stays_out_of_url(self):
        responses = [FakeResponse(503, text="busy"), FakeResponse(503, text="busy"),
                     gemini_ok(json.dumps(VALID))]
        with mock.patch.object(tickets.requests, "post", side_effect=responses) as post, \
             mock.patch.object(tickets.time, "sleep") as sleep, quiet():
            result = tickets.analyze_with_gemini("wifi slow")
        self.assertEqual(result, VALID)
        self.assertEqual(post.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        first = post.call_args_list[0]
        self.assertNotIn("secret-test-key", first.args[0])
        self.assertNotIn("key=", first.args[0])
        self.assertEqual(first.kwargs["headers"]["x-goog-api-key"], "secret-test-key")

    def test_gives_up_after_max_attempts(self):
        with mock.patch.object(tickets.requests, "post",
                               return_value=FakeResponse(503, text="busy")) as post, \
             mock.patch.object(tickets.time, "sleep"), quiet():
            with self.assertRaises(tickets.ProviderError):
                tickets.analyze_with_gemini("x")
        self.assertEqual(post.call_count, tickets.GEMINI_ATTEMPTS)

    def test_timeout_is_reported_without_retrying(self):
        with mock.patch.object(tickets.requests, "post",
                               side_effect=requests.exceptions.Timeout()) as post:
            with self.assertRaisesRegex(tickets.ProviderError, "timed out"):
                tickets.analyze_with_gemini("x")
        self.assertEqual(post.call_count, 1)

    def test_missing_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            with self.assertRaisesRegex(tickets.ProviderError, "not set"):
                tickets.analyze_with_gemini("x")


class MiscTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"GEMINI_API_KEY": "secret-test-key"})
    def test_redact(self):
        self.assertEqual(tickets.redact("boom secret-test-key boom"), "boom *** boom")

    def test_clean_text(self):
        self.assertEqual(tickets.clean_text("a\nb\t\x1b[31mc"), "a b [31mc")
        self.assertEqual(len(tickets.clean_text("x" * 500, 50)), 50)

    def test_env_file_does_not_override_existing(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, ".env")
            with open(path, "w") as f:
                f.write('# comment\nCF_TEST_A="from-file"\nexport CF_TEST_B=from-file\nCF_TEST_C=from-file\n')
            with mock.patch.dict(os.environ, {"CF_TEST_C": "already-set"}):
                os.environ.pop("CF_TEST_A", None)
                os.environ.pop("CF_TEST_B", None)
                tickets.load_env_file(path)
                self.assertEqual(os.environ["CF_TEST_A"], "from-file")
                self.assertEqual(os.environ["CF_TEST_B"], "from-file")
                self.assertEqual(os.environ["CF_TEST_C"], "already-set")
                os.environ.pop("CF_TEST_A", None)
                os.environ.pop("CF_TEST_B", None)


if __name__ == "__main__":
    unittest.main()