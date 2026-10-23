"""Modulo per la sincronizzazione ordini via email tramite Gmail IMAP e Gemini AI."""

import email
import html
import http.client
import imaplib
import json
import re
import urllib.parse
from datetime import datetime, timezone
from email.header import decode_header
from typing import Any

from .config import RSM_AUTH_KEY, STATUS_PREORDER, WORKER_URL


def _clean_header(header_value: str | None) -> str:
    """Decodifica un'intestazione MIME di un'email in stringa UTF-8 leggibile."""
    if not header_value:
        return ""
    try:
        decoded_fragments = decode_header(header_value)
        result = []
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                if encoding:
                    try:
                        result.append(fragment.decode(encoding, errors="replace"))
                    except (LookupError, UnicodeDecodeError):
                        result.append(fragment.decode("utf-8", errors="replace"))
                else:
                    result.append(fragment.decode("utf-8", errors="replace"))
            else:
                result.append(str(fragment))
        return "".join(result).strip()
    except (LookupError, UnicodeDecodeError, ValueError):
        return str(header_value).strip()


def _strip_html(html_content: str) -> str:
    """Rimuove tag HTML, script e fogli di stile per restituire il testo pulito."""
    text = re.sub(r"(?is)<(script|style|head).*?>.*?</\1>", "", html_content)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n\n", text)
    text = re.sub(r"(?is)</tr\s*>", "\n", text)
    text = re.sub(r"(?is)</td\s*>", " | ", text)
    text = re.sub(r"(?is)<.*?>", " ", text)
    text = html.unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    clean_text = "\n".join(line for line in lines if line)
    return clean_text


def _extract_body(msg: email.message.Message) -> str:
    """Estrae il corpo del messaggio preferendo il testo semplice o convertendo l'HTML."""
    body = ""
    if msg.is_multipart():
        html_body = ""
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disp = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disp:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded_str = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                decoded_str = payload.decode("utf-8", errors="replace")

            if content_type == "text/plain" and not body:
                body = decoded_str
            elif content_type == "text/html":
                html_body = decoded_str

        if not body and html_body:
            body = _strip_html(html_body)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                decoded_str = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                decoded_str = payload.decode("utf-8", errors="replace")

            if msg.get_content_type() == "text/html":
                body = _strip_html(decoded_str)
            else:
                body = decoded_str

    return body.strip()


def test_gmail_connection(email_addr: str, app_password: str) -> tuple[bool, str]:
    """Testa la connessione a Gmail con l'indirizzo email e la password per le app."""
    clean_email = email_addr.strip()
    clean_pass = app_password.replace(" ", "").strip()
    if not clean_email or not clean_pass:
        return False, "Inserisci sia l'indirizzo email che la password per le app."

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(clean_email, clean_pass)
        status, _ = mail.select("INBOX", readonly=True)
        mail.close()
        mail.logout()
        if status == "OK":
            return True, "Connessione a Gmail stabilita con successo!"
        return False, "Impossibile accedere alla cartella INBOX."
    except imaplib.IMAP4.error as exc:
        msg = str(exc)
        if "Application-specific password required" in msg or "Invalid credentials" in msg:
            return (
                False,
                "Credenziali non valide: assicurati di usare la Password per le App a 16 caratteri creata su Google.",
            )
        return False, f"Errore autenticazione IMAP: {msg}"
    except OSError as exc:
        return False, f"Errore di connessione: {exc}"


def fetch_unread_order_emails(email_addr: str, app_password: str, max_emails: int = 20) -> list[dict[str, Any]]:
    """Recupera le email non lette (UNSEEN) dalla casella INBOX."""
    clean_email = email_addr.strip()
    clean_pass = app_password.replace(" ", "").strip()
    results: list[dict[str, Any]] = []

    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    try:
        mail.login(clean_email, clean_pass)
        mail.select("INBOX")

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            return []

        email_ids = messages[0].split()
        if max_emails and len(email_ids) > max_emails:
            email_ids = email_ids[-max_emails:]

        for e_id in reversed(email_ids):
            uid_str = e_id.decode("utf-8")
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            if status != "OK" or not msg_data:
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _clean_header(msg.get("Subject"))
            sender = _clean_header(msg.get("From"))
            date_raw = _clean_header(msg.get("Date"))
            body = _extract_body(msg)

            # Estrai una data sintetica se possibile
            date_formatted = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
            try:
                parsed_tuple = email.utils.parsedate_tz(msg.get("Date"))
                if parsed_tuple:
                    ts = email.utils.mktime_tz(parsed_tuple)
                    date_formatted = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
            except (ValueError, OverflowError, TypeError, OSError):
                pass

            results.append(
                {
                    "uid": uid_str,
                    "subject": subject,
                    "sender": sender,
                    "date": date_formatted,
                    "date_raw": date_raw,
                    "body": body[:6000],  # Limite per prompt compatto
                }
            )

    finally:
        try:
            mail.close()
        except (imaplib.IMAP4.error, OSError):
            pass
        try:
            mail.logout()
        except (imaplib.IMAP4.error, OSError):
            pass

    return results


