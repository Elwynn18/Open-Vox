"""Lecture/écriture de config.json (le fichier édité par la GUI).

Principe du projet : aucune valeur en dur ailleurs — tout passe par config.json.
"""
from __future__ import annotations

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULTS: dict = {
    "language": "fr",                  # langue de synthèse (voir gui.LANGUAGES)
    "device": "auto",                  # auto | cpu | cuda  (toggle d'accélération)
    "active_voice": "",                # chemin vers un .wav de voices/
    "hotkey_speak": "<ctrl>+<alt>+s",  # raccourci : lire la sélection
    "hotkey_stop": "<ctrl>+<alt>+x",   # raccourci : stopper la lecture
    "temperature": 0.7,                # créativité de la synthèse XTTS
    "volume": 1.0,                     # gain de lecture 0.0–1.0 (curseur GUI)
    "theme": "light",                  # light | dark  (apparence de la GUI)
    "ui_language": "fr",               # fr | en | es  (langue de l'interface)
    "window_geometry": "",             # position mémorisée (la taille de la fenêtre est fixe)
}


def load_config() -> dict:
    """Charge config.json par-dessus les valeurs par défaut (tolérant aux erreurs)."""
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass  # config corrompue → on repart des défauts
    return cfg


def save_config(cfg: dict) -> None:
    """Écrit la config sur disque (appelé par la GUI à chaque changement)."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
