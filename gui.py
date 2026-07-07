"""Fenêtre OpenVox — design **glassmorphisme** moderne, rendu 100 % stdlib + Pillow.

Tkinter n'a pas de transparence/flou natifs : on compose donc toute l'UI avec Pillow
(fond dégradé + blobs floutés, carte en verre dépoli, ombre douce) affichée sur un Canvas,
et des contrôles arrondis dessinés à la main (boutons pilule, sélecteurs, slider). Le texte
statique est « cuit » dans l'image (net, parfaitement fondu au verre) ; les contrôles et les
textes dynamiques (statut, %) sont des widgets Canvas posés par-dessus.

Mode clair / sombre (bouton ☀/☾) et interface fr/en/es. Le moteur n'émet que des CLÉS de
statut ; la traduction est faite ici. Changer de thème/langue ou redimensionner re-rend tout.
L'app vit en tâche de fond (tray géré par main.py).
"""
from __future__ import annotations

import math
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

from engine import TARGET_SAMPLE_S, prepare_sample

HERE = os.path.dirname(__file__)
VOICES_DIR = os.path.join(HERE, "voices")
ASSETS_DIR = os.path.join(HERE, "assets")

LANGUAGES = ["fr", "en", "es", "de", "it", "pt", "pl", "tr", "ru", "nl",
             "cs", "ar", "zh-cn", "hu", "ko", "ja", "hi"]
DEVICES = ["auto", "cpu", "cuda"]
UI_LANGS = {"fr": "Français", "en": "English", "es": "Español"}

CARD_W = 420          # largeur fixe de la carte (centrée) ; la fenêtre peut varier autour
PAD = 22              # marge intérieure de la carte
HEADER_H = 126        # hauteur de la zone « hero » (logo + titre) au-dessus de la carte
RADIUS = 26           # rayon des coins de la carte
CTRL_R = 12           # rayon des contrôles (champs, boutons)

# Palettes glassmorphisme (clair / sombre). Les couleurs de dégradé/blobs sont des RGB ;
# 'glass'/'border' des RGBA (translucides) ; le reste des hex pour Tk/Pillow.
THEMES = {
    "light": {
        "grad_top": (238, 235, 255), "grad_bot": (255, 236, 246),
        "blobs": [((124, 77, 255), 120), ((80, 150, 255), 110), ((255, 130, 190), 110)],
        "glass": (255, 255, 255, 150), "border": (255, 255, 255, 210),
        "fg": "#22243a", "muted": "#6f7285",
        "accent": "#7c4dff", "accent_dk": "#6636e0", "on_accent": "#ffffff",
        "input": "#ffffff", "input_bd": (124, 100, 210, 90), "input_fg": "#22243a",
        "sec": "#ffffff", "sec_fg": "#4a4d63",
        "track": (210, 206, 230), "knob": "#ffffff",
        "ready": "#12a06e", "error": "#dd4d64", "working": "#d4872a",
        "menu_bg": "#ffffff", "menu_fg": "#22243a", "shadow": 55,
    },
    "dark": {
        "grad_top": (26, 19, 48), "grad_bot": (12, 22, 44),
        "blobs": [((124, 77, 255), 150), ((70, 110, 255), 130), ((190, 77, 255), 120)],
        "glass": (255, 255, 255, 26), "border": (255, 255, 255, 46),
        "fg": "#eef0f8", "muted": "#a4a8bd",
        "accent": "#8b6cff", "accent_dk": "#7a5bf5", "on_accent": "#ffffff",
        "input": "#2a2c3a", "input_bd": (255, 255, 255, 40), "input_fg": "#eef0f8",
        "sec": "#33364a", "sec_fg": "#dfe2ee",
        "track": (74, 78, 100), "knob": "#ffffff",
        "ready": "#2ec48b", "error": "#ef6b80", "working": "#f0ad4e",
        "menu_bg": "#22243250", "menu_fg": "#eef0f8", "shadow": 120,
    },
}

ENGINE_LEVELS = {
    "ready_no_voice": "ready", "voice_ready": "ready",
    "voice_invalid": "error", "load_error": "error", "no_voice": "error",
    "synth_error": "error", "play_error": "error",
}

