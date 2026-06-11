"""Unit tests for currency utilities."""

from decimal import Decimal

import pytest

from app.utils.currency import calculate_tax, calculate_total, format_currency


class TestFormatCurrency:
    def test_rounds_to_two_decimal_places(self) -> None:
        assert format_currency(Decimal("10.555")) == Decimal("10.56")

    def test_accepts_float(self) -> None:
        assert format_currency(10.5) == Decimal("10.50")

    def test_accepts_int(self) -> None:
        assert format_currency(100) == Decimal("100.00")

    def test_zero(self) -> None:
        assert format_currency(0) == Decimal("0.00")


class TestCalculateTax:
    def test_default_gst_rate(self) -> None:
        tax = calculate_tax(Decimal("1000.00"))
        assert tax == Decimal("180.00")

    def test_custom_rate(self) -> None:
        tax = calculate_tax(Decimal("1000.00"), Decimal("0.05"))
        assert tax == Decimal("50.00")

    def test_zero_amount(self) -> None:
        tax = calculate_tax(Decimal("0.00"))
        assert tax == Decimal("0.00")


class TestCalculateTotal:
    def test_basic_total(self) -> None:
        total = calculate_total(Decimal("1000.00"))
        # 1000 + 180 (18% GST) = 1180
        assert total == Decimal("1180.00")

    def test_with_discount(self) -> None:
        total = calculate_total(Decimal("1000.00"), discount=Decimal("100.00"))
        # (1000 - 100) + 162 (18% of 900) = 1062
        assert total == Decimal("1062.00")

    def test_with_shipping(self) -> None:
        total = calculate_total(Decimal("400.00"), shipping=Decimal("50.00"))
        # 400 + 72 (18% GST) + 50 = 522
        assert total == Decimal("522.00")

    def test_with_discount_and_shipping(self) -> None:
        total = calculate_total(
            Decimal("1000.00"),
            discount=Decimal("200.00"),
            shipping=Decimal("0.00"),
        )
        # (1000 - 200) + 144 (18% of 800) = 944
        assert total == Decimal("944.00")
