import json
from unittest.mock import MagicMock, patch

from src.updater import check_for_updates, parse_version_tuple


def test_parse_version_tuple():
    assert parse_version_tuple("v1.2.0") == (1, 2, 0)
    assert parse_version_tuple("1.1.0") == (1, 1, 0)
    assert parse_version_tuple("2.0.0-rc1") == (2, 0, 0)
    assert parse_version_tuple("") == (0, 0, 0)
    assert parse_version_tuple("1.6") == (1, 6, 0)
    assert parse_version_tuple("update_1.6.1") == (1, 6, 1)
    assert parse_version_tuple("v1.10.0") > parse_version_tuple("v1.2.0")
    assert parse_version_tuple("v2.0.0") > parse_version_tuple("v1.9.9")
    assert parse_version_tuple("1.1.0") == parse_version_tuple("v1.1.0")


def test_check_for_updates_direct_github(monkeypatch):
    monkeypatch.setattr("src.updater.GITHUB_REPO", "leorusso34/RSM")
    monkeypatch.setattr("src.updater.WORKER_URL", "https://rsm-proxy.test.workers.dev")
    monkeypatch.setattr("src.updater.RSM_AUTH_KEY", "secret123")

    fake_github_release = {
        "tag_name": "update_1.6.1",
        "name": "RSM 1.6.1",
        "body": "Changelog 1.6.1",
        "assets": [
            {
                "id": 12345,
                "name": "RSM-Windows.zip",
                "size": 115000000,
                "browser_download_url": "https://github.com/leorusso34/RSM/releases/download/update_1.6.1/RSM-Windows.zip",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(fake_github_release).encode("utf-8")
    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPSConnection", return_value=mock_conn):
        res = check_for_updates(current_version="1.6.0")
        assert res is not None
        assert res["version"] == "update_1.6.1"
        assert res["download_url"] == "https://github.com/leorusso34/RSM/releases/download/update_1.6.1/RSM-Windows.zip"
        assert res["asset_name"] == "RSM-Windows.zip"


def test_check_for_updates_via_worker_proxy(monkeypatch):
    # Simula GitHub API non disponibile per testare il fallback sul Worker
    monkeypatch.setattr("src.updater.GITHUB_REPO", "")
    monkeypatch.setattr("src.updater.WORKER_URL", "https://rsm-proxy.test.workers.dev")
    monkeypatch.setattr("src.updater.RSM_AUTH_KEY", "secret123")
    fake_release = {
        "tag_name": "v1.5.0",
        "name": "RSM v1.5.0",
        "body": "Proxy support",
        "assets": [
            {
                "id": 998877,
                "name": "RSM-v1.5.0.zip",
                "size": 123456,
            }
        ],
    }
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(fake_release).encode("utf-8")
    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPSConnection", return_value=mock_conn):
        # 1. Nuova versione disponibile
        res = check_for_updates(current_version="1.4.0")
        assert res is not None
        assert res["version"] == "v1.5.0"
        assert res["download_url"] == "https://rsm-proxy.test.workers.dev/api/updates/download/998877"

        # 2. Versione uguale
        res_same = check_for_updates(current_version="1.5.0")
        assert res_same is None

        # 3. Versione più recente
        res_newer = check_for_updates(current_version="2.0.0")
        assert res_newer is None


def test_check_for_updates_platform_asset_selection(monkeypatch):
    import sys
    monkeypatch.setattr("src.updater.WORKER_URL", "https://rsm-proxy.test.workers.dev")
    monkeypatch.setattr("src.updater.RSM_AUTH_KEY", "secret123")
    fake_release = {
        "tag_name": "v1.6.0",
        "name": "RSM v1.6.0",
        "body": "Cross-platform release",
        "assets": [
            {
                "id": 111,
                "name": "RSM-macOS.zip",
                "size": 1000,
            },
            {
                "id": 222,
                "name": "RSM-Windows.zip",
                "size": 2000,
            },
        ],
    }
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(fake_release).encode("utf-8")
    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPSConnection", return_value=mock_conn):
        # Su Windows deve selezionare l'asset id 222 (RSM-Windows.zip)
        monkeypatch.setattr(sys, "platform", "win32")
        win_res = check_for_updates(current_version="1.5.0")
        assert win_res is not None
        assert win_res["asset_name"] == "RSM-Windows.zip"
        assert "222" in win_res["download_url"]

        # Su macOS deve selezionare l'asset id 111 (RSM-macOS.zip)
        monkeypatch.setattr(sys, "platform", "darwin")
        mac_res = check_for_updates(current_version="1.5.0")
        assert mac_res is not None
        assert mac_res["asset_name"] == "RSM-macOS.zip"
        assert "111" in mac_res["download_url"]



def test_ebay_fetch_market_prices_proxy(monkeypatch):
    from src.ebay_api import fetch_market_prices
    monkeypatch.setattr("src.ebay_api.WORKER_URL", "https://rsm-proxy.test.workers.dev")
    monkeypatch.setattr("src.ebay_api.RSM_AUTH_KEY", "secret123")

    fake_items = {
        "itemSummaries": [
            {"price": {"value": "100.00"}},
            {"price": {"value": "120.00"}},
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(fake_items).encode("utf-8")
    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPSConnection", return_value=mock_conn):
        res = fetch_market_prices("Nike Dunk", "42")
        assert res["count"] == 2
        assert res["min"] == 100.0
        assert res["avg"] == 110.0
        assert res["max"] == 120.0


def test_ai_parse_product_proxy(monkeypatch):
    from src.ai_agent import parse_product_with_ai
    monkeypatch.setattr("src.ai_agent.WORKER_URL", "https://rsm-proxy.test.workers.dev")
    monkeypatch.setattr("src.ai_agent.RSM_AUTH_KEY", "secret123")

    fake_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "products": [
                                    {
                                        "name": "Jordan 4",
                                        "size": "43",
                                        "quantity": 1,
                                        "purchased_price": 200.0,
                                        "status": "In Stock",
                                    }
                                ]
                            })
                        }
                    ]
                }
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPSConnection", return_value=mock_conn):
        res = parse_product_with_ai("Jordan 4 taglia 43 presa a 200")
        assert len(res) == 1
        assert res[0]["name"] == "Jordan 4"
        assert res[0]["purchased_price"] == 200.0


