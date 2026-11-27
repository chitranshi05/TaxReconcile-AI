"""
app/services/ingestion/entity_normalizer.py

Entity and Description Normalization Engine for Financial Statements.

Standardizes messy transaction descriptions (especially Indian banking narrations),
removes noise prefixes, payment gateway tags, reference numbers, and VPA handles,
identifies banking channels, and maps counterparty names to canonical corporate/merchant entities.
"""

from __future__ import annotations

import re
from typing import Any, NamedTuple


class NormalizedEntityResult(NamedTuple):
    raw_description: str
    clean_description: str
    normalized_entity: str
    channel: str
    reference_id: str | None
    counterparty_type: str
    vpa: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_description": self.raw_description,
            "clean_description": self.clean_description,
            "normalized_entity": self.normalized_entity,
            "channel": self.channel,
            "reference_id": self.reference_id,
            "counterparty_type": self.counterparty_type,
            "vpa": self.vpa,
        }


# Known Merchant & Organization Directory (lowercase aliases -> Canonical Name)
KNOWN_MERCHANTS: dict[str, tuple[str, str]] = {
    # alias: (Canonical Name, Counterparty Type)
    "amazon": ("Amazon", "MERCHANT"),
    "amzn": ("Amazon", "MERCHANT"),
    "amazon payments": ("Amazon", "MERCHANT"),
    "amazon seller": ("Amazon", "MERCHANT"),
    "amazon pay": ("Amazon", "MERCHANT"),
    "swiggy": ("Swiggy", "MERCHANT"),
    "bundl technologies": ("Swiggy", "MERCHANT"),
    "zomato": ("Zomato", "MERCHANT"),
    "hyperpure": ("Zomato", "MERCHANT"),
    "zomato media": ("Zomato", "MERCHANT"),
    "uber": ("Uber", "MERCHANT"),
    "uber india": ("Uber", "MERCHANT"),
    "ola": ("Ola", "MERCHANT"),
    "ani technologies": ("Ola", "MERCHANT"),
    "olacabs": ("Ola", "MERCHANT"),
    "flipkart": ("Flipkart", "MERCHANT"),
    "flipkart internet": ("Flipkart", "MERCHANT"),
    "myntra": ("Myntra", "MERCHANT"),
    "myntra designs": ("Myntra", "MERCHANT"),
    "google": ("Google", "MERCHANT"),
    "google cloud": ("Google", "MERCHANT"),
    "google india": ("Google", "MERCHANT"),
    "google play": ("Google", "MERCHANT"),
    "microsoft": ("Microsoft", "MERCHANT"),
    "msft": ("Microsoft", "MERCHANT"),
    "azure": ("Microsoft", "MERCHANT"),
    "apple": ("Apple", "MERCHANT"),
    "itunes": ("Apple", "MERCHANT"),
    "apple.com/bill": ("Apple", "MERCHANT"),
    "netflix": ("Netflix", "MERCHANT"),
    "netflix entertainment": ("Netflix", "MERCHANT"),
    "spotify": ("Spotify", "MERCHANT"),
    "starbucks": ("Starbucks", "MERCHANT"),
    "tata starbucks": ("Starbucks", "MERCHANT"),
    "mcdonalds": ("McDonald's", "MERCHANT"),
    "hardcastle restaurants": ("McDonald's", "MERCHANT"),
    "airtel": ("Bharti Airtel", "MERCHANT"),
    "bharti airtel": ("Bharti Airtel", "MERCHANT"),
    "jio": ("Reliance Jio", "MERCHANT"),
    "reliance jio": ("Reliance Jio", "MERCHANT"),
    "rel jio": ("Reliance Jio", "MERCHANT"),
    "infosys": ("Infosys", "CORPORATE"),
    "tcs": ("Tata Consultancy Services", "CORPORATE"),
    "tata consultancy": ("Tata Consultancy Services", "CORPORATE"),
    "wipro": ("Wipro", "CORPORATE"),
    "reliance industries": ("Reliance Industries", "CORPORATE"),
    "ril": ("Reliance Industries", "CORPORATE"),
    "hdfc": ("HDFC Bank", "BANK"),
    "hdfc bank": ("HDFC Bank", "BANK"),
    "icici": ("ICICI Bank", "BANK"),
    "icici bank": ("ICICI Bank", "BANK"),
    "sbi": ("State Bank of India", "BANK"),
    "state bank of india": ("State Bank of India", "BANK"),
    "axis bank": ("Axis Bank", "BANK"),
    "kotak": ("Kotak Mahindra Bank", "BANK"),
    "kotak mahindra": ("Kotak Mahindra Bank", "BANK"),
    "income tax": ("Income Tax Department", "GOVERNMENT"),
    "incometax": ("Income Tax Department", "GOVERNMENT"),
    "cbdt": ("Income Tax Department", "GOVERNMENT"),
    "gstn": ("GST Department", "GOVERNMENT"),
    "gst payment": ("GST Department", "GOVERNMENT"),
    "epfo": ("EPFO", "GOVERNMENT"),
}

