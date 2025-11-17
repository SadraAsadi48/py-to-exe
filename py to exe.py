import os
import sys
import subprocess
import threading
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

# -------------------- Helpers --------------------
def ensure_pyinstaller(log_fn):
    """Install pyinstaller via pip if not present."""
    try:
        import PyInstaller  # noqa: F401
        log_fn("PyInstaller already installed.\n")
        return True
    except Exception:
        log_fn("PyInstaller not found. Installing via pip...\n")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            log_fn("PyInstaller installed successfully.\n")
            return True
        except subprocess.CalledProcessError as e:
            log_fn(f"Failed to install PyInstaller: {e}\n")
            return False

def run_subprocess(cmd, cwd, log_fn, on_done=None):
    """Run subprocess and stream stdout/stderr to log_fn."""
    log_fn("Running: " + " ".join(cmd) + "\n\n")
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    except Exception as e:
        log_fn(f"Failed to start process: {e}\n")
        if on_done:
            on_done(False)
        return

    # Stream output
    for line in proc.stdout:
        log_fn(line)
    proc.wait()
    success = (proc.returncode == 0)
    log_fn("\nProcess finished with exit code: {}\n".format(proc.returncode))
    if on_done:
        on_done(success)

# -------------------- GUI --------------------
class ConverterGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("py → exe Converter (PyInstaller frontend)")
        self.geometry("720x520")
        self.resizable(False, False)

        # Variables
        self.src_path = tk.StringVar()
        self.icon_path = tk.StringVar()
        self.out_name = tk.StringVar()
        self.onefile = tk.BooleanVar(value=True)
        self.windowed = tk.BooleanVar(value=False)

        # Layout
        frm = tk.Frame(self, padx=12, pady=12)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Source .py file:", anchor="w").grid(row=0, column=0, sticky="w")
        ent_src = tk.Entry(frm, textvariable=self.src_path, width=60)
        ent_src.grid(row=1, column=0, columnspan=3, sticky="w")
        tk.Button(frm, text="Browse...", command=self.browse_src, width=12).grid(row=1, column=3, padx=6)

        tk.Label(frm, text="Output name (optional, without .exe):", anchor="w").grid(row=2, column=0, sticky="w", pady=(8,0))
        tk.Entry(frm, textvariable=self.out_name, width=30).grid(row=3, column=0, sticky="w")

        tk.Checkbutton(frm, text="One-file (--onefile)", variable=self.onefile).grid(row=3, column=1, sticky="w", padx=8)
        tk.Checkbutton(frm, text="Windowed (--noconsole)", variable=self.windowed).grid(row=3, column=2, sticky="w", padx=8)

        tk.Label(frm, text="Icon (.ico) (optional):", anchor="w").grid(row=4, column=0, sticky="w", pady=(8,0))
        tk.Entry(frm, textvariable=self.icon_path, width=60).grid(row=5, column=0, columnspan=3, sticky="w")
        tk.Button(frm, text="Browse Icon...", command=self.browse_icon, width=12).grid(row=5, column=3, padx=6)

        tk.Button(frm, text="Start Convert", command=self.start_convert, bg="#1E88E5", fg="white", width=16).grid(row=6, column=0, pady=12)

        # Log text box
        tk.Label(frm, text="Log:").grid(row=7, column=0, sticky="w")
        self.logbox = tk.Text(frm, height=16, width=86, state="disabled", wrap="none")
        self.logbox.grid(row=8, column=0, columnspan=4, pady=(4,0))
        # scrollbar
        sb = tk.Scrollbar(frm, command=self.logbox.yview)
        sb.grid(row=8, column=4, sticky="ns")
        self.logbox['yscrollcommand'] = sb.set

        # Info label
        self.info_lbl = tk.Label(frm, text="Note: Best results on Windows. PyInstaller will create 'dist' and 'build' folders.", fg="#666")
        self.info_lbl.grid(row=9, column=0, columnspan=4, pady=(8,0), sticky="w")

    def browse_src(self):
        f = filedialog.askopenfilename(filetypes=[("Python files", "*.py")])
        if f:
            self.src_path.set(f)

    def browse_icon(self):
        f = filedialog.askopenfilename(filetypes=[("ICO files", "*.ico")])
        if f:
            self.icon_path.set(f)

    def log(self, text):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", text)
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def start_convert(self):
        src = self.src_path.get().strip()
        if not src or not os.path.isfile(src) or not src.lower().endswith(".py"):
            messagebox.showerror("Error", "Please select a valid .py source file.")
            return

        # disable UI while running
        self.disable_ui(True)
        threading.Thread(target=self._convert_thread, daemon=True).start()

    def disable_ui(self, disabled):
        for child in self.winfo_children():
            try:
                child_state = "disabled" if disabled else "normal"
                # don't disable text widget
                if isinstance(child, tk.Text):
                    continue
                # disable direct children (frame), then iterate inner widgets
                if isinstance(child, tk.Frame):
                    for w in child.winfo_children():
                        if isinstance(w, tk.Text):
                            continue
                        try:
                            w.configure(state=child_state)
                        except Exception:
                            pass
            except Exception:
                pass

    def _convert_thread(self):
        try:
            self.log("=== Starting conversion ===\n")
            src = self.src_path.get().strip()
            src_dir = os.path.dirname(src) or "."
            src_name = os.path.splitext(os.path.basename(src))[0]
            out_name = self.out_name.get().strip() or src_name

            # ensure pyinstaller
            ok = ensure_pyinstaller(self.log)
            if not ok:
                self.log("Cannot continue without PyInstaller.\n")
                self.disable_ui(False)
                return

            # build command
            cmd = [sys.executable, "-m", "PyInstaller"]
            if self.onefile.get():
                cmd.append("--onefile")
            if self.windowed.get():
                cmd.append("--noconsole")
            # name
            cmd.extend(["--name", out_name])
            # icon
            icon = self.icon_path.get().strip()
            if icon and os.path.isfile(icon):
                cmd.extend(["--icon", icon])
            # add the script path
            cmd.append(src)

            # optional: remove previous build/dist for cleanliness
            prev_build = os.path.join(src_dir, "build")
            prev_dist = os.path.join(src_dir, "dist")
            spec_file = os.path.join(src_dir, out_name + ".spec")
            try:
                if os.path.exists(prev_build):
                    shutil.rmtree(prev_build)
                    self.log("Removed previous 'build' folder.\n")
                if os.path.exists(prev_dist):
                    shutil.rmtree(prev_dist)
                    self.log("Removed previous 'dist' folder.\n")
                if os.path.exists(spec_file):
                    os.remove(spec_file)
                    self.log("Removed previous .spec file.\n")
            except Exception as e:
                self.log(f"Warning: could not clean previous build artifacts: {e}\n")

            # run pyinstaller
            self.log("Invoking PyInstaller...\n\n")
            run_subprocess(cmd, cwd=src_dir, log_fn=self.log, on_done=self._on_done)
        except Exception as e:
            self.log(f"Unexpected error: {e}\n")
            self.disable_ui(False)

    def _on_done(self, success):
        if success:
            # show where the exe is
            src = self.src_path.get().strip()
            src_dir = os.path.dirname(src) or "."
            out_name = self.out_name.get().strip() or os.path.splitext(os.path.basename(src))[0]
            exe_path = os.path.join(src_dir, "dist", out_name + (".exe" if os.name == "nt" else ""))
            self.log(f"\n✅ Done. Check the EXE at:\n{exe_path}\n")
            messagebox.showinfo("Done", f"Conversion finished.\nExe should be in:\n{exe_path}")
        else:
            self.log("\n❌ PyInstaller reported an error. See log above.\n")
            messagebox.showerror("Error", "PyInstaller failed. Check log for details.")
        self.disable_ui(False)

if __name__ == "__main__":
    app = ConverterGUI()
    app.mainloop()
