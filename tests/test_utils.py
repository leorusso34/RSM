"""Suite di test unitari focalizzata sugli edge case per src.utils."""

from decimal import Decimal

import pytest

from src.utils import (
    calculate_profit,
    cents_to_money,
    format_month_label,
    money,
    money_to_cents,
    normalize_header,
    parse_date,
    parse_int,
    parse_money,
)


class TestParseMoney:
    """Test ed edge case per la funzione parse_money."""

    @pytest.mark.parametrize(
        ("input_val", "expected"),
        [
            ("12.50", Decimal("12.50")),
            ("12,50", Decimal("12.50")),
            ("€ 1.250,00", Decimal("1250.00")),
            ("£ 99,99", Decimal("99.99")),
            ("1.000", Decimal("1000.00")),
            ("1.234", Decimal("1234.00")),
            ("0", Decimal("0.00")),
            ("0,00", Decimal("0.00")),
            ("  50  ", Decimal("50.00")),
            (100, Decimal("100.00")),
            (49.99, Decimal("49.99")),
            (Decimal("75.25"), Decimal("75.25")),
        ],
    )
    def test_parse_money_valid_formats(self, input_val, expected):
        assert parse_money(input_val) == expected

    @pytest.mark.parametrize(
        "empty_val",
        [None, "", "   ", "\t\n"],
    )
    def test_parse_money_allow_empty(self, empty_val):
        assert parse_money(empty_val, allow_empty=True) is None

    @pytest.mark.parametrize(
        "empty_val",
        [None, "", "   "],
    )
    def test_parse_money_disallow_empty_raises(self, empty_val):
        with pytest.raises(ValueError, match="Valore monetario obbligatorio"):
            parse_money(empty_val, allow_empty=False)

    @pytest.mark.parametrize(
        "invalid_val",
        [
            "-50",
            "-12,50",
            "€ -10",
        ],
    )
    def test_parse_money_negative_raises(self, invalid_val):
        with pytest.raises(ValueError, match="L'importo non può essere negativo"):
            parse_money(invalid_val)

    @pytest.mark.parametrize(
        "invalid_val",
        [
            "abc",
            "12,345",  # 3 decimali con virgola (non consentiti)
            "12.3456",  # Più di due decimali o punto migliaia errato
            "€ 10..50",
            "---",
            "...",
            ",,,",
            "12,34,56",
        ],
    )
    def test_parse_money_invalid_syntax_raises(self, invalid_val):
        with pytest.raises(ValueError, match="Inserisci un importo valido"):
            parse_money(invalid_val)


class TestMoneyAndCentsConversion:
    """Test per conversioni centesimi SQLite e formattazione monetaria."""

    @pytest.mark.parametrize(
        ("amount", "cents"),
        [
            (Decimal("12.50"), 1250),
            (Decimal("0.00"), 0),
            (Decimal("1000.00"), 100000),
            ("99.99", 9999),
            (15, 1500),
            (None, None),
        ],
    )
    def test_money_to_cents(self, amount, cents):
        assert money_to_cents(amount) == cents

    @pytest.mark.parametrize(
        ("cents", "amount"),
        [
            (1250, Decimal("12.50")),
            (0, Decimal("0.00")),
            (100000, Decimal("1000.00")),
            (None, None),
        ],
    )
    def test_cents_to_money(self, cents, amount):
        assert cents_to_money(cents) == amount

    @pytest.mark.parametrize(
        ("input_val", "expected_str"),
        [
            (Decimal("1250.50"), "€ 1.250,50"),
            (0, "€ 0,00"),
            (None, "€ 0,00"),
            ("invalid", "€ 0,00"),
            (1000000, "€ 1.000.000,00"),
        ],
    )
    def test_money_formatter(self, input_val, expected_str):
        assert money(input_val) == expected_str


class TestParseInt:
    """Test ed edge case per la funzione parse_int."""

    @pytest.mark.parametrize(
        ("input_val", "expected"),
        [
            ("1", 1),
            ("10", 10),
            (5, 5),
            ("  42  ", 42),
        ],
    )
    def test_parse_int_valid(self, input_val, expected):
        assert parse_int(input_val) == expected

    @pytest.mark.parametrize(
        ("empty_val", "default_val"),
        [
            (None, 1),
            ("", 2),
            ("   ", 5),
        ],
    )
    def test_parse_int_empty_defaults(self, empty_val, default_val):
        assert parse_int(empty_val, default=default_val) == default_val

    @pytest.mark.parametrize(
        "invalid_val",
        [
            "0",
            "-1",
            "-100",
            "abc",
            "1.5",
            "2x",
        ],
    )
    def test_parse_int_invalid_raises(self, invalid_val):
        with pytest.raises(ValueError, match="La quantità deve essere"):
            parse_int(invalid_val)


