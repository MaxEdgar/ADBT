import subprocess, shutil, threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk, simpledialog

# Globals
command_history = []

# Check for adb and fastboot
if shutil.which("adb") is None:
    messagebox.showerror("ADB Missing", "ADB is not installed or not in PATH.")
    exit()

if shutil.which("fastboot") is None:
    messagebox.showerror("Fastboot Missing", "Fastboot is not installed or not in PATH.")
    exit()

# GUI Setup
root = tk.Tk()
root.title("Android Reboot & Flash Tool")
root.geometry("720x600")

theme = tk.StringVar(value="Light")

# Styles
def apply_theme():
    dark = (theme.get() == "Dark")
    bg = "#1e1e1e" if dark else "#f4f4f4"
    fg = "#ffffff" if dark else "#000000"
    entry_command.configure(bg=bg, fg=fg, insertbackground=fg)
    log_box.configure(bg="#2b2b2b" if dark else "#ffffff", fg=fg)
    root.configure(bg=bg)
    for widget in root.winfo_children():
        if isinstance(widget, tk.Label):
            widget.configure(bg=bg, fg=fg)

# Get Connected Devices
def get_device_list():
    devices = subprocess.check_output(["adb", "devices"], text=True).splitlines()
    return [line.split()[0] for line in devices if "\tdevice" in line]

# Device Info
def get_device_info(device_id):
    try:
        model = subprocess.check_output(["adb", "-s", device_id, "shell", "getprop ro.product.model"], text=True).strip()
        build = subprocess.check_output(["adb", "-s", device_id, "shell", "getprop ro.build.display.id"], text=True).strip()
        android = subprocess.check_output(["adb", "-s", device_id, "shell", "getprop ro.build.version.release"], text=True).strip()
        return {"id": device_id, "model": model, "build": build, "android": android}
    except:
        return None

# Logger
def log(text):
    log_box.config(state='normal')
    log_box.insert(tk.END, f"{text}\n")
    log_box.see(tk.END)
    log_box.config(state='disabled')

def threaded(func, *args):
    threading.Thread(target=func, args=args).start()

