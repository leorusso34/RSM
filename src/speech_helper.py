#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modulo per il riconoscimento vocale tramite Google Speech API.
Usa sounddevice per la cattura dell'audio e permette l'interruzione immediata al riclic del microfono.
"""

import io
import threading
from typing import Callable, Optional


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
        max_duration: int = 15,
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
                on_error(f"Dipendenza mancante: {e}\nEsegui: pip install sounddevice scipy SpeechRecognition")
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
                wav_buffer.seek(0)

                # Riconoscimento vocale
                recognizer = sr.Recognizer()
                audio = sr.AudioData(wav_buffer.read(), sample_rate, 2)
                text = recognizer.recognize_google(audio, language=language)
                on_result(text)

            except Exception as e:
                self._is_recording = False
                name = type(e).__name__
                msg = str(e)
                if "UnknownValueError" in name or "Could not understand" in msg:
                    on_error("Non ho capito. Parla più chiaramente e riprova.")
                elif "RequestError" in name:
                    on_error(f"Errore connessione Google Speech: {msg}")
                elif "Invalid" in msg or "device" in msg.lower():
                    on_error("Microfono non trovato o non accessibile.")
                else:
                    on_error(f"Errore: {msg}")

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
    language: str = "it-IT"
) -> SpeechTranscriber:
    """Helper per avviare la trascrizione vocale restituendo l'istanza controllabile."""
    transcriber = SpeechTranscriber()
    transcriber.start(on_result, on_error, on_listening, language=language)
    return transcriber
