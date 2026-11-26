"""
backend/app/services/reconciliation/semantic_matcher.py

Semantic Matching Engine for Financial Transactions.
Computes semantic similarity between transaction narrations using TF-IDF vectorization,
domain-aware synonym mapping (Indian accounting/banking concepts), and cosine similarity.

Overcomes limitations of lexical/character-level fuzzy matching by understanding that
e.g. "Office premises lease rental" and "Rent payment property" convey the same economic meaning.
"""

from __future__ import annotations

import re
from typing import Any
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ---------------------------------------------------------------------------
# Domain Synsets: Financial and Accounting Concept Canonical Mapping
# ---------------------------------------------------------------------------

DOMAIN_SYNSET_MAP: dict[str, str] = {
    # Rent & Premises
    "rent": "concept_rent",
    "rental": "concept_rent",
    "lease": "concept_rent",
    "leasing": "concept_rent",
    "tenancy": "concept_rent",
    "sublease": "concept_rent",
    "premises": "concept_rent",

    # Salary & Payroll
    "salary": "concept_salary",
    "salaries": "concept_salary",
    "payroll": "concept_salary",
    "wages": "concept_salary",
    "stipend": "concept_salary",
    "remuneration": "concept_salary",
    "compensation": "concept_salary",
    "payscale": "concept_salary",
    "emolument": "concept_salary",
    "staff": "concept_salary",

    # Professional & Legal
    "consulting": "concept_professional",
    "consultancy": "concept_professional",
    "professional": "concept_professional",
    "advisory": "concept_professional",
    "retainer": "concept_professional",
    "advocate": "concept_professional",
    "legal": "concept_professional",
    "counsel": "concept_professional",
    "audit": "concept_professional",
    "auditing": "concept_professional",
    "taxation": "concept_professional",

    # Utilities
    "electricity": "concept_utility",
    "power": "concept_utility",
    "bescom": "concept_utility",
    "tneb": "concept_utility",
    "msedcl": "concept_utility",
    "water": "concept_utility",
    "utility": "concept_utility",
    "utilities": "concept_utility",

    # Telecom & Internet
    "broadband": "concept_telecom",
    "internet": "concept_telecom",
    "wifi": "concept_telecom",
    "telecom": "concept_telecom",
    "telephone": "concept_telecom",
    "airtel": "concept_telecom",
    "jio": "concept_telecom",
    "vodafone": "concept_telecom",

    # Software & Cloud
    "software": "concept_software",
    "subscription": "concept_software",
    "license": "concept_software",
    "licence": "concept_software",
    "saas": "concept_software",
    "cloud": "concept_software",
    "aws": "concept_software",
    "azure": "concept_software",
    "gcp": "concept_software",
    "hosting": "concept_software",
    "server": "concept_software",

    # Advertising & Marketing
    "advertising": "concept_marketing",
    "advertisement": "concept_marketing",
    "marketing": "concept_marketing",
    "promotion": "concept_marketing",
    "promo": "concept_marketing",
    "campaign": "concept_marketing",
    "meta": "concept_marketing",
    "googleads": "concept_marketing",

    # Insurance
    "insurance": "concept_insurance",
    "premium": "concept_insurance",
    "policy": "concept_insurance",
    "coverage": "concept_insurance",
    "assurance": "concept_insurance",
    "mediclaim": "concept_insurance",

    # Travel & Hospitality
    "travel": "concept_travel",
    "flight": "concept_travel",
    "airfare": "concept_travel",
    "lodging": "concept_travel",
    "hotel": "concept_travel",
    "accommodation": "concept_travel",
    "conveyance": "concept_travel",
    "cab": "concept_travel",
    "taxi": "concept_travel",
    "trip": "concept_travel",

    # Logistics & Freight
    "freight": "concept_freight",
    "courier": "concept_freight",
    "shipping": "concept_freight",
    "transport": "concept_freight",
    "logistics": "concept_freight",
    "cartage": "concept_freight",
    "carriage": "concept_freight",
    "dispatch": "concept_freight",

    # Maintenance & Repairs
    "maintenance": "concept_maintenance",
    "repair": "concept_maintenance",
    "repairs": "concept_maintenance",
    "amc": "concept_maintenance",
    "upkeep": "concept_maintenance",
    "servicing": "concept_maintenance",

    # Dividends & Interest
    "dividend": "concept_investment",
    "dividends": "concept_investment",
    "interest": "concept_investment",
    "yield": "concept_investment",
    "coupon": "concept_investment",

    # Taxes & Statutory
    "tds": "concept_tax",
    "gst": "concept_tax",
    "challan": "concept_tax",
    "statutory": "concept_tax",
    "provident": "concept_tax",

    # Supplies & Refreshments
    "stationery": "concept_supplies",
    "consumables": "concept_supplies",
    "pantry": "concept_supplies",
    "refreshments": "concept_supplies",
    "groceries": "concept_supplies",
}

# Regex to strip transaction reference codes (e.g., UTRs, IMPS/NEFT reference ids, VPA tags)
REFERENCE_STRIP_REGEX = re.compile(
    r"\b(?:neft|rtgs|imps|upi|ach|pos|cms|ref|utr|rrn|txn|chq|no|id)[\s/:-]*[a-z0-9]+\b|\b\d{10,18}\b",
    re.IGNORECASE,
)


