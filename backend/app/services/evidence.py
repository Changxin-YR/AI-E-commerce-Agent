from unicodedata import normalize

from app.services.product_quality import digest


def evidence_key(reference: str) -> str:
    """Shared exact-reference policy for manual expenses and statement fee rows."""
    return digest({"reference": " ".join(normalize("NFKC", reference).casefold().split())})
