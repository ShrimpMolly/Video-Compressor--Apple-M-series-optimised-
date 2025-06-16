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
        self.geometry("520x650")

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
        self.input_type_var = tk.StringVar(value="files")

        self.inputs = []

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
        ttk.Button(self, text="Select Input", command=self.select_input).pack(
            fill="x", padx=10, pady=5)
        self.lbl_in = ttk.Label(self, text="No input selected")
        self.lbl_in.pack(fill="x", padx=10)
        ttk.Button(self, text="Select Output Directory",
                   command=self.select_output).pack(fill="x", padx=10, pady=5)
        self.lbl_out = ttk.Label(self, text="No output selected")
        self.lbl_out.pack(fill="x", padx=10)

        # file order list & reorder
        self.listbox = tk.Listbox(self, height=5)
        self.listbox.pack(fill="x", padx=10, pady=(5, 0))
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10)
        ttk.Button(btn_frame, text="Move Up",
                   command=self.move_up).pack(side="left")
        ttk.Button(btn_frame, text="Move Down",
                   command=self.move_down).pack(side="left", padx=5)

        # --- Settings section ---
        cfg = ttk.LabelFrame(self, text="Settings")
        cfg.pack(fill="x", padx=10, pady=5)
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

        # --- Compress button ---
        self.compress_button = ttk.Button(
            self, text="Compress", command=self.start_compression_thread)
        self.compress_button.pack(
            fill="x", padx=10, pady=10)

        btns2 = ttk.Frame(self)
        btns2.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns2, text="Pause",
                   command=lambda: self.pause_event.clear()).pack(side="left")
        ttk.Button(btns2, text="Resume",  command=self.pause_event.set).pack(
            side="left", padx=5)
        ttk.Button(btns2, text="Cancel",  command=lambda: self.cancel_event.set()).pack(
            side="left", padx=5)

        # --- Overall Progress ---
        self.overall_label = ttk.Label(self, text="Overall: 0/0 (0%)")
        self.overall_label.pack(fill="x", padx=10)
        self.overall_progress = ttk.Progressbar(
            self, orient="horizontal", length=500, mode="determinate")
        self.overall_progress.pack(fill="x", padx=10, pady=(0, 10))

        # --- File Progress ---
        self.file_label = ttk.Label(self, text="File: N/A (0%)")
        self.file_label.pack(fill="x", padx=10)
        self.file_progress = ttk.Progressbar(
            self, orient="horizontal", length=500, mode="determinate")
        self.file_progress.pack(fill="x", padx=10, pady=(0, 10))

        self.open_btn = ttk.Button(
            self, text="Open Output Folder", command=self.open_output, state="disabled")
        self.open_btn.pack(fill="x", padx=10, pady=(5, 10))

        self.eta_label = ttk.Label(self, text="ETA: N/A")
        self.eta_label.pack(fill="x", padx=10)
        # Thumbnail display
        self.thumb_label = ttk.Label(self)
        self.thumb_label.pack(fill="both", padx=10, pady=5)

    def select_input(self):
        fs = filedialog.askopenfilenames(
            title="Select video files",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.avi *.mov *.flv *.wmv"),
                ("All", "*.*")
            ]
        )
        self.inputs = [Path(x) for x in fs]
        self.lbl_in.config(text=f"{len(self.inputs)} file(s) selected")
        self.refresh_listbox()
        if len(self.inputs) == 1:
            self.recommend_settings(self.inputs[0])

    def select_output(self):
        d = filedialog.askdirectory(title="Select output")
        if d:
            self.outdir = Path(d)
            self.lbl_out.config(text=str(self.outdir))
            self.open_btn.config(state="normal")

    def recommend_settings(self, fp: Path):
        try:
            dur = float(subprocess.check_output([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(fp)
            ]))
            wh = subprocess.check_output([
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                str(fp)
            ])
            # w, h = map(int, wh.decode().split(',')) # Original line
            # Strip leading/trailing whitespace from the whole output
            wh_str = wh.decode().strip()
            parts = wh_str.split(',')
            # if len(parts) == 2: # Previous check
            if len(parts) >= 2:  # Ensure we have at least two parts
                w_str_cleaned = parts[0].strip()
                h_str_cleaned = parts[1].strip()
                # Ensure parts are not empty after stripping, before calling int()
                if not w_str_cleaned or not h_str_cleaned:
                    raise ValueError(
                        f"ffprobe returned empty string for width or height. Raw output: '{wh.decode()}'")
                w = int(w_str_cleaned)
                h = int(h_str_cleaned)
            else:
                # This will be caught by the generic Exception handler below and show a message box
                raise ValueError(
                    f"ffprobe output for width/height not in expected format (expected at least 2 comma-separated values). Raw output: '{wh.decode()}'")
            ts = 350 * 1024 * 1024
            # detect audio channels
            ch_output = subprocess.check_output([
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=channels",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(fp)
            ])
            ch_str = ch_output.decode().strip()
            if not ch_str:  # Handle cases where audio stream might be missing or channels not reported
                messagebox.showwarning(
                    "Audio Info", f"Could not determine audio channels for {fp.name}. Assuming mono for recommendations.")
                ch = 1
            else:
                ch = int(ch_str)

            # recommend audio bitrate based on channels and mono setting
            if self.mono_var.get():
                rec_ab = 96
            else:
                rec_ab = 96 if ch == 1 else 128
            self.audio_bitrate_var.set(f"{rec_ab}k")
            ab = int(self.audio_bitrate_var.get().rstrip('k')) * 1000
            tb = ts * 8 / dur
            vk = int(max(tb - ab, 100000) / 1000)  # Ensure vk is at least 100k

            self.resolution_var.set(f"{w}x{h}")
            self.codec_var.set("hevc_videotoolbox" if self.hw else "libx265")
            self.preset_var.set("slow")
            self.video_bitrate_var.set(vk)

            messagebox.showinfo(
                "Recommended Settings",
                f"Output size ~350MB\\n"
                f"Resolution: {w}x{h}\\n"
                f"Codec: {self.codec_var.get()}\\n"
                f"Preset: {self.preset_var.get()}\\n"
                f"Audio: {self.audio_bitrate_var.get()}\\n"
                f"Video: {vk}kbit/s"
            )
        except subprocess.CalledProcessError as e:
            messagebox.showerror(
                "Error Reading Video Info", f"Failed to get video details for {fp.name} using ffprobe. Error: {e}")
        except Exception as e:
            messagebox.showerror(
                "Recommendation Error", f"An unexpected error occurred while generating recommendations for {fp.name}: {e}")

    def start_compression_thread(self):
        threading.Thread(target=self.compress_all, daemon=True).start()

    def compress_all(self):
        if not self.inputs or not self.outdir:
            self.after(0, lambda: messagebox.showwarning(
                "Missing", "Select input and output"))
            return

        total = len(self.inputs)
        # thumbnail timing for low-rate grabs (~0.03 fps)
        last_thumb_time = 0
        thumb_interval = 1 / 0.03
        # init overall
        self.after(0, lambda: (
            self.overall_progress.configure(maximum=total, value=0),
            self.overall_label.config(text=f"Overall: 0/{total} (0%)")
        ))

        for idx, inp in enumerate(self.inputs, start=1):
            # apply per-file recommended settings before compression
            self.recommend_settings(inp)
            start_time = time.time()
            # get duration
            dur = float(subprocess.check_output([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(inp)
            ]))
            # init file
            self.after(0, lambda d=dur, name=inp.name: (
                self.file_progress.configure(maximum=d, value=0),
                self.file_label.config(text=(
                    f"File: {name} (0%) - Res: {self.resolution_var.get()} "
                    f"Codec: {self.codec_var.get()} "
                    f"{'Bitrate: '+str(self.video_bitrate_var.get())+'kbit/s' if self.video_bitrate_var.get()>0 else 'CRF: '+str(self.crf_var.get())} "
                    f"Audio: {self.audio_bitrate_var.get()}"
                ))
            ))

            stem = inp.stem + "_mobile"
            out = self.outdir / f"{stem}.mp4"
            cmd = ["ffmpeg", "-y"]
            # apply trim options if provided
            if self.trim_start_var.get():
                cmd += ["-ss", self.trim_start_var.get()]
            if "videotoolbox" in self.codec_var.get():
                cmd += ["-hwaccel", "videotoolbox"]
            cmd += [
                "-i", str(inp),
                # add trim end if specified
            ] + (["-to", self.trim_end_var.get()] if self.trim_end_var.get() else []) + [
                "-c:v", self.codec_var.get(),
                "-preset", self.preset_var.get(),
                "-vf", f"scale={self.resolution_var.get()}",
                "-pix_fmt", "yuv420p",
            ]
            # if mono is requested, force single channel audio
            if self.mono_var.get():
                cmd += ["-ac", "1"]
            if self.video_bitrate_var.get() > 0:
                cmd += ["-b:v", f"{self.video_bitrate_var.get()}k"]
            else:
                cmd += ["-crf", str(self.crf_var.get())]
            cmd += ["-c:a", "aac", "-b:a", self.audio_bitrate_var.get(),
                    str(out)]

            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
            for line in proc.stderr:
                # respect pause/cancel
                while not self.pause_event.is_set():
                    time.sleep(0.1)
                if self.cancel_event.is_set():
                    break

                m = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
                if m:
                    h, mn, s = map(float, m.groups())
                    secs = h*3600 + mn*60 + s
                    pct_file = secs / dur * 100
                    elapsed = time.time() - start_time
                    # compute estimated time remaining, avoid extreme values early on
                    if secs > 1:
                        eta = (elapsed / secs) * (dur - secs)
                    else:
                        eta = dur - secs
                    # clamp to non-negative
                    eta = max(eta, 0)
                    self.after(0, lambda pct=pct_file, secs=secs, name=inp.name, e=eta: (
                        self.file_progress.configure(value=secs),
                        self.file_label.config(text=(
                            f"File: {name} ({pct:.1f}%) - Res: {self.resolution_var.get()} "
                            f"Codec: {self.codec_var.get()} "
                            f"{'Bitrate: '+str(self.video_bitrate_var.get())+'kbit/s' if self.video_bitrate_var.get()>0 else 'CRF: '+str(self.crf_var.get())} "
                            f"Audio: {self.audio_bitrate_var.get()}"
                        )),
                        self.eta_label.config(text=f"ETA: {e:.1f}s")
                    ))
                    # thumbnail extraction at low rate
                    if time.time() - last_thumb_time >= thumb_interval:
                        thumb_cmd = [
                            "ffmpeg", "-ss", str(secs), "-i", str(inp),
                            "-frames:v", "1", "-vf", "scale=160:-1",
                            "-f", "image2pipe", "pipe:1"
                        ]
                        thumb_proc = subprocess.Popen(
                            thumb_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
                        )
                        thumb_data = thumb_proc.stdout.read()
                        thumb_proc.wait()
                        try:
                            img = Image.open(io.BytesIO(thumb_data))
                            photo = ImageTk.PhotoImage(img)
                            # update thumbnail on main thread
                            self.after(0, lambda p=photo: (
                                self.thumb_label.config(image=p),
                                setattr(self, 'current_thumb', p)
                            ))
                        except Exception:
                            pass
                        last_thumb_time = time.time()
            proc.wait()

            if self.cancel_event.is_set():
                break

            # update overall
            pct_overall = idx / total * 100
            self.after(0, lambda i=idx, pct=pct_overall: (
                self.overall_progress.step(),
                self.overall_label.config(
                    text=f"Overall: {i}/{total} ({pct:.1f}%)")
            ))

        # done
        self.after(0, lambda: messagebox.showinfo(
            "Done", "Compression complete!"))
        self.cancel_event.clear()
        self.pause_event.set()

    def move_up(self):
        idx = self.listbox.curselection()
        if not idx or idx[0] == 0:
            return
        i = idx[0]
        self.inputs[i], self.inputs[i-1] = self.inputs[i-1], self.inputs[i]
        self.refresh_listbox()
        self.listbox.selection_set(i-1)

    def move_down(self):
        idx = self.listbox.curselection()
        if not idx or idx[0] == len(self.inputs)-1:
            return
        i = idx[0]
        self.inputs[i], self.inputs[i+1] = self.inputs[i+1], self.inputs[i]
        self.refresh_listbox()
        self.listbox.selection_set(i+1)

    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for p in self.inputs:
            self.listbox.insert(tk.END, p.name)

    def open_output(self):
        if self.outdir:
            if sys.platform == "darwin":
                subprocess.run(["open", str(self.outdir)])
            elif sys.platform.startswith("win"):
                os.startfile(str(self.outdir))
            else:
                subprocess.run(["xdg-open", str(self.outdir)])


if __name__ == "__main__":
    app = VideoCompressorApp()
    app.mainloop()