STRINGS = {
    "fr": {
        "subtitle": "Lecture de la sélection à voix haute",
        "voice_active": "Voix", "import_btn": "Importer un échantillon",
        "playback": "Lecture",
        "reading_lang": "Langue de lecture", "accel": "Accélération", "volume": "Volume",
        "shortcuts": "Raccourcis", "read": "Lire", "stop": "Stop", "modify": "Modifier",
        "delete": "Supprimer", "delete_confirm": "Supprimer la voix « {name} » ?",
        "deleted": "Voix supprimée : {name}.", "delete_failed": "Suppression impossible : {err}",
        "restart_btn": "Redémarrer l'application",
        "menu_open": "Ouvrir", "menu_restart": "Redémarrer", "menu_quit": "Quitter",
        "interface": "Interface", "theme": "Thème", "theme_light": "Clair",
        "theme_dark": "Sombre", "ui_lang": "Langue",
        "init": "Initialisation…",
        "accel_changed": "Accélération modifiée — prise en compte au prochain démarrage.",
        "press_combo": "Appuyez sur la combinaison voulue (Échap pour annuler).",
        "cancelled": "Modification annulée.",
        "shortcut_saved": "Raccourci « {combo} » enregistré.",
        "imported": "Échantillon importé ({note}).", "import_failed": "Import impossible : {err}",
        "op_mono": "converti en mono", "op_trimmed": "redécoupé au centre à {s} s",
        "status": {
            "loading": "Chargement du modèle XTTS… (1er lancement : téléchargement ~1,8 Go)",
            "ready_no_voice": "Prêt. {info} Importez une voix pour commencer.",
            "analyzing": "Analyse de la voix…",
            "voice_ready": "Voix prête : {voice} ({device}).",
            "voice_invalid": "Voix invalide : {err}",
            "load_error": "Erreur de chargement : {err}",
            "not_ready": "Modèle pas encore prêt.",
            "no_voice": "Aucune voix chargée — importez un .wav.",
            "synth_error": "Erreur de synthèse : {err}",
            "play_error": "Erreur de lecture audio : {err}",
            "dev_cpu": "Mode CPU.", "dev_gpu": "GPU CUDA détecté.",
            "dev_gpu_fallback": "GPU demandé mais CUDA indisponible → repli CPU.",
            "dev_no_gpu": "Pas de GPU CUDA → CPU.",
        },
    },
    "en": {
        "subtitle": "Read your text selection aloud",
        "voice_active": "Voice", "import_btn": "Import a sample",
        "playback": "Playback",
        "reading_lang": "Reading language", "accel": "Acceleration", "volume": "Volume",
        "shortcuts": "Shortcuts", "read": "Read", "stop": "Stop", "modify": "Change",
        "delete": "Delete", "delete_confirm": "Delete voice “{name}”?",
        "deleted": "Voice deleted: {name}.", "delete_failed": "Delete failed: {err}",
        "restart_btn": "Restart the app",
        "menu_open": "Open", "menu_restart": "Restart", "menu_quit": "Quit",
        "interface": "Interface", "theme": "Theme", "theme_light": "Light",
        "theme_dark": "Dark", "ui_lang": "Language",
        "init": "Initializing…",
        "accel_changed": "Acceleration changed — applied on next start.",
        "press_combo": "Press the desired key combination (Esc to cancel).",
        "cancelled": "Change cancelled.",
        "shortcut_saved": "Shortcut “{combo}” saved.",
        "imported": "Sample imported ({note}).", "import_failed": "Import failed: {err}",
        "op_mono": "converted to mono", "op_trimmed": "trimmed to a central {s} s",
        "status": {
            "loading": "Loading the XTTS model… (first run: ~1.8 GB download)",
            "ready_no_voice": "Ready. {info} Import a voice to begin.",
            "analyzing": "Analyzing the voice…",
            "voice_ready": "Voice ready: {voice} ({device}).",
            "voice_invalid": "Invalid voice: {err}",
            "load_error": "Loading error: {err}",
            "not_ready": "Model not ready yet.",
            "no_voice": "No voice loaded — import a .wav.",
            "synth_error": "Synthesis error: {err}",
            "play_error": "Audio playback error: {err}",
            "dev_cpu": "CPU mode.", "dev_gpu": "CUDA GPU detected.",
            "dev_gpu_fallback": "GPU requested but CUDA unavailable → CPU fallback.",
            "dev_no_gpu": "No CUDA GPU → CPU.",
        },
    },
    "es": {
        "subtitle": "Lee en voz alta el texto seleccionado",
        "voice_active": "Voz", "import_btn": "Importar una muestra",
        "playback": "Reproducción",
        "reading_lang": "Idioma de lectura", "accel": "Aceleración", "volume": "Volumen",
        "shortcuts": "Atajos", "read": "Leer", "stop": "Parar", "modify": "Cambiar",
        "delete": "Eliminar", "delete_confirm": "¿Eliminar la voz «{name}»?",
        "deleted": "Voz eliminada: {name}.", "delete_failed": "Error al eliminar: {err}",
        "restart_btn": "Reiniciar la aplicación",
        "menu_open": "Abrir", "menu_restart": "Reiniciar", "menu_quit": "Salir",
        "interface": "Interfaz", "theme": "Tema", "theme_light": "Claro",
        "theme_dark": "Oscuro", "ui_lang": "Idioma",
        "init": "Inicializando…",
        "accel_changed": "Aceleración modificada — se aplicará al reiniciar.",
        "press_combo": "Pulsa la combinación deseada (Esc para cancelar).",
        "cancelled": "Cambio cancelado.",
        "shortcut_saved": "Atajo «{combo}» guardado.",
        "imported": "Muestra importada ({note}).", "import_failed": "Error de importación: {err}",
        "op_mono": "convertida a mono", "op_trimmed": "recortada a {s} s centrales",
        "status": {
            "loading": "Cargando el modelo XTTS… (primer inicio: descarga ~1,8 GB)",
            "ready_no_voice": "Listo. {info} Importa una voz para empezar.",
            "analyzing": "Analizando la voz…",
            "voice_ready": "Voz lista: {voice} ({device}).",
            "voice_invalid": "Voz no válida: {err}",
            "load_error": "Error de carga: {err}",
            "not_ready": "El modelo aún no está listo.",
            "no_voice": "Ninguna voz cargada — importa un .wav.",
            "synth_error": "Error de síntesis: {err}",
            "play_error": "Error de reproducción de audio: {err}",
            "dev_cpu": "Modo CPU.", "dev_gpu": "GPU CUDA detectada.",
            "dev_gpu_fallback": "GPU solicitada pero CUDA no disponible → CPU.",
            "dev_no_gpu": "Sin GPU CUDA → CPU.",
        },
    },
}


