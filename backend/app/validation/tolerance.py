"""Configurable tolerance policy (absolute AND percentage). Editable via Settings API."""
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class TolerancePolicy:
    abs_amount: Decimal = Decimal("1.00")      # rounding slack, in invoice currency
    pct_amount: Decimal = Decimal("0.5")       # % of expected value
    po_overrun_abs: Decimal = Decimal("0.00")  # allowed invoicing beyond PO remaining
    po_overrun_pct: Decimal = Decimal("2.0")
    price_variance_pct: Decimal = Decimal("1.0")  # unit price vs PO
    min_field_confidence: Decimal = Decimal("0.75")

    def within(self, expected: Decimal, actual: Decimal, abs_t=None, pct_t=None) -> bool:
        """True if |actual-expected| <= max(abs, pct% of expected). Either limit suffices."""
        abs_t = self.abs_amount if abs_t is None else abs_t
        pct_t = self.pct_amount if pct_t is None else pct_t
        diff = abs(actual - expected)
        return diff <= max(abs_t, abs(expected) * pct_t / Decimal(100))
