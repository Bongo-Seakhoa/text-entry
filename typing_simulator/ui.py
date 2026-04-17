from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

try:
    import winsound
except ImportError:  # pragma: no cover - only expected outside Windows
    winsound = None

from .keyboard_engine import KeyboardTyper, TypingResult
from .timing import TimingProfile, TypingRhythm, format_duration


PANEL_BG = "#F7F1E3"
SURFACE_BG = "#FFF9EF"
ACCENT = "#E16B2D"
ACCENT_SOFT = "#F8D8C1"
INK = "#183153"
MUTED = "#53657D"
SUCCESS = "#3C8050"
WARNING = "#A8432A"


@dataclass(slots=True)
class WorkerState:
    text: str
    profile: TimingProfile


class TypingSimulatorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Typing Simulator")
        self.root.geometry("1180x760")
        self.root.minsize(980, 680)
        self.root.configure(bg=PANEL_BG)

        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._typing_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._countdown_job: str | None = None
        self._countdown_remaining = 0
        self._pending_worker: WorkerState | None = None

        self.wpm_var = tk.IntVar(value=65)
        self.delay_var = tk.IntVar(value=4)
        self.humanize_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready. Paste the source text, click Start, and focus the browser field.")
        self.detail_var = tk.StringVar(value="Supports multiline text, punctuation, and Unicode fallback.")
        self.stats_var = tk.StringVar(value="0 characters")
        self.estimate_var = tk.StringVar(value="Estimated typing time: 0s")

        self._configure_style()
        self._build_layout()
        self._bind_events()
        self._refresh_metrics()
        self._poll_queue()

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("App.TFrame", background=PANEL_BG)
        style.configure("Card.TFrame", background=SURFACE_BG)
        style.configure("Hero.TFrame", background=INK)
        style.configure("Title.TLabel", background=INK, foreground="#FFF7E8", font=("Bahnschrift SemiBold", 26))
        style.configure("Subtitle.TLabel", background=INK, foreground="#D7E6F2", font=("Georgia", 11))
        style.configure("CardTitle.TLabel", background=SURFACE_BG, foreground=INK, font=("Bahnschrift SemiBold", 14))
        style.configure("Body.TLabel", background=SURFACE_BG, foreground=INK, font=("Georgia", 10))
        style.configure("Muted.TLabel", background=SURFACE_BG, foreground=MUTED, font=("Georgia", 10))
        style.configure("Metric.TLabel", background=ACCENT_SOFT, foreground=INK, font=("Bahnschrift SemiBold", 11))
        style.configure("Hint.TLabel", background=ACCENT_SOFT, foreground=INK, font=("Georgia", 10))
        style.configure("Primary.TButton", background=ACCENT, foreground="#FFFFFF", borderwidth=0, focusthickness=0, font=("Bahnschrift SemiBold", 11), padding=(14, 10))
        style.map("Primary.TButton", background=[("active", "#C85821"), ("disabled", "#E5BFA7")])
        style.configure("Secondary.TButton", background="#E6EDF4", foreground=INK, borderwidth=0, focusthickness=0, font=("Bahnschrift", 10), padding=(12, 9))
        style.map("Secondary.TButton", background=[("active", "#D2DCE8")])
        style.configure("Panel.TLabelframe", background=SURFACE_BG, foreground=INK, bordercolor="#E8DCC7", relief="solid")
        style.configure("Panel.TLabelframe.Label", background=SURFACE_BG, foreground=INK, font=("Bahnschrift SemiBold", 11))
        style.configure("Accent.Horizontal.TScale", troughcolor="#ECD8C2", background=ACCENT)
        style.configure("Card.TCheckbutton", background=SURFACE_BG, foreground=INK, font=("Bahnschrift", 10))

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        hero = ttk.Frame(self.root, style="Hero.TFrame", padding=(26, 20))
        hero.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))
        hero.columnconfigure(0, weight=1)

        ttk.Label(hero, text="Typing Simulator", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            hero,
            text="Paste any source text here, then hand focus to a browser field and let the app type it in verbatim.",
            style="Subtitle.TLabel",
            wraplength=840,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        container = ttk.Frame(self.root, style="App.TFrame")
        container.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        container.columnconfigure(0, weight=2)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        composer = ttk.Frame(container, style="Card.TFrame", padding=20)
        composer.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        composer.columnconfigure(0, weight=1)
        composer.rowconfigure(2, weight=1)

        ttk.Label(composer, text="Source Text", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            composer,
            text="Everything in this box will be typed exactly in order. Tabs and new lines are preserved as far as the target field allows them.",
            style="Muted.TLabel",
            wraplength=720,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 14))

        self.text_box = scrolledtext.ScrolledText(
            composer,
            wrap="word",
            undo=True,
            font=("Cascadia Code", 11),
            bg="#FFFDF8",
            fg=INK,
            insertbackground=INK,
            relief="flat",
            borderwidth=0,
            padx=16,
            pady=16,
        )
        self.text_box.grid(row=2, column=0, sticky="nsew")

        footer = ttk.Frame(composer, style="Card.TFrame")
        footer.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        footer.columnconfigure(1, weight=1)

        ttk.Label(footer, textvariable=self.stats_var, style="Metric.TLabel", padding=(10, 6)).grid(row=0, column=0, sticky="w")
        ttk.Label(footer, textvariable=self.estimate_var, style="Metric.TLabel", padding=(10, 6)).grid(row=0, column=1, sticky="w", padx=(8, 0))

        controls = ttk.Frame(container, style="Card.TFrame", padding=20)
        controls.grid(row=0, column=1, sticky="nsew")
        controls.columnconfigure(0, weight=1)

        ttk.Label(controls, text="Controls", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            controls,
            text="The app counts down so you can click into Chrome or any other target field before typing begins.",
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 14))

        guide = tk.Text(
            controls,
            height=5,
            wrap="word",
            bg=ACCENT_SOFT,
            fg=INK,
            relief="flat",
            font=("Georgia", 10),
            padx=14,
            pady=12,
            highlightthickness=0,
        )
        guide.insert(
            "1.0",
            "1. Paste text here.\n2. Click Start Typing.\n3. Move focus to the destination field during the countdown.\n4. Hold Esc any time to cancel.",
        )
        guide.configure(state="disabled")
        guide.grid(row=2, column=0, sticky="ew")

        speed_frame = ttk.LabelFrame(controls, text="Typing Pace", style="Panel.TLabelframe", padding=14)
        speed_frame.grid(row=3, column=0, sticky="ew", pady=(16, 12))
        speed_frame.columnconfigure(0, weight=1)
        speed_frame.columnconfigure(1, weight=0)

        ttk.Label(speed_frame, text="Words per minute", style="Body.TLabel").grid(row=0, column=0, sticky="w")
        self.wpm_label = ttk.Label(speed_frame, text=str(self.wpm_var.get()), style="CardTitle.TLabel")
        self.wpm_label.grid(row=0, column=1, sticky="e")
        self.wpm_scale = ttk.Scale(
            speed_frame,
            from_=20,
            to=160,
            orient="horizontal",
            variable=self.wpm_var,
            style="Accent.Horizontal.TScale",
            command=self._on_wpm_changed,
        )
        self.wpm_scale.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        delay_frame = ttk.LabelFrame(controls, text="Targeting Delay", style="Panel.TLabelframe", padding=14)
        delay_frame.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        delay_frame.columnconfigure(0, weight=1)
        delay_frame.columnconfigure(1, weight=0)

        ttk.Label(delay_frame, text="Countdown seconds", style="Body.TLabel").grid(row=0, column=0, sticky="w")
        self.delay_spin = ttk.Spinbox(delay_frame, from_=2, to=15, textvariable=self.delay_var, width=6, justify="center")
        self.delay_spin.grid(row=0, column=1, sticky="e")
        ttk.Checkbutton(
            delay_frame,
            text="Humanize rhythm with QWERTY movement",
            variable=self.humanize_var,
            style="Card.TCheckbutton",
            command=self._refresh_metrics,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))

        action_bar = ttk.Frame(controls, style="Card.TFrame")
        action_bar.grid(row=5, column=0, sticky="ew", pady=(4, 0))
        action_bar.columnconfigure(0, weight=1)

        self.start_button = ttk.Button(action_bar, text="Start Typing", style="Primary.TButton", command=self.start_typing)
        self.start_button.grid(row=0, column=0, sticky="ew")

        self.stop_button = ttk.Button(action_bar, text="Stop", style="Secondary.TButton", command=self.stop_typing, state="disabled")
        self.stop_button.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        quick_actions = ttk.Frame(controls, style="Card.TFrame")
        quick_actions.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        quick_actions.columnconfigure((0, 1), weight=1)

        ttk.Button(quick_actions, text="Load Sample", style="Secondary.TButton", command=self.load_sample).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(quick_actions, text="Clear", style="Secondary.TButton", command=self.clear_text).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        status_panel = ttk.Frame(controls, style="Card.TFrame", padding=(0, 18, 0, 0))
        status_panel.grid(row=7, column=0, sticky="ew")
        status_panel.columnconfigure(0, weight=1)

        ttk.Label(status_panel, text="Status", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(status_panel, textvariable=self.status_var, style="Body.TLabel", wraplength=320, justify="left").grid(row=1, column=0, sticky="ew", pady=(6, 6))
        ttk.Label(status_panel, textvariable=self.detail_var, style="Muted.TLabel", wraplength=320, justify="left").grid(row=2, column=0, sticky="ew")

    def _bind_events(self) -> None:
        self.text_box.bind("<<Modified>>", self._on_text_modified)
        self.delay_var.trace_add("write", lambda *_: self._refresh_metrics())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_text_modified(self, _event: tk.Event) -> None:
        self.text_box.edit_modified(False)
        self._refresh_metrics()

    def _on_wpm_changed(self, _value: str) -> None:
        self.wpm_var.set(int(round(self.wpm_scale.get())))
        self.wpm_label.configure(text=str(self.wpm_var.get()))
        self._refresh_metrics()

    def _refresh_metrics(self) -> None:
        text = self.get_text()
        char_count = len(text)
        line_count = text.count("\n") + (1 if text else 0)
        self.stats_var.set(f"{char_count} characters across {line_count} line{'s' if line_count != 1 else ''}")

        if not text:
            self.estimate_var.set("Estimated typing time: 0s")
            return

        profile = self._build_profile()
        estimate = TypingRhythm(profile, seed=7).estimate_duration(text)
        countdown = max(profile.startup_delay_seconds, 0)
        self.estimate_var.set(f"Estimated typing time: {format_duration(estimate + countdown)}")

    def get_text(self) -> str:
        return self.text_box.get("1.0", "end-1c")

    def load_sample(self) -> None:
        sample = (
            "Typing Simulator Test\n"
            "\n"
            "This sample gives you a quick way to check the workflow.\n"
            "Paste your own content when you're ready, click Start Typing,\n"
            "switch to the destination field, and let the app reproduce it."
        )
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", sample)
        self._refresh_metrics()

    def clear_text(self) -> None:
        if self._typing_thread and self._typing_thread.is_alive():
            return
        self.text_box.delete("1.0", "end")
        self._refresh_metrics()

    def start_typing(self) -> None:
        if self._typing_thread and self._typing_thread.is_alive():
            return

        text = self.get_text()
        if not text:
            messagebox.showwarning("No text to type", "Paste or enter the source text first.")
            return

        profile = self._build_profile()
        self._pending_worker = WorkerState(text=text, profile=profile)
        self._stop_event.clear()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._countdown_remaining = profile.startup_delay_seconds
        self._set_status(
            f"Countdown started: {self._countdown_remaining}s.",
            "Move focus to the destination text box now. Typing begins automatically when the countdown ends.",
        )
        self._beep("countdown")
        self._run_countdown()

    def stop_typing(self) -> None:
        self._stop_event.set()
        if self._countdown_job is not None:
            self.root.after_cancel(self._countdown_job)
            self._countdown_job = None
            self._finish_idle_state()
            self._set_status("Countdown cancelled.", "Nothing was typed.")
            return

        if self._typing_thread and self._typing_thread.is_alive():
            self._set_status("Stopping typing...", "The current keypress will finish, then the worker will stop.")

    def _run_countdown(self) -> None:
        if self._stop_event.is_set():
            return

        if self._countdown_remaining <= 0:
            self._countdown_job = None
            self._launch_typing_worker()
            return

        self._set_status(
            f"Typing starts in {self._countdown_remaining}s.",
            "Click into the target browser field before the countdown reaches zero.",
        )
        self._countdown_remaining -= 1
        self._countdown_job = self.root.after(1000, self._run_countdown)

    def _launch_typing_worker(self) -> None:
        worker = self._pending_worker
        if worker is None:
            self._finish_idle_state()
            return

        self._beep("start")
        self._set_status("Typing in progress.", "Keep the destination field focused. Hold Esc to cancel immediately.")
        self._typing_thread = threading.Thread(
            target=self._typing_worker,
            args=(worker,),
            daemon=True,
        )
        self._typing_thread.start()

    def _typing_worker(self, worker: WorkerState) -> None:
        typer = KeyboardTyper()
        last_reported = 0

        def progress(current: int, total: int) -> None:
            nonlocal last_reported
            if current == total or current - last_reported >= 4:
                last_reported = current
                self._queue.put(("progress", (current, total)))

        try:
            result = typer.type_text(
                worker.text,
                worker.profile,
                stop_requested=self._stop_event.is_set,
                progress_callback=progress,
            )
            self._queue.put(("finished", result))
        except Exception as exc:  # pragma: no cover - depends on Windows input state
            self._queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                event, payload = self._queue.get_nowait()
                if event == "progress":
                    current, total = payload  # type: ignore[misc]
                    self._set_status(
                        f"Typing in progress: {current}/{total} characters.",
                        "Keep the target field focused until the final status appears here.",
                    )
                elif event == "finished":
                    self._handle_finished(payload)  # type: ignore[arg-type]
                elif event == "error":
                    self._finish_idle_state()
                    self._set_status("Typing stopped because of an error.", str(payload))
                    messagebox.showerror("Typing simulator", str(payload))
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue)

    def _handle_finished(self, result: TypingResult) -> None:
        self._finish_idle_state()
        detail = f"Typed {result.characters_typed} of {result.total_characters} characters."
        if result.completed:
            self._set_status(result.message, detail)
            self._beep("done")
        else:
            self._set_status(result.message, detail + " If needed, place the cursor where you want to resume and start again.")

    def _finish_idle_state(self) -> None:
        self._pending_worker = None
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self._typing_thread = None
        self._stop_event.clear()

    def _set_status(self, summary: str, detail: str) -> None:
        self.status_var.set(summary)
        self.detail_var.set(detail)

    def _build_profile(self) -> TimingProfile:
        delay = max(2, min(self._safe_int(self.delay_var, fallback=4), 15))
        wpm = max(20, min(self._safe_int(self.wpm_var, fallback=65), 160))
        humanize = bool(self.humanize_var.get())
        return TimingProfile(
            words_per_minute=wpm,
            startup_delay_seconds=delay,
            humanize=humanize,
        )

    def _safe_int(self, variable: tk.Variable, *, fallback: int) -> int:
        try:
            return int(variable.get())
        except (tk.TclError, TypeError, ValueError):
            return fallback

    def _beep(self, kind: str) -> None:
        if winsound is None:
            return

        sound_type = {
            "countdown": getattr(winsound, "MB_ICONASTERISK", winsound.MB_OK),
            "start": getattr(winsound, "MB_OK", 0),
            "done": getattr(winsound, "MB_ICONASTERISK", winsound.MB_OK),
        }.get(kind, getattr(winsound, "MB_OK", 0))

        try:
            winsound.MessageBeep(sound_type)
        except RuntimeError:
            pass

    def _on_close(self) -> None:
        self._stop_event.set()
        self.root.destroy()


def launch_app() -> None:
    root = tk.Tk()
    app = TypingSimulatorApp(root)
    root.mainloop()
