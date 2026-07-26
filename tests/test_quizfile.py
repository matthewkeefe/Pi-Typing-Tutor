"""
Validates the shipped data/quiz.txt against the format documented in its
own header (issue #26).

Whisker Quiz isn't built yet, so this deliberately uses its own small
reference parser rather than importing one: the thing under test is the
data file, and it should stay verifiable no matter how the mode ends up
reading it. If the file and this parser ever disagree, the header is the
tie-breaker.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QUIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "quiz.txt")

MAX_Q = 72          # must fit an 80-col screen with room for a border
MAX_ANSWER_WORDS = 3


def parse(path):
    """(entries, malformed) per the documented format."""
    entries, malformed = [], []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "|" not in s:
                malformed.append((n, s))
                continue
            q, _, a = s.partition("|")
            q, a = q.strip(), a.strip()
            if not q or not a:
                malformed.append((n, s))
                continue
            alts = [x.strip().lower() for x in a.split(";") if x.strip()]
            if not alts:
                malformed.append((n, s))
                continue
            entries.append((q, alts))
    return entries, malformed


class TestQuizFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries, cls.malformed = parse(QUIZ)

    def test_the_file_exists_and_has_content(self):
        self.assertTrue(os.path.exists(QUIZ))
        self.assertGreaterEqual(len(self.entries), 40)

    def test_nothing_shipped_is_malformed(self):
        self.assertEqual(self.malformed, [])

    def test_no_duplicate_questions(self):
        seen = {}
        for q, _ in self.entries:
            seen.setdefault(q.lower(), 0)
            seen[q.lower()] += 1
        self.assertEqual([q for q, n in seen.items() if n > 1], [])

    def test_questions_fit_an_80_column_screen(self):
        for q, _ in self.entries:
            self.assertLessEqual(len(q), MAX_Q, q)

    def test_answers_stay_short_enough_to_type(self):
        """A long answer turns a quiz into a transcription drill."""
        for q, alts in self.entries:
            for a in alts:
                self.assertLessEqual(len(a.split()), MAX_ANSWER_WORDS,
                                     "%s -> %s" % (q, a))
                self.assertTrue(a, q)

    def test_everything_is_plain_ascii(self):
        """TERM=linux on a Pi -- no smart quotes, no accents."""
        for q, alts in self.entries:
            self.assertTrue(q.isascii(), q)
            for a in alts:
                self.assertTrue(a.isascii(), a)

    def test_answers_are_lowercase_and_trimmed_by_the_parser(self):
        for _, alts in self.entries:
            for a in alts:
                self.assertEqual(a, a.strip().lower())

    def test_numeric_questions_accept_both_digits_and_words(self):
        """
        Being marked wrong for typing "eight" instead of "8" is exactly the
        technicality that loses a 7-year-old, so the shipped set has to
        cover both. Checks the arithmetic questions specifically.
        """
        digits = {"2", "3", "4", "5", "6", "7", "8", "9", "10"}
        for q, alts in self.entries:
            numeric = [a for a in alts if a in digits]
            if not numeric:
                continue
            words = {"2": "two", "3": "three", "4": "four", "5": "five",
                     "6": "six", "7": "seven", "8": "eight", "9": "nine",
                     "10": "ten"}
            for d in numeric:
                self.assertIn(words[d], alts,
                              "%r accepts %s but not %s" % (q, d, words[d]))

    def test_a_decent_share_offer_alternates(self):
        with_alts = sum(1 for _, alts in self.entries if len(alts) > 1)
        self.assertGreater(with_alts, len(self.entries) * 0.2)

    def test_comments_and_blanks_are_ignored(self):
        with open(QUIZ, encoding="utf-8") as fh:
            raw = fh.readlines()
        self.assertGreater(sum(1 for l in raw if l.strip().startswith("#")), 10)
        self.assertGreater(len(raw), len(self.entries))

    def test_an_empty_or_missing_file_parses_to_nothing(self):
        """The mode hides itself on empty -- it must not raise first."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "q.txt")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("# only a comment\n\n")
            entries, malformed = parse(p)
            self.assertEqual(entries, [])
            self.assertEqual(malformed, [])

    def test_malformed_lines_are_reported_not_fatal(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "q.txt")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("no pipe here\n|no question\nq only|\ngood|fine\n")
            entries, malformed = parse(p)
            self.assertEqual(entries, [("good", ["fine"])])
            self.assertEqual(len(malformed), 3)


if __name__ == "__main__":
    unittest.main()
