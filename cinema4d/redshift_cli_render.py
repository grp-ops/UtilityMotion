#!/usr/bin/env python3

# C4D + RS CLI RENDER [GUI]
# 25FPS DEFAULT
# SUPPORTS WIN-UNC PATHS

import json
import os
import shlex
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "REDSHIFT CLI BUT IN A GUI"
DEFAULT_FPS = 25
DEFAULT_FORMAT = "png"  # png | exr | tif | jpg
PRESET_EXT = ".c4drs.json"

class RenderConfig:
    def __init__(self):
        self.c4d_cmd = guess_c4d_command()
        self.scene_path = ""
        self.output_dir = ""
        self.base_name = "frame_"
        self.format = DEFAULT_FORMAT
        self.override_format = True
        self.override_res = False
        self.res_w = 1920
        self.res_h = 1080
        self.use_duration = True
        self.duration_seconds = 15.0
        self.fps = DEFAULT_FPS
        self.start_frame = 0
        self.end_frame = 100
        self.renderer = "Redshift"
        self.force_renderer = True
        self.threads = 0  # 0 = all
        self.extra_args = ""  # advanced users

    def to_dict(self):
        return self.__dict__.copy()

    @staticmethod
    def from_dict(d):
        cfg = RenderConfig()
        cfg.__dict__.update(d)
        return cfg

