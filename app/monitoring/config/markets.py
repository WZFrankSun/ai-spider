DEFAULT_POSTAL_CODES = {
    "DE": "10115",
    "IT": "00174",
    "FR": "75001",
    "ES": "28001",
    "GB": "SW1A 1AA",
    "NL": "1012",
    "SE": "111 22",
    "BE": "1049",
    "PL": "00-001",
}
AMAZON_DOMAINS = {
    "DE": "amazon.de", "IT": "amazon.it", "FR": "amazon.fr", "ES": "amazon.es",
    "GB": "amazon.co.uk", "SE": "amazon.se", "BE": "amazon.com.be",
    "PL": "amazon.pl", "NL": "amazon.nl",
}
ENTRY_COUNTRIES = tuple(AMAZON_DOMAINS)
LIVE_AMAZON_COUNTRIES = frozenset(ENTRY_COUNTRIES)

AMAZON_LOCALES = {
    "DE": "de-DE", "IT": "it-IT", "FR": "fr-FR", "ES": "es-ES",
    "GB": "en-GB", "SE": "sv-SE", "BE": "fr-BE", "PL": "pl-PL", "NL": "nl-NL",
}


def resolve_target_postal_code(country: str | None) -> str:
    return DEFAULT_POSTAL_CODES.get((country or "").strip().upper(), "")
