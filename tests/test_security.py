from app.utils.security import redact,safe_url

def test_redaction_and_url_query_removal():
    assert "[REDACTED]" in redact("Authorization=secret")
    assert safe_url("https://x.test/a?token=secret")=="https://x.test/a"
