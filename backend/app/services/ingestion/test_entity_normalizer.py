"""
app/services/ingestion/test_entity_normalizer.py

Unit tests for Entity and Description Normalization Engine.
"""

import unittest

from app.services.ingestion.entity_normalizer import (
    EntityNormalizer,
    normalize_transaction_entity,
    extract_clean_entity,
)


class TestEntityNormalizer(unittest.TestCase):
    """Test suite for description cleaning and entity extraction."""

    def setUp(self):
        self.normalizer = EntityNormalizer()

    def test_empty_and_none_descriptions(self):
        """Empty or None input safely returns default structure."""
        res_none = self.normalizer.normalize(None)
        self.assertEqual(res_none.normalized_entity, "UNKNOWN")
        self.assertEqual(res_none.channel, "UNKNOWN")
        self.assertIsNone(res_none.reference_id)
        self.assertIsNone(res_none.vpa)

        res_empty = self.normalizer.normalize("")
        self.assertEqual(res_empty.normalized_entity, "UNKNOWN")
        self.assertEqual(res_empty.clean_description, "")

    def test_upi_swiggy_cleaning_and_entity(self):
        """UPI narration with UTR, merchant, and VPA is correctly parsed."""
        raw = "UPI/512391203912/Swiggy Bangalore/swiggy@icici/Payment"
        res = self.normalizer.normalize(raw)

        self.assertEqual(res.channel, "UPI")
        self.assertEqual(res.reference_id, "512391203912")
        self.assertEqual(res.vpa, "swiggy@icici")
        self.assertEqual(res.normalized_entity, "Swiggy")
        self.assertEqual(res.counterparty_type, "MERCHANT")
        self.assertNotIn("512391203912", res.clean_description)
        self.assertNotIn("swiggy@icici", res.clean_description)

    def test_neft_corporate_salary(self):
        """NEFT transaction extracts Infosys and CORPORATE counterparty type."""
        raw = "NEFT-N123456789012-INFOSYS TECHNOLOGIES-SALARY APR 2026"
        res = self.normalizer.normalize(raw)

        self.assertEqual(res.channel, "NEFT")
        self.assertEqual(res.reference_id, "123456789012")
        self.assertEqual(res.normalized_entity, "Infosys")
        self.assertEqual(res.counterparty_type, "CORPORATE")

    def test_rtgs_reliance_industries(self):
        """RTGS narration with IFSC code strips code and maps to Reliance Industries."""
        raw = "RTGS/YESB0000001/RELIANCE INDUSTRIES LTD/INV9912"
        res = self.normalizer.normalize(raw)

        self.assertEqual(res.channel, "RTGS")
        self.assertEqual(res.normalized_entity, "Reliance Industries")
        self.assertEqual(res.counterparty_type, "CORPORATE")
        self.assertNotIn("YESB0000001", res.clean_description)

    def test_pos_card_mask_stripped(self):
        """POS transaction strips card mask numbers and maps Starbucks."""
        raw = "POS 412345XXXXXX1234 STARBUCKS COFFEE MUMBAI IN"
        res = self.normalizer.normalize(raw)

        self.assertEqual(res.channel, "POS")
        self.assertEqual(res.normalized_entity, "Starbucks")
        self.assertEqual(res.counterparty_type, "MERCHANT")
        self.assertNotIn("XXXXXX1234", res.clean_description)
        self.assertNotIn("412345", res.clean_description)

    def test_ach_netflix_subscription(self):
        """ACH recurring debit maps to Netflix."""
        raw = "ACH D- NETFLIX ENTERTAINMENT SERVICES"
        res = self.normalizer.normalize(raw)

        self.assertEqual(res.channel, "ACH")
        self.assertEqual(res.normalized_entity, "Netflix")
        self.assertEqual(res.counterparty_type, "MERCHANT")

    def test_atm_cash_withdrawal(self):
        """ATM cash withdrawal maps to Bank entity and BANK type."""
        raw = "ATM WDL HDFC000123 CASH WITHDRAWAL"
        res = self.normalizer.normalize(raw)

        self.assertEqual(res.channel, "ATM")
        self.assertEqual(res.normalized_entity, "Bank")
        self.assertEqual(res.counterparty_type, "BANK")

    def test_interest_and_bank_charges(self):
        """Bank interest and service charges map to BANK counterparty."""
        raw_int = "INT.PD 01-04-2026 TO 30-06-2026"
        res_int = self.normalizer.normalize(raw_int)
        self.assertEqual(res_int.channel, "INTEREST")
        self.assertEqual(res_int.counterparty_type, "BANK")

        raw_chg = "ANNUAL FEE CONSOLIDATED SERVICE CHARGES"
        res_chg = self.normalizer.normalize(raw_chg)
        self.assertEqual(res_chg.channel, "CHARGES")
        self.assertEqual(res_chg.counterparty_type, "BANK")

    def test_government_tax_challan(self):
        """Tax challan narration maps to Income Tax Department and GOVERNMENT."""
        raw = "INCOME TAX PAYMENT CHALLAN 280 ITNS"
        res = self.normalizer.normalize(raw)

        self.assertEqual(res.normalized_entity, "Income Tax Department")
        self.assertEqual(res.counterparty_type, "GOVERNMENT")

    def test_individual_p2p_upi_transfer(self):
        """Non-merchant individual P2P transfer identifies counterparty as INDIVIDUAL."""
        raw = "UPI/309182910293/Rahul Sharma/rahul@okaxis/Rent payment"
        res = self.normalizer.normalize(raw)

        self.assertEqual(res.channel, "UPI")
        self.assertEqual(res.vpa, "rahul@okaxis")
        self.assertEqual(res.reference_id, "309182910293")
        self.assertEqual(res.normalized_entity, "Rahul Sharma")
        self.assertEqual(res.counterparty_type, "INDIVIDUAL")

    def test_custom_merchant_registry(self):
        """Custom merchant dictionary overrides/supplements defaults."""
        custom = {"artisan cafe": ("The Artisan Cafe", "MERCHANT")}
        custom_norm = EntityNormalizer(custom_merchants=custom)
        res = custom_norm.normalize("POS SWIPE ARTISAN CAFE BANGALORE")

        self.assertEqual(res.normalized_entity, "The Artisan Cafe")
        self.assertEqual(res.counterparty_type, "MERCHANT")

    def test_convenience_helper_functions(self):
        """normalize_transaction_entity and extract_clean_entity work as expected."""
        data = normalize_transaction_entity("UPI/123456789012/Zomato/zomato@hdfc/Food")
        self.assertIsInstance(data, dict)
        self.assertEqual(data["normalized_entity"], "Zomato")
        self.assertEqual(data["channel"], "UPI")

        entity_str = extract_clean_entity("UBER INDIA RIDES MUMBAI")
        self.assertEqual(entity_str, "Uber")


if __name__ == "__main__":
    unittest.main()