# Channel detection regular expressions
CHANNEL_PATTERNS = [
    (r"\bUPI(?:/|-|\s)(?:CR/|DR/|P2P/|P2M/)?", "UPI"),
    (r"\bNEFT(?:/|-|\s)", "NEFT"),
    (r"\bRTGS(?:/|-|\s)", "RTGS"),
    (r"\bIMPS(?:/|-|\s)(?:P2A/|P2U/)?", "IMPS"),
    (r"\b(?:POS|EDC|ECOM|SWIPE)(?:/|-|\s)", "POS"),
    (r"\b(?:ACH|NACH)(?:/|-|\s)(?:D-|CR-|DR-)?", "ACH"),
    (r"\bATM(?:/|-|\s)(?:WDL|WITHDRAWAL|CASH)?", "ATM"),
    (r"\b(?:CHQ|CHEQUE|CLG)(?:/|-|\s)", "CHEQUE"),
    (r"\b(?:INT\.PD|INT\.CR|INTEREST)\b", "INTEREST"),
    (r"\b(?:CHG|CHARGES|SERVICE CHARGE|ANNUAL FEE)\b", "CHARGES"),
    (r"\b(?:NETBANK|NET BANKING|INB|TFR)\b", "NET_BANKING"),
]

# Patterns for extracting and stripping technical metadata
VPA_REGEX = re.compile(r"\b([a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64})\b", re.IGNORECASE)
IFSC_REGEX = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)
CARD_MASK_REGEX = re.compile(r"\b(?:\d{6}[X*]{4,8}\d{4}|[X*]{4,8}\d{4})\b", re.IGNORECASE)
REFERENCE_REGEX = re.compile(r"\b(?:N|R)?(\d{11,16})\b", re.IGNORECASE)
DATE_PATTERN_REGEX = re.compile(r"\b\d{2}[-/]\d{2}[-/]\d{2,4}\b")
TIME_PATTERN_REGEX = re.compile(r"\b\d{2}:\d{2}(?::\d{2})?\b")

# Corporate suffixes pattern
CORP_SUFFIX_PATTERN = re.compile(
    r"\b(pvt\.?\s*ltd\.?|private\s*limited|ltd\.?|limited|llp|inc\.?|incorporated|corp\.?|corporation)\b",
    re.IGNORECASE,
)

# Common purpose or category words to filter out when extracting entity names
PURPOSE_KEYWORDS = {
    "payment", "transfer", "tfr", "paid", "dr", "cr", "in", "bill",
    "rent", "salary", "emi", "loan", "fees", "fee", "charges", "chg",
    "services", "advance", "reimbursement", "order", "purchase",
}


