"""Small, dependency-free number/text-formatting helpers shared by the renderers."""

import re


def amount_already_mentioned(text: str, amount: float) -> bool:
    """True if `amount`'s digit representation already appears in `text`.

    A cheap, language-agnostic heuristic (works the same for Russian,
    English, Kazakh action text): only catches the amount when the model
    wrote it in the same decimal notation the schema uses (e.g. "2"), not
    other notations such as fractions ("1/2") - a known limitation, see
    REPORT.md / docs/recipe_contract.md.
    """
    amount_str = format_amount(amount)
    return re.search(rf"(?<!\d){re.escape(amount_str)}(?!\d)", text) is not None


def strip_trailing_period(text: str) -> str:
    """Drop a sentence-final period the model already wrote into `action`.

    Real model output sometimes writes a complete, already-punctuated
    sentence for `action` even though the composer appends more clauses
    after it; without this, sentences ended up with a stray mid-sentence
    period (e.g. "...на среднем огне. 1 минуту."). The composer always
    owns final punctuation, so any trailing period is redundant.
    """
    return text.rstrip().rstrip(".").rstrip()


def format_amount(amount: float) -> str:
    """Render a quantity without a spurious trailing '.0'."""
    if amount == int(amount):
        return str(int(amount))
    return str(amount)


def plural_form(n: float, forms: tuple[str, str, str]) -> str:
    """Pick the Russian plural form for `n` from (one, few, many).

    Standard Russian counting-noun agreement:
    - non-integer n (e.g. 1.5) always takes the "few" (genitive singular) slot,
      e.g. "1.5 литра", never "1.5 литр"/"1.5 литров".
    - n ending in 11-14 (mod 100) takes "many", regardless of the last digit.
    - n ending in 1 (but not 11) takes "one".
    - n ending in 2-4 (but not 12-14) takes "few".
    - everything else takes "many".
    """
    if n != int(n):
        return forms[1]
    n_int = abs(int(n))
    if n_int % 100 in (11, 12, 13, 14):
        return forms[2]
    last_digit = n_int % 10
    if last_digit == 1:
        return forms[0]
    if 2 <= last_digit <= 4:
        return forms[1]
    return forms[2]
