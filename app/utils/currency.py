"""Currency and pricing utilities.

All monetary calculations use Decimal to avoid floating-point errors.
"""

from decimal import ROUND_HALF_UP, Decimal


def format_currency(amount: Decimal | float | int) -> Decimal:
    """Standardize currency to 2 decimal places."""
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_tax(
    amount: Decimal, tax_rate: Decimal = Decimal("0.18")
) -> Decimal:
    """Calculate tax for a given amount (default 18% GST).

    Args:
        amount: Taxable amount.
        tax_rate: Tax rate as a decimal (e.g., 0.18 for 18%).
    """
    tax = amount * tax_rate
    return format_currency(tax)


def calculate_total(
    subtotal: Decimal,
    discount: Decimal = Decimal("0"),
    shipping: Decimal = Decimal("0"),
) -> Decimal:
    """Calculate total order value including tax.

    Total = (subtotal - discount) + GST on (subtotal - discount) + shipping.
    """
    taxable = subtotal - discount
    tax = calculate_tax(taxable)
    total = taxable + tax + shipping
    return format_currency(total)
