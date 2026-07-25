"""
Algorithm: subsequence matching + dynamic-programming alignment (same family
as fzf's "V2" algorithm and VS Code's fuzzyScore). This is NOT edit-distance
(Levenshtein) matching — it answers a different question:

    "Can every character of the query be found, in order, somewhere in the
    target string?" — and if so, what's the *best-scoring* way to place them?

Scoring rewards:
  - matches right at word boundaries (after space/-/_/ or camelCase, e.g.
    "dhc" hitting the D, H, C in "Disable Headphone Configs")
  - consecutive runs of matched characters (a contiguous match beats a
    scattered one)
  - matches near the start of the string
and penalizes:
  - gaps between matched characters (the further apart, the bigger the hit)

Speed strategy:
  1. Per-item bonus arrays (word-boundary / camelCase positions) are computed
     ONCE when items are added, not on every keystroke.
  2. A cheap O(n) subsequence pre-check rejects non-matches before the O(n*m)
     DP alignment ever runs.
  3. IncrementalMatcher remembers the previous query's surviving candidates.
     If the new query extends the old one (user typed one more letter), it
     only re-scans that (usually much smaller) surviving set instead of the
     full list — this is the single biggest win for large lists.
"""

from __future__ import annotations

from dataclasses import dataclass

SCORE_MATCH = 16
SCORE_GAP_EXTENSION = 1
BONUS_BOUNDARY = 6  # right after a separator (space, -, _, /, .) or at start
BONUS_CAMEL_CASE = 3  # an uppercase letter following a lowercase letter
BONUS_CONSECUTIVE = 6  # this match immediately follows the previous match
BONUS_FIRST_CHAR_MULT = 2  # extra weight on where the query's 1st char lands
EXACT_MATCH = 20  # exact full string match

NEG_INF = float("-inf")


@dataclass
class BaseChoice:
    text: str


def _char_class(c: str) -> str:
    if c.isupper():
        return "upper"
    if c.islower() or c.isdigit():
        return "lower"
    return "other"  # spaces, punctuation, separators


def compute_bonuses(text: str) -> list[int]:
    """Precompute a per-character bonus array for `text`. Call this once per
    item, not per keystroke."""
    n = len(text)
    bonus = [0] * n
    prev_class = "other"
    for i, ch in enumerate(text):
        cls = _char_class(ch)
        b = 0
        if prev_class == "other" and cls != "other":
            b = BONUS_BOUNDARY
        elif prev_class == "lower" and cls == "upper":
            b = BONUS_CAMEL_CASE
        bonus[i] = b
        prev_class = cls
    if n:
        bonus[0] = max(bonus[0], BONUS_BOUNDARY)  # start of string is a boundary too
    return bonus


def _is_subsequence(query_lower: str, text_lower: str) -> bool:
    """Cheap O(n) reject before running the O(n*m) DP."""
    pos = 0
    for qc in query_lower:
        idx = text_lower.find(qc, pos)
        if idx == -1:
            return False
        pos = idx + 1
    return True


