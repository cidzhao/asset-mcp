import pytest

from asset_mcp.config import ConfigError, parse_config, redact_secrets


def test_parse_config_supports_multiple_accounts():
    config = parse_config(
        {
            "rates": {"USD": 1, "CNY": 0.14},
            "exchanges": {
                "binance": {
                    "accounts": [
                        {"id": "binance-main", "label": "Main", "apiKey": "k1", "apiSecret": "s1"},
                        {"id": "binance-sub", "label": "Sub", "apiKey": "k2", "apiSecret": "s2"},
                    ]
                },
                "okx": {
                    "accounts": [
                        {
                            "id": "okx-main",
                            "label": "OKX",
                            "apiKey": "k",
                            "apiSecret": "s",
                            "passphrase": "p",
                        }
                    ]
                },
            },
            "manual": {
                "accounts": [
                    {
                        "id": "bank-cmb",
                        "label": "CMB",
                        "category": "cash",
                        "assets": [{"symbol": "CNY", "quantity": 100, "currency": "CNY"}],
                    }
                ]
            },
        }
    )

    assert [account.id for account in config.binanceAccounts] == ["binance-main", "binance-sub"]
    assert config.okxAccounts[0].id == "okx-main"
    assert config.manualAccounts[0].assets[0].quantity == 100


def test_duplicate_account_ids_are_rejected():
    with pytest.raises(ConfigError, match="Duplicate account id"):
        parse_config(
            {
                "exchanges": {
                    "binance": {
                        "accounts": [{"id": "same", "apiKey": "k", "apiSecret": "s"}],
                    },
                    "okx": {
                        "accounts": [
                            {"id": "same", "apiKey": "k", "apiSecret": "s", "passphrase": "p"}
                        ],
                    },
                }
            }
        )


def test_redact_secrets_hides_nested_secret_values():
    redacted = redact_secrets(
        {
            "apiKey": "key",
            "nested": {"apiSecret": "secret", "passphrase": "phrase"},
            "label": "visible",
        }
    )

    assert redacted["apiKey"] == "***REDACTED***"
    assert redacted["nested"]["apiSecret"] == "***REDACTED***"
    assert redacted["nested"]["passphrase"] == "***REDACTED***"
    assert redacted["label"] == "visible"
