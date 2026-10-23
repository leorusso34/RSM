"""Suite di test unitari con isolamento totale (Mocks) per src.email_sync."""

import imaplib
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from src.email_sync import (
    _clean_header,
    _extract_body,
    _strip_html,
    fetch_unread_order_emails,
    mark_emails_as_read,
    parse_order_email_with_gemini,
)
from src.email_sync import (
    test_gmail_connection as check_gmail_connection,
)


class TestEmailHeaderAndBodyExtraction:
    """Test per le funzioni di decodifica e sanitizzazione delle email."""

    @pytest.mark.parametrize(
        ("input_header", "expected"),
        [
            (None, ""),
            ("", ""),
            ("Conferma Ordine #1234", "Conferma Ordine #1234"),
            ("=?UTF-8?B?T2tl?= Ricevuto", "Oke Ricevuto"),
            ("=?ISO-8859-1?Q?Caf=E9?=", "Café"),
        ],
    )
    def test_clean_header(self, input_header, expected):
        assert _clean_header(input_header) == expected

    def test_strip_html_tags_and_scripts(self):
        html_input = """
        <html>
            <head><title>Test</title><style>body { color: red; }</style></head>
            <body>
                <script>alert('malware');</script>
                <h1>Riepilogo Ordine</h1>
                <p>Grazie per il tuo acquisto &euro; 50,00.</p>
                <table>
                    <tr><td>Prodotto:</td><td>Nike Air Force 1</td></tr>
                </table>
            </body>
        </html>
        """
        cleaned = _strip_html(html_input)
        assert "alert('malware')" not in cleaned
        assert "color: red" not in cleaned
        assert "Riepilogo Ordine" in cleaned
        assert "Grazie per il tuo acquisto € 50,00." in cleaned
        assert "Prodotto: | Nike Air Force 1" in cleaned

    def test_extract_body_plain_text(self):
        msg = EmailMessage()
        msg.set_content("Questo è un messaggio di prova in testo semplice.")
        body = _extract_body(msg)
        assert body == "Questo è un messaggio di prova in testo semplice."

    def test_extract_body_multipart_prefers_plain(self):
        msg = EmailMessage()
        msg.set_content("Corpo testuale preferito.")
        msg.add_alternative("<p>Corpo HTML secondario</p>", subtype="html")
        body = _extract_body(msg)
        assert body == "Corpo testuale preferito."

    def test_extract_body_multipart_html_only(self):
        msg = EmailMessage()
        msg.add_alternative("<p>Solo contenuto <b>HTML</b></p>", subtype="html")
        body = _extract_body(msg)
        assert "Solo contenuto HTML" in body

    def test_extract_body_skips_attachments(self):
        msg = EmailMessage()
        msg.set_content("Testo ordine principale.")
        msg.add_attachment(b"PDFDATA...", maintype="application", subtype="pdf", filename="fattura.pdf")
        body = _extract_body(msg)
        assert "Testo ordine principale." in body
        assert "PDFDATA" not in body


class TestGmailConnection:
    """Test isolati per test_gmail_connection con mock IMAP."""

    def test_missing_credentials(self):
        ok, msg = check_gmail_connection("", "")
        assert ok is False
        assert "Inserisci sia l'indirizzo" in msg

        ok, msg = check_gmail_connection("user@gmail.com", "")
        assert ok is False

    @patch("imaplib.IMAP4_SSL")
    def test_successful_connection(self, mock_imap_cls):
        mock_instance = MagicMock()
        mock_instance.select.return_value = ("OK", [b"1"])
        mock_imap_cls.return_value = mock_instance

        ok, msg = check_gmail_connection("user@gmail.com", "abcd efgh ijkl mnop")
        assert ok is True
        assert "successo" in msg
        mock_instance.login.assert_called_once_with("user@gmail.com", "abcdefghijklmnop")
        mock_instance.close.assert_called_once()
        mock_instance.logout.assert_called_once()

    @patch("imaplib.IMAP4_SSL")
    def test_invalid_credentials_error(self, mock_imap_cls):
        mock_instance = MagicMock()
        mock_instance.login.side_effect = imaplib.IMAP4.error("Invalid credentials (Failure)")
        mock_imap_cls.return_value = mock_instance

        ok, msg = check_gmail_connection("user@gmail.com", "bad_pass")
        assert ok is False
        assert "Password per le App" in msg

    @patch("imaplib.IMAP4_SSL")
    def test_network_connection_error(self, mock_imap_cls):
        mock_imap_cls.side_effect = OSError("Host non raggiungibile")

        ok, msg = check_gmail_connection("user@gmail.com", "secretpass")
        assert ok is False
        assert "Errore di connessione" in msg