def guess_c4d_command():
    #NOTE:  [!] SET YOUR RENDER PATH HERE [!] 
    candidates = []
    if sys.platform.startswith("win"):
        candidates += [
            r"C:\Program Files\Maxon Cinema 4D 2025\Commandline.exe",
            r"C:\Program Files\Maxon Cinema 4D 2024\Commandline.exe",
            r"C:\Program Files\Maxon Cinema 4D R26\Commandline.exe",
        ]
    elif sys.platform == "darwin":
        candidates += [
            "/Applications/Maxon Cinema 4D 2025/Commandline.app/Contents/MacOS/Commandline",
            "/Applications/Maxon Cinema 4D 2024/Commandline.app/Contents/MacOS/Commandline",
            "/Applications/Maxon Cinema 4D R26/Commandline.app/Contents/MacOS/Commandline",
        ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""

def build_command(cfg: RenderConfig):
    # BUILD COMMAND AS LIST
    cmd = [cfg.c4d_cmd] if cfg.c4d_cmd else []

    if cfg.force_renderer and cfg.renderer:
        cmd += ["-renderer", cfg.renderer]

    # SCENE_PATH
    if not cfg.scene_path:
        raise ValueError("Scene path is required.")
    cmd += ["-render", cfg.scene_path]

    # OUTPUT_PATH
    if not cfg.output_dir:
        raise ValueError("Output directory is required.")
    base = cfg.base_name or "frame_"
    oimage = os.path.join(cfg.output_dir, base)
    cmd += ["-oimage", oimage]

    # FORMAT_OVERRIDE
    if cfg.override_format and cfg.format:
        cmd += ["-ofmt", cfg.format]

    # RESOLUTION_OVERRIDE
    if cfg.override_res:
        cmd += ["-ores", str(int(cfg.res_w)), str(int(cfg.res_h))]

    # FRAMES
    if cfg.use_duration:
        total_frames = int(round(cfg.duration_seconds * cfg.fps))
        start = 0
        end = total_frames
        cmd += ["-frame", str(start), str(end)]
    else:
        if cfg.end_frame < cfg.start_frame:
            raise ValueError("End frame must be >= start frame.")
        cmd += ["-frame", str(int(cfg.start_frame)), str(int(cfg.end_frame))]

    # THREADS (0 = ALL)
    cmd += ["-threads", str(int(cfg.threads))]

    # EXTRA_ARGS
    if cfg.extra_args.strip():
        # QUOTED_FLAGS
        cmd += shlex.split(cfg.extra_args, posix=not sys.platform.startswith("win"))

    # DISPLAY_STRING
    pretty = " ".join(shlex.quote(x) if not sys.platform.startswith("win") else quote_win(x) for x in cmd)
    return cmd, pretty

def quote_win(s: str) -> str:
    # WIN PATHS (WRAP IF SPACES OR BLACKSLASHES PRESENT)
    if any(c.isspace() for c in s) or "\\" in s:
        return f"\"{s}\""
    return s

def run_command_async(cmd, on_output, on_done):
    # RUN IN BACKGROUND THREAD
    def worker():
        try:
            #NOTE: USE `shell=False; pass list` FOR PROPER QUOTING
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            on_output("ERROR: Commandline executable not found.\n")
            on_done(1)
            return
        except Exception as e:
            on_output(f"ERROR: {e}\n")
            on_done(1)
            return

        ret = None
        with proc.stdout:
            for line in proc.stdout:
                on_output(line)
        ret = proc.wait()
        on_done(ret)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x720")
        self.minsize(920, 640)
        self.cfg = RenderConfig()
        self.create_widgets()

    # UI_LAYOUT
    def create_widgets(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        # PATHS
        path_frame = ttk.LabelFrame(root, text="Paths")
        path_frame.pack(fill="x", pady=(0,8))

        self.c4d_cmd_var = tk.StringVar(value=self.cfg.c4d_cmd)
        self.scene_var   = tk.StringVar(value=self.cfg.scene_path)
        self.outdir_var  = tk.StringVar(value=self.cfg.output_dir)
        self.base_var    = tk.StringVar(value=self.cfg.base_name)

        self._row(path_frame, "C4D Commandline:", self.c4d_cmd_var, browse_btn=True, file=True)
        self._row(path_frame, "Scene (.c4d):",   self.scene_var,   browse_btn=True, file=True)
        self._row(path_frame, "Output folder:",  self.outdir_var,  browse_btn=True, file=False)
        self._row(path_frame, "Base filename:",  self.base_var)

        # EXPORT_OPS
        export = ttk.LabelFrame(root, text="Export Options")
        export.pack(fill="x", pady=(0,8))

        self.override_fmt_var = tk.BooleanVar(value=self.cfg.override_format)
        self.format_var = tk.StringVar(value=self.cfg.format)
        fmt_row = ttk.Frame(export)
        fmt_row.pack(fill="x", pady=3)
        ttk.Checkbutton(fmt_row, text="Override Format", variable=self.override_fmt_var).pack(side="left")
        ttk.Label(fmt_row, text="Format:").pack(side="left", padx=(12,4))
        ttk.OptionMenu(fmt_row, self.format_var, self.format_var.get(), "png", "exr", "tif", "jpg").pack(side="left")

        self.override_res_var = tk.BooleanVar(value=self.cfg.override_res)
        self.res_w_var = tk.IntVar(value=self.cfg.res_w)
        self.res_h_var = tk.IntVar(value=self.cfg.res_h)
        res_row = ttk.Frame(export)
        res_row.pack(fill="x", pady=3)
        ttk.Checkbutton(res_row, text="Override Resolution", variable=self.override_res_var).pack(side="left")
        ttk.Label(res_row, text="W:").pack(side="left", padx=(12,4))
        ttk.Entry(res_row, textvariable=self.res_w_var, width=7).pack(side="left")
        ttk.Label(res_row, text="H:").pack(side="left", padx=(8,4))
        ttk.Entry(res_row, textvariable=self.res_h_var, width=7).pack(side="left")

        # TIMING
        timing = ttk.LabelFrame(root, text="Timing")
        timing.pack(fill="x", pady=(0,8))

        self.use_duration_var = tk.BooleanVar(value=self.cfg.use_duration)
        dur_row = ttk.Frame(timing)
        dur_row.pack(fill="x", pady=3)
        ttk.Radiobutton(dur_row, text="Use duration × FPS", variable=self.use_duration_var, value=True).pack(side="left")
        ttk.Label(dur_row, text="Duration (s):").pack(side="left", padx=(12,4))
        self.duration_var = tk.DoubleVar(value=self.cfg.duration_seconds)
        ttk.Entry(dur_row, textvariable=self.duration_var, width=8).pack(side="left")
        ttk.Label(dur_row, text="FPS:").pack(side="left", padx=(12,4))
        self.fps_var = tk.IntVar(value=self.cfg.fps or DEFAULT_FPS)
        ttk.Entry(dur_row, textvariable=self.fps_var, width=6).pack(side="left")

        fr_row = ttk.Frame(timing)
        fr_row.pack(fill="x", pady=3)
        ttk.Radiobutton(fr_row, text="Use explicit frame range", variable=self.use_duration_var, value=False).pack(side="left")
        ttk.Label(fr_row, text="Start:").pack(side="left", padx=(12,4))
        self.start_var = tk.IntVar(value=self.cfg.start_frame)
        ttk.Entry(fr_row, textvariable=self.start_var, width=8).pack(side="left")
        ttk.Label(fr_row, text="End:").pack(side="left", padx=(12,4))
        self.end_var = tk.IntVar(value=self.cfg.end_frame)
        ttk.Entry(fr_row, textvariable=self.end_var, width=8).pack(side="left")

        # EXTRA_CONFIGS
        adv = ttk.LabelFrame(root, text="Advanced")
        adv.pack(fill="x", pady=(0,8))

        self.force_renderer_var = tk.BooleanVar(value=self.cfg.force_renderer)
        self.renderer_var = tk.StringVar(value=self.cfg.renderer)
        self.threads_var = tk.IntVar(value=self.cfg.threads)
        self.extra_args_var = tk.StringVar(value=self.cfg.extra_args)

        adv_row1 = ttk.Frame(adv); adv_row1.pack(fill="x", pady=3)
        ttk.Checkbutton(adv_row1, text="Force Renderer", variable=self.force_renderer_var).pack(side="left")
        ttk.Label(adv_row1, text="Renderer:").pack(side="left", padx=(12,4))
        ttk.Entry(adv_row1, textvariable=self.renderer_var, width=16).pack(side="left")
        ttk.Label(adv_row1, text="Threads (0=all):").pack(side="left", padx=(12,4))
        ttk.Entry(adv_row1, textvariable=self.threads_var, width=8).pack(side="left")

        adv_row2 = ttk.Frame(adv); adv_row2.pack(fill="x", pady=3)
        ttk.Label(adv_row2, text="Extra args:").pack(side="left")
        ttk.Entry(adv_row2, textvariable=self.extra_args_var, width=80).pack(side="left", padx=(8,0))

        # PRESETS_RUN
        bar = ttk.Frame(root); bar.pack(fill="x", pady=(0,8))
        ttk.Button(bar, text="Save Preset…", command=self.on_save_preset).pack(side="left")
        ttk.Button(bar, text="Load Preset…", command=self.on_load_preset).pack(side="left", padx=(8,0))
        ttk.Button(bar, text="Preview Command", command=self.on_preview).pack(side="left", padx=(16,0))
        self.run_btn = ttk.Button(bar, text="Run Render", command=self.on_run)
        self.run_btn.pack(side="right")

        # OUTPUT_LOG
        log_frame = ttk.LabelFrame(root, text="Output / Log")
        log_frame.pack(fill="both", expand=True)
        self.cmd_preview = tk.Text(log_frame, height=4, wrap="word")
        self.cmd_preview.pack(fill="x", padx=6, pady=6)
        self.log = tk.Text(log_frame, height=16, wrap="word")
        self.log.pack(fill="both", expand=True, padx=6, pady=(0,6))

    def _row(self, parent, label, var, browse_btn=False, file=False):
        row = ttk.Frame(parent); row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=20).pack(side="left")
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)
        if browse_btn:
            ttk.Button(row, text="Browse…",
                       command=(lambda v=var, f=file: self.on_browse(v, f))).pack(side="left", padx=(6,0))

    # EVENT_HANDLERS
    def on_browse(self, var, file_mode: bool):
        if file_mode:
            path = filedialog.askopenfilename(title="Select file")
        else:
            path = filedialog.askdirectory(title="Select folder")
        if path:
            var.set(path)

    def sync_cfg(self):
        c = self.cfg
        c.c4d_cmd = self.c4d_cmd_var.get().strip()
        c.scene_path = self.scene_var.get().strip()
        c.output_dir = self.outdir_var.get().strip()
        c.base_name = self.base_var.get().strip() or "frame_"
        c.override_format = self.override_fmt_var.get()
        c.format = self.format_var.get().strip()
        c.override_res = self.override_res_var.get()
        c.res_w = int(self.res_w_var.get())
        c.res_h = int(self.res_h_var.get())
        c.use_duration = self.use_duration_var.get()
        c.duration_seconds = float(self.duration_var.get())
        c.fps = int(self.fps_var.get() or DEFAULT_FPS)
        c.start_frame = int(self.start_var.get())
        c.end_frame = int(self.end_var.get())
        c.force_renderer = self.force_renderer_var.get()
        c.renderer = self.renderer_var.get().strip() or "Redshift"
        c.threads = int(self.threads_var.get())
        c.extra_args = self.extra_args_var.get()
        return c

    def on_preview(self):
        try:
            cfg = self.sync_cfg()
            _, pretty = build_command(cfg)
            self.cmd_preview.delete("1.0", "end")
            self.cmd_preview.insert("end", pretty + "\n")
        except Exception as e:
            messagebox.showerror("Build Error", str(e))

    def on_run(self):
        try:
            cfg = self.sync_cfg()
            cmd, pretty = build_command(cfg)
        except Exception as e:
            messagebox.showerror("Build Error", str(e))
            return

        # MAKE SURE OUTPUT DIR EXISTS
        try:
            os.makedirs(cfg.output_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Output Error", f"Cannot create output folder:\n{e}")
            return

        self.cmd_preview.delete("1.0", "end")
        self.cmd_preview.insert("end", pretty + "\n")
        self.log.delete("1.0", "end")
        self.run_btn.config(state="disabled")
        self.append_log("Starting render…\n")

        def on_output(text):
            self.log.insert("end", text)
            self.log.see("end")
            self.update_idletasks()

        def on_done(code):
            if code == 0:
                self.append_log("\nRender completed successfully.\n")
            else:
                self.append_log(f"\nRender FAILED with exit code {code}.\n")
            self.run_btn.config(state="normal")

        run_command_async(cmd, on_output, on_done)

    def append_log(self, text):
        self.log.insert("end", text)
        self.log.see("end")

    def on_save_preset(self):
        cfg = self.sync_cfg()
        initial = os.path.splitext(os.path.basename(cfg.scene_path) or "preset")[0] + PRESET_EXT
        path = filedialog.asksaveasfilename(
            title="Save Preset",
            defaultextension=PRESET_EXT,
            initialfile=initial,
            filetypes=[("C4D RS Preset", f"*{PRESET_EXT}"), ("JSON", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg.to_dict(), f, indent=2)
            messagebox.showinfo("Preset Saved", f"Saved:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def on_load_preset(self):
        path = filedialog.askopenfilename(
            title="Load Preset",
            filetypes=[("C4D RS Preset", f"*{PRESET_EXT}"), ("JSON", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.cfg = RenderConfig.from_dict(data)
            self._apply_cfg_to_ui()
            messagebox.showinfo("Preset Loaded", f"Loaded:\n{path}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _apply_cfg_to_ui(self):
        c = self.cfg
        self.c4d_cmd_var.set(c.c4d_cmd)
        self.scene_var.set(c.scene_path)
        self.outdir_var.set(c.output_dir)
        self.base_var.set(c.base_name)
        self.override_fmt_var.set(c.override_format)
        self.format_var.set(c.format)
        self.override_res_var.set(c.override_res)
        self.res_w_var.set(c.res_w)
        self.res_h_var.set(c.res_h)
        self.use_duration_var.set(c.use_duration)
        self.duration_var.set(c.duration_seconds)
        self.fps_var.set(c.fps or DEFAULT_FPS)
        self.start_var.set(c.start_frame)
        self.end_var.set(c.end_frame)
        self.force_renderer_var.set(c.force_renderer)
        self.renderer_var.set(c.renderer)
        self.threads_var.set(c.threads)
        self.extra_args_var.set(c.extra_args)

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