class TestParseDate:
    """Test ed edge case per la funzione parse_date."""

    @pytest.mark.parametrize(
        ("input_date", "expected_iso"),
        [
            ("2026-10-23", "2026-10-23"),
            ("23/10/2026", "2026-10-23"),
            ("23-10-2026", "2026-10-23"),
            ("2026/10/23", "2026-10-23"),
            ("23.10.2026", "2026-10-23"),
        ],
    )
    def test_parse_date_valid_formats(self, input_date, expected_iso):
        assert parse_date(input_date) == expected_iso

    def test_parse_date_empty_handling(self):
        assert parse_date("", allow_empty=True) == ""
        assert parse_date(None, allow_empty=True) == ""
        with pytest.raises(ValueError, match="Formato data non supportato"):
            parse_date("", allow_empty=False)

    @pytest.mark.parametrize(
        "invalid_date",
        [
            "not-a-date",
            "2026-02-30",
            "32/01/2026",
            "2026-13-01",
        ],
    )
    def test_parse_date_invalid_raises(self, invalid_date):
        with pytest.raises(ValueError, match="Formato data non supportato"):
            parse_date(invalid_date)


class TestFormatMonthLabel:
    """Test per l'etichettatura compatta del mese in italiano."""

    @pytest.mark.parametrize(
        ("input_val", "expected"),
        [
            ("2026-10", "OTT '26"),
            ("2026-01-15", "GEN '26"),
            ("2025-08-30", "AGO '25"),
            ("", ""),
            (None, ""),
            ("GEN", "GEN"),
        ],
    )
    def test_format_month_label(self, input_val, expected):
        assert format_month_label(input_val) == expected


class TestCalculateProfit:
    """Test per il calcolo di profitto e ROI con diverse combinazioni e edge case."""

    def test_single_quantity_profit(self):
        # Acquisto 100€, Vendita 150€, Fees 15€, Qty 1
        profit, roi = calculate_profit(Decimal("100.00"), Decimal("150.00"), Decimal("15.00"), 1)
        assert profit == Decimal("35.00")
        assert roi == Decimal("35.00")

    def test_multi_quantity_profit(self):
        # Acquisto 50€/pz, Vendita totale 200€, Fees 10€, Qty 3 -> Costo tot 150€, Utile 40€
        profit, roi = calculate_profit(Decimal("50.00"), Decimal("200.00"), Decimal("10.00"), 3)
        assert profit == Decimal("40.00")
        assert roi == Decimal("26.67")

    def test_zero_purchase_cost_gift(self):
        # Omaggio a costo 0, Vendita 50€, Fees 2€
        profit, roi = calculate_profit(Decimal("0.00"), Decimal("50.00"), Decimal("2.00"), 1)
        assert profit == Decimal("48.00")
        assert roi == Decimal("0.00")

    def test_loss_scenario(self):
        # Acquisto 100€, Vendita 80€, Fees 5€ -> Utile -25€
        profit, roi = calculate_profit(Decimal("100.00"), Decimal("80.00"), Decimal("5.00"), 1)
        assert profit == Decimal("-25.00")
        assert roi == Decimal("-25.00")

    def test_unsold_item_returns_zero(self):
        profit, roi = calculate_profit(Decimal("100.00"), None, Decimal("0.00"), 1)
        assert profit == Decimal("0.00")
        assert roi == Decimal("0.00")


class TestNormalizeHeader:
    """Test per normalizzazione di stringhe di intestazione."""

    @pytest.mark.parametrize(
        ("input_str", "expected"),
        [
            ("  Prezzo_Acquisto  ", "PREZZO ACQUISTO"),
            ("data   vendita\t", "DATA VENDITA"),
            (None, ""),
            ("", ""),
        ],
    )
    def test_normalize_header(self, input_str, expected):
        assert normalize_header(input_str) == expected
