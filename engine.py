"""Moteur XTTS v2 : chargement du modèle, gestion des voix, synthèse en streaming.

100 % local. Voir XTTS-v2_setup_recap.md pour les pièges d'installation (Python 3.10,
torch 2.5.1, transformers<5.0, etc.). Le pipeline 2 threads (synth/play) est repris du recap.
"""
from __future__ import annotations

import os
# COQUI_TOS_AGREED doit être posé AVANT d'importer TTS, sinon prompt licence interactif
# qui bloque en non-interactif (recap §⑤).
os.environ.setdefault("COQUI_TOS_AGREED", "1")

import queue
import re
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
SAMPLE_RATE = 24000        # XTTS v2 sort en 24 kHz
END_SILENCE_S = 0.35       # ~350 ms de respiration concaténés en fin de phrase (recap §5)

MAX_SAMPLE_S = 40.0        # au-delà, l'embedding speaker XTTS se dilue (recap §4)
TARGET_SAMPLE_S = 30.0     # longueur visée de l'extrait central après redécoupe

# Acronymes prononçables : on ne les épelle PAS (le reste : "LLM" -> "L L M").
_ACRONYM_KEEP = {"NASA", "OTAN", "UNESCO", "OVNI", "SIDA", "RADAR", "LASER",
                 "OPEP", "FIFA", "UEFA"}


def resolve_device(pref: str) -> tuple[str, str]:
    """Résout le device à partir du réglage. Retourne (device, clé d'info traduite côté GUI)."""
    import torch
    if pref == "cpu":
        return "cpu", "dev_cpu"
    if torch.cuda.is_available():
        return "cuda", "dev_gpu"
    if pref == "cuda":
        return "cpu", "dev_gpu_fallback"
    return "cpu", "dev_no_gpu"


# ----------------------------- pré-traitement texte -----------------------------

def _spell_acronyms(text: str) -> str:
    def repl(m: re.Match) -> str:
        w = m.group(0)
        return w if w in _ACRONYM_KEEP else " ".join(w)
    return re.sub(r"\b[A-Z]{2,}\b", repl, text)


def clean_for_synthesis(text: str) -> str:
    """Filet de sécurité : retire le Markdown courant, normalise, épelle les acronymes."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)   # [texte](url) -> texte
    text = re.sub(r"[*_`#>]+", " ", text)                  # gras/italique/code/titres/citations
    text = re.sub(r"[ \t]+", " ", text)
    return _spell_acronyms(text).strip()


def split_sentences(text: str) -> list[str]:
    """Découpe en phrases : XTTS a besoin d'unités sémantiques complètes pour la prosodie."""
    out: list[str] = []
    for part in re.split(r"(?<=[.!?])\s+|\n{2,}", text):
        part = part.strip()
        if not part:
            continue
        # Retire le « . » / « : » final (sinon XTTS prononce parfois « point »). On garde ? et !.
        part = re.sub(r"[.:]+$", "", part).strip()
        if part:
            out.append(part)
    return out


# ------------------------- préparation d'un échantillon -------------------------

def prepare_sample(src_path: str, dst_path: str) -> list[str]:
    """Écrit src_path vers dst_path en le ramenant en mono et en le redécoupant
    sur un extrait central de TARGET_SAMPLE_S s'il dépasse MAX_SAMPLE_S.

    Retourne la liste des opérations effectuées ("mono", "trimmed") pour affichage GUI.
    """
    import soundfile as sf

    data, sr = sf.read(src_path, dtype="float32")
    ops: list[str] = []
    if data.ndim > 1:                              # stéréo (ou plus) → mono
        data = data.mean(axis=1)
        ops.append("mono")
    if len(data) / sr > MAX_SAMPLE_S:              # trop long → extrait central
        keep = int(TARGET_SAMPLE_S * sr)
        start = (len(data) - keep) // 2
        data = data[start:start + keep]
        ops.append("trimmed")
    sf.write(dst_path, data, sr)
    return ops


# ----------------------------------- moteur -----------------------------------

