"""Point d'entrée : assemble config + moteur XTTS + GUI Tkinter + raccourci global + tray.

Boucle Tk dans le thread principal ; le modèle se charge en tâche de fond ; l'icône tray
tourne dans son propre thread (pystray bloque). Fermer la fenêtre la masque (l'app vit en fond).
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk

from config import load_config, save_config
from engine import TTSEngine
from gui import STRINGS, AppGUI
from hotkey import Clipboard, HotkeyManager


def _make_tray(gui: AppGUI, labels: dict, on_restart, on_quit):
    """Icône de zone de notification (pystray) — utilise le logo OpenVox."""
    import pystray
    from PIL import Image, ImageDraw

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        img = Image.open(icon_path)
    else:  # repli : petite bulle stylisée si l'asset manque
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse([6, 6, 58, 58], fill="#7c4dff")
    menu = pystray.Menu(
        pystray.MenuItem(labels["menu_open"], lambda *_: gui.show(), default=True),
        pystray.MenuItem(labels["menu_restart"], lambda *_: on_restart()),
        pystray.MenuItem(labels["menu_quit"], lambda *_: on_quit()),
    )
    return pystray.Icon("openvox", img, "OpenVox", menu)


def main() -> None:
    config = load_config()

    root = tk.Tk()
    engine = TTSEngine(config)
    gui = AppGUI(root, config, engine, save_config)
    engine.set_status_callback(gui.on_engine_status)

    clipboard = Clipboard(root)
    hotkeys = HotkeyManager(config, clipboard, on_speak=engine.speak, on_stop=engine.stop)
    gui.attach_hotkeys(hotkeys)  # permet d'éditer les raccourcis depuis la GUI
    hotkeys.start()

    # Chargement du modèle en tâche de fond : ne fige ni la GUI ni l'écoute du raccourci.
    threading.Thread(target=engine.load, daemon=True).start()

    state: dict = {}

    def _cleanup() -> None:
        try:
            hotkeys.stop()
        except Exception:
            pass
        tray = state.get("tray")
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass

    def quit_app() -> None:
        _cleanup()
        root.after(0, root.destroy)

    def restart_app() -> None:
        # Relance une nouvelle instance (même interpréteur) puis ferme l'actuelle.
        script = os.path.abspath(__file__)
        try:
            subprocess.Popen([sys.executable, script], cwd=os.path.dirname(script))
        except Exception:
            pass
        quit_app()

    gui.attach_restart(restart_app)

    labels = STRINGS.get(config.get("ui_language", "fr"), STRINGS["fr"])
    tray = _make_tray(gui, labels, on_restart=restart_app, on_quit=quit_app)
    state["tray"] = tray
    threading.Thread(target=tray.run, daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    main()