class EntityNormalizer:
    """
    Intelligent normalizer for transaction descriptions and counterparty entities.
    """

    def __init__(self, custom_merchants: dict[str, tuple[str, str]] | None = None):
        self.merchants = dict(KNOWN_MERCHANTS)
        if custom_merchants:
            for alias, target in custom_merchants.items():
                self.merchants[alias.lower().strip()] = target

    def normalize(self, description: str | None) -> NormalizedEntityResult:
        """
        Normalize a raw transaction description string.

        Extracts:
        - clean_description: Text free of gateway noise and IDs
        - normalized_entity: Canonical entity or merchant name
        - channel: Banking channel (UPI, NEFT, IMPS, POS, etc.)
        - reference_id: Extracted UTR or transaction reference number
        - counterparty_type: MERCHANT, CORPORATE, INDIVIDUAL, BANK, GOVERNMENT, UNKNOWN
        - vpa: Extracted UPI VPA handle if present
        """
        if not description or not str(description).strip():
            return NormalizedEntityResult(
                raw_description="",
                clean_description="",
                normalized_entity="UNKNOWN",
                channel="UNKNOWN",
                reference_id=None,
                counterparty_type="UNKNOWN",
                vpa=None,
            )

        raw = str(description).strip()

        # 1. Detect Channel
        channel = "UNKNOWN"
        for pattern, ch_name in CHANNEL_PATTERNS:
            if re.search(pattern, raw, re.IGNORECASE):
                channel = ch_name
                break

        # 2. Extract VPA (UPI ID) if present
        vpa_match = VPA_REGEX.search(raw)
        vpa = vpa_match.group(1) if vpa_match else None

        # 3. Extract Reference ID (UTR / RRN)
        reference_id = None
        ref_match = REFERENCE_REGEX.search(raw)
        if ref_match:
            reference_id = ref_match.group(1)

        # 4. Clean description: strip technical tokens & noise
        cleaned = raw

        # Remove channel prefixes
        for pattern, _ in CHANNEL_PATTERNS:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        # Remove VPA
        if vpa:
            cleaned = cleaned.replace(vpa, " ")

        # Remove card masks, IFSC codes, UTR, and dates/times
        cleaned = CARD_MASK_REGEX.sub(" ", cleaned)
        cleaned = IFSC_REGEX.sub(" ", cleaned)
        if ref_match:
            cleaned = cleaned.replace(ref_match.group(0), " ")
        cleaned = DATE_PATTERN_REGEX.sub(" ", cleaned)
        cleaned = TIME_PATTERN_REGEX.sub(" ", cleaned)

        # Remove delimiters and extra symbols
        cleaned = re.sub(r"[/\\|\-_:;*#]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # 5. Extract and normalize counterparty entity
        entity_name, counterparty_type = self._extract_entity(raw, cleaned, vpa, channel)

        return NormalizedEntityResult(
            raw_description=raw,
            clean_description=cleaned,
            normalized_entity=entity_name,
            channel=channel,
            reference_id=reference_id,
            counterparty_type=counterparty_type,
            vpa=vpa,
        )

    def _extract_entity(
        self,
        raw: str,
        cleaned: str,
        vpa: str | None,
        channel: str,
    ) -> tuple[str, str]:
        """
        Identify canonical entity and counterparty type.
        """
        lower_raw = raw.lower()
        lower_cleaned = cleaned.lower()

        # Check known merchants & corporate directory first
        for alias, (canonical, c_type) in self.merchants.items():
            if re.search(r"\b" + re.escape(alias) + r"\b", lower_raw) or re.search(
                r"\b" + re.escape(alias) + r"\b", lower_cleaned
            ):
                return canonical, c_type

        # Check VPA handle prefix if known (e.g. swiggy@icici -> Swiggy)
        if vpa:
            vpa_prefix = vpa.split("@")[0].lower()
            for alias, (canonical, c_type) in self.merchants.items():
                if alias in vpa_prefix:
                    return canonical, c_type

        # Handle standard slash-separated UPI format (UPI/ref/Name/vpa/remark)
        if channel == "UPI" and "/" in raw:
            parts = [p.strip() for p in raw.split("/") if p.strip()]
            for p in parts:
                p_lower = p.lower()
                # Skip channel tag, reference digits, vpa, and purpose words
                if (
                    p_lower == "upi"
                    or p.isdigit()
                    or "@" in p
                    or p_lower in PURPOSE_KEYWORDS
                ):
                    continue
                # Found candidate counterparty segment
                cand = self._clean_token_string(p)
                if cand:
                    return self._title_case(cand), "INDIVIDUAL"

        # Check for corporate suffix in cleaned text
        has_corp_suffix = bool(CORP_SUFFIX_PATTERN.search(cleaned))

        # Check for Government keywords
        if any(w in lower_raw for w in ["tax", "challan", "govt", "epfo", "gst"]):
            return (self._title_case(cleaned) if cleaned else "Government Entity"), "GOVERNMENT"

        # Check for Bank operations
        if channel in ("INTEREST", "CHARGES", "ATM"):
            return "Bank", "BANK"

        # Fallback to intelligent extraction from cleaned text
        tokens = [t for t in cleaned.split() if len(t) > 1 and not t.isdigit()]

        if tokens:
            filtered_tokens = [t for t in tokens if t.lower() not in PURPOSE_KEYWORDS]
            candidate_tokens = filtered_tokens if filtered_tokens else tokens
            candidate_name = " ".join(candidate_tokens[:2])
            canonical_name = self._title_case(candidate_name)

            c_type = "CORPORATE" if has_corp_suffix else ("MERCHANT" if channel == "POS" else "INDIVIDUAL")
            return canonical_name, c_type

        return "UNKNOWN", "UNKNOWN"

    @staticmethod
    def _clean_token_string(text: str) -> str:
        """Strip non-alphanumeric noise from a token string."""
        return re.sub(r"[^a-zA-Z0-9\s]", "", text).strip()

    @staticmethod
    def _title_case(text: str) -> str:
        """Capitalize each word properly while preserving acronyms."""
        words = text.split()
        res = []
        for w in words:
            if w.isupper() and len(w) <= 4:
                res.append(w)
            else:
                res.append(w.capitalize())
        return " ".join(res)


# Module-level default instance
_default_normalizer = EntityNormalizer()


def normalize_transaction_entity(description: str | None) -> dict[str, Any]:
    """Convenience helper to normalize a transaction description."""
    return _default_normalizer.normalize(description).to_dict()


def extract_clean_entity(description: str | None) -> str:
    """Convenience helper to extract just the normalized entity name."""
    return _default_normalizer.normalize(description).normalized_entity