class TestFetchAndMarkEmails:
    """Test isolati per il recupero e la marcatura di lettura delle email."""

    @patch("imaplib.IMAP4_SSL")
    def test_fetch_unread_emails_empty(self, mock_imap_cls):
        mock_instance = MagicMock()
        mock_instance.search.return_value = ("OK", [b""])
        mock_imap_cls.return_value = mock_instance

        emails = fetch_unread_order_emails("user@gmail.com", "app_pass")
        assert emails == []
        mock_instance.close.assert_called_once()
        mock_instance.logout.assert_called_once()

    @patch("imaplib.IMAP4_SSL")
    def test_fetch_unread_emails_parses_content(self, mock_imap_cls):
        mock_instance = MagicMock()
        mock_instance.search.return_value = ("OK", [b"101 102"])

        raw_email = b"""From: SNKRS <order@nike.com>\r
Subject: Il tuo ordine Nike e' confermato\r
Date: Fri, 23 Oct 2026 08:00:00 +0000\r
Content-Type: text/plain; charset="utf-8"\r
\r
Nike Dunk Low Size 42 Prezzo 120 EUR\r
"""
        mock_instance.fetch.return_value = ("OK", [(b"102 (RFC822 {100})", raw_email)])
        mock_imap_cls.return_value = mock_instance

        emails = fetch_unread_order_emails("user@gmail.com", "app_pass", max_emails=1)
        assert len(emails) == 1
        assert emails[0]["uid"] == "102"
        assert emails[0]["subject"] == "Il tuo ordine Nike e' confermato"
        assert "order@nike.com" in emails[0]["sender"]
        assert "Nike Dunk Low" in emails[0]["body"]

    @patch("imaplib.IMAP4_SSL")
    def test_mark_emails_as_read(self, mock_imap_cls):
        # Lista vuota non apre nemmeno la connessione
        mark_emails_as_read("user@gmail.com", "pass", [])
        mock_imap_cls.assert_not_called()

        mock_instance = MagicMock()
        mock_imap_cls.return_value = mock_instance
        mark_emails_as_read("user@gmail.com", "pass", ["101", "102"])
        assert mock_instance.store.call_count == 2
        mock_instance.close.assert_called_once()
        mock_instance.logout.assert_called_once()

    @patch("http.client.HTTPSConnection")
    def test_parse_order_email_with_gemini_success(self, mock_http_cls, monkeypatch):
        monkeypatch.setattr("src.email_sync.WORKER_URL", "https://rsm-proxy.test.workers.dev")
        monkeypatch.setattr("src.email_sync.RSM_AUTH_KEY", "secret123")

        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"candidates":[{"content":{"parts":[{"text":"{\\"products\\":[{\\"name\\":\\"Nike Air Max\\",\\"size\\":\\"42\\",\\"quantity\\":1,\\"purchased_price\\":110.0,\\"purchased_place\\":\\"Nike\\"}]}"}]}}]}'
        mock_conn.getresponse.return_value = mock_resp
        mock_http_cls.return_value = mock_conn

        email_data = {
            "subject": "Ordine Nike",
            "sender": "order@nike.com",
            "date": "2026-10-23",
            "body": "Hai acquistato Nike Air Max taglia 42 a 110 euro.",
        }

        products = parse_order_email_with_gemini(email_data)
        assert len(products) == 1
        assert products[0]["name"] == "Nike Air Max"
        assert products[0]["status"] == "Pre-ordine"
        assert products[0]["release_date"] == "2026-10-23"
        mock_conn.close.assert_called_once()

    def test_parse_order_email_no_worker_url(self, monkeypatch):
        monkeypatch.setattr("src.email_sync.WORKER_URL", "")
        with pytest.raises(RuntimeError, match="WORKER_URL non"):
            parse_order_email_with_gemini({"subject": "Test"})