# ============================ helpers de rendu (Pillow) ============================

_FONT_CACHE: dict = {}


def _font(size: int, weight: str = "regular"):
    """Charge Segoe UI à la taille voulue (px), avec repli sur la police par défaut."""
    key = (size, weight)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    files = {"regular": ["segoeui.ttf"], "semibold": ["seguisb.ttf", "segoeuib.ttf"],
             "bold": ["segoeuib.ttf", "seguisb.ttf"]}[weight]
    font = None
    for name in files:
        try:
            font = ImageFont.truetype(name, size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def _vgrad(w: int, h: int, top, bot) -> Image.Image:
    """Dégradé vertical rapide (colonne 1×h agrandie)."""
    col = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        col.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return col.resize((w, h))


def _backdrop(w: int, h: int, C: dict) -> Image.Image:
    """Fond dégradé + blobs colorés floutés (l'arrière-plan « derrière le verre »)."""
    bg = _vgrad(w, h, C["grad_top"], C["grad_bot"]).convert("RGBA")
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    spots = [(0.16, 0.10), (0.92, 0.24), (0.20, 0.85)]     # positions relatives des blobs
    rad = int(max(w, h) * 0.42)
    for (color, alpha), (rx, ry) in zip(C["blobs"], spots):
        cx, cy = int(w * rx), int(h * ry)
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(*color, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(int(max(w, h) * 0.11)))
    return Image.alpha_composite(bg, layer)


def _rrect(size, radius, fill=None, outline=None, width=1) -> Image.Image:
    """Rectangle arrondi anti-crénelé (fill et/ou contour), RGBA."""
    w, h = size
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill,
                        outline=outline, width=width)
    return im


def _frost_card(backdrop: Image.Image, x, y, w, h, C) -> tuple[int, int, int]:
    """Pose une ombre douce + une carte en verre dépoli sur `backdrop` (modifié en place).
    Retourne la couleur RGB moyenne du verre (fond des widgets posés dessus)."""
    # Ombre portée : rectangle sombre flouté, légèrement décalé vers le bas.
    shadow = Image.new("RGBA", backdrop.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x + 3, y + 10, x + w + 3, y + h + 10], radius=RADIUS, fill=(20, 12, 40, C["shadow"]))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    backdrop.alpha_composite(shadow)
    # Verre = zone d'arrière-plan floutée + voile translucide + bordure claire, masqué arrondi.
    patch = backdrop.crop((x, y, x + w, y + h)).filter(ImageFilter.GaussianBlur(18))
    glass = Image.alpha_composite(patch, Image.new("RGBA", (w, h), C["glass"]))
    glass = Image.alpha_composite(glass, _rrect((w, h), RADIUS, outline=C["border"], width=1))
    # Léger halo lumineux en haut (effet reflet).
    sheen = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sheen).rounded_rectangle([0, 0, w - 1, int(h * 0.5)], radius=RADIUS,
                                            fill=(255, 255, 255, 14))
    glass = Image.alpha_composite(glass, sheen)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=RADIUS, fill=255)
    glass.putalpha(mask)
    backdrop.alpha_composite(glass, (x, y))
    cx, cy = w // 2, h // 2
    return backdrop.crop((x + cx - 20, y + cy - 20, x + cx + 20, y + cy + 20)) \
                   .convert("RGB").resize((1, 1)).getpixel((0, 0))


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % rgb[:3]


# ============================ widgets custom (Canvas) ============================