def mark_emails_as_read(email_addr: str, app_password: str, email_uids: list[str]) -> None:
    """Contrassegna le email specificate con il flag \\Seen (Letta)."""
    if not email_uids:
        return

    clean_email = email_addr.strip()
    clean_pass = app_password.replace(" ", "").strip()

    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    try:
        mail.login(clean_email, clean_pass)
        mail.select("INBOX")
        for uid in email_uids:
            try:
                mail.store(uid, "+FLAGS", "\\Seen")
            except (imaplib.IMAP4.error, OSError):
                pass
    finally:
        try:
            mail.close()
        except (imaplib.IMAP4.error, OSError):
            pass
        try:
            mail.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def parse_order_email_with_gemini(email_item: dict[str, Any]) -> list[dict[str, Any]]:
    """Invia il contenuto dell'email a Cloudflare Worker per estrarre i dati dei prodotti tramite Gemini AI."""
    if not WORKER_URL:
        raise RuntimeError("WORKER_URL non è configurato.")

    product_schema = {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "Nome completo e modello del prodotto ordinato."},
            "size": {
                "type": "STRING",
                "description": "Taglia del prodotto (es. 42, 43, M, L). Se non specificata usa 'UNI'.",
            },
            "quantity": {
                "type": "INTEGER",
                "description": "Quantità di pezzi ordinati per questo articolo (default: 1).",
            },
            "purchased_price": {
                "type": "NUMBER",
                "description": "Prezzo unitario o totale pagato per il prodotto (in euro).",
            },
            "purchased_place": {
                "type": "STRING",
                "description": "Negozio, brand o sito dove è stato effettuato l'ordine (es. Nike, SNKRS, StockX, Amazon, Vinted, Zalando, ecc.).",
            },
            "status": {"type": "STRING", "description": "Imposta sempre rigorosamente 'Pre-ordine'."},
            "release_date": {
                "type": "STRING",
                "description": "Data presunta di uscita/spedizione o data dell'ordine in formato AAAA-MM-GG.",
            },
        },
        "required": ["name", "quantity", "purchased_price", "purchased_place"],
    }

    response_schema = {
        "type": "OBJECT",
        "properties": {"products": {"type": "ARRAY", "items": product_schema}},
        "required": ["products"],
    }

    prompt_text = (
        f"Oggetto Email: {email_item.get('subject', '')}\n"
        f"Mittente: {email_item.get('sender', '')}\n"
        f"Data Email: {email_item.get('date', '')}\n\n"
        f"--- Testo dell'Email di Conferma Ordine ---\n"
        f"{email_item.get('body', '')}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "Sei un assistente per l'inventario. Analizza questa email di conferma ordine ed estrai "
                        "TUTTI i prodotti acquistati/ordinati. "
                        "Imposta SEMPRE lo stato ('status') su 'Pre-ordine'. "
                        "Identifica il negozio/piattaforma di acquisto dal mittente o dal corpo dell'email. "
                        "Restituisci sempre una lista 'products' conforme allo schema JSON, senza markdown."
                    )
                }
            ]
        },
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }

    data = json.dumps(payload).encode("utf-8")

    parsed_w = urllib.parse.urlparse(WORKER_URL.strip())
    w_host = parsed_w.netloc
    w_path = f"{parsed_w.path.rstrip('/')}/api/gemini/generate"
    w_headers = {"Content-Type": "application/json"}
    if RSM_AUTH_KEY:
        w_headers["X-RSM-Auth"] = RSM_AUTH_KEY.strip()

    conn_cls = http.client.HTTPSConnection if parsed_w.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(w_host, timeout=25)
    try:
        conn.request("POST", w_path, body=data, headers=w_headers)
        response = conn.getresponse()
        resp_data = response.read().decode("utf-8")
        if response.status != 200:
            raise RuntimeError(f"Errore Proxy AI ({response.status}): {resp_data}")
        result = json.loads(resp_data)
        if "candidates" in result and len(result["candidates"]) > 0:
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(content)
            products = parsed.get("products", [])
            for p in products:
                p["status"] = STATUS_PREORDER
                if not p.get("release_date"):
                    p["release_date"] = email_item.get(
                        "date", datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
                    )
            return products
        return []
    except (
        http.client.HTTPException,
        OSError,
        json.JSONDecodeError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        raise RuntimeError(f"Errore Proxy AI Gemini: {exc}") from exc
    finally:
        conn.close()
