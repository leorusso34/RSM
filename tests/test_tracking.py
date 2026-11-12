"""Test unitari e di integrazione per il modulo 17TRACK e gli endpoint di tracking.
RSM - Russo Stock Management.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.database import InventoryDatabase
from src.tracking import fetch_tracking_info, translate_status


def test_translate_status():
    """Verifica la corretta traduzione in italiano degli stati 17TRACK."""
    assert translate_status("Delivered") == "Consegnato"
    assert translate_status("InTransit") == "In Transito"
    assert translate_status("PickedUp") == "Ritirato"
    assert translate_status("OutForDelivery") == "In Consegna"
    assert translate_status("NotFound") == "In attesa di tracciamento"
    assert translate_status("Alert") == "Avviso / Eccezione"
    assert translate_status("StatoInedito") == "StatoInedito"
    assert translate_status("") == "In Lavorazione"


def test_fetch_tracking_info_validation():
    """Verifica che codici vuoti o composti da soli spazi vengano rifiutati."""
    res_empty = fetch_tracking_info("")
    assert res_empty["success"] is False
    assert "vuoto" in res_empty["error"]

    res_spaces = fetch_tracking_info("   \n\t  ")
    assert res_spaces["success"] is False
    assert "vuoto" in res_spaces["error"]


def test_fetch_tracking_info_success_mock():
    """Verifica il parsing corretto di un payload di successo di 17TRACK."""
    mock_payload = {
        "code": 0,
        "data": {
            "accepted": [
                {
                    "number": "179090188502104",
                    "carrier": 100014,
                    "track_info": {
                        "latest_status": {
                            "status": "Delivered",
                            "sub_status": "Delivered_Other",
                            "sub_status_descr": "Delivered to recipient",
                        },
                        "tracking": {
                            "providers": [
                                {
                                    "provider": {
                                        "key": "brt",
                                        "name": "BRT Bartolini",
                                        "alias": "brt",
                                    },
                                    "events": [
                                        {
                                            "time_iso": "2026-11-03T15:27:00+01:00",
                                            "description": "DELIVERED",
                                            "location": "LUCCA (090)",
                                            "stage": "Delivered",
                                        },
                                        {
                                            "time_iso": "2026-11-03T08:30:00+01:00",
                                            "description": "FOR DELIVERY",
                                            "location": "LUCCA (090)",
                                            "stage": "OutForDelivery",
                                        },
                                    ],
                                }
                            ]
                        },
                    },
                }
            ],
            "rejected": [],
        },
    }

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPSConnection", return_value=mock_conn):
        res = fetch_tracking_info("179090188502104", carrier="brt")

    assert res["success"] is True
    assert res["tracking_number"] == "179090188502104"
    assert res["carrier"] == "brt"
    assert res["carrier_name"] == "BRT Bartolini"
    assert res["status"] == "Delivered"
    assert res["status_label"] == "Consegnato"
    assert res["events_count"] == 2
    assert res["latest_event"]["description"] == "DELIVERED"
    assert res["latest_event"]["location"] == "LUCCA (090)"


def test_fetch_tracking_info_rejected_mock():
    """Verifica la corretta gestione degli errori restituiti da 17TRACK (es. codice sconosciuto)."""
    mock_payload = {
        "code": 0,
        "data": {
            "accepted": [],
            "rejected": [
                {
                    "number": "INVALID999",
                    "error": {
                        "code": -18019901,
                        "message": "Tracking number is not found or unsupported carrier.",
                    },
                }
            ],
        },
    }

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPSConnection", return_value=mock_conn):
        res = fetch_tracking_info("INVALID999")

    assert res["success"] is False
    assert "not found" in res["error"]


def test_fetch_tracking_info_network_error():
    """Verifica la resilienza in caso di errore di connessione HTTP / socket timeout."""
    with patch("http.client.HTTPSConnection", side_effect=OSError("Network unreachable")):
        res = fetch_tracking_info("179090188502104")

    assert res["success"] is False
    assert "Errore di connessione" in res["error"]


def test_database_tracking_persistence(tmp_path):
    """Verifica che il database SQLite persista tracking_number, carrier e tracking_cache."""
    db_file = tmp_path / "test_tracking_db.sqlite"
    db = InventoryDatabase(db_file)

    # Inserimento nuovo prodotto con dati di tracking
    prod_id = db.save(
        {
            "name": "Nike Dunk Low",
            "purchased_price": Decimal("100.00"),
            "status": "Venduto",
            "sold_price": Decimal("160.00"),
            "fees": Decimal("15.00"),
            "tracking_number": "179090188502104",
            "carrier": "brt",
            "tracking_cache": json.dumps({"status": "Delivered"}),
        }
    )

    prod = db.get(prod_id)
    assert prod is not None
    assert prod["tracking_number"] == "179090188502104"
    assert prod["carrier"] == "brt"
    assert "Delivered" in prod["tracking_cache"]

    # Aggiornamento tramite metodo dedicato update_product_tracking
    db.update_product_tracking(
        prod_id,
        tracking_number="GLS987654321",
        carrier="gls",
        tracking_cache=json.dumps({"status": "InTransit"}),
    )

    prod_updated = db.get(prod_id)
    assert prod_updated["tracking_number"] == "GLS987654321"
    assert prod_updated["carrier"] == "gls"
    assert "InTransit" in prod_updated["tracking_cache"]
