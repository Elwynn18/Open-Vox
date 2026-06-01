"""Fenêtre Tkinter (stdlib) d'OpenVox : voix, langue, accélération, raccourcis, statut.

Habillage maison (charte du logo) avec **mode clair / sombre** et **interface fr/en/es**.
Le moteur n'émet que des CLÉS de statut ; toute la traduction est faite ici. Changer de thème
ou de langue reconstruit la fenêtre. L'app vit en tâche de fond (tray géré par main.py).
"""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from engine import TARGET_SAMPLE_S, prepare_sample

HERE = os.path.dirname(__file__)
VOICES_DIR = os.path.join(HERE, "voices")
ASSETS_DIR = os.path.join(HERE, "assets")

# Langues de SYNTHÈSE supportées par XTTS v2 (codes).
LANGUAGES = ["fr", "en", "es", "de", "it", "pt", "pl", "tr", "ru", "nl",
             "cs", "ar", "zh-cn", "hu", "ko", "ja", "hi"]
DEVICES = ["auto", "cpu", "cuda"]
# Langues d'INTERFACE (autonymes, jamais traduits).
UI_LANGS = {"fr": "Français", "en": "English", "es": "Español"}

# Palettes (clair / sombre).
THEMES = {
    "light": {
        "bg": "#ffffff", "card": "#f4f5fb", "fg": "#1b1b3a", "muted": "#8a8a9a",
        "field": "#ffffff", "field_fg": "#1b1b3a", "sep": "#e2e2ec",
        "sec_btn": "#e7e7f2", "sec_btn_fg": "#1b1b3a",
        "accent": "#7c4dff", "accent_dk": "#6636e0",
        "ready": "#22b07d", "error": "#e0556b", "working": "#e8a13a",
    },
    "dark": {
        "bg": "#1e1e2a", "card": "#272735", "fg": "#e9e9f2", "muted": "#9a9ab0",
        "field": "#2f2f40", "field_fg": "#e9e9f2", "sep": "#3a3a4e",
        "sec_btn": "#3a3a4e", "sec_btn_fg": "#e9e9f2",
        "accent": "#8b5cff", "accent_dk": "#7a45f0",
        "ready": "#33c08d", "error": "#ef6b80", "working": "#f0ad4e",
    },
}

# Niveau (= couleur de pastille) par clé de statut moteur ; sinon "working".
ENGINE_LEVELS = {
    "ready_no_voice": "ready", "voice_ready": "ready",
    "voice_invalid": "error", "load_error": "error", "no_voice": "error",
    "synth_error": "error", "play_error": "error",
}

