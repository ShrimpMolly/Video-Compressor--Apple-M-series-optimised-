#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import subprocess
import threading
import re
from pathlib import Path
import platform
import sys
import time
import shutil
import os
import io
from PIL import Image, ImageTk


class VideoCompressorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Compressor")
        # Increased height to accommodate the new button and better thumbnail display
        self.geometry("520x680")

        # --- Variables ---
        self.resolution_var = tk.StringVar(value="640x360")
        self.codec_var = tk.StringVar(value="")
        self.crf_var = tk.IntVar(value=28)
        self.preset_var = tk.StringVar(value="")
        self.audio_bitrate_var = tk.StringVar(value="96k")
        self.video_bitrate_var = tk.IntVar(value=0)
        self.mono_var = tk.BooleanVar(value=False)
        self.trim_start_var = tk.StringVar(value="")
        self.trim_end_var = tk.StringVar(value="")
        # Currently unused, but kept for future extension
        self.input_type_var = tk.StringVar(value="files")

        self.inputs = []
        # FIX: Store individual file settings
        self.file_settings = {}
        # FIX: Track which file's settings are currently displayed in the UI
        self.currently_selected_path = None

        # Pause/Resume and Cancel flags
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.cancel_event = threading.Event()

        self.outdir = None

        # detect Apple Silicon
        self.hw = (sys.platform ==
                   "darwin" and platform.machine().startswith("arm"))
        self.codec_var.set("hevc_videotoolbox" if self.hw else "libx265")
        self.preset_var.set("slow")

        self.create_widgets()

        if not shutil.which("ffmpeg"):
            messagebox.showwarning(
                "FFmpeg Not Found", "FFmpeg executable not found. Please install or add to PATH.\nVisit https://ffmpeg.org/download.html")
            self.compress_button.config(state="disabled")

    def create_widgets(self):
        # --- Input section ---
        f1 = ttk.LabelFrame(self, text="Input Type")
        f1.pack(fill="x", padx=10, pady=5)
        ttk.Radiobutton(f1, text="Files",  variable=self.input_type_var,
                        value="files").pack(side="left", padx=5)
        ttk.Radiobutton(f1, text="Folder", variable=self.input_type_var,
                        value="folder").pack(side="left", padx=5)
        ttk.Button(self, text="Select Input Files", command=self.select_input).pack(
            fill="x", padx=10, pady=5)
        ttk.Button(self, text="Clear List", command=self.clear_list).pack(
            fill="x", padx=10, pady=(0, 5))
        self.lbl_in = ttk.Label(self, text="No input selected")
        self.lbl_in.pack(fill="x", padx=10)
        ttk.Button(self, text="Select Output Directory",
                   command=self.select_output).pack(fill="x", padx=10, pady=5)
        self.lbl_out = ttk.Label(self, text="No output selected")
        self.lbl_out.pack(fill="x", padx=10)

        # file order list & reorder
        self.listbox = tk.Listbox(self, height=5)
        self.listbox.pack(fill="x", padx=10, pady=(5, 0))
        # load settings when a file is selected
        self.listbox.bind('<<ListboxSelect>>', self.on_file_select)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10)
        ttk.Button(btn_frame, text="Move Up",
                   command=self.move_up).pack(side="left")
        ttk.Button(btn_frame, text="Move Down",
                   command=self.move_down).pack(side="left", padx=5)
        # FIX: Added button to apply recommendations on demand
        ttk.Button(btn_frame, text="Recommend Settings for Selected",
                   command=self.apply_recommendations).pack(side="left", padx=5)

        # --- Settings section ---
        cfg = ttk.LabelFrame(self, text="Settings (for selected file)")
        cfg.pack(fill="x", padx=10, pady=5)
        # ... (rest of the settings widgets are unchanged) ...
        ttk.Label(cfg, text="Resolution:").grid(
            row=0, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(cfg, textvariable=self.resolution_var, width=12).grid(
            row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(cfg, text="Codec:").grid(
            row=1, column=0, sticky="e", padx=5, pady=2)
        codecs = ["libx265", "libx264"]
        if self.hw:
            codecs += ["hevc_videotoolbox", "h264_videotoolbox"]
        ttk.OptionMenu(cfg, self.codec_var, self.codec_var.get(),
                       *codecs).grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(cfg, text="CRF:").grid(
            row=2, column=0, sticky="e", padx=5, pady=2)
        ttk.Spinbox(cfg, from_=0, to=51, textvariable=self.crf_var, width=5).grid(
            row=2, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(cfg, text="Preset:").grid(
            row=3, column=0, sticky="e", padx=5, pady=2)
        presets = ["ultrafast", "fast", "medium", "slow", "slower", "veryslow"]
        ttk.OptionMenu(cfg, self.preset_var, self.preset_var.get(
        ), *presets).grid(row=3, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(cfg, text="Audio bitrate:").grid(
            row=4, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(cfg, textvariable=self.audio_bitrate_var, width=7).grid(
            row=4, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(cfg, text="Video bitrate (kbit/s):").grid(row=5,
                                                            column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(cfg, textvariable=self.video_bitrate_var, width=10).grid(
            row=5, column=1, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(cfg, text="Mono audio", variable=self.mono_var).grid(
            row=6, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        ttk.Label(cfg, text="Trim Start (hh:mm:ss):").grid(
            row=7, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(cfg, textvariable=self.trim_start_var, width=12).grid(
            row=7, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(cfg, text="Trim End (hh:mm:ss):").grid(
            row=8, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(cfg, textvariable=self.trim_end_var, width=12).grid(
            row=8, column=1, sticky="w", padx=5, pady=2)

        # --- Control buttons ---
        self.compress_button = ttk.Button(
            self, text="Compress", command=self.start_compression_thread)
        self.compress_button.pack(fill="x", padx=10, pady=10)
        btns2 = ttk.Frame(self)
        btns2.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns2, text="Pause",
                   command=lambda: self.pause_event.clear()).pack(side="left")
        ttk.Button(btns2, text="Resume",  command=self.pause_event.set).pack(
            side="left", padx=5)
        ttk.Button(btns2, text="Cancel",  command=lambda: self.cancel_event.set()).pack(
            side="left", padx=5)

        # --- Progress section ---
        self.overall_label = ttk.Label(self, text="Overall: 0/0 (0%)")
        self.overall_label.pack(fill="x", padx=10)
        self.overall_progress = ttk.Progressbar(
            self, orient="horizontal", length=500, mode="determinate")
        self.overall_progress.pack(fill="x", padx=10, pady=(0, 10))
        self.file_label = ttk.Label(self, text="File: N/A (0%)")
        self.file_label.pack(fill="x", padx=10)
        self.file_progress = ttk.Progressbar(
            self, orient="horizontal", length=500, mode="determinate")
        self.file_progress.pack(fill="x", padx=10, pady=(0, 10))
        self.eta_label = ttk.Label(self, text="ETA: N/A")
        self.eta_label.pack(fill="x", padx=10)
        self.open_btn = ttk.Button(
            self, text="Open Output Folder", command=self.open_output, state="disabled")
        self.open_btn.pack(fill="x", padx=10, pady=(5, 10))
        self.thumb_label = ttk.Label(self)
        self.thumb_label.pack(fill="both", expand=True, padx=10, pady=5)

    def select_input(self):
        fs = filedialog.askopenfilenames(
            title="Select video files",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.avi *.mov *.flv *.wmv"), ("All", "*.*")]
        )
        new_inputs = [Path(x) for x in fs if Path(x) not in self.inputs]
        self.inputs.extend(new_inputs)
        # FIX: Initialize settings for each newly added file based on current UI defaults
        for p in new_inputs:
            self.file_settings[p] = {
                'resolution': self.resolution_var.get(), 'codec': self.codec_var.get(),
                'crf': self.crf_var.get(), 'preset': self.preset_var.get(),
                'audio_bitrate': self.audio_bitrate_var.get(), 'video_bitrate': self.video_bitrate_var.get(),
                'mono': self.mono_var.get(), 'trim_start': self.trim_start_var.get(),
                'trim_end': self.trim_end_var.get()
            }
        self.lbl_in.config(text=f"{len(self.inputs)} file(s) selected")
        self.refresh_listbox()

    def select_output(self):
        d = filedialog.askdirectory(title="Select output")
        if d:
            self.outdir = Path(d)
            self.lbl_out.config(text=str(self.outdir))
            self.open_btn.config(state="normal")

    def apply_recommendations(self):
        """Applies recommended settings to the currently selected file."""
        if not self.listbox.curselection():
            messagebox.showwarning(
                "No Selection", "Please select a file from the list first.")
            return
        idx = self.listbox.curselection()[0]
        selected_path = self.inputs[idx]
        # This function updates the UI variables
        self.recommend_settings(selected_path)
        # After UI is updated, save them to the file's settings dictionary
        self._save_current_settings()

    def recommend_settings(self, fp: Path):
        """Calculates recommended settings for a file and updates the UI."""
        try:
            dur = float(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(fp)
            ], text=True))
            wh_str = subprocess.check_output([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0", str(
                    fp)
            ], text=True).strip()
            w, h = map(int, wh_str.split(','))
            ts = 350 * 1024 * 1024  # Target size in bytes (~350MB)
            ch_str = subprocess.check_output([
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=channels", "-of", "default=noprint_wrappers=1:nokey=1", str(
                    fp)
            ], text=True).strip()
            ch = int(ch_str) if ch_str else 1

            # Recommend audio bitrate based on channels
            rec_ab = 96 if ch == 1 else 128
            self.audio_bitrate_var.set(f"{rec_ab}k")
            ab_bits = rec_ab * 1000
            total_bitrate = ts * 8 / dur
            vk = int(max(total_bitrate - ab_bits, 100000) / 1000)

            # Update UI variables with recommendations
            self.resolution_var.set(f"{w}x{h}")
            self.codec_var.set("hevc_videotoolbox" if self.hw else "libx265")
            self.preset_var.set("slow")
            self.video_bitrate_var.set(vk)
            self.crf_var.set(28)  # Reset CRF as bitrate is now primary
            self.mono_var.set(ch == 1)

        except (subprocess.CalledProcessError, ValueError) as e:
            messagebox.showerror(
                "Error Reading Video Info", f"Failed to get video details for {fp.name}. It may be corrupt or have no video/audio stream.\n\nError: {e}")
        except Exception as e:
            messagebox.showerror(
                "Recommendation Error", f"An unexpected error occurred while generating recommendations for {fp.name}: {e}")

    def start_compression_thread(self):
        threading.Thread(target=self.compress_all, daemon=True).start()

    def compress_all(self):
        # FIX: Save any pending changes for the last selected file before starting
        self.after(0, self._save_current_settings)

        if not self.inputs or not self.outdir:
            self.after(0, lambda: messagebox.showwarning(
                "Missing", "Select input files and an output directory."))
            return

        total = len(self.inputs)
        last_thumb_time = 0
        thumb_interval = 1 / 0.03
        self.after(0, lambda: (
            self.overall_progress.config(maximum=total, value=0),
            self.overall_label.config(text=f"Overall: 0/{total} (0%)")
        ))

        for idx, inp in enumerate(self.inputs, start=1):
            if self.cancel_event.is_set():
                break

            # --- FIX: GET PER-FILE SETTINGS ---
            settings = self.file_settings[inp]
            start_time = time.time()
            try:
                dur = float(subprocess.check_output([
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(inp)
                ], text=True))
            except (subprocess.CalledProcessError, ValueError):
                dur = 1  # Avoid division by zero for unreadable files

            # FIX: Update file label with correct per-file settings
            self.after(0, lambda d=dur, name=inp.name, s=settings: (
                self.file_progress.config(maximum=d, value=0),
                self.file_label.config(text=(
                    f"File: {name} (0%) - Res: {s['resolution']} | Codec: {s['codec']} | "
                    f"{'Bitrate: '+str(s['video_bitrate'])+'k' if s['video_bitrate'] > 0 else 'CRF: '+str(s['crf'])} | "
                    f"Audio: {s['audio_bitrate']}"
                ))
            ))

            stem = inp.stem + "_mobile"
            out = self.outdir / f"{stem}.mp4"

            # --- FIX: Build command using per-file settings from the dictionary ---
            cmd = ["ffmpeg", "-y"]
            if settings['trim_start']:
                cmd += ["-ss", settings['trim_start']]
            if "videotoolbox" in settings['codec']:
                cmd += ["-hwaccel", "videotoolbox"]
            cmd += ["-i", str(inp)]
            if settings['trim_end']:
                cmd += ["-to", settings['trim_end']]
            cmd += [
                "-c:v", settings['codec'], "-preset", settings['preset'],
                "-vf", f"scale={settings['resolution']}", "-pix_fmt", "yuv420p",
            ]
            if settings['mono']:
                cmd += ["-ac", "1"]
            if settings['video_bitrate'] > 0:
                cmd += ["-b:v", f"{settings['video_bitrate']}k"]
            else:
                cmd += ["-crf", str(settings['crf'])]
            cmd += ["-c:a", "aac", "-b:a", settings['audio_bitrate'], str(out)]

            proc = subprocess.Popen(
                cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            for line in proc.stderr:
                while not self.pause_event.is_set():
                    time.sleep(0.1)
                if self.cancel_event.is_set():
                    break

                m = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
                if m:
                    h, mn, s = map(float, m.groups())
                    secs = h*3600 + mn*60 + s
                    pct_file = (secs / dur * 100) if dur > 0 else 0
                    elapsed = time.time() - start_time
                    eta = (elapsed / secs) * \
                        (dur - secs) if secs > 1 else dur - secs
                    eta = max(eta, 0)
                    # FIX: Update progress label with per-file settings
                    self.after(0, lambda p=pct_file, sc=secs, n=inp.name, e=eta, st=settings: (
                        self.file_progress.config(value=sc),
                        self.file_label.config(text=(
                            f"File: {n} ({p:.1f}%) - Res: {st['resolution']} | Codec: {st['codec']} | "
                            f"{'Bitrate: '+str(st['video_bitrate'])+'k' if st['video_bitrate'] > 0 else 'CRF: '+str(st['crf'])} | "
                            f"Audio: {st['audio_bitrate']}"
                        )),
                        self.eta_label.config(text=f"ETA: {e:.1f}s")
                    ))
                    if time.time() - last_thumb_time >= thumb_interval:
                        thumb_cmd = ["ffmpeg", "-ss", str(secs), "-i", str(inp), "-frames:v", "1",
                                     "-vf", "scale=240:-1", "-f", "image2pipe", "pipe:1"]
                        thumb_proc = subprocess.Popen(
                            thumb_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                        thumb_data = thumb_proc.stdout.read()
                        thumb_proc.wait()
                        if thumb_data:
                            try:
                                img = Image.open(io.BytesIO(thumb_data))
                                photo = ImageTk.PhotoImage(img)
                                self.after(0, lambda p=photo: (
                                    self.thumb_label.config(image=p), setattr(self, 'current_thumb', p)))
                            except Exception:
                                pass
                        last_thumb_time = time.time()
            proc.wait()
            if self.cancel_event.is_set():
                break

            pct_overall = idx / total * 100
            self.after(0, lambda i=idx, pct=pct_overall: (
                self.overall_progress.config(value=i),
                self.overall_label.config(
                    text=f"Overall: {i}/{total} ({pct:.1f}%)")
            ))

        msg = "Compression cancelled." if self.cancel_event.is_set() else "Compression complete!"
        self.after(0, lambda: messagebox.showinfo("Done", msg))
        self.cancel_event.clear()
        self.pause_event.set()

    def _save_current_settings(self):
        """Saves the current UI settings to the file tracked by currently_selected_path."""
        if self.currently_selected_path and self.currently_selected_path in self.file_settings:
            self.file_settings[self.currently_selected_path] = {
                'resolution': self.resolution_var.get(), 'codec': self.codec_var.get(),
                'crf': self.crf_var.get(), 'preset': self.preset_var.get(),
                'audio_bitrate': self.audio_bitrate_var.get(), 'video_bitrate': self.video_bitrate_var.get(),
                'mono': self.mono_var.get(), 'trim_start': self.trim_start_var.get(),
                'trim_end': self.trim_end_var.get()
            }

    def on_file_select(self, event):
        # FIX: Save settings for the previously selected file before loading new ones
        self._save_current_settings()
        if not self.listbox.curselection():
            self.currently_selected_path = None
            return
        idx = self.listbox.curselection()[0]
        path = self.inputs[idx]
        self.currently_selected_path = path  # Update the tracker
        settings = self.file_settings.get(path)
        if settings:
            self.resolution_var.set(settings['resolution'])
            self.codec_var.set(settings['codec'])
            self.crf_var.set(settings['crf'])
            self.preset_var.set(settings['preset'])
            self.audio_bitrate_var.set(settings['audio_bitrate'])
            self.video_bitrate_var.set(settings['video_bitrate'])
            self.mono_var.set(settings['mono'])
            self.trim_start_var.set(settings['trim_start'])
            self.trim_end_var.set(settings['trim_end'])

    def move_up(self):
        idx_tuple = self.listbox.curselection()
        if not idx_tuple or idx_tuple[0] == 0:
            return
        i = idx_tuple[0]
        self.inputs[i], self.inputs[i-1] = self.inputs[i-1], self.inputs[i]
        self.refresh_listbox()
        self.listbox.selection_set(i-1)
        self.listbox.event_generate("<<ListboxSelect>>")

    def move_down(self):
        idx_tuple = self.listbox.curselection()
        if not idx_tuple or idx_tuple[0] == len(self.inputs)-1:
            return
        i = idx_tuple[0]
        self.inputs[i], self.inputs[i+1] = self.inputs[i+1], self.inputs[i]
        self.refresh_listbox()
        self.listbox.selection_set(i+1)
        self.listbox.event_generate("<<ListboxSelect>>")

    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for p in self.inputs:
            self.listbox.insert(tk.END, p.name)

    def clear_list(self):
        self._save_current_settings()
        self.inputs.clear()
        self.file_settings.clear()
        self.currently_selected_path = None
        self.listbox.delete(0, tk.END)
        self.lbl_in.config(text="No input selected")

    def open_output(self):
        if self.outdir and self.outdir.exists():
            if sys.platform == "darwin":
                subprocess.run(["open", str(self.outdir)])
            elif sys.platform.startswith("win"):
                os.startfile(str(self.outdir))
            else:
                subprocess.run(["xdg-open", str(self.outdir)])


if __name__ == "__main__":
    app = VideoCompressorApp()
    app.mainloop()