class TTSEngine:
    """Charge XTTS, gère la voix active, synthétise et joue le texte sans figer la GUI."""

    def __init__(self, config: dict):
        self.config = config
        # Callback de statut : reçoit une CLÉ + des paramètres (la GUI traduit). Découple
        # le moteur de toute langue d'affichage.
        self._on_status: Callable[[str, dict], None] = lambda key, params: None
        self.ready = False
        self.device = "cpu"

        self._model = None
        self._lock = threading.Lock()        # protège les latents de la voix
        self._gpt_cond = None
        self._speaker_emb = None
        self.current_voice = ""

        self._stop = threading.Event()
        self._synth_q: "queue.Queue" = queue.Queue()
        self._play_q: "queue.Queue" = queue.Queue()
        threading.Thread(target=self._synth_loop, daemon=True).start()
        threading.Thread(target=self._play_loop, daemon=True).start()

    def set_status_callback(self, cb: Callable[[str, dict], None]) -> None:
        self._on_status = cb

    def _emit(self, key: str, **params) -> None:
        self._on_status(key, params)

    # ---- chargement (lourd : à lancer dans un thread depuis main) ----
    def load(self) -> None:
        try:
            self._emit("loading")
            self.device, info = resolve_device(self.config.get("device", "auto"))
            from TTS.api import TTS  # import tardif : laisse la GUI s'afficher d'abord
            tts = TTS(MODEL_NAME).to(self.device)
            self._model = tts.synthesizer.tts_model
            self.ready = True
            voice = self.config.get("active_voice", "")
            if voice and os.path.exists(voice):
                self.set_voice(voice)
            else:
                self._emit("ready_no_voice", info=info)
        except Exception as e:  # noqa: BLE001 — on remonte toute erreur dans la GUI
            self._emit("load_error", err=str(e))

    def set_voice(self, wav_path: str) -> None:
        """Recalcule l'embedding speaker (coûteux) — fait UNE fois par voix, pas par phrase."""
        if not self.ready:
            return
        try:
            self._emit("analyzing")
            gpt, spk = self._model.get_conditioning_latents(audio_path=[wav_path])
            with self._lock:
                self._gpt_cond, self._speaker_emb = gpt, spk
                self.current_voice = wav_path
            self._warmup()
            self._emit("voice_ready", voice=os.path.basename(wav_path), device=self.device)
        except Exception as e:  # noqa: BLE001
            self._emit("voice_invalid", err=str(e))

    def _warmup(self) -> None:
        """Synthèse à blanc pour absorber le cold-start (gain ~2 s au 1er vrai prompt)."""
        try:
            with self._lock:
                gpt, spk = self._gpt_cond, self._speaker_emb
            self._model.inference(text="Bonjour.", language=self.config.get("language", "fr"),
                                  gpt_cond_latent=gpt, speaker_embedding=spk, temperature=0.7)
        except Exception:
            pass

    def has_voice(self) -> bool:
        return self._speaker_emb is not None

    def clear_voice(self) -> None:
        """Oublie la voix chargée (ex. après suppression de son fichier)."""
        with self._lock:
            self._gpt_cond = None
            self._speaker_emb = None
            self.current_voice = ""

    # ---- API publique (appelée depuis le thread du raccourci) ----
    def speak(self, text: str) -> None:
        if not self.ready:
            self._emit("not_ready")
            return
        if not self.has_voice():
            self._emit("no_voice")
            return
        self._stop.clear()
        for sentence in split_sentences(clean_for_synthesis(text)):
            self._synth_q.put(sentence)

    def stop(self) -> None:
        self._stop.set()
        _drain(self._synth_q)
        _drain(self._play_q)
        sd.stop()

    # ---- threads ----
    def _synth_loop(self) -> None:
        silence = np.zeros(int(SAMPLE_RATE * END_SILENCE_S), dtype=np.float32)
        while True:
            sentence = self._synth_q.get()
            try:
                if self._stop.is_set():
                    continue
                with self._lock:
                    gpt, spk = self._gpt_cond, self._speaker_emb
                out = self._model.inference(
                    text=sentence, language=self.config.get("language", "fr"),
                    gpt_cond_latent=gpt, speaker_embedding=spk,
                    temperature=float(self.config.get("temperature", 0.7)),
                )
                wav = np.concatenate([np.asarray(out["wav"], dtype=np.float32), silence])
                if not self._stop.is_set():
                    self._play_q.put(wav)
            except Exception as e:  # noqa: BLE001
                self._emit("synth_error", err=str(e))
            finally:
                self._synth_q.task_done()

    def _play_loop(self) -> None:
        while True:
            wav = self._play_q.get()
            try:
                if not self._stop.is_set():
                    sd.play(wav, samplerate=SAMPLE_RATE, blocking=True)
            except Exception as e:  # noqa: BLE001 — surtout pas tuer le thread de lecture
                self._emit("play_error", err=str(e))
            finally:
                self._play_q.task_done()


def _drain(q: "queue.Queue") -> None:
    """Vide une file sans bloquer (utilisé par stop())."""
    try:
        while True:
            q.get_nowait()
            q.task_done()
    except queue.Empty:
        pass
