"""BehindWatch: Windows local camera monitoring and non-blocking alerts."""
if __name__ == '__main__':
    from bootstrap import ensure_runtime
    ensure_runtime()

import io
import multiprocessing as mp
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from PIL import Image, ImageDraw, ImageTk
from vision import worker

BG, CARD, TEXT, MUTED, GREEN, AMBER = '#10181e', '#19252d', '#edf3f4', '#a5b7c1', '#62dab4', '#ffd18a'


class App:
    def __init__(self, root):
        self.root = root
        self.process = None
        self.stopping = False
        self.last_frame = None
        self.last_received = 0
        self.failed = False
        self.tray = None
        self.ui_commands = queue.Queue()
        self.toast = None
        self.toast_after = None
        self.photo = None
        root.title('BehindWatch · 身后提醒')
        root.geometry('1120x780')
        root.minsize(980, 720)
        root.configure(bg=BG)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        root.protocol('WM_DELETE_WINDOW', self.quit)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox', padding=8, font=('Microsoft YaHei UI', 10))
        self.build()
        self.setup_tray()
        self.refresh_cameras()
        root.after(100, self.poll)

    def label(self, parent, text, size=11, color=TEXT, **kw):
        return tk.Label(parent, text=text, bg=parent['bg'], fg=color,
                        font=('Microsoft YaHei UI', size), **kw)

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=GREEN if primary else CARD,
                         fg=BG if primary else TEXT, activebackground='#90e6ca',
                         activeforeground=BG, relief='flat', padx=18, pady=7,
                         font=('Microsoft YaHei UI', 11), cursor='hand2',
                         highlightthickness=1, highlightbackground='#364751', takefocus=True)

    def build(self):
        header = tk.Frame(self.root, bg=BG)
        header.grid(row=0, column=0, sticky='ew', padx=28, pady=(18, 12))
        self.label(header, 'BehindWatch', 24).pack(side='left')
        self.label(header, '  身后提醒 / 本地监测', 11, MUTED).pack(side='left', pady=(10, 0))
        self.label(header, '●  画面仅在本机内存中处理', 10, GREEN).pack(side='right')
        body = tk.Frame(self.root, bg=BG)
        body.grid(row=1, column=0, sticky='nsew', padx=28)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, minsize=310)
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=CARD)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 18))
        self.label(left, '摄像头视野', 14, anchor='w').pack(fill='x', padx=18, pady=(16, 6))
        self.label(left, '启动后，点击画面中属于你的检测框完成校准。', 10, MUTED, anchor='w').pack(fill='x', padx=18)
        self.canvas = tk.Canvas(left, bg='#0c1217', highlightthickness=0, width=640, height=480)
        self.canvas.pack(fill='both', expand=True, padx=16, pady=16)
        self.canvas.bind('<Button-1>', self.select_person)
        self.canvas.bind('<Configure>', lambda _: self.render())
        self.meta = self.label(left, '摄像头尚未开启', 10, MUTED, anchor='w')
        self.meta.pack(fill='x', padx=18, pady=(0, 16))
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky='nsew')
        state = tk.Frame(right, bg=CARD, padx=18, pady=16)
        state.pack(fill='x')
        self.label(state, '监测状态', 11, MUTED, anchor='w').pack(fill='x')
        self.status = self.label(state, '未启动', 20, AMBER, anchor='w', wraplength=270, justify='left')
        self.status.pack(fill='x', pady=(8, 4))
        self.detail = self.label(state, '选择摄像头，然后开始监测。', 10, MUTED, wraplength=270, justify='left', anchor='w')
        self.detail.pack(fill='x')
        controls = tk.Frame(right, bg=BG)
        controls.pack(fill='x', pady=10)
        self.label(controls, '摄像头', 11, anchor='w').pack(fill='x', pady=(0, 6))
        self.camera = ttk.Combobox(controls, state='readonly', width=28)
        self.camera.pack(fill='x')
        self.refresh_button = self.button(controls, '刷新设备', self.refresh_cameras)
        self.refresh_button.pack(fill='x', pady=(8, 10))
        self.start_button = self.button(controls, '开始监测', self.start, True)
        self.start_button.pack(fill='x')
        self.stop_button = self.button(controls, '暂停并释放摄像头', self.stop)
        self.stop_button.pack(fill='x', pady=8)
        self.stop_button.configure(state='disabled')
        owner_row = tk.Frame(controls, bg=BG)
        owner_row.pack(fill='x', pady=(4, 0))
        self.owner_choice = ttk.Combobox(owner_row, state='readonly', width=9)
        self.owner_choice.pack(side='left', fill='x', expand=True)
        self.button(owner_row, '这是我', self.select_from_list).pack(side='right', padx=(8, 0))
        reminder_row = tk.Frame(controls, bg=BG)
        reminder_row.pack(fill='x', pady=10)
        self.label(reminder_row, '提醒方式', 10, MUTED).pack(side='left', padx=(0, 8))
        self.reminder_mode = ttk.Combobox(reminder_row, state='readonly', values=('角落提示点', '文字提示'), width=17)
        self.reminder_mode.current(0)
        self.reminder_mode.pack(side='right', fill='x', expand=True)
        self.hide_button = self.button(controls, '收起到系统托盘', self.hide)
        self.hide_button.pack(fill='x')
        footer = tk.Frame(self.root, bg=BG)
        footer.grid(row=2, column=0, sticky='ew', padx=28, pady=(10, 12))
        self.label(footer, '最近提醒  ·  仅保留本次运行的 50 条事件', 10, MUTED, anchor='w').pack(fill='x', pady=(0, 5))
        self.log = tk.Listbox(footer, height=3, bg=CARD, fg=TEXT, relief='flat', highlightthickness=0,
                              font=('Microsoft YaHei UI', 10), selectbackground='#355449')
        self.log.pack(fill='x')
        self.label(footer, '能力边界：“看向屏幕”仅依据头部朝向估计，不能确认阅读行为；视野外和被遮挡的人可能漏检。',
                   10, MUTED, anchor='w').pack(fill='x', pady=(5, 0))
        self.render()

    def refresh_cameras(self):
        try:
            import cv2
            from cv2_enumerate_cameras import enumerate_cameras
            self.cameras = list(enumerate_cameras(cv2.CAP_DSHOW))
            self.camera['values'] = [f'{c.index} · {c.name}' for c in self.cameras]
            if self.cameras:
                self.camera.current(0)
            else:
                self.set_status('未发现摄像头', '请连接摄像头后刷新设备。', AMBER)
        except ImportError as exc:
            self.cameras = []
            self.set_status('运行依赖缺失', f'{exc}。请运行 launch.cmd 修复环境。', AMBER)
        except Exception as exc:
            self.cameras = []
            self.set_status('设备枚举失败', str(exc), AMBER)

    def set_status(self, title, detail='', color=GREEN):
        self.status.configure(text=title, fg=color)
        self.detail.configure(text=detail)

    def start(self):
        if self.process is not None:
            return
        if self.camera.current() < 0 or not self.cameras:
            self.set_status('请选择摄像头', '连接摄像头并刷新设备后再启动。', AMBER)
            return
        self.commands, self.frames, self.events = mp.Queue(), mp.Queue(maxsize=1), mp.Queue()
        self.failed = self.stopping = False
        self.last_frame = None
        self.last_received = time.monotonic()
        self.started = self.last_received
        self.process = mp.Process(target=worker, args=(self.cameras[self.camera.current()].index, self.commands, self.frames, self.events), daemon=True)
        self.process.start()
        self.start_button.configure(state='disabled')
        self.refresh_button.configure(state='disabled')
        self.camera.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.set_status('正在启动', '加载本地模型并连接摄像头…', AMBER)

    def stop(self):
        if self.process is not None and not self.stopping:
            self.stopping = True
            self.commands.put(('stop', None))
            self.stop_at = time.monotonic()
            self.set_status('正在暂停', '正在释放摄像头…', AMBER)
            self.stop_button.configure(state='disabled')
        self.last_frame = None
        self.render()

    def cleanup(self):
        if self.process is not None:
            self.process.join(timeout=0.1)
            self.process.close()
            self.process = None
            for q in (self.commands, self.frames, self.events):
                q.close()
                q.cancel_join_thread()
        self.last_frame = None
        self.owner_choice['values'] = ()
        self.owner_choice.set('')
        self.start_button.configure(state='normal')
        self.refresh_button.configure(state='normal')
        self.camera.configure(state='readonly')
        self.stop_button.configure(state='disabled')
        self.meta.configure(text='摄像头已释放')
        if not self.failed:
            self.set_status('已暂停', '摄像头已释放，重新启动后需要校准。', AMBER)
        self.render()

    def calibrate(self, identity):
        if self.process and not self.stopping and self.last_frame and time.monotonic()-self.last_frame['at'] < 1:
            self.commands.put(('owner', identity))

    def select_from_list(self):
        try:
            self.calibrate(int(self.owner_choice.get().replace('人员 #', '')))
        except ValueError:
            pass

    def select_person(self, event):
        if not self.last_frame or not hasattr(self, 'image_rect'):
            return
        ox, oy, w, h = self.image_rect
        x, y = (event.x-ox)/w, (event.y-oy)/h
        matches = [t for t in self.last_frame['tracks'] if t['box'][0] <= x <= t['box'][2] and t['box'][1] <= y <= t['box'][3]]
        if matches:
            target = min(matches, key=lambda t: (t['box'][2]-t['box'][0])*(t['box'][3]-t['box'][1]))
            self.calibrate(target['id'])

    def render(self):
        self.canvas.delete('all')
        cw, ch = max(100, self.canvas.winfo_width()), max(100, self.canvas.winfo_height())
        if self.last_frame is None:
            self.photo = None
            self.canvas.create_text(cw/2, ch/2-16, text='视野就绪后，在这里校准本人', fill=MUTED, font=('Microsoft YaHei UI', 14))
            self.canvas.create_text(cw/2, ch/2+20, text='不上传 · 不录像 · 不采集麦克风', fill=MUTED, font=('Microsoft YaHei UI', 10))
            return
        picture = Image.open(io.BytesIO(self.last_frame['jpeg']))
        picture.thumbnail((cw, ch))
        w, h = picture.size
        ox, oy = (cw-w)/2, (ch-h)/2
        self.image_rect = ox, oy, w, h
        self.photo = ImageTk.PhotoImage(picture)
        self.canvas.create_image(ox, oy, anchor='nw', image=self.photo)
        for t in self.last_frame['tracks']:
            x1, y1, x2, y2 = t['box']
            owner = t['id'] == self.last_frame['owner']
            color = GREEN if owner else AMBER
            self.canvas.create_rectangle(ox+x1*w, oy+y1*h, ox+x2*w, oy+y2*h, outline=color, width=2)
            label = '本人' if owner else f"人员 #{t['id']}" + (' · 朝向屏幕附近' if t['facing'] else ' · 朝向未确认')
            self.canvas.create_text(ox+x1*w+4, oy+y1*h+4, anchor='nw', text=label, fill=color, font=('Microsoft YaHei UI', 10, 'bold'))

    def notify(self, message):
        self.log.insert(0, f'{datetime.now():%H:%M:%S}   {message}')
        if self.log.size() > 50:
            self.log.delete(50, 'end')
        # Reminders are intentionally silent; camera monitoring should not interrupt nearby people.
        if self.toast_after is not None:
            self.root.after_cancel(self.toast_after)
            self.toast_after = None
        if self.toast is not None:
            if self.toast.winfo_exists():
                self.toast.destroy()
        toast = self.toast = tk.Toplevel(self.root)
        toast.withdraw()
        def dismiss():
            if toast.winfo_exists():
                toast.destroy()
            if self.toast is toast:
                self.toast = None
            self.toast_after = None
        toast.title('BehindWatch 提醒')
        toast.configure(bg=CARD)
        toast.attributes('-topmost', True)
        if self.reminder_mode.get() == '角落提示点':
            # A borderless, non-activating indicator keeps typing focus in the user's working app.
            import ctypes
            from ctypes import wintypes
            class Rect(ctypes.Structure):
                _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG),
                            ('right', wintypes.LONG), ('bottom', wintypes.LONG)]
            area = Rect()
            if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(area), 0):
                right, bottom = area.right, area.bottom
            else:
                right, bottom = self.root.winfo_screenwidth(), self.root.winfo_screenheight()-48
            toast.overrideredirect(True)
            toast.attributes('-transparentcolor', '#010203')
            toast.configure(bg='#010203')
            toast.geometry(f'28x28+{max(0,right-44)}+{max(0,bottom-44)}')
            dot = tk.Canvas(toast, width=28, height=28, bg='#010203', highlightthickness=0, cursor='hand2')
            dot.pack()
            color = '#f38383' if '看向屏幕' in message else AMBER
            dot.create_oval(7, 7, 21, 21, fill=color, outline='#17252d', width=2)
            def show_detail(_):
                dismiss()
                self.root.deiconify()
                self.root.lift()
            dot.bind('<Button-1>', show_detail)
            toast.update_idletasks()
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongW.restype = ctypes.c_long
            user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
            hwnd = user32.GetParent(toast.winfo_id())
            styles = user32.GetWindowLongW(hwnd, -20)
            user32.SetWindowLongW(hwnd, -20, styles | 0x08000000 | 0x00000080)
        else:
            toast.geometry(f'380x130+{max(0,self.root.winfo_screenwidth()-405)}+40')
            self.label(toast, message, 13, AMBER, wraplength=340).pack(padx=18, pady=(18, 8))
            self.button(toast, '知道了', dismiss).pack()
        toast.protocol('WM_DELETE_WINDOW', dismiss)
        toast.deiconify()
        self.toast_after = self.root.after(6000, dismiss)

    def setup_tray(self):
        try:
            import pystray
            icon = Image.new('RGB', (64, 64), BG)
            draw = ImageDraw.Draw(icon)
            draw.rounded_rectangle((10, 10, 54, 54), radius=14, outline=GREEN, width=5)
            draw.ellipse((25, 25, 39, 39), fill=GREEN)
            self.tray = pystray.Icon('BehindWatch', icon, 'BehindWatch · 身后提醒', menu=pystray.Menu(
                pystray.MenuItem('打开监测面板', lambda *_: self.ui_commands.put('show'), default=True),
                pystray.MenuItem('暂停监测', lambda *_: self.ui_commands.put('stop')),
                pystray.MenuItem('退出', lambda *_: self.ui_commands.put('quit'))))
            threading.Thread(target=self.tray.run, daemon=True).start()
        except Exception:
            self.tray = None
            self.hide_button.configure(state='disabled')

    def hide(self):
        if self.tray and self.tray.visible:
            self.root.withdraw()
        else:
            self.root.iconify()

    def poll(self):
        while True:
            try:
                action = self.ui_commands.get_nowait()
            except queue.Empty:
                break
            if action == 'show':
                self.root.deiconify()
                self.root.lift()
            elif action == 'stop':
                self.stop()
            elif action == 'quit':
                self.quit()
                return
        if self.process is not None:
            while True:
                try:
                    kind, data = self.events.get_nowait()
                except queue.Empty:
                    break
                if kind == 'status' and not self.stopping:
                    self.detail.configure(text=data)
                elif kind == 'error':
                    self.failed = True
                    self.set_status('监测不可用', data, AMBER)
                    self.notify('监测已中断，请检查摄像头或模型。')
                elif kind == 'alert' and not self.stopping:
                    self.notify(f"{data['message']} · 人员 #{data['id']}")
                elif kind == 'calibration' and not data:
                    self.set_status('请重新选择本人', '目标已离开画面。', AMBER)
            try:
                frame = self.frames.get_nowait()
            except queue.Empty:
                frame = None
            if frame and not self.stopping and not self.failed:
                previous_owner = self.last_frame['owner'] if self.last_frame else None
                self.last_frame = frame
                self.last_received = frame['at']
                tracks, owner = frame['tracks'], frame['owner']
                self.owner_choice['values'] = [f"人员 #{t['id']}" for t in tracks]
                if not self.owner_choice.get() and tracks:
                    self.owner_choice.current(0)
                if owner is None:
                    self.set_status('需要本人校准', '点击属于你的框，或选择人员编号再点“这是我”。', AMBER)
                    if previous_owner is not None:
                        # Calibration loss disables person alerts, so notify even when hidden in the tray.
                        self.notify('本人跟踪已丢失，请打开面板重新校准。')
                else:
                    count = sum(t['id'] != owner for t in tracks)
                    self.set_status(f'检测到 {count} 位其他人员' if count else '监测运行中',
                                    '持续分析人员活动和朝向。' if count else '当前画面未检测到其他人员。', AMBER if count else GREEN)
                self.meta.configure(text=f"{frame['fps']} 帧/秒  ·  镜像预览  ·  {len(tracks)} 个可见目标")
                self.render()
            now = time.monotonic()
            if self.stopping and now-self.stop_at > 3 and self.process.is_alive():
                # Drivers may block inside read(); terminate only this owned capture process.
                self.process.terminate()
            elif not self.stopping and now-self.last_received > (30 if self.last_frame is None else 8):
                self.failed = True
                self.stop()
                self.set_status('监测已超时', '长时间未收到新画面，请重新启动。', AMBER)
                self.notify('监测超时，当前无法判断身后情况。')
            if not self.process.is_alive():
                if not self.failed and not self.stopping:
                    self.failed = True
                    self.set_status('监测异常退出', '检测进程已结束，请重新启动。', AMBER)
                self.cleanup()
        self.root.after(100, self.poll)

    def quit(self):
        if self.process is not None:
            self.commands.put(('stop', None))
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)
        if self.tray:
            self.tray.stop()
        self.root.destroy()


if __name__ == '__main__':
    mp.freeze_support()
    App(tk.Tk()).root.mainloop()