def test_source_root_extraction_resolution(tmp_path):
    # Caso 1: archivio zip con cartella radice 'RSM'
    extract_dir1 = tmp_path / "extract1"
    rsm_folder = extract_dir1 / "RSM"
    rsm_folder.mkdir(parents=True)
    exe_file = rsm_folder / "RSM.exe"
    exe_file.write_text("dummy")

    candidates = (
        [p for p in extract_dir1.rglob("RSM.exe") if p.is_file()]
        + [p for p in extract_dir1.rglob("RSM.app") if p.is_dir()]
        + [p for p in extract_dir1.rglob("RSM") if p.is_file()]
    )
    assert len(candidates) == 1
    assert candidates[0].parent == rsm_folder

    # Caso 2: archivio zip flat (eseguibile direttamente nella radice)
    extract_dir2 = tmp_path / "extract2"
    extract_dir2.mkdir()
    flat_exe = extract_dir2 / "RSM.exe"
    flat_exe.write_text("dummy")

    candidates2 = (
        [p for p in extract_dir2.rglob("RSM.exe") if p.is_file()]
        + [p for p in extract_dir2.rglob("RSM.app") if p.is_dir()]
        + [p for p in extract_dir2.rglob("RSM") if p.is_file()]
    )
    assert len(candidates2) == 1
    assert candidates2[0].parent == extract_dir2


def test_nested_zip_extraction(tmp_path):
    import zipfile
    inner_zip_path = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner_zip_path, "w") as z:
        z.writestr("RSM/RSM.exe", "fake_binary")
        z.writestr("RSM/src/main.py", "print(1)")

    outer_zip_path = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer_zip_path, "w") as z:
        z.write(inner_zip_path, arcname="RSM-Windows.zip")

    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()
    with zipfile.ZipFile(outer_zip_path, "r") as z:
        z.extractall(extract_dir)

    # Verifica gestione zip annidato come in updater.py
    nested_zips = list(extract_dir.glob("*.zip"))
    if len(nested_zips) == 1 and not (extract_dir / "RSM.exe").is_file() and not (extract_dir / "src").is_dir():
        with zipfile.ZipFile(nested_zips[0], "r") as nz:
            nz.extractall(extract_dir)
        nested_zips[0].unlink(missing_ok=True)

    assert (extract_dir / "RSM" / "RSM.exe").is_file()