# Traductions de l'interface.
STRINGS = {
    "fr": {
        "subtitle": "Lecture de la sélection à voix haute",
        "voice_active": "Voix active", "import_btn": "＋  Importer un échantillon .wav",
        "reading_lang": "Langue de lecture", "accel": "Accélération",
        "shortcuts": "Raccourcis", "read": "Lire", "stop": "Stop", "modify": "Modifier",
        "delete": "Supprimer", "delete_confirm": "Supprimer la voix « {name} » ?",
        "deleted": "Voix supprimée : {name}.", "delete_failed": "Suppression impossible : {err}",
        "restart_btn": "↻  Redémarrer l'application",
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
        "voice_active": "Active voice", "import_btn": "＋  Import a .wav sample",
        "reading_lang": "Reading language", "accel": "Acceleration",
        "shortcuts": "Shortcuts", "read": "Read", "stop": "Stop", "modify": "Change",
        "delete": "Delete", "delete_confirm": "Delete voice “{name}”?",
        "deleted": "Voice deleted: {name}.", "delete_failed": "Delete failed: {err}",
        "restart_btn": "↻  Restart the app",
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
        "voice_active": "Voz activa", "import_btn": "＋  Importar una muestra .wav",
        "reading_lang": "Idioma de lectura", "accel": "Aceleración",
        "shortcuts": "Atajos", "read": "Leer", "stop": "Parar", "modify": "Cambiar",
        "delete": "Eliminar", "delete_confirm": "¿Eliminar la voz «{name}»?",
        "deleted": "Voz eliminada: {name}.", "delete_failed": "Error al eliminar: {err}",
        "restart_btn": "↻  Reiniciar la aplicación",
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


class AppGUI:
    def __init__(self, root: tk.Tk, config: dict, engine, save_config):
        self.root = root
        self.config = config
        self.engine = engine
        self.save_config = save_config
        self.hotkeys = None              # branché après coup par attach_hotkeys()
        self._restart_cb = None          # branché après coup par attach_restart()
        self._imgs: list = []            # réfs PhotoImage du contenu (vidées au rebuild)
        self._last_status = None         # ("engine", key, params) | ("text", text, level)
        os.makedirs(VOICES_DIR, exist_ok=True)

        root.title("OpenVox")
        root.resizable(False, False)
        root.geometry("430x710")
        self._set_window_icon()
        root.protocol("WM_DELETE_WINDOW", self.hide)  # fermer = masquer (reste en tray)
        self._build()

    # ---------- construction / reconstruction ----------
    def _build(self) -> None:
        self.ui_lang = self.config.get("ui_language", "fr")
        if self.ui_lang not in STRINGS:
            self.ui_lang = "fr"
        self.theme = self.config.get("theme", "light")
        if self.theme not in THEMES:
            self.theme = "light"
        self.T = STRINGS[self.ui_lang]
        self.C = THEMES[self.theme]
        C, T = self.C, self.T

        self._init_style()
        self.root.configure(bg=C["bg"])

        # --- Header : logo (clair) ou bulle + nom (sombre, pour rester lisible) ---
        header = tk.Frame(self.root, bg=C["bg"])
        header.pack(fill="x", pady=(16, 4))
        if self.theme == "light":
            logo = self._load_image("logo.png", width=120)
            if logo:
                tk.Label(header, image=logo, bg=C["bg"]).pack()
            else:
                tk.Label(header, text="OpenVox", font=("Segoe UI", 20, "bold"),
                         fg=C["fg"], bg=C["bg"]).pack()
        else:
            icon = self._load_image("icon.png", width=72)
            if icon:
                tk.Label(header, image=icon, bg=C["bg"]).pack()
            tk.Label(header, text="OpenVox", font=("Segoe UI", 17, "bold"),
                     fg=C["fg"], bg=C["bg"]).pack(pady=(4, 0))
        tk.Label(header, text=T["subtitle"], font=("Segoe UI", 9),
                 fg=C["muted"], bg=C["bg"]).pack(pady=(2, 0))

        # --- Carte de réglages ---
        card = tk.Frame(self.root, bg=C["card"])
        card.pack(fill="x", padx=18, pady=12)
        inner = tk.Frame(card, bg=C["card"])
        inner.pack(fill="x", padx=16, pady=14)
        inner.columnconfigure(1, weight=1)

        self._head(inner, 0, T["voice_active"], columnspan=2)
        vrow = tk.Frame(inner, bg=C["card"])
        vrow.grid(row=1, column=0, columnspan=2, sticky="we", pady=(4, 6))
        vrow.columnconfigure(0, weight=1)
        self.voice_var = tk.StringVar()
        self.voice_cb = ttk.Combobox(vrow, textvariable=self.voice_var, state="readonly")
        self.voice_cb.grid(row=0, column=0, sticky="we")
        self.voice_cb.bind("<<ComboboxSelected>>", self._on_voice)
        ttk.Button(vrow, text=T["delete"], style="Sec.TButton",
                   command=self._delete_voice).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(inner, text=T["import_btn"], style="Accent.TButton",
                   command=self._import).grid(row=2, column=0, columnspan=2, sticky="we")

        self._sep(inner, 3)

        self._head(inner, 4, T["reading_lang"], col=0)
        self._head(inner, 4, T["accel"], col=1)
        self.lang_var = tk.StringVar(value=self.config.get("language", "fr"))
        lang_cb = ttk.Combobox(inner, textvariable=self.lang_var, values=LANGUAGES,
                               state="readonly", width=8)
        lang_cb.grid(row=5, column=0, sticky="w", pady=(4, 0))
        lang_cb.bind("<<ComboboxSelected>>", self._on_lang)
        self.dev_var = tk.StringVar(value=self.config.get("device", "auto"))
        dev_cb = ttk.Combobox(inner, textvariable=self.dev_var, values=DEVICES,
                              state="readonly", width=8)
        dev_cb.grid(row=5, column=1, sticky="w", pady=(4, 0))
        dev_cb.bind("<<ComboboxSelected>>", self._on_device)

        self._sep(inner, 6)

        self._head(inner, 7, T["shortcuts"], columnspan=2)
        hk = tk.Frame(inner, bg=C["card"])
        hk.grid(row=8, column=0, columnspan=2, sticky="we", pady=(6, 0))
        hk.columnconfigure(1, weight=1)
        self.speak_disp = tk.StringVar(value=self._pretty(self.config.get("hotkey_speak")))
        self.stop_disp = tk.StringVar(value=self._pretty(self.config.get("hotkey_stop")))
        self._hotkey_row(hk, 0, T["read"], self.speak_disp, "hotkey_speak")
        self._hotkey_row(hk, 1, T["stop"], self.stop_disp, "hotkey_stop")

        self._sep(inner, 9)

        self._head(inner, 10, T["theme"], col=0)
        self._head(inner, 10, T["ui_lang"], col=1)
        theme_labels = {"light": T["theme_light"], "dark": T["theme_dark"]}
        self._theme_l2v = {v: k for k, v in theme_labels.items()}
        self.theme_var = tk.StringVar(value=theme_labels[self.theme])
        theme_cb = ttk.Combobox(inner, textvariable=self.theme_var,
                                values=list(theme_labels.values()), state="readonly", width=8)
        theme_cb.grid(row=11, column=0, sticky="w", pady=(4, 0))
        theme_cb.bind("<<ComboboxSelected>>",
                      lambda _e: self._change_theme(self._theme_l2v[self.theme_var.get()]))
        self._lang_l2v = {v: k for k, v in UI_LANGS.items()}
        self.uilang_var = tk.StringVar(value=UI_LANGS[self.ui_lang])
        uilang_cb = ttk.Combobox(inner, textvariable=self.uilang_var,
                                 values=list(UI_LANGS.values()), state="readonly", width=10)
        uilang_cb.grid(row=11, column=1, sticky="w", pady=(4, 0))
        uilang_cb.bind("<<ComboboxSelected>>",
                       lambda _e: self._change_ui_lang(self._lang_l2v[self.uilang_var.get()]))

        ttk.Button(inner, text=T["restart_btn"], style="Sec.TButton",
                   command=self._restart).grid(row=12, column=0, columnspan=2,
                                               sticky="we", pady=(14, 0))

        # --- Statut (pastille + texte) ---
        status = tk.Frame(self.root, bg=C["bg"])
        status.pack(fill="x", padx=20, pady=(2, 12))
        self.dot = tk.Label(status, text="●", font=("Segoe UI", 11),
                            fg=C["working"], bg=C["bg"])
        self.dot.pack(side="left")
        self.status_var = tk.StringVar(value=T["init"])
        tk.Label(status, textvariable=self.status_var, font=("Segoe UI", 9),
                 fg=C["fg"], bg=C["bg"], wraplength=360, justify="left", anchor="w").pack(
            side="left", padx=(6, 0), fill="x")

        self._refresh_voices()

    def _rebuild(self) -> None:
        for w in self.root.winfo_children():
            w.destroy()
        self._imgs.clear()
        self._build()
        last = self._last_status                # ré-affiche le statut courant traduit
        if last and last[0] == "engine":
            self.on_engine_status(last[1], last[2])
        elif last:
            self._status(last[1], last[2])

    # ---------- petits helpers de widgets ----------
    def _head(self, parent, row, text, col=0, columnspan=1):
        tk.Label(parent, text=text, bg=self.C["card"], fg=self.C["fg"],
                 font=("Segoe UI", 10, "bold")).grid(
            row=row, column=col, columnspan=columnspan, sticky="w")

    def _sep(self, parent, row):
        ttk.Separator(parent).grid(row=row, column=0, columnspan=2, sticky="we", pady=12)

    def _hotkey_row(self, parent, r, name, var, key):
        tk.Label(parent, text=name, bg=self.C["card"], fg=self.C["fg"],
                 font=("Segoe UI", 10), width=5, anchor="w").grid(
            row=r, column=0, sticky="w", pady=3)
        tk.Label(parent, textvariable=var, bg=self.C["field"], fg=self.C["field_fg"],
                 font=("Segoe UI", 10), relief="solid", bd=1, padx=8, pady=3,
                 anchor="w").grid(row=r, column=1, sticky="we", padx=(0, 8))
        btn = ttk.Button(parent, text=self.T["modify"], style="Sec.TButton",
                         command=lambda: self._record_hotkey(key, var, btn))
        btn.grid(row=r, column=2)

    # ---------- style ----------
    def _init_style(self) -> None:
        C = self.C
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=C["bg"], foreground=C["fg"], font=("Segoe UI", 10))
        st.configure("TSeparator", background=C["sep"])
        st.configure("Accent.TButton", background=C["accent"], foreground="white",
                     borderwidth=0, focusthickness=0, padding=9, font=("Segoe UI", 10, "bold"))
        st.map("Accent.TButton",
               background=[("pressed", C["accent_dk"]), ("active", C["accent_dk"])],
               foreground=[("disabled", "#cccccc")])
        st.configure("Sec.TButton", background=C["sec_btn"], foreground=C["sec_btn_fg"],
                     borderwidth=0, focusthickness=0, padding=(12, 5), font=("Segoe UI", 9))
        st.map("Sec.TButton",
               background=[("pressed", C["accent_dk"]), ("active", C["sep"]),
                           ("disabled", C["card"])],
               foreground=[("disabled", C["muted"])])
        st.configure("TCombobox", fieldbackground=C["field"], background=C["field"],
                     foreground=C["field_fg"], borderwidth=1, arrowsize=14, padding=4,
                     lightcolor=C["field"], darkcolor=C["field"], bordercolor=C["sep"],
                     arrowcolor=C["fg"])
        st.map("TCombobox",
               fieldbackground=[("readonly", C["field"])],
               selectbackground=[("readonly", C["field"])],
               selectforeground=[("readonly", C["field_fg"])],
               foreground=[("readonly", C["field_fg"])],
               bordercolor=[("focus", C["accent"])])
        # Couleurs de la liste déroulante (popdown) des combobox.
        self.root.option_add("*TCombobox*Listbox.background", C["field"])
        self.root.option_add("*TCombobox*Listbox.foreground", C["field_fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", C["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    def _load_image(self, name: str, width: int):
        path = os.path.join(ASSETS_DIR, name)
        if not os.path.exists(path):
            return None
        try:
            img = Image.open(path)
            h = round(img.height * width / img.width)
            photo = ImageTk.PhotoImage(img.resize((width, h), Image.LANCZOS))
            self._imgs.append(photo)
            return photo
        except Exception:
            return None

    def _set_window_icon(self) -> None:
        ico = os.path.join(ASSETS_DIR, "icon.ico")
        try:
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass
        photo = self._load_image("icon.png", width=64)
        if photo:
            self._iconphoto = photo            # réf persistante (jamais vidée au rebuild)
            try:
                self.root.iconphoto(True, photo)
            except Exception:
                pass

    @staticmethod
    def _pretty(combo: str | None) -> str:
        """'<ctrl>+<alt>+s' -> 'Ctrl+Alt+S' pour l'affichage."""
        if not combo:
            return "—"
        return "+".join(p.strip("<>").capitalize() for p in combo.split("+"))

    def attach_hotkeys(self, hotkeys) -> None:
        """Branche le HotkeyManager (créé après la GUI) pour permettre l'édition à chaud."""
        self.hotkeys = hotkeys

    def attach_restart(self, fn) -> None:
        """Branche la fonction de redémarrage (définie par main.py)."""
        self._restart_cb = fn

    def _restart(self) -> None:
        if self._restart_cb:
            self._restart_cb()

    # ---------- statut ----------
    def on_engine_status(self, key: str, params: dict | None = None) -> None:
        """Callback du moteur : reçoit une clé + params, traduit et affiche."""
        params = params or {}
        self._last_status = ("engine", key, params)
        self._apply(self._render_status(key, params), ENGINE_LEVELS.get(key, "working"))

    def _render_status(self, key: str, params: dict) -> str:
        s = self.T["status"]
        p = dict(params)
        if "info" in p and p["info"] in s:        # 'info' est elle-même une clé (device)
            p["info"] = s[p["info"]]
        try:
            return s.get(key, key).format(**p)
        except Exception:
            return s.get(key, key)

    def _status(self, text: str, level: str = "working") -> None:
        """Statut produit par la GUI elle-même (déjà traduit)."""
        self._last_status = ("text", text, level)
        self._apply(text, level)

    def _apply(self, text: str, level: str) -> None:
        color = self.C.get(level, self.C["working"])
        self.root.after(0, lambda: (self.status_var.set(text), self.dot.config(fg=color)))

    # ---------- voix ----------
    def _refresh_voices(self) -> None:
        files = sorted(f for f in os.listdir(VOICES_DIR) if f.lower().endswith(".wav"))
        self.voice_cb["values"] = files
        active = os.path.basename(self.config.get("active_voice", ""))
        if active in files:
            self.voice_var.set(active)

    def _on_voice(self, _evt=None) -> None:
        name = self.voice_var.get()
        if not name:
            return
        path = os.path.join(VOICES_DIR, name)
        self.config["active_voice"] = path
        self.save_config(self.config)
        # set_voice est coûteux (embedding) → en tâche de fond pour ne pas figer la GUI.
        threading.Thread(target=lambda: self.engine.set_voice(path), daemon=True).start()

    def _import(self) -> None:
        src = filedialog.askopenfilename(title=self.T["import_btn"].strip("＋ "),
                                         filetypes=[("WAV", "*.wav")])
        if not src:
            return
        dst = os.path.join(VOICES_DIR, os.path.basename(src))
        try:
            # importer = normaliser en mono + redécouper si trop long, puis écrire dans voices/
            ops = prepare_sample(src, dst)
        except Exception as e:  # noqa: BLE001
            self._status(self.T["import_failed"].format(err=e), "error")
            return
        self._refresh_voices()
        self.voice_var.set(os.path.basename(dst))
        if ops:
            parts = [self.T["op_trimmed"].format(s=int(TARGET_SAMPLE_S)) if op == "trimmed"
                     else self.T["op_mono"] for op in ops]
            self._status(self.T["imported"].format(note=", ".join(parts)), "ready")
        self._on_voice()

    def _delete_voice(self) -> None:
        name = self.voice_var.get()
        if not name:
            return
        if not messagebox.askyesno(self.T["delete"], self.T["delete_confirm"].format(name=name)):
            return
        path = os.path.join(VOICES_DIR, name)
        try:
            os.remove(path)
        except OSError as e:
            self._status(self.T["delete_failed"].format(err=e), "error")
            return
        # Si c'était la voix active, on l'oublie (config + embedding chargé).
        if os.path.abspath(self.config.get("active_voice", "")) == os.path.abspath(path):
            self.config["active_voice"] = ""
            self.save_config(self.config)
            self.engine.clear_voice()
        self.voice_var.set("")
        self._refresh_voices()
        self._status(self.T["deleted"].format(name=name), "working")

    def _on_lang(self, _evt=None) -> None:
        self.config["language"] = self.lang_var.get()
        self.save_config(self.config)

    def _on_device(self, _evt=None) -> None:
        self.config["device"] = self.dev_var.get()
        self.save_config(self.config)
        self._status(self.T["accel_changed"], "working")

    # ---------- raccourcis ----------
    def _record_hotkey(self, key: str, var: tk.StringVar, btn) -> None:
        if not self.hotkeys:
            return
        previous = var.get()
        var.set("…")
        btn.state(["disabled"])
        self._status(self.T["press_combo"], "working")

        def done(combo: str | None) -> None:
            def apply() -> None:
                btn.state(["!disabled"])
                if combo:
                    self.config[key] = combo
                    self.save_config(self.config)
                    var.set(self._pretty(combo))
                    self._status(self.T["shortcut_saved"].format(combo=self._pretty(combo)),
                                 "ready")
                else:
                    var.set(previous)
                    self._status(self.T["cancelled"], "working")
                self.hotkeys.restart()           # ré-enregistre les raccourcis globaux
            self.root.after(0, apply)

        self.hotkeys.record(done)

    # ---------- thème / langue ----------
    def _change_theme(self, value: str) -> None:
        if value == self.theme:
            return
        self.config["theme"] = value
        self.save_config(self.config)
        self._rebuild()

    def _change_ui_lang(self, value: str) -> None:
        if value == self.ui_lang:
            return
        self.config["ui_language"] = value
        self.save_config(self.config)
        self._rebuild()

    # ---------- fenêtre / tray ----------
    def hide(self) -> None:
        self.root.withdraw()

    def show(self) -> None:
        self.root.after(0, self.root.deiconify)
