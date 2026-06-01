"""Raccourci global + capture de la sélection (copie simulée) + presse-papiers.

Presse-papiers via Tkinter (stdlib) → pas de dépendance pyperclip. Comme Tkinter n'est pas
thread-safe, les accès sont marshalés sur le thread de la boucle Tk via root.after().
Seule branche OS du projet : le modificateur de copie (Cmd sur macOS, Ctrl ailleurs).
"""
from __future__ import annotations

import platform
import queue
import threading
import time
from typing import Callable

from pynput import keyboard

_IS_MAC = platform.system() == "Darwin"

# Touches modificatrices → token canonique attendu par pynput.GlobalHotKeys.
_MOD_TOKENS = {
    keyboard.Key.ctrl: "<ctrl>", keyboard.Key.ctrl_l: "<ctrl>", keyboard.Key.ctrl_r: "<ctrl>",
    keyboard.Key.alt: "<alt>", keyboard.Key.alt_l: "<alt>", keyboard.Key.alt_r: "<alt>",
    keyboard.Key.alt_gr: "<alt>",
    keyboard.Key.shift: "<shift>", keyboard.Key.shift_l: "<shift>", keyboard.Key.shift_r: "<shift>",
    keyboard.Key.cmd: "<cmd>", keyboard.Key.cmd_l: "<cmd>", keyboard.Key.cmd_r: "<cmd>",
}
_MOD_ORDER = ["<ctrl>", "<alt>", "<shift>", "<cmd>"]


def _key_token(key) -> str | None:
    """Token GlobalHotKeys d'une touche NON modificatrice ('s', '<f1>'…), ou None à ignorer."""
    if isinstance(key, keyboard.Key):
        return f"<{key.name}>"                       # f1, space, enter, esc…
    ch = getattr(key, "char", None)
    if ch and ch.isprintable() and ch != " ":
        return ch.lower()
    vk = getattr(key, "vk", None)                    # Ctrl+lettre : char vaut un car. de contrôle
    if vk is not None and (65 <= vk <= 90 or 48 <= vk <= 57):
        return chr(vk).lower()
    return None


class Clipboard:
    """Accès au presse-papiers système via Tkinter, exécuté sur le thread Tk (thread-safe)."""

    def __init__(self, root):
        self._root = root

    def get(self) -> str:
        box: "queue.Queue[str]" = queue.Queue()

        def _read() -> None:
            try:
                box.put(self._root.clipboard_get())
            except Exception:
                box.put("")  # presse-papiers vide ou contenu non textuel (image…)

        self._root.after(0, _read)
        try:
            return box.get(timeout=2)
        except queue.Empty:
            return ""

    def set(self, text: str) -> None:
        def _write() -> None:
            self._root.clipboard_clear()
            if text:
                self._root.clipboard_append(text)

        self._root.after(0, _write)


class HotkeyManager:
    """Enregistre les raccourcis globaux et orchestre la capture de la sélection."""

    def __init__(self, config: dict, clipboard: Clipboard,
                 on_speak: Callable[[str], None], on_stop: Callable[[], None]):
        self.config = config
        self.clipboard = clipboard
        self.on_speak = on_speak
        self.on_stop = on_stop
        self._kb = keyboard.Controller()
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        # Les callbacks tournent dans le thread du hook clavier : ils doivent être
        # ultra-brefs et NE PAS y simuler de touches (cela fige le hook sous Windows).
        # On délègue donc systématiquement le travail à un thread séparé.
        self._listener = keyboard.GlobalHotKeys({
            self.config.get("hotkey_speak", "<ctrl>+<alt>+s"):
                lambda: threading.Thread(target=self._do_speak, daemon=True).start(),
            self.config.get("hotkey_stop", "<ctrl>+<alt>+x"):
                lambda: threading.Thread(target=self.on_stop, daemon=True).start(),
        })
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    def restart(self) -> None:
        """Ré-enregistre les raccourcis depuis la config courante (après modification)."""
        self.stop()
        self.start()

    def record(self, on_done: Callable[[str | None], None]) -> None:
        """Capture la prochaine combinaison (modificateurs + une touche) et appelle
        on_done(combo) — ou on_done(None) si annulé via Échap.

        Les raccourcis actuels sont libérés le temps de la capture (l'appelant doit
        appeler restart() ensuite, que la capture aboutisse ou non).
        """
        self.stop()
        mods: list[str] = []
        holder: dict = {}

        def finish(combo: str | None) -> None:
            lst = holder.get("listener")
            if lst:
                lst.stop()
            on_done(combo)

        def on_press(key) -> bool | None:
            if key == keyboard.Key.esc:
                finish(None)
                return False
            tok = _MOD_TOKENS.get(key)
            if tok:
                if tok not in mods:
                    mods.append(tok)
                return None
            token = _key_token(key)
            if token is None:
                return None
            # Une touche simple sans modificateur ferait un raccourci global dangereux :
            # on n'accepte que (modificateur + touche) ou une touche spéciale seule (F1…).
            if not mods and not token.startswith("<"):
                return None
            ordered = [m for m in _MOD_ORDER if m in mods]
            finish("+".join(ordered + [token]))
            return False

        def on_release(key) -> None:
            tok = _MOD_TOKENS.get(key)
            if tok and tok in mods:
                mods.remove(tok)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        holder["listener"] = listener
        listener.start()

    def _do_speak(self) -> None:
        saved = self.clipboard.get()       # sauvegarde le presse-papiers de l'utilisateur
        text = self._copy_selection()
        self.clipboard.set(saved)          # …et le restaure aussitôt
        if text.strip():
            self.on_speak(text)

    def _copy_selection(self) -> str:
        mod = keyboard.Key.cmd if _IS_MAC else keyboard.Key.ctrl
        # L'utilisateur tient peut-être encore les touches du raccourci (ex. Alt) : on relâche
        # les modificateurs parasites pour que le Ctrl/Cmd+C synthétique soit propre.
        for k in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r,
                  keyboard.Key.alt_gr, keyboard.Key.shift, keyboard.Key.shift_r):
            try:
                self._kb.release(k)
            except Exception:
                pass
        time.sleep(0.03)
        with self._kb.pressed(mod):
            self._kb.press("c")
            self._kb.release("c")
        time.sleep(0.12)                   # laisse l'OS remplir le presse-papiers
        return self.clipboard.get()
