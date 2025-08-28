# See original source in parent folder. This copy is self-contained for the new repo.
# The code below mirrors the modernized UI, theme, ring, tray, and packaging fixes.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import os
import sys
import datetime

try:
    import winsound
    def play_sound():
        winsound.Beep(1000, 700)
except Exception:
    def play_sound():
        try:
            print('\a', end='')
        except Exception:
            pass

try:
    from plyer import notification
    def notify(title, message):
        try:
            notification.notify(title=title, message=message, timeout=5)
        except Exception:
            messagebox.showinfo(title, message)
except Exception:
    def notify(title, message):
        messagebox.showinfo(title, message)

HAS_TRAY = False
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False

# Resolve app directory for both script and PyInstaller bundle
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, 'pomodoro_config.json')
HISTORY_FILE = os.path.join(APP_DIR, 'pomodoro_history.json')


class PomodoroApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Pomodoro — Focus Timer')
        self.geometry('460x520')
        self.minsize(420, 480)
        self.resizable(False, False)

        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass

        self.is_running = False
        self.is_focus = True
        self.remaining = 0
        self.session_total_seconds = 0
        self._timer_job = None
        self._pulse_job = None

        self.focus_minutes = tk.IntVar(value=25)
        self.break_minutes = tk.IntVar(value=5)
        self.auto_repeat = tk.BooleanVar(value=True)
        self.dark_mode = tk.BooleanVar(value=True)

        self.load_settings()
        self.setup_theme()
        self.create_widgets()
        self.update_display(0)
        self.update_progress_ring(0.0)
        self.in_tray = False
        if HAS_TRAY:
            self.setup_tray()
        self.protocol('WM_DELETE_WINDOW', self.on_closing)
        self.bind('<space>', lambda e: self.start_pause())
        self.bind('<Key-r>', lambda e: self.reset())
        self.bind('<Control-d>', lambda e: self.toggle_theme())

    # --- Theming ---
    def palette(self):
        if self.dark_mode.get():
            return {
                'bg': '#0d1117', 'fg': '#c9d1d9', 'subtle': '#8b949e', 'card': '#161b22',
                'accent': '#1f6feb', 'accent2': '#2ea043', 'warn': '#f0883e',
                'break_accent': '#a371f7', 'ring_bg': '#30363d',
            }
        return {
            'bg': '#f5f7fb', 'fg': '#061022', 'subtle': '#5b6b7b', 'card': '#ffffff',
            'accent': '#2563eb', 'accent2': '#16a34a', 'warn': '#ea580c',
            'break_accent': '#7c3aed', 'ring_bg': '#e5e7eb',
        }

    def setup_theme(self):
        p = self.palette()
        self.configure(bg=p['bg'])
        style = ttk.Style(self)
        style.configure('TFrame', background=p['bg'])
        style.configure('Card.TFrame', background=p['card'])
        style.configure('TLabel', background=p['bg'], foreground=p['fg'])
        style.configure('Card.TLabel', background=p['card'], foreground=p['fg'])
        style.configure('Subtle.TLabel', background=p['bg'], foreground=p['subtle'])
        style.configure('H1.TLabel', font=('Segoe UI', 28, 'bold'), background=p['bg'], foreground=p['accent'])
        style.configure('Mode.TLabel', font=('Segoe UI', 10, 'bold'), background=p['card'])
        style.configure('Card.TCheckbutton', background=p['card'])
        style.configure('Primary.TButton', font=('Segoe UI', 10, 'bold'))
        style.map('Primary.TButton', background=[('active', p['accent'])], foreground=[('!disabled', '#fff')])
        style.configure('Primary.TButton', background=p['accent'], foreground='#fff', focuscolor=p['accent'])
        style.configure('TButton', padding=6)

    def toggle_theme(self):
        self.dark_mode.set(not self.dark_mode.get())
        self.setup_theme()
        self.restyle_widgets()
        self.draw_ring_base()
        self.update_progress_ring(self.current_progress_ratio())

    def create_widgets(self):
        pad = 12
        p = self.palette()

        root = ttk.Frame(self, padding=pad, style='TFrame')
        root.pack(fill='both', expand=True)

        header = ttk.Frame(root, style='TFrame')
        header.pack(fill='x', pady=(0, 8))
        ttk.Label(header, text='Pomodoro', style='H1.TLabel').pack(side='left')
        self.theme_btn = ttk.Button(header, text='🌓 Theme', command=self.toggle_theme)
        self.theme_btn.pack(side='right', padx=(8, 0))

        card = ttk.Frame(root, padding=16, style='Card.TFrame')
        card.pack(fill='both', expand=True)

        inputs = ttk.Frame(card, style='Card.TFrame')
        inputs.pack(fill='x', pady=(0, 10))
        ttk.Label(inputs, text='Focus', style='Card.TLabel').grid(row=0, column=0, sticky='w')
        self.focus_spin = ttk.Spinbox(inputs, from_=1, to=180, width=5, textvariable=self.focus_minutes, justify='center')
        self.focus_spin.grid(row=0, column=1, padx=(6, 18))
        ttk.Label(inputs, text='Break', style='Card.TLabel').grid(row=0, column=2, sticky='w')
        self.break_spin = ttk.Spinbox(inputs, from_=1, to=180, width=5, textvariable=self.break_minutes, justify='center')
        self.break_spin.grid(row=0, column=3, padx=(6, 18))
        ttk.Checkbutton(inputs, text='Auto Repeat', variable=self.auto_repeat, style='Card.TCheckbutton').grid(row=0, column=4, padx=(6,0))
        for i in range(5):
            inputs.grid_columnconfigure(i, weight=1)

        ring_frame = ttk.Frame(card, style='Card.TFrame')
        ring_frame.pack(pady=(4, 10))
        self.canvas_size = 260
        self.ring_thickness = 14
        self.ring_canvas = tk.Canvas(ring_frame, width=self.canvas_size, height=self.canvas_size, bg=p['card'], highlightthickness=0, bd=0, relief='flat')
        self.ring_canvas.pack()
        self.ring_ids = {'bg': None, 'fg': None}
        self.draw_ring_base()

        self.mode_label = ttk.Label(ring_frame, text='Ready', style='Mode.TLabel')
        self.mode_label.place(relx=0.5, rely=0.28, anchor='center')
        self.time_label = ttk.Label(ring_frame, text='00:00', font=('Segoe UI', 40, 'bold'))
        self.time_label.place(relx=0.5, rely=0.55, anchor='center')

        ctrls = ttk.Frame(card, style='Card.TFrame')
        ctrls.pack(pady=(6, 0))
        self.start_btn = ttk.Button(ctrls, text='▶ Start', style='Primary.TButton', command=self.start_pause)
        self.start_btn.grid(row=0, column=0, padx=6)
        self.reset_btn = ttk.Button(ctrls, text='🔁 Reset', command=self.reset)
        self.reset_btn.grid(row=0, column=1, padx=6)
        self.settings_btn = ttk.Button(ctrls, text='💾 Save', command=self.save_settings)
        self.settings_btn.grid(row=0, column=2, padx=6)
        self.history_btn = ttk.Button(ctrls, text='📜 History', command=self.show_history)
        self.history_btn.grid(row=0, column=3, padx=6)

        self.status_label = ttk.Label(root, text='Configure times and press Start', style='Subtle.TLabel')
        self.status_label.pack(pady=(10, 0))

    def restyle_widgets(self):
        p = self.palette()
        try:
            self.ring_canvas.configure(bg=p['card'])
        except Exception:
            pass
        self.mode_label.configure(style='Mode.TLabel')
        self.status_label.configure(style='Subtle.TLabel')
        self.update()

    def ring_bbox(self):
        pad = self.ring_thickness + 6
        return (pad, pad, self.canvas_size - pad, self.canvas_size - pad)

    def draw_ring_base(self):
        p = self.palette()
        bbox = self.ring_bbox()
        if self.ring_ids['bg'] is not None:
            try:
                self.ring_canvas.delete(self.ring_ids['bg'])
            except Exception:
                pass
        self.ring_ids['bg'] = self.ring_canvas.create_oval(*bbox, outline=p['ring_bg'], width=self.ring_thickness)
        if self.ring_ids['fg'] is None:
            self.ring_ids['fg'] = self.ring_canvas.create_arc(*bbox, start=90, extent=0, style='arc', outline=self.current_accent(), width=self.ring_thickness)
        else:
            self.ring_canvas.itemconfig(self.ring_ids['fg'], outline=self.current_accent(), width=self.ring_thickness)

    def current_accent(self):
        p = self.palette()
        return p['accent'] if self.is_focus else p['break_accent']

    def current_progress_ratio(self):
        if self.session_total_seconds <= 0:
            return 0.0
        done = max(0, self.session_total_seconds - max(0, self.remaining))
        return min(1.0, done / self.session_total_seconds)

    def update_progress_ring(self, ratio: float):
        try:
            extent = -360 * ratio
            self.ring_canvas.itemconfig(self.ring_ids['fg'], extent=extent, outline=self.current_accent())
        except Exception:
            pass
        if self.is_running:
            self.start_pulse()
        else:
            self.stop_pulse()

    def start_pulse(self):
        if self._pulse_job is not None:
            return
        phase = {'t': 0}
        def step():
            t = phase['t']
            w = self.ring_thickness + (1 if (t % 6) < 3 else 0)
            try:
                self.ring_canvas.itemconfig(self.ring_ids['fg'], width=w)
            except Exception:
                pass
            phase['t'] += 1
            self._pulse_job = self.after(180, step)
        self._pulse_job = self.after(180, step)

    def stop_pulse(self):
        if self._pulse_job is not None:
            try:
                self.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None
            try:
                self.ring_canvas.itemconfig(self.ring_ids['fg'], width=self.ring_thickness)
            except Exception:
                pass

    # History
    def append_history(self, kind, minutes, ts_iso):
        entry = {'type': kind, 'minutes': minutes, 'ts': ts_iso}
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    history = json.load(f)
            except Exception:
                history = []
        history.append(entry)
        try:
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history, f)
        except Exception:
            pass

    def load_history(self):
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []

    def show_history(self):
        hist = self.load_history()
        dlg = tk.Toplevel(self)
        dlg.title('Pomodoro History')
        dlg.geometry('420x400')
        dlg.transient(self)

        frame = ttk.Frame(dlg, padding=8)
        frame.pack(fill='both', expand=True)

        text = tk.Text(frame, wrap='none')
        text.pack(fill='both', expand=True)
        text.insert('1.0', 'Timestamp (UTC)\tType\tMinutes\n')
        text.insert('1.0', '---\n')
        for e in reversed(hist[-100:]):
            ts = e.get('ts', '')
            typ = e.get('type', '')
            mins = e.get('minutes', '')
            text.insert('1.0', f'{ts}\t{typ}\t{mins}\n')

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(6,0))
        ttk.Button(btn_frame, text='Export', command=self.export_history).pack(side='left', padx=6)
        ttk.Button(btn_frame, text='Clear', command=self.clear_history).pack(side='left', padx=6)
        ttk.Button(btn_frame, text='Close', command=dlg.destroy).pack(side='right', padx=6)

    def export_history(self):
        hist = self.load_history()
        if not hist:
            messagebox.showinfo('History', 'No history to export')
            return
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON files','*.json')])
        if not path:
            return
        try:
            with open(path, 'w') as f:
                json.dump(hist, f, indent=2)
            messagebox.showinfo('Export', 'History exported')
        except Exception as e:
            messagebox.showerror('Export', f'Failed to export: {e}')

    def clear_history(self):
        if messagebox.askyesno('Clear History', 'Are you sure you want to clear history?'):
            try:
                if os.path.exists(HISTORY_FILE):
                    os.remove(HISTORY_FILE)
                messagebox.showinfo('History', 'Cleared')
            except Exception as e:
                messagebox.showerror('History', f'Failed to clear: {e}')

    def start_pause(self):
        if not self.is_running:
            if self.is_focus:
                minutes = int(self.focus_minutes.get())
            else:
                minutes = int(self.break_minutes.get())
            self.session_total_seconds = minutes * 60
            if self.remaining <= 0 or self.remaining > self.session_total_seconds:
                self.remaining = self.session_total_seconds
            self.is_running = True
            self.start_btn.config(text='⏸ Pause')
            self.status_label.config(text='Running — press Space to pause')
            self.tick()
        else:
            self.is_running = False
            self.start_btn.config(text='▶ Start')
            self.status_label.config(text='Paused — press Space to resume')
            if self._timer_job:
                self.after_cancel(self._timer_job)
                self._timer_job = None
            self.update_progress_ring(self.current_progress_ratio())

    def reset(self):
        self.is_running = False
        if self._timer_job:
            self.after_cancel(self._timer_job)
            self._timer_job = None
        self.stop_pulse()
        self.is_focus = True
        self.remaining = 0
        self.session_total_seconds = 0
        self.start_btn.config(text='▶ Start')
        self.mode_label.config(text='Ready')
        self.update_display(0)
        self.draw_ring_base()
        self.update_progress_ring(0.0)
        self.status_label.config(text='Reset')

    def on_closing(self):
        if HAS_TRAY:
            self.hide_to_tray()
        else:
            self.destroy()

    def hide_to_tray(self):
        try:
            self.withdraw()
            self.in_tray = True
            self.status_label.config(text='Minimized to tray')
        except Exception:
            pass

    def restore_from_tray(self):
        try:
            self.deiconify()
            self.lift()
            self.in_tray = False
            self.status_label.config(text='Restored')
        except Exception:
            pass

    def setup_tray(self):
        try:
            img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse((8, 8, 56, 56), fill='#1f6feb')
            d.rectangle((26, 20, 38, 44), fill='#fff')
        except Exception:
            img = None

        def on_show(icon, item):
            self.after(0, self.restore_from_tray)
        def on_stretch(icon, item):
            self.after(0, lambda: (self.restore_from_tray(), self.show_stretch_popup(), self.after(25000, self.hide_to_tray())))
        def on_toggle(icon, item):
            self.after(0, self.start_pause)
        def on_quit(icon, item):
            try:
                icon.stop()
            except Exception:
                pass
            self.after(0, self.destroy)

        menu = pystray.Menu(
            pystray.MenuItem('Show', on_show),
            pystray.MenuItem('Start/Pause', on_toggle),
            pystray.MenuItem('Stretch', on_stretch),
            pystray.MenuItem('Quit', on_quit)
        )
        try:
            self.tray_icon = pystray.Icon('pomodoro', img, 'Pomodoro', menu)
            t = threading.Thread(target=self.tray_icon.run, daemon=True)
            t.start()
        except Exception:
            self.tray_icon = None

    def tick(self):
        self.mode_label.config(text='Focus' if self.is_focus else 'Break')
        if not self.is_running:
            return
        if self.remaining <= 0:
            play_sound()
            if self.is_focus:
                try:
                    self.append_history('focus', int(self.focus_minutes.get()), datetime.datetime.utcnow().isoformat())
                except Exception:
                    pass
                if self.in_tray:
                    self.restore_from_tray()
                    self.show_stretch_popup()
                    self.after(25000, lambda: self.hide_to_tray())
                else:
                    self.show_stretch_popup()
            title = 'Focus session complete' if self.is_focus else 'Break finished'
            message = 'Time for a break!' if self.is_focus else 'Back to focus!'
            notify(title, message)
            self.is_focus = not self.is_focus
            self.draw_ring_base()
            if self.is_focus:
                minutes = int(self.focus_minutes.get())
            else:
                minutes = int(self.break_minutes.get())
            self.session_total_seconds = minutes * 60
            self.remaining = self.session_total_seconds
            if not self.auto_repeat.get() and not self.is_focus:
                self.is_running = False
                self.start_btn.config(text='▶ Start')
                self.status_label.config(text='Cycle complete')
                self.update_display(self.remaining)
                self.update_progress_ring(0.0)
                return

        self.update_display(self.remaining)
        self.update_progress_ring(self.current_progress_ratio())
        self.remaining -= 1
        self._timer_job = self.after(1000, self.tick)

    def update_display(self, seconds):
        mins, secs = divmod(int(seconds), 60)
        self.time_label.config(text=f'{mins:02d}:{secs:02d}', foreground=self.current_accent())

    def save_settings(self):
        data = {
            'focus_minutes': int(self.focus_minutes.get()),
            'break_minutes': int(self.break_minutes.get()),
            'auto_repeat': bool(self.auto_repeat.get())
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f)
            self.status_label.config(text='Settings saved')
        except Exception as e:
            self.status_label.config(text=f'Error saving settings: {e}')

    def show_stretch_popup(self):
        try:
            popup = tk.Toplevel(self)
            popup.title('Stretch Time')
            popup.geometry('380x240')
            popup.resizable(False, False)
            popup.attributes('-topmost', True)

            header = ttk.Label(popup, text='Time for a break — Stretch!', font=('Segoe UI', 12, 'bold'))
            header.pack(pady=(8, 4))

            canvas = tk.Canvas(popup, width=330, height=130, bg=self.cget('bg'), highlightthickness=0)
            canvas.pack(pady=4)

            cx, cy = 160, 40
            head = canvas.create_oval(cx-12, cy-12, cx+12, cy+12, fill='#ffe0b2', outline='#b8860b')
            body = canvas.create_line(cx, cy+12, cx, cy+48, width=4, fill='#37474f')
            left_arm = canvas.create_line(cx, cy+6, cx-30, cy+20, width=4, fill='#37474f')
            right_arm = canvas.create_line(cx, cy+6, cx+30, cy+20, width=4, fill='#37474f')
            left_leg = canvas.create_line(cx, cy+48, cx-20, cy+86, width=4, fill='#37474f')
            right_leg = canvas.create_line(cx, cy+48, cx+20, cy+86, width=4, fill='#37474f')

            countdown_var = tk.IntVar(value=20)
            countdown_lbl = ttk.Label(popup, text='20s', font=('Segoe UI', 11, 'bold'))
            countdown_lbl.pack()

            progress = ttk.Progressbar(popup, length=320, mode='determinate', maximum=20)
            progress.pack(pady=(6, 8))

            anim_state = {'t': 0}
            def animate_frame():
                t = anim_state['t']
                frac = (t % 12) / 12
                swing = 30
                offset = int((1 - abs(2*frac-1)) * swing)
                canvas.coords(left_arm, cx, cy+6, cx-30, cy+20-offset)
                canvas.coords(right_arm, cx, cy+6, cx+30, cy+20-offset)
                anim_state['t'] += 1
                popup.after(100, animate_frame)
            def countdown_step():
                s = countdown_var.get()
                countdown_lbl.config(text=f'{s}s')
                progress['value'] = 20 - s
                if s <= 0:
                    popup.destroy()
                    return
                countdown_var.set(s-1)
                popup.after(1000, countdown_step)
            animate_frame()
            countdown_step()
            try:
                self_center_x = self.winfo_rootx() + self.winfo_width()//2
                self_center_y = self.winfo_rooty() + self.winfo_height()//2
                popup.geometry(f'+{self_center_x-190}+{self_center_y-120}')
            except Exception:
                pass
        except Exception:
            pass

    def load_settings(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
            self.focus_minutes.set(data.get('focus_minutes', self.focus_minutes.get()))
            self.break_minutes.set(data.get('break_minutes', self.break_minutes.get()))
            self.auto_repeat.set(data.get('auto_repeat', self.auto_repeat.get()))
        except Exception:
            pass


def main():
    app = PomodoroApp()
    app.mainloop()


if __name__ == '__main__':
    main()
