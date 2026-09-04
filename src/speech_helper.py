#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modulo per il riconoscimento vocale tramite Google Speech API e Google Gemini.
Usa sounddevice per la cattura dell'audio e permette l'interruzione immediata al riclic del microfono.
"""

import io
import threading
from typing import Callable, Optional


def _transcribe_with_gemini(wav_bytes: bytes, api_key: str) -> Optional[str]:
    """Tenta la trascrizione fedele dell'audio tramite l'API Gemini."""
    import base64
    import json
    import http.client

    try:
        b64_audio = base64.b64encode(wav_bytes).decode("utf-8")
        host = "generativelanguage.googleapis.com"
        path = f"/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"

        payload = {
            "contents": [{
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "audio/wav",
                            "data": b64_audio
                        }
                    },
                    {
                        "text": "Trascrivi esattamente e fedelmente le parole pronunciate in questo audio in lingua italiana. Restituisci SOLO ed esclusivamente il testo trascritto, senza virgolette, senza markdown e senza commenti."
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.0
            }
        }

        conn = http.client.HTTPSConnection(host, timeout=15)
        try:
            conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            if resp.status == 200:
                result = json.loads(resp.read().decode("utf-8"))
                if "candidates" in result and result["candidates"]:
                    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text:
                        return text
        finally:
            conn.close()
    except Exception:
        pass
    return None


class SpeechTranscriber:
    """Gestisce la registrazione audio e la trascrizione vocale con controllo di stop immediato."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._is_recording = False
        self._thread: Optional[threading.Thread] = None

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
        language: str = "it-IT"
    ) -> None:
        """Avvia la registrazione in background."""
        if self._is_recording:
            return

        self._stop_event.clear()
        self._is_recording = True

        def _run():
            try:
                import sounddevice as sd
                import numpy as np
                import scipy.io.wavfile as wav_io
                import speech_recognition as sr
            except ImportError as e:
                self._is_recording = False
                on_error(f"Dipendenza mancante: {e}")
                return

            frames = []

            def _audio_callback(indata, frame_count, time_info, status):
                if not self._stop_event.is_set():
                    frames.append(indata.copy())

            try:
                sample_rate = 16000
                on_listening()

                with sd.InputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype="int16",
                    callback=_audio_callback
                ):
                    self._stop_event.wait(timeout=max_duration)

                self._is_recording = False

                if not frames:
                    on_error("Nessun audio registrato.")
                    return

                audio_data = np.concatenate(frames, axis=0)

                # Converti in WAV in memoria
                wav_buffer = io.BytesIO()
                wav_io.write(wav_buffer, sample_rate, audio_data)
                wav_bytes = wav_buffer.getvalue()

                # 1. Prova prima con Gemini se la chiave API è configurata
                if api_key:
                    gemini_text = _transcribe_with_gemini(wav_bytes, api_key)
                    if gemini_text:
                        on_result(gemini_text)
                        return

                # 2. Fallback su Google Speech Recognition
                wav_buffer.seek(0)
                recognizer = sr.Recognizer()
                audio = sr.AudioData(wav_buffer.read(), sample_rate, 2)
                text = recognizer.recognize_google(audio, language=language)
                on_result(text)

            except Exception as e:
                self._is_recording = False
                name = type(e).__name__
                msg = str(e)
                if "11001" in msg or "getaddrinfo" in msg or "connection failed" in msg.lower() or "RequestError" in name:
                    on_error("Connessione internet non disponibile per il riconoscimento vocale. Puoi scrivere direttamente nel testo.")
                elif "UnknownValueError" in name or "Could not understand" in msg:
                    on_error("Nessun parlato chiaro rilevato. Riprova parlando più vicino al microfono.")
                elif "Invalid" in msg or "device" in msg.lower():
                    on_error("Dispositivo microfono non rilevato o non accessibile.")
                else:
                    on_error(f"Impossibile completare la trascrizione: {msg}")

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
    language: str = "it-IT"
) -> SpeechTranscriber:
    """Helper per avviare la trascrizione vocale restituendo l'istanza controllabile."""
    transcriber = SpeechTranscriber()
    transcriber.start(on_result, on_error, on_listening, api_key=api_key, language=language)
    return transcriber