def _clean_text(value: Any) -> str:
    """Clean and normalize text for semantic vectorization."""
    if value is None or (pd.isna(value) if "pd" in globals() else False):
        return ""
    text = str(value).strip().lower()
    return re.sub(r"\s+", " ", text)


class SemanticMatcher:
    """
    Computes semantic similarity across transaction descriptions using
    accounting domain concept expansion and TF-IDF cosine similarity.
    """

    def __init__(self, semantic_threshold: float = 70.0):
        self.semantic_threshold = max(0.0, min(100.0, float(semantic_threshold)))

    @staticmethod
    def preprocess_description(text: Any) -> str:
        """
        Cleans description, strips bank transaction codes/references, and
        normalizes whitespace.
        """
        raw = _clean_text(text)
        if not raw:
            return ""
        cleaned = REFERENCE_STRIP_REGEX.sub(" ", raw)
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def extract_matched_concepts(text1: Any, text2: Any) -> list[str]:
        """Return list of shared domain concepts between two texts."""
        c1 = REFERENCE_STRIP_REGEX.sub(" ", _clean_text(text1))
        c2 = REFERENCE_STRIP_REGEX.sub(" ", _clean_text(text2))

        tokens1 = set(re.findall(r"[a-z0-9]+", c1.lower()))
        tokens2 = set(re.findall(r"[a-z0-9]+", c2.lower()))

        concepts1 = {DOMAIN_SYNSET_MAP[t] for t in tokens1 if t in DOMAIN_SYNSET_MAP}
        concepts2 = {DOMAIN_SYNSET_MAP[t] for t in tokens2 if t in DOMAIN_SYNSET_MAP}

        shared = sorted(concepts1.intersection(concepts2))
        return [c.replace("concept_", "").title() for c in shared]

    def compute_similarity(self, desc1: Any, desc2: Any) -> float:
        """
        Compute semantic similarity (0.0 to 100.0) between two transaction descriptions.
        Combines word/char TF-IDF cosine similarity with domain accounting concept expansion.
        """
        raw1 = _clean_text(desc1)
        raw2 = _clean_text(desc2)

        if not raw1 and not raw2:
            return 100.0
        if not raw1 or not raw2:
            return 0.0
        if raw1 == raw2:
            return 100.0

        c1 = self.preprocess_description(desc1)
        c2 = self.preprocess_description(desc2)

        if not c1 or not c2:
            return 0.0
        if c1 == c2:
            return 100.0

        tokens1 = set(re.findall(r"[a-z0-9]+", c1.lower()))
        tokens2 = set(re.findall(r"[a-z0-9]+", c2.lower()))

        concepts1 = {DOMAIN_SYNSET_MAP[t] for t in tokens1 if t in DOMAIN_SYNSET_MAP}
        concepts2 = {DOMAIN_SYNSET_MAP[t] for t in tokens2 if t in DOMAIN_SYNSET_MAP}
        shared_concepts = concepts1.intersection(concepts2)

        # Word-level TF-IDF
        try:
            vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, token_pattern=r"(?u)\b\w+\b")
            m = vec.fit_transform([c1, c2])
            base_tfidf = float(cosine_similarity(m[0:1], m[1:2])[0][0]) * 100.0
        except Exception:
            base_tfidf = 0.0

        # Char n-gram TF-IDF (captures subword similarities)
        try:
            char_vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 4), sublinear_tf=True)
            cm = char_vec.fit_transform([c1, c2])
            char_tfidf = float(cosine_similarity(cm[0:1], cm[1:2])[0][0]) * 100.0
        except Exception:
            char_tfidf = 0.0

        lexical_sim = max(base_tfidf, char_tfidf)

        if shared_concepts:
            concept_base = 75.0 if len(shared_concepts) == 1 else 85.0
            final_score = max(lexical_sim, concept_base + (lexical_sim * 0.15))
        else:
            final_score = lexical_sim

        score = float(np.clip(final_score, 0.0, 100.0))
        return round(score, 2)

    def compare_pairwise(
        self,
        reference_text: str,
        candidates: list[str],
    ) -> list[dict[str, Any]]:
        """
        Compare a reference description against a list of candidate descriptions,
        returning similarity scores and domain concept matches sorted by highest similarity.
        """
        results = []
        for cand in candidates:
            sim = self.compute_similarity(reference_text, cand)
            concepts = self.extract_matched_concepts(reference_text, cand)
            results.append({
                "candidate": cand,
                "similarity_score": sim,
                "is_match": sim >= self.semantic_threshold,
                "matched_concepts": concepts,
            })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results


# Module-level convenience functions
_DEFAULT_MATCHER = SemanticMatcher(semantic_threshold=70.0)


def compute_semantic_similarity(desc1: Any, desc2: Any) -> float:
    """Convenience helper to compute 0-100 semantic similarity between descriptions."""
    return _DEFAULT_MATCHER.compute_similarity(desc1, desc2)


def get_shared_concepts(desc1: Any, desc2: Any) -> list[str]:
    """Convenience helper to get shared accounting concepts."""
    return SemanticMatcher.extract_matched_concepts(desc1, desc2)
