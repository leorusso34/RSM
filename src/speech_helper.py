"""
Modulo ottimizzato per il riconoscimento vocale rapido tramite Gemini 2.5 Flash e Google Speech API.
Usa sounddevice per la cattura a 16kHz Mono e supporta interruzione istantanea e trimming del silenzio.
"""

import io
import threading
from collections.abc import Callable
from typing import Any

from .utils import tr_msg


def _normalize_language(language: Any = "it-IT") -> str:
    """Normalizza il codice lingua per la trascrizione ('en*' -> 'en-US', fallback 'it-IT')."""
    if not language:
        return "it-IT"
    if isinstance(language, (list, tuple)) and language:
        language = language[0]
    cleaned = str(language or "").strip().lower()
    if cleaned.startswith("en"):
        return "en-US"
    return "it-IT"


normalize_language = _normalize_language


def _transcribe_with_gemini(wav_bytes: bytes, api_key: str, language: str = "it-IT") -> str | None:
    """Tenta la trascrizione fedele e veloce dell'audio tramite l'API Gemini 2.5 Flash."""
    import base64
    import http.client
    import json

    try:
        norm_lang = _normalize_language(language)
        if norm_lang == "en-US":
            prompt_text = (
                "Transcribe the audio accurately into text. Return ONLY the spoken words, without explanations."
            )
        else:
            prompt_text = (
                "Trascrivi l'audio in testo italiano. Restituisci SOLO le parole pronunciate, senza spiegazioni."
            )

        b64_audio = base64.b64encode(wav_bytes).decode("utf-8")
        host = "generativelanguage.googleapis.com"
        path = f"/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"inlineData": {"mimeType": "audio/wav", "data": b64_audio}},
                        {
                            "text": prompt_text,
                        },
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 250},
        }

        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        conn = http.client.HTTPSConnection(host, timeout=10)
        try:
            conn.request("POST", path, body=data, headers=headers)
            resp = conn.getresponse()
            if resp.status == 200:
                result = json.loads(resp.read().decode("utf-8"))
                if isinstance(result, dict):
                    candidates = result.get("candidates")
                    if isinstance(candidates, list) and candidates:
                        for candidate in candidates:
                            if not isinstance(candidate, dict):
                                continue
                            content = candidate.get("content")
                            if not isinstance(content, dict):
                                continue
                            parts = content.get("parts")
                            if not isinstance(parts, list) or not parts:
                                continue
                            chunks = [
                                part["text"].strip()
                                for part in parts
                                if isinstance(part, dict)
                                and not part.get("thought")
                                and isinstance(part.get("text"), str)
                                and part["text"].strip()
                            ]
                            if chunks:
                                return " ".join(chunks)
        finally:
            conn.close()
    except (
        OSError,
        http.client.HTTPException,
        json.JSONDecodeError,
        ValueError,
        LookupError,
        AttributeError,
        TypeError,
    ):
        pass
    return None


class SpeechTranscriber:
    """Gestisce la registrazione audio e la trascrizione vocale con controllo di stop immediato."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._is_recording = False
        self._thread: threading.Thread | None = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(
        self,
        on_result: Callable[[str], None],
        on_error: Callable[[str], None],
        on_listening: Callable[[], None],
        api_key: str = "",
        max_duration: int = 20,
        language: str = "it-IT",
    ) -> None:
        """Avvia la registrazione in background."""
        if self._is_recording:
            return

        normalized_lang = _normalize_language(language)
        self._stop_event.clear()
        self._is_recording = True

        def _run():
            try:
                import numpy as np
                import scipy.io.wavfile as wav_io
                import sounddevice as sd
                import speech_recognition as sr
            except ImportError as e:
                self._is_recording = False
                on_error(tr_msg(normalized_lang, f"Dipendenza mancante: {e}", f"Missing dependency: {e}"))
                return

            frames = []

            def _audio_callback(indata, frame_count, time_info, status):
                if not self._stop_event.is_set():
                    frames.append(indata.copy())

            try:
                sample_rate = 16000
                on_listening()

                with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", callback=_audio_callback):
                    self._stop_event.wait(timeout=max_duration)

                self._is_recording = False

                if not frames:
                    on_error(tr_msg(normalized_lang, "Nessun audio registrato.", "No audio recorded."))
                    return

                audio_data = np.concatenate(frames, axis=0)

                # Trimming intelligente del silenzio iniziale e finale per velocizzare il caricamento
                if len(audio_data) > 0:
                    abs_data = np.abs(audio_data.flatten())
                    indices = np.where(abs_data > 400)[0]
                    if len(indices) > 0:
                        pad = int(0.15 * sample_rate)
                        start_idx = max(0, indices[0] - pad)
                        end_idx = min(len(audio_data), indices[-1] + pad)
                        audio_data = audio_data[start_idx:end_idx]

                # Converti in WAV in memoria
                wav_buffer = io.BytesIO()
                wav_io.write(wav_buffer, sample_rate, audio_data)
                wav_bytes = wav_buffer.getvalue()

                # 1. Prova prima con Gemini 2.5 Flash
                if api_key:
                    gemini_text = _transcribe_with_gemini(wav_bytes, api_key, language=normalized_lang)
                    if gemini_text:
                        on_result(gemini_text)
                        return

                # 2. Fallback su Google Speech Recognition
                wav_buffer.seek(0)
                recognizer = sr.Recognizer()
                audio = sr.AudioData(wav_buffer.read(), sample_rate, 2)
                text = recognizer.recognize_google(audio, language=normalized_lang)
                on_result(text)

            except Exception as e:  # noqa: BLE001
                self._is_recording = False
                name = type(e).__name__
                msg = str(e)
                if (
                    "11001" in msg
                    or "getaddrinfo" in msg
                    or "connection failed" in msg.lower()
                    or "RequestError" in name
                ):
                    on_error(
                        tr_msg(
                            normalized_lang,
                            "Connessione internet non disponibile per il riconoscimento vocale. Puoi scrivere direttamente nel testo.",
                            "Internet connection unavailable for speech recognition. You can type directly in the text box.",
                        )
                    )
                elif "UnknownValueError" in name or "Could not understand" in msg:
                    on_error(
                        tr_msg(
                            normalized_lang,
                            "Nessun parlato chiaro rilevato. Riprova parlando più vicino al microfono.",
                            "No clear speech detected. Try speaking closer to the microphone.",
                        )
                    )
                elif "Invalid" in msg or "device" in msg.lower():
                    on_error(
                        tr_msg(
                            normalized_lang,
                            "Dispositivo microfono non rilevato o non accessibile.",
                            "Microphone device not found or inaccessible.",
                        )
                    )
                else:
                    on_error(
                        tr_msg(
                            normalized_lang,
                            f"Impossibile completare la trascrizione: {msg}",
                            f"Unable to complete transcription: {msg}",
                        )
                    )

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Interrompe immediatamente la registrazione e avvia subito la trascrizione."""
        if self._is_recording:
            self._stop_event.set()


def transcribe_from_microphone(
    on_result: Callable[[str], None],
    on_error: Callable[[str], None],
    on_listening: Callable[[], None],
    api_key: str = "",
    language: str = "it-IT",
) -> SpeechTranscriber:
    """Helper per avviare la trascrizione vocale restituendo l'istanza controllabile."""
    normalized_lang = _normalize_language(language)
    transcriber = SpeechTranscriber()
    transcriber.start(on_result, on_error, on_listening, api_key=api_key, language=normalized_lang)
    return transcriber
