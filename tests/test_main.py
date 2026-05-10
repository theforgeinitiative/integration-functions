from main import _normalize_email


def test_normalize_email_lowercases():
    assert _normalize_email("Alice@Example.COM") == "alice@examplecom"


def test_normalize_email_removes_dots():
    assert _normalize_email("alice.smith@gmail.com") == "alicesmith@gmailcom"


def test_normalize_email_gmail_equivalence():
    # Gmail ignores dots, so these should normalize to the same key
    assert _normalize_email("alice.smith@gmail.com") == _normalize_email("alicesmith@gmail.com")


def test_normalize_email_non_gmail_dots_also_removed():
    # Normalization is applied uniformly; comparison key removes dots everywhere
    assert _normalize_email("user@sub.domain.org") == _normalize_email("user@subdomainorg")