# Run ADB Command
def run_adb(command, label="ADB"):
    def execute():
        try:
            result = subprocess.run(["adb"] + command.split(), capture_output=True, text=True)
            log(f"> {label}: {command}")
            if result.stdout: log(result.stdout.strip())
            if result.stderr: log(result.stderr.strip())
            if result.returncode == 0:
                messagebox.showinfo("Success", f"{label} completed successfully.")
            else:
                messagebox.showerror("Error", f"{label} failed.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            log(f"Error: {str(e)}")
    threaded(execute)

def run_custom_command():
    cmd = entry_command.get().strip()
    if not cmd:
        messagebox.showwarning("Input Needed", "Enter a command first.")
        return
    command_history.append(cmd)
    args = cmd.split() if cmd.startswith("fastboot") else ["adb"] + cmd.split()
    def execute():
        try:
            result = subprocess.run(args, capture_output=True, text=True)
            log(f"> Custom: {cmd}")
            if result.stdout: log(result.stdout.strip())
            if result.stderr: log(result.stderr.strip())
        except Exception as e:
            log(f"Error: {str(e)}")
    threaded(execute)

def save_logs():
    file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
    if file:
        with open(file, "w") as f:
            f.write(log_box.get("1.0", tk.END))
        messagebox.showinfo("Saved", f"Logs saved to:\n{file}")

def simple_prompt(prompt):
    return simpledialog.askstring("Input", prompt)

def fastboot_flash_img():
    path = filedialog.askopenfilename(title="Select .img file", filetypes=[("IMG Files", "*.img")])
    if path:
        partition = simple_prompt("Enter partition name (e.g., boot, recovery):")
        if not partition.isalnum():
            messagebox.showerror("Invalid", "Partition name must be alphanumeric.")
            return
        try:
            devices = subprocess.check_output(["fastboot", "devices"], text=True).splitlines()
            if not devices:
                messagebox.showerror("No Fastboot Device", "No device in fastboot mode detected.")
                return
            result = subprocess.run(["fastboot", "flash", partition, path], capture_output=True, text=True)
            log(f"> Fastboot flash {partition}: {path}")
            if result.stdout: log(result.stdout.strip())
            if result.stderr: log(result.stderr.strip())
            messagebox.showinfo("Done", f"Flashed to {partition} successfully.")
        except Exception as e:
            log(f"Error flashing: {str(e)}")

def refresh_device_info():
    connected = get_device_list()
    if not connected:
        label_info.config(text="No device detected. Plug in and enable ADB.")
        log("\u2716 No device detected.")
        return
    device_id = connected[0] if len(connected) == 1 else simpledialog.askstring("Choose device", f"Multiple devices detected:\n{connected}\nEnter device ID:")
    if not device_id:
        return
    device = get_device_info(device_id)
    if device:
        label_info.config(text=f"{device['model']} | Build: {device['build']} | Android: {device['android']}")
        log(f"\u2714 Device connected: {device['model']} - Android {device['android']}")

def check_root_magisk():
    def execute():
        try:
            output = subprocess.check_output(["adb", "shell", "su -v"], text=True).strip()
            log("\u2714 Magisk Detected:\n" + output)
            messagebox.showinfo("Magisk", f"Magisk/SU Version:\n{output}")
        except subprocess.CalledProcessError:
            log("\u2716 No root/Magisk detected.")
            messagebox.showwarning("No Root", "Device is not rooted or Magisk is not installed.")
    threaded(execute)

def view_logcat():
    def logcat_thread():
        win = tk.Toplevel(root)
        win.title("Logcat Viewer")
        text = scrolledtext.ScrolledText(win, width=100, height=30, bg="#000", fg="#0f0", font=("Consolas", 10))
        text.pack()
        try:
            process = subprocess.Popen(["adb", "logcat"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                text.insert(tk.END, line)
                text.see(tk.END)
        except Exception as e:
            messagebox.showerror("Logcat Error", str(e))
    threading.Thread(target=logcat_thread).start()

def install_apk():
    apk = filedialog.askopenfilename(filetypes=[("APK files", "*.apk")])
    if apk:
        def install():
            result = subprocess.run(["adb", "install", apk], capture_output=True, text=True)
            log(f"> Installing APK: {apk}")
            log(result.stdout.strip() if result.stdout else "")
            log(result.stderr.strip() if result.stderr else "")
        threaded(install)

def push_file():
    local = filedialog.askopenfilename()
    if local:
        remote = simple_prompt("Enter destination path on device (e.g. /sdcard/):")
        subprocess.run(["adb", "push", local, remote], text=True)
        log(f"Pushed {local} to {remote}")

def pull_file():
    remote = simple_prompt("Enter path on device to pull (e.g. /sdcard/file.txt):")
    local = filedialog.asksaveasfilename()
    if remote and local:
        subprocess.run(["adb", "pull", remote, local], text=True)
        log(f"Pulled {remote} to {local}")

def take_screenshot():
    output = "screenshot.png"
    try:
        with open(output, "wb") as f:
            subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=f)
        messagebox.showinfo("Screenshot Saved", f"Screenshot saved as {output}")
        log("\u2714 Screenshot captured.")
    except Exception as e:
        log(f"\u274C Screenshot failed: {str(e)}")

def list_apps():
    try:
        result = subprocess.check_output(["adb", "shell", "pm", "list", "packages", "-3"], text=True)
        win = tk.Toplevel(root)
        win.title("Installed Apps")
        text = scrolledtext.ScrolledText(win, width=60, height=25)
        text.insert(tk.END, result)
        text.pack()
    except Exception as e:
        messagebox.showerror("Error", str(e))

def show_battery_thermal():
    try:
        battery = subprocess.check_output(["adb", "shell", "dumpsys", "battery"], text=True)
        thermal = subprocess.check_output(["adb", "shell", "dumpsys", "thermalservice"], text=True)
        win = tk.Toplevel(root)
        win.title("Battery & Thermal Info")
        text = scrolledtext.ScrolledText(win, width=80, height=30)
        text.insert(tk.END, "=== Battery Info ===\n" + battery + "\n=== Thermal Info ===\n" + thermal)
        text.pack()
    except Exception as e:
        messagebox.showerror("Error", str(e))

def run_shell_script():
    path = filedialog.askopenfilename(filetypes=[("Shell Scripts", "*.sh")])
    if path:
        try:
            subprocess.run(["adb", "push", path, "/sdcard/script.sh"], text=True)
            subprocess.run(["adb", "shell", "chmod", "+x", "/sdcard/script.sh"], text=True)
            result = subprocess.run(["adb", "shell", "sh /sdcard/script.sh"], capture_output=True, text=True)
            log(f"\u2714 Ran script: {path}")
            log(result.stdout.strip())
        except Exception as e:
            log(f"Error running script: {str(e)}")

def reboot_edl():
    try:
        subprocess.run(["adb", "reboot", "edl"], text=True)
        log("\u26A1 Rebooting to EDL mode.")
    except Exception as e:
        log(f"EDL Error: {str(e)}")

# GUI Layout
label_title = tk.Label(root, text="Portable ADB Tool By Max", font=("Comic Sans MS", 16, "bold"))
label_title.pack(pady=10)

label_info = tk.Label(root, text="Waiting for device...", font=("Comic Sans MS", 10))
label_info.pack()

frame_buttons = tk.Frame(root)
frame_buttons.pack(pady=10)

btns = [
    ("\ud83d\udd01 Reboot", lambda: run_adb("reboot", "Reboot")),
    ("\ud83c\udf19 Soft Reboot", lambda: run_adb("shell setprop sys.powerctl reboot", "Soft Reboot")),
    ("\ud83d\udee0\ufe0f Recovery", lambda: run_adb("reboot recovery", "Recovery")),
    ("\u2699\ufe0f Bootloader", lambda: run_adb("reboot bootloader", "Bootloader")),
    ("\ud83d\udd3b Download", lambda: run_adb("reboot download", "Download Mode")),
    ("\ud83d\uded1 Shutdown", lambda: run_adb("shell reboot -p", "Shutdown")),
    ("\ud83d\udd04 Refresh", refresh_device_info),
    ("\ud83d\udcbe Save Logs", save_logs),
    ("\ud83d\udcc2 Flash .img", fastboot_flash_img),
    ("\ud83e\uddea Root Check", check_root_magisk),
    ("\ud83d\udcc3 Logcat", view_logcat),
    ("\ud83d\udce6 Install APK", install_apk),
    ("\ud83d\udce4 Push File", push_file),
    ("\ud83d\udce5 Pull File", pull_file),
    ("\ud83d\udcf8 Screenshot", take_screenshot),
    ("\ud83d\udcf2 List Apps", list_apps),
    ("\ud83d\udd0b Battery/Temp", show_battery_thermal),
    ("\ud83d\udcbb Run .sh", run_shell_script),
    ("\ud83d\udca3 EDL Mode", reboot_edl),
]

for i, (text, cmd) in enumerate(btns):
    ttk.Button(frame_buttons, text=text, command=cmd, width=20).grid(row=i//3, column=i%3, padx=8, pady=5)

frame_custom = tk.Frame(root)
frame_custom.pack(pady=10)
tk.Label(frame_custom, text="Custom ADB/Fastboot Command:").pack(anchor='w')
entry_command = tk.Entry(frame_custom, width=80)
entry_command.pack(side='left', padx=5)
ttk.Button(frame_custom, text="Run", command=run_custom_command).pack(side='left')

log_box = scrolledtext.ScrolledText(root, height=15, width=85, state='disabled', font=("Consolas", 10))
log_box.pack(pady=10)

theme.trace("w", lambda *args: apply_theme())
apply_theme()
refresh_device_info()
root.mainloop()
