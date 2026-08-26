from creditpool.redact import redact_env, redact_text


def test_redact_bearer_and_sk() -> None:
    text = "Authorization: Bearer abcdefg token=supersecret sk-abcdefghijklmnop"
    out = redact_text(text)
    assert "abcdefg" not in out
    assert "supersecret" not in out
    assert "sk-abcdefghijklmnop" not in out
    assert "[REDACTED]" in out


def test_redact_env_keys() -> None:
    env = redact_env(
        {
            "PATH": "/usr/bin",
            "OPENAI_API_KEY": "sk-live-secret",
            "CURSOR_API_KEY": "abc",
        }
    )
    assert env["PATH"] == "/usr/bin"
    assert env["OPENAI_API_KEY"] == "[REDACTED]"
    assert env["CURSOR_API_KEY"] == "[REDACTED]"