class GlassButton(tk.Canvas):
    """Bouton arrondi dessiné (Pillow) : 'primary' (accent), 'ghost' (verre), 'icon'.
    `plus=True` préfixe un « + » vectoriel ; `icon` ∈ {"sun","moon"} dessine une icône
    (on ne s'appuie pas sur des glyphes Unicode : Pillow n'a pas de repli de police)."""

    def __init__(self, parent, text, command, w, h, C, bg, kind="primary", size=14,
                 plus=False, icon=None):
        super().__init__(parent, width=w, height=h, highlightthickness=0, bd=0, bg=bg)
        self.text, self.command, self.w, self.h = text, command, w, h
        self.C, self.kind, self.size = C, kind, size
        self.plus, self.icon, self.bg = plus, icon, bg
        self.bind("<Button-1>", lambda _e: self.command())
        self.bind("<Enter>", lambda _e: self._render(True))
        self.bind("<Leave>", lambda _e: self._render(False))
        self.configure(cursor="hand2")
        self._render(False)

    def _render(self, hover: bool) -> None:
        C, w, h = self.C, self.w, self.h
        if self.kind == "primary":
            fill = C["accent_dk"] if hover else C["accent"]
            img = _rrect((w, h), min(CTRL_R, h // 2), fill=_rgba(fill))
            fg, weight = C["on_accent"], "semibold"
        elif self.kind == "icon":
            img = _rrect((w, h), h // 2, fill=_rgba(C["input"], 64 if hover else 34))
            fg, weight = (C["accent"] if hover else C["muted"]), "regular"
        else:  # ghost
            fill = _rgba(C["sec"], 235 if hover else 200)
            img = _rrect((w, h), min(CTRL_R, h // 2), fill=fill, outline=C["input_bd"], width=1)
            fg, weight = C["fg"], "semibold"
        d = ImageDraw.Draw(img)
        if self.icon == "sun":
            self._sun(d, w // 2, h // 2, fg)
        elif self.icon == "moon":
            self._moon(d, w // 2, h // 2, fg)
        else:
            font = _font(self.size, weight)
            tx = w // 2
            if self.plus:                          # « + » vectoriel à gauche du texte
                tw = d.textlength(self.text, font=font)
                px = int((w - (tw + 22)) / 2) + 7
                d.line([px - 7, h // 2, px + 1, h // 2], fill=fg, width=2)
                d.line([px - 3, h // 2 - 4, px - 3, h // 2 + 4], fill=fg, width=2)
                tx = px + 14
                d.text((tx, h // 2), self.text, font=font, fill=fg, anchor="lm")
            else:
                d.text((tx, h // 2), self.text, font=font, fill=fg, anchor="mm")
        self._photo = ImageTk.PhotoImage(img)
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._photo)

    @staticmethod
    def _sun(d, cx, cy, color) -> None:
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=color)
        for a in range(0, 360, 45):
            dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
            d.line([cx + dx * 7, cy + dy * 7, cx + dx * 9.5, cy + dy * 9.5], fill=color, width=2)

    def _moon(self, d, cx, cy, color) -> None:
        d.ellipse([cx - 6, cy - 7, cx + 6, cy + 5], fill=color)          # disque plein
        d.ellipse([cx - 2, cy - 8, cx + 10, cy + 4], fill=self.bg)       # évidé → croissant


class GlassSelect(tk.Canvas):
    """Sélecteur arrondi maison : champ + chevron ; clic → menu natif (coins arrondis Win11).
    `readonly=True` en fait une simple puce d'affichage (raccourcis)."""

    def __init__(self, parent, values, value, on_change, w, h, C, bg,
                 readonly=False, size=13):
        super().__init__(parent, width=w, height=h, highlightthickness=0, bd=0, bg=bg)
        self.values, self.value, self.on_change = list(values), value, on_change
        self.w, self.h, self.C, self.readonly, self.size = w, h, C, readonly, size
        if not readonly:
            self.bind("<Button-1>", self._open)
            self.bind("<Enter>", lambda _e: self._render(True))
            self.bind("<Leave>", lambda _e: self._render(False))
            self.configure(cursor="hand2")
        self._render(False)

    def set_values(self, values) -> None:
        self.values = list(values)

    def set(self, value) -> None:
        self.value = value
        self._render(False)

    def _render(self, hover: bool) -> None:
        C, w, h = self.C, self.w, self.h
        bd = _rgba_t(C["input_bd"]) if not hover else _rgba(C["accent"], 200)
        img = _rrect((w, h), CTRL_R, fill=_rgba(C["input"]), outline=bd, width=1)
        d = ImageDraw.Draw(img)
        d.text((14, h // 2), str(self.value), font=_font(self.size), fill=C["input_fg"],
               anchor="lm")
        if not self.readonly:                       # chevron vectoriel à droite
            cx, cy = w - 17, h // 2 - 1
            d.line([cx - 4, cy - 2, cx, cy + 2], fill=C["muted"], width=2)
            d.line([cx, cy + 2, cx + 4, cy - 2], fill=C["muted"], width=2)
        self._photo = ImageTk.PhotoImage(img)
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._photo)

    def _open(self, _e) -> None:
        C = self.C
        m = tk.Menu(self, tearoff=0, bg=_hex6(C["menu_bg"]), fg=C["menu_fg"],
                    activebackground=C["accent"], activeforeground=C["on_accent"],
                    bd=0, relief="flat", font=("Segoe UI", 10))
        for v in self.values:
            m.add_command(label=v, command=lambda vv=v: self._pick(vv))
        try:
            m.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.h + 2)
        finally:
            m.grab_release()

    def _pick(self, v) -> None:
        if v != self.value:
            self.value = v
            self._render(False)
            self.on_change(v)


class Slider(tk.Canvas):
    """Curseur : piste + remplissage accent + pastille, avec le % à droite. bg = verre."""

    def __init__(self, parent, value, on_change, on_release, w, h, C, bg, valvar):
        super().__init__(parent, width=w, height=h, highlightthickness=0, bd=0, bg=bg)
        self.value = max(0.0, min(1.0, value))
        self.on_change, self.on_release = on_change, on_release
        self.C, self.w, self.h, self.valvar = C, w, h, valvar
        self._pad = 9
        self.bind("<Button-1>", self._set)
        self.bind("<B1-Motion>", self._set)
        self.bind("<ButtonRelease-1>", lambda _e: self.on_release())
        self._render()

    def set(self, value) -> None:
        self.value = max(0.0, min(1.0, value))
        self._render()

    def _render(self) -> None:
        C, w, h = self.C, self.w, self.h
        self.delete("all")
        cy = h // 2
        x0, x1 = self._pad, w - self._pad
        kx = x0 + (x1 - x0) * self.value
        self._bar(x0, x1, cy, _hex(C["track"]))
        if kx > x0:
            self._bar(x0, kx, cy, C["accent"])
        kr = 8
        self.create_oval(kx - kr, cy - kr, kx + kr, cy + kr, fill=C["knob"],
                         outline=C["accent"], width=2)

    def _bar(self, x0, x1, cy, color) -> None:
        r = 3
        self.create_rectangle(x0, cy - r, x1, cy + r, fill=color, width=0)
        self.create_oval(x0 - r, cy - r, x0 + r, cy + r, fill=color, width=0)
        self.create_oval(x1 - r, cy - r, x1 + r, cy + r, fill=color, width=0)

    def _set(self, e) -> None:
        x0, x1 = self._pad, self.w - self._pad
        self.value = max(0.0, min(1.0, (e.x - x0) / max(1, x1 - x0)))
        self._render()
        self.on_change(self.value)


def _rgba(hexstr: str, alpha: int = 255):
    hexstr = hexstr.lstrip("#")[:6]
    return (int(hexstr[0:2], 16), int(hexstr[2:4], 16), int(hexstr[4:6], 16), alpha)


def _rgba_t(rgba):  # passe un tuple RGBA tel quel
    return tuple(rgba)


def _hex6(hexstr: str) -> str:
    """Tk n'accepte pas #rrggbbaa : on retombe sur les 6 premiers hex."""
    return "#" + hexstr.lstrip("#")[:6]


# ==================================== AppGUI ====================================

class AppGUI:
    def __init__(self, root: tk.Tk, config: dict, engine, save_config):
        self.root = root
        self.config = config
        self.engine = engine
        self.save_config = save_config
        self.hotkeys = None
        self._restart_cb = None
        self._last_status = None          # ("engine", key, params) | ("text", text, level)
        self._widgets: list = []          # widgets Canvas posés (détruits à chaque rendu)
        os.makedirs(VOICES_DIR, exist_ok=True)

        root.title("OpenVox")
        _, card_h = self._layout()
        total_h = HEADER_H + card_h + 16          # hauteur qui fait tenir tout le contenu
        root.resizable(False, False)              # taille fixe (non redimensionnable)
        # On ne restaure QUE la position (la taille est figée) : rouvrir au même endroit.
        saved = self.config.get("window_geometry") or ""
        pos = next((saved[i:] for i, ch in enumerate(saved) if ch in "+-"), "")
        geo = f"470x{total_h}{pos}"
        root.geometry(geo)
        self._geom = geo
        self._set_window_icon()
        root.protocol("WM_DELETE_WINDOW", self.hide)

        self.canvas = tk.Canvas(root, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._bg_photo = None

        w, h = self._parse_geo(geo)
        self._render_all(w, h)
        root.bind("<Configure>", self._on_configure)

    @staticmethod
    def _parse_geo(geo: str) -> tuple[int, int]:
        try:
            size = geo.split("+")[0]
            w, h = size.split("x")
            return int(w), int(h)
        except Exception:
            return 470, 812

    # ------------------------------ rendu complet ------------------------------
    def _render_all(self, w: int, h: int) -> None:
        """Compose tout le fond (dégradé + carte verre + textes cuits) puis pose les widgets."""
        self.ui_lang = self.config.get("ui_language", "fr")
        if self.ui_lang not in STRINGS:
            self.ui_lang = "fr"
        self.theme = self.config.get("theme", "light")
        if self.theme not in THEMES:
            self.theme = "light"
        self.T, self.C = STRINGS[self.ui_lang], THEMES[self.theme]
        C, T = self.C, self.T

        for wdg in self._widgets:
            wdg.destroy()
        self._widgets.clear()
        self.canvas.delete("all")

        L, card_h = self._layout()
        card_x = (w - CARD_W) // 2
        card_y = HEADER_H
        self._card_x, self._card_y = card_x, card_y

        img = _backdrop(w, h, C)
        self._draw_header(img, w, card_y, C, T)
        self.glass_rgb = _frost_card(img, card_x, card_y, CARD_W, card_h, C)
        glass_bg = _hex(self.glass_rgb)
        self._bake_labels(img, card_x, card_y, L, C, T)

        self._bg_photo = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self._bg_photo)

        self._place_widgets(L, card_x, card_y, glass_bg, C, T)
        self._draw_toggle(img, w, C)

        # ré-affiche le statut courant traduit
        last = self._last_status
        if last and last[0] == "engine":
            self.on_engine_status(last[1], last[2])
        elif last:
            self._status(last[1], last[2])
        else:
            self._status(T["init"], "working")

    def _layout(self) -> tuple[dict, int]:
        """Positions (x, y, w, h) des éléments, relatives au coin de la carte, + hauteur carte."""
        cw = CARD_W - 2 * PAD
        half = (cw - 14) // 2
        midx = PAD + half + 14
        L: dict = {}
        y = PAD
        # VOIX
        L["lbl_voice"] = (PAD, y); y += 20
        L["voice"] = (PAD, y, cw - 102, 40)
        L["delete"] = (PAD + cw - 92, y, 92, 40); y += 40 + 10
        L["import"] = (PAD, y, cw, 42); y += 42 + 14
        L["div1"] = (PAD, y); y += 16
        # LECTURE
        L["lbl_play"] = (PAD, y); y += 20
        L["lbl_lang"] = (PAD, y); L["lbl_accel"] = (midx, y); y += 18
        L["lang"] = (PAD, y, half, 40); L["accel"] = (midx, y, half, 40); y += 40 + 12
        L["lbl_vol"] = (PAD, y); L["vol_pct"] = (PAD + cw, y); y += 20
        L["vol"] = (PAD, y, cw, 28); y += 28 + 16
        L["div2"] = (PAD, y); y += 16
        # RACCOURCIS
        L["lbl_sc"] = (PAD, y); y += 20
        L["read"] = (PAD, y, cw, 36); y += 36 + 8
        L["stop"] = (PAD, y, cw, 36); y += 36 + 16
        L["div3"] = (PAD, y); y += 16
        # INTERFACE
        L["lbl_if"] = (PAD, y)
        L["uilang"] = (PAD + cw - 150, y - 4, 150, 40); y += 40 + 16
        L["div4"] = (PAD, y); y += 14
        L["restart"] = (PAD, y, cw, 42); y += 42 + 12
        L["status"] = (PAD, y, cw, 38); y += 38
        return L, y + PAD - 6

    # ---- header (hero) : logo + titre + sous-titre, cuits sur le dégradé ----
    def _draw_header(self, img, w, card_y, C, T) -> None:
        cx = w // 2
        icon = self._pil_asset("icon.png", 46)
        top = 18
        if icon is not None:
            img.alpha_composite(icon, (cx - icon.width // 2, top))
            ty = top + icon.height + 4
        else:
            ty = 34
        d = ImageDraw.Draw(img)
        d.text((cx, ty), "OpenVox", font=_font(26, "bold"), fill=C["fg"], anchor="ma")
        d.text((cx, ty + 34), T["subtitle"], font=_font(12), fill=C["muted"], anchor="ma")

    def _draw_toggle(self, img, w, C) -> None:
        # bg échantillonné sur le fond, pour que le rond se fonde dans le dégradé
        bx, by, bs = w - 50, 18, 34
        bg = _hex(img.crop((bx, by, bx + bs, by + bs)).convert("RGB").resize((1, 1)).getpixel((0, 0)))
        btn = GlassButton(self.canvas, "", self._toggle_theme, bs, bs, C, bg, kind="icon",
                          icon="sun" if self.theme == "dark" else "moon")
        self.canvas.create_window(bx, by, anchor="nw", window=btn)
        self._widgets.append(btn)

    # ---- textes statiques cuits dans l'image (sections, champs, noms de raccourcis) ----
    def _bake_labels(self, img, ox, oy, L, C, T) -> None:
        d = ImageDraw.Draw(img)

        def eyebrow(key, text):
            x, y = L[key]
            d.text((ox + x, oy + y), text.upper(), font=_font(11, "semibold"),
                   fill=C["muted"], anchor="lm")

        def field(key, text):
            x, y = L[key]
            d.text((ox + x, oy + y), text, font=_font(13), fill=C["muted"], anchor="lm")

        def divider(key):
            x, y = L[key]
            d.line([ox + x, oy + y, ox + x + (CARD_W - 2 * PAD), oy + y],
                   fill=_rgba_t(C["input_bd"]), width=1)

        eyebrow("lbl_voice", T["voice_active"])
        eyebrow("lbl_play", T["playback"])
        eyebrow("lbl_sc", T["shortcuts"])
        eyebrow("lbl_if", T["interface"])
        field("lbl_lang", T["reading_lang"])
        field("lbl_accel", T["accel"])
        field("lbl_vol", T["volume"])
        for key in ("div1", "div2", "div3", "div4"):
            divider(key)
        # noms des raccourcis (à gauche de leur puce)
        for key, name in (("read", T["read"]), ("stop", T["stop"])):
            x, y, _w, hh = L[key]
            d.text((ox + x, oy + y + hh // 2), name, font=_font(13), fill=C["fg"], anchor="lm")

    # ---- pose des widgets interactifs sur la carte ----
    def _place_widgets(self, L, ox, oy, glass_bg, C, T) -> None:
        # Voix : sélecteur + supprimer
        files = self._voice_files()
        active = os.path.basename(self.config.get("active_voice", ""))
        vx, vy, vw, vh = L["voice"]
        self.voice_sel = GlassSelect(self.canvas, files, active if active in files else "—",
                                     self._on_voice, vw, vh, C, glass_bg)
        self.canvas.create_window(ox + vx, oy + vy, anchor="nw", window=self.voice_sel)
        self._widgets.append(self.voice_sel)
        dx, dy, dw, dh = L["delete"]
        b = GlassButton(self.canvas, T["delete"], self._delete_voice, dw, dh, C, glass_bg,
                        kind="ghost", size=12)
        self.canvas.create_window(ox + dx, oy + dy, anchor="nw", window=b)
        self._widgets.append(b)
        # Importer
        ix, iy, iw, ih = L["import"]
        b = GlassButton(self.canvas, T["import_btn"], self._import, iw, ih, C, glass_bg,
                        kind="primary", size=14, plus=True)
        self.canvas.create_window(ox + ix, oy + iy, anchor="nw", window=b)
        self._widgets.append(b)
        # Langue de lecture / accélération
        lx, ly, lw, lh = L["lang"]
        self.lang_sel = GlassSelect(self.canvas, LANGUAGES, self.config.get("language", "fr"),
                                    self._on_lang, lw, lh, C, glass_bg)
        self.canvas.create_window(ox + lx, oy + ly, anchor="nw", window=self.lang_sel)
        self._widgets.append(self.lang_sel)
        ax, ay, aw, ah = L["accel"]
        self.dev_sel = GlassSelect(self.canvas, DEVICES, self.config.get("device", "auto"),
                                   self._on_device, aw, ah, C, glass_bg)
        self.canvas.create_window(ox + ax, oy + ay, anchor="nw", window=self.dev_sel)
        self._widgets.append(self.dev_sel)
        # Volume : % (dynamique) + slider
        vol0 = float(self.config.get("volume", 1.0))
        px, py = L["vol_pct"]
        self.vol_pct = self.canvas.create_text(ox + px, oy + py, text=f"{int(round(vol0*100))} %",
                                               font=("Segoe UI", 10), fill=C["muted"], anchor="e")
        sx, sy, sw, sh = L["vol"]
        self.vol_slider = Slider(self.canvas, vol0, self._on_volume,
                                 lambda: self.save_config(self.config), sw, sh, C, glass_bg, None)
        self.canvas.create_window(ox + sx, oy + sy, anchor="nw", window=self.vol_slider)
        self._widgets.append(self.vol_slider)
        # Raccourcis : puce + bouton Modifier
        for key, ckey in (("read", "hotkey_speak"), ("stop", "hotkey_stop")):
            rx, ry, rw, rh = L[key]
            chip_w, btn_w = rw - 58 - 108, 100
            chip = GlassSelect(self.canvas, [], self._pretty(self.config.get(ckey)),
                               None, chip_w, rh, C, glass_bg, readonly=True)
            self.canvas.create_window(ox + rx + 58, oy + ry, anchor="nw", window=chip)
            self._widgets.append(chip)
            btn = GlassButton(self.canvas, T["modify"],
                              lambda c=ckey, ch=chip, k=key: self._record_hotkey(c, ch),
                              btn_w, rh, C, glass_bg, kind="ghost", size=12)
            self.canvas.create_window(ox + rx + rw - btn_w, oy + ry, anchor="nw", window=btn)
            self._widgets.append(btn)
            setattr(self, f"chip_{key}", chip)
        # Interface : langue
        ux, uy, uw, uh = L["uilang"]
        self._lang_l2v = {v: k for k, v in UI_LANGS.items()}
        self.uilang_sel = GlassSelect(self.canvas, list(UI_LANGS.values()),
                                      UI_LANGS[self.ui_lang],
                                      lambda v: self._change_ui_lang(self._lang_l2v[v]),
                                      uw, uh, C, glass_bg)
        self.canvas.create_window(ox + ux, oy + uy, anchor="nw", window=self.uilang_sel)
        self._widgets.append(self.uilang_sel)
        # Redémarrer
        rx, ry, rw, rh = L["restart"]
        b = GlassButton(self.canvas, T["restart_btn"], self._restart, rw, rh, C, glass_bg,
                        kind="ghost", size=13)
        self.canvas.create_window(ox + rx, oy + ry, anchor="nw", window=b)
        self._widgets.append(b)
        # Statut : dessiné directement sur le canvas principal (sur le verre) pour éviter
        # tout liseré de fond ; redessiné via le tag "status".
        stx, sty, stw, _sth = L["status"]
        self._status_pos = (ox + stx, oy + sty, stw)

    # ------------------------------ position ------------------------------
    def _on_configure(self, event) -> None:
        # Fenêtre à taille fixe : on ne mémorise que la position (pour rouvrir au même
        # endroit) ; aucun re-rendu.
        if event.widget is self.root and self.root.state() == "normal":
            self._geom = self.root.geometry()

    # ------------------------------ statut ------------------------------
    def on_engine_status(self, key: str, params: dict | None = None) -> None:
        params = params or {}
        self._last_status = ("engine", key, params)
        self._apply(self._render_status(key, params), ENGINE_LEVELS.get(key, "working"))

    def _render_status(self, key: str, params: dict) -> str:
        s = self.T["status"]
        p = dict(params)
        if "info" in p and p["info"] in s:
            p["info"] = s[p["info"]]
        try:
            return s.get(key, key).format(**p)
        except Exception:
            return s.get(key, key)

    def _status(self, text: str, level: str = "working") -> None:
        self._last_status = ("text", text, level)
        self._apply(text, level)

    def _apply(self, text: str, level: str) -> None:
        color = self.C.get(level, self.C["working"])

        def draw():
            if not self.canvas.winfo_exists() or not hasattr(self, "_status_pos"):
                return
            x, y, w = self._status_pos
            self.canvas.delete("status")
            self.canvas.create_oval(x, y + 5, x + 9, y + 14, fill=color, outline=color,
                                    tags="status")
            self.canvas.create_text(x + 16, y, text=text, font=("Segoe UI", 9),
                                    fill=self.C["muted"], anchor="nw", width=w - 16,
                                    tags="status")
        self.root.after(0, draw)

    # ------------------------------ voix ------------------------------
    def _voice_files(self) -> list:
        return sorted(f for f in os.listdir(VOICES_DIR) if f.lower().endswith(".wav"))

    def _on_voice(self, name) -> None:
        if not name or name == "—":
            return
        path = os.path.join(VOICES_DIR, name)
        self.config["active_voice"] = path
        self.save_config(self.config)
        threading.Thread(target=lambda: self.engine.set_voice(path), daemon=True).start()

    def _import(self) -> None:
        src = filedialog.askopenfilename(title=self.T["import_btn"], filetypes=[("WAV", "*.wav")])
        if not src:
            return
        dst = os.path.join(VOICES_DIR, os.path.basename(src))
        try:
            ops = prepare_sample(src, dst)
        except Exception as e:  # noqa: BLE001
            self._status(self.T["import_failed"].format(err=e), "error")
            return
        name = os.path.basename(dst)
        self.voice_sel.set_values(self._voice_files())
        self.voice_sel.set(name)
        if ops:
            parts = [self.T["op_trimmed"].format(s=int(TARGET_SAMPLE_S)) if op == "trimmed"
                     else self.T["op_mono"] for op in ops]
            self._status(self.T["imported"].format(note=", ".join(parts)), "ready")
        self._on_voice(name)

    def _delete_voice(self) -> None:
        name = self.voice_sel.value
        if not name or name == "—":
            return
        if not messagebox.askyesno(self.T["delete"], self.T["delete_confirm"].format(name=name)):
            return
        path = os.path.join(VOICES_DIR, name)
        try:
            os.remove(path)
        except OSError as e:
            self._status(self.T["delete_failed"].format(err=e), "error")
            return
        if os.path.abspath(self.config.get("active_voice", "")) == os.path.abspath(path):
            self.config["active_voice"] = ""
            self.save_config(self.config)
            self.engine.clear_voice()
        self.voice_sel.set_values(self._voice_files())
        self.voice_sel.set("—")
        self._status(self.T["deleted"].format(name=name), "working")

    def _on_lang(self, value) -> None:
        self.config["language"] = value
        self.save_config(self.config)

    def _on_device(self, value) -> None:
        self.config["device"] = value
        self.save_config(self.config)
        self._status(self.T["accel_changed"], "working")

    def _on_volume(self, frac) -> None:
        self.config["volume"] = round(float(frac), 3)
        self.canvas.itemconfigure(self.vol_pct, text=f"{int(round(float(frac) * 100))} %")

    # ------------------------------ raccourcis ------------------------------
    def _record_hotkey(self, key: str, chip: "GlassSelect") -> None:
        if not self.hotkeys:
            return
        previous = chip.value
        chip.set("…")
        self._status(self.T["press_combo"], "working")

        def done(combo: str | None) -> None:
            def apply() -> None:
                if combo:
                    self.config[key] = combo
                    self.save_config(self.config)
                    chip.set(self._pretty(combo))
                    self._status(self.T["shortcut_saved"].format(combo=self._pretty(combo)),
                                 "ready")
                else:
                    chip.set(previous)
                    self._status(self.T["cancelled"], "working")
                self.hotkeys.restart()
            self.root.after(0, apply)

        self.hotkeys.record(done)

    # ------------------------------ thème / langue ------------------------------
    def _toggle_theme(self) -> None:
        self._change_theme("dark" if self.theme == "light" else "light")

    def _change_theme(self, value: str) -> None:
        if value == self.theme:
            return
        self.config["theme"] = value
        self.save_config(self.config)
        self._rerender()

    def _change_ui_lang(self, value: str) -> None:
        if value == self.ui_lang:
            return
        self.config["ui_language"] = value
        self.save_config(self.config)
        self._rerender()

    def _rerender(self) -> None:
        w = self.root.winfo_width() or self._parse_geo(self._geom)[0]
        h = self.root.winfo_height() or self._parse_geo(self._geom)[1]
        self._render_all(w, h)

    # ------------------------------ divers ------------------------------
    @staticmethod
    def _pretty(combo: str | None) -> str:
        if not combo:
            return "—"
        return "+".join(p.strip("<>").capitalize() for p in combo.split("+"))

    def _pil_asset(self, name: str, width: int):
        path = os.path.join(ASSETS_DIR, name)
        if not os.path.exists(path):
            return None
        try:
            img = Image.open(path).convert("RGBA")
            h = round(img.height * width / img.width)
            return img.resize((width, h), Image.LANCZOS)
        except Exception:
            return None

    def _set_window_icon(self) -> None:
        ico = os.path.join(ASSETS_DIR, "icon.ico")
        try:
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass
        png = os.path.join(ASSETS_DIR, "icon.png")
        try:
            if os.path.exists(png):
                self._iconphoto = ImageTk.PhotoImage(Image.open(png).resize((64, 64)))
                self.root.iconphoto(True, self._iconphoto)
        except Exception:
            pass

    def attach_hotkeys(self, hotkeys) -> None:
        self.hotkeys = hotkeys

    def attach_restart(self, fn) -> None:
        self._restart_cb = fn

    def _restart(self) -> None:
        if self._restart_cb:
            self._restart_cb()

    # ------------------------------ fenêtre / tray ------------------------------
    def save_geometry(self) -> None:
        if self._geom:
            self.config["window_geometry"] = self._geom
            self.save_config(self.config)

    def hide(self) -> None:
        self.save_geometry()
        self.root.withdraw()

    def show(self) -> None:
        self.root.after(0, self.root.deiconify)
