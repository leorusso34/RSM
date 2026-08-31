"""
Modulo per il riconoscimento vocale tramite Google Speech API.
Usa sounddevice (nessuna compilazione richiesta) + riconosce via HTTP direttamente.
"""
import threading
import io
import json
import http.client
import base64
from typing import Callable


def transcribe_from_microphone(
    on_result: Callable[[str], None],
    on_error: Callable[[str], None],
    on_listening: Callable[[], None],
    language: str = "it-IT"
) -> None:
    """
    Registra dal microfono e trascrive con Google Speech API (gratuita).
    Chiama on_listening() quando pronto, on_result(testo) con la trascrizione,
    on_error(msg) in caso di errore.
    """
    def _run():
        try:
            import sounddevice as sd
            import numpy as np
            import scipy.io.wavfile as wav_io
            import speech_recognition as sr
        except ImportError as e:
            on_error(f"Dipendenza mancante: {e}\nEsegui: pip install sounddevice scipy SpeechRecognition")
            return

        try:
            on_listening()

            sample_rate = 16000
            duration = 15  # secondi massimi di registrazione

            audio_data = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype="int16"
            )

            # Attendi il silenzio o il termine dei 6 secondi
            sd.wait()

            # Converti in WAV in memoria
            wav_buffer = io.BytesIO()
            wav_io.write(wav_buffer, sample_rate, audio_data)
            wav_buffer.seek(0)

            # Usa SpeechRecognition per riconoscere (senza PyAudio, solo AudioData)
            recognizer = sr.Recognizer()
            audio = sr.AudioData(wav_buffer.read(), sample_rate, 2)  # 2 bytes = int16
            text = recognizer.recognize_google(audio, language=language)
            on_result(text)

        except Exception as e:
            name = type(e).__name__
            msg = str(e)
            if "UnknownValueError" in name or "Could not understand" in msg:
                on_error("Non ho capito. Parla piu chiaramente e riprova.")
            elif "RequestError" in name:
                on_error(f"Errore connessione Google Speech: {msg}")
            elif "Invalid" in msg or "device" in msg.lower():
                on_error("Microfono non trovato o non accessibile.")
            else:
                on_error(f"Errore: {msg}")

    threading.Thread(target=_run, daemon=True).start()
