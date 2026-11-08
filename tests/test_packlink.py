"""Unit test per l'integrazione con Packlink PRO e gli endpoint dedicati."""

import json
from unittest.mock import MagicMock, patch

from src.packlink import (
    create_packlink_draft,
    fallback_regex_parse_address,
)


def test_create_packlink_draft_validation_missing_key():
    """Verifica il blocco se la chiave API è assente."""
    res = create_packlink_draft(api_key="", recipient={"name": "Mario Rossi"})
    assert res["success"] is False
    assert "Chiave API" in res["error"]


def test_create_packlink_draft_validation_missing_fields():
    """Verifica la validazione dei campi anagrafici minimi obbligatori."""
    dummy_auth = "mock_test_token"

    # Senza nome
    r1 = create_packlink_draft(dummy_auth, {"name": ""})
    assert r1["success"] is False
    assert "nome" in r1["error"].lower()

    # Senza indirizzo
    r2 = create_packlink_draft(dummy_auth, {"name": "Mario Rossi", "street1": ""})
    assert r2["success"] is False
    assert "indirizzo" in r2["error"].lower()

    # Senza CAP
    r3 = create_packlink_draft(dummy_auth, {"name": "Mario Rossi", "street1": "Via Roma 1", "zip": ""})
    assert r3["success"] is False
    assert "cap" in r3["error"].lower()

    # Senza città
    r4 = create_packlink_draft(
        dummy_auth, {"name": "Mario Rossi", "street1": "Via Roma 1", "zip": "20121", "city": ""}
    )
    assert r4["success"] is False
    assert "città" in r4["error"].lower()

    # Senza telefono
    r5 = create_packlink_draft(
        dummy_auth,
        {"name": "Mario Rossi", "street1": "Via Roma 1", "zip": "20121", "city": "Milano", "phone": ""},
    )
    assert r5["success"] is False
    assert "telefono" in r5["error"].lower()


@patch("http.client.HTTPSConnection")
def test_create_packlink_draft_success(mock_conn_cls):
    """Verifica la corretta creazione di una bozza su Packlink PRO con risposta 201."""
    mock_conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 201
    mock_resp.read.return_value = json.dumps(
        {
            "id": "673891024bcde",
            "shipment_reference": "IT2026PACKLINK001",
            "status": "DRAFT",
        }
    ).encode("utf-8")
    mock_conn.getresponse.return_value = mock_resp
    mock_conn_cls.return_value = mock_conn

    recipient = {
        "name": "Mario Rossi",
        "street1": "Via Monte Napoleone 8",
        "street2": "Piano 2",
        "zip": "20121",
        "city": "Milano",
        "country": "IT",
        "phone": "+393331234567",
        "email": "mario.rossi@example.com",
    }
    package_info = {
        "weight": 1.5,
        "length": 35.0,
        "width": 24.0,
        "height": 14.0,
    }

    res = create_packlink_draft("mock_test_token", recipient, package_info, content="Sneakers Nike")
    assert res["success"] is True
    assert res["draft_id"] == "673891024bcde"
    assert res["reference"] == "IT2026PACKLINK001"
    assert "pro.packlink.it" in res["web_url"]

    # Verifica payload inviato all'API Packlink
    args, kwargs = mock_conn.request.call_args
    assert args[0] == "POST"
    assert args[1] == "/v1/drafts"
    sent_payload = json.loads(kwargs["body"].decode("utf-8"))
    assert sent_payload["source"] == "RSM"
    assert sent_payload["to"]["name"] == "Mario"
    assert sent_payload["to"]["surname"] == "Rossi"
    assert sent_payload["to"]["street1"] == "Via Monte Napoleone 8"
    assert sent_payload["to"]["zip"] == "20121"
    assert sent_payload["packages"][0]["weight"] == 1.5


@patch("http.client.HTTPSConnection")
def test_create_packlink_draft_unauthorized(mock_conn_cls):
    """Verifica la gestione errore 401 Unauthorized (API Key non valida)."""
    mock_conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 401
    mock_resp.read.return_value = b'{"message": "Unauthorized"}'
    mock_conn.getresponse.return_value = mock_resp
    mock_conn_cls.return_value = mock_conn

    recipient = {
        "name": "Mario Rossi",
        "street1": "Via Roma 1",
        "zip": "20121",
        "city": "Milano",
        "phone": "+393331234567",
    }
    res = create_packlink_draft("invalid_key", recipient)
    assert res["success"] is False
    assert res["status_code"] == 401
    assert "non valida" in res["error"]


def test_fallback_regex_parse_address():
    """Verifica l'estrazione euristica regex su testo disordinato."""
    text = (
        "Spedisci a Marco Bianchi, via torino 45 scala A int 3, cap 10121 Torino. "
        "Cellulare 338 1234567, email marco.b@gmail.com, pacco scarpe da 1.4kg"
    )
    parsed = fallback_regex_parse_address(text)
    assert parsed["zip"] == "10121"
    assert "3381234567" in parsed["phone"]
    assert parsed["email"] == "marco.b@gmail.com"
    assert parsed["weight"] == 1.4
