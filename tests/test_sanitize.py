from inflection_scanner.sanitize import safe_exception, sanitize_text
from inflection_scanner.providers.sec import valid_user_agent


def test_safe_exception_does_not_echo_raw_header_value():
    exc=ValueError("InvalidHeader User-Agent: George somebody@example.com secret=abc123")
    out=safe_exception(exc,"SEC failed")
    assert "somebody@example.com" not in out
    assert "abc123" not in out
    assert out=="SEC failed: ValueError"


def test_sanitize_text_redacts_email_and_secret_assignment():
    out=sanitize_text("token=abc user@example.com")
    assert "abc" not in out
    assert "user@example.com" not in out


def test_sec_user_agent_rejects_copied_ui_blob():
    assert not valid_user_agent("Name:\nSEC_USER_AGENT\n\nValue:\nGeorge user@example.com")
    assert valid_user_agent("Example Person user@example.com")