def fuzzy_match(
    query_lower: str,
    text: str,
    text_lower: str,
    bonus: list[int],
) -> tuple[int, list[int]] | None:
    """Return (score, matched_positions) or None if query isn't a subsequence
    of text. matched_positions are indexes into the ORIGINAL `text` you can
    use directly for bolding."""
    m, n = len(query_lower), len(text_lower)
    if m == 0:
        return 0, []
    if m > n:
        return None
    if not _is_subsequence(query_lower, text_lower):
        return None

    # dp[j] = best score for the alignment of query[0..i] that ends with
    # query[i] matched at text position j. back[j] = the text position where
    # query[i-1] was matched in that best alignment (for traceback).
    dp_prev = [NEG_INF] * n
    backpointers: list[list[int]] = []

    for i in range(m):
        qc = query_lower[i]
        dp_curr = [NEG_INF] * n
        back_curr = [-1] * n

        if i == 0:
            for j in range(n):
                if text_lower[j] == qc:
                    dp_curr[j] = SCORE_MATCH + bonus[j] * BONUS_FIRST_CHAR_MULT
        else:
            running_best = NEG_INF
            running_pos = -1
            for j in range(n):
                if j > 0:
                    candidate = dp_prev[j - 1]
                    decayed = running_best - SCORE_GAP_EXTENSION
                    if candidate > decayed:
                        running_best = candidate
                        running_pos = j - 1
                    else:
                        running_best = decayed
                if text_lower[j] == qc and running_best != NEG_INF:
                    consecutive = running_pos == j - 1
                    dp_curr[j] = (
                        running_best
                        + SCORE_MATCH
                        + bonus[j]
                        + (BONUS_CONSECUTIVE if consecutive else 0)
                    )
                    back_curr[j] = running_pos

        backpointers.append(back_curr)
        dp_prev = dp_curr

    best_score, best_j = NEG_INF, -1
    for j, s in enumerate(dp_prev):
        if s > best_score:
            best_score, best_j = s, j
    if best_j == -1:
        return None

    positions = [0] * m
    j = best_j
    for i in range(m - 1, -1, -1):
        positions[i] = j
        j = backpointers[i][j]

    # give score if full match
    if query_lower == text_lower:
        best_score += EXACT_MATCH

    return int(best_score), positions


@dataclass
class Match[T_CHOICE: BaseChoice]:
    index: int
    choice: T_CHOICE
    score: int
    positions: list[int]

    def highlighted(self, open_tag: str = "**", close_tag: str = "**") -> str:
        """Wrap matched characters, e.g. for bolding in a UI."""
        pos = set(self.positions)
        out: list[str] = []
        for i, ch in enumerate(self.choice.text):
            out.append(f"{open_tag}{ch}{close_tag}" if i in pos else ch)
        return "".join(out)


class IncrementalMatcher[T_CHOICE: BaseChoice]:
    """Holds a fixed choice list and serves fast, incremental fuzzy search as
    the user types letter by letter — call `.search()` on every keystroke."""

    def __init__(self, choices: list[T_CHOICE], limit: int = 20):
        self.choices: list[T_CHOICE]
        self._lower: list[str]
        self._bonus: list[list[int]]
        self._last_query: str
        self._candidates: list[int]
        """Survivors of last search"""

        self.limit: int = limit

        self.update_choices(choices)

    def update_choices(self, choices: list[T_CHOICE]) -> None:
        """Replace the dataset (e.g. app list changed) and reset state."""
        self.choices = choices
        self._lower = [c.text.lower() for c in self.choices]
        self._bonus = [compute_bonuses(c.text) for c in self.choices]
        self._last_query = ""
        self._candidates = list(range(len(self.choices)))

    def search(self, query: str) -> list[Match[T_CHOICE]]:
        if not query:
            self._last_query = ""
            self._candidates = list(range(len(self.choices)))
            return [
                Match(i, self.choices[i], 0, []) for i in range(min(self.limit, len(self.choices)))
            ]

        query_lower = query.lower()

        # KEY OPTIMIZATION: if the new query extends the previous one,
        # only re-scan indexes that survived the previous (shorter) query —
        # subsequence containment only shrinks as the query grows, so any
        # index that already failed can never start matching again.
        if self._last_query and query.startswith(self._last_query):
            pool = self._candidates
        else:
            pool = range(len(self.choices))

        results: list[Match[T_CHOICE]] = []
        survivors: list[int] = []
        for i in pool:
            m = fuzzy_match(query_lower, self.choices[i].text, self._lower[i], self._bonus[i])
            if m is not None:
                score, positions = m
                survivors.append(i)
                results.append(Match(i, self.choices[i], score, positions))

        self._candidates = survivors
        self._last_query = query
        results.sort(key=lambda r: -r.score)
        return results[: self.limit]
