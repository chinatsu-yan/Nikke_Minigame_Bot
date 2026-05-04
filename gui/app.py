import customtkinter as ctk
import win32gui
from games.parkour import ParkourBot

ctk.set_appearance_mode("Dark")  
ctk.set_default_color_theme("blue")  

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Nikke Minigame Auto Bot v1.0.0")
        self.geometry("800x500")
        
        self.current_bot = None 

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(self.sidebar_frame, text="NIkke-Minigame Hub", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))
        ctk.CTkButton(self.sidebar_frame, text="🎮 小游戏脚本", fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE")).grid(row=1, column=0, padx=20, pady=10)
        
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.main_frame, text="选择游戏窗口:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.window_optionmenu = ctk.CTkOptionMenu(self.main_frame, dynamic_resizing=False, width=300)
        self.window_optionmenu.grid(row=1, column=0, sticky="w", pady=(0, 20))
        ctk.CTkButton(self.main_frame, text="🔄 刷新", width=80, command=self.refresh_windows).grid(row=1, column=1, sticky="w", padx=10, pady=(0, 20))

        ctk.CTkLabel(self.main_frame, text="选择执行脚本:", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, sticky="w", pady=(0, 5))
        self.script_optionmenu = ctk.CTkOptionMenu(self.main_frame, values=["跑酷 (Parkour)"], width=300)
        self.script_optionmenu.grid(row=3, column=0, sticky="w", pady=(0, 20))

        ctk.CTkLabel(self.main_frame, text="运行日志:", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, sticky="w", pady=(0, 5))
        self.log_textbox = ctk.CTkTextbox(self.main_frame, height=150)
        self.log_textbox.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(0, 20))
        self.log_textbox.configure(state="disabled")

        self.toggle_btn = ctk.CTkButton(self.main_frame, text="▶️ 启动脚本", font=ctk.CTkFont(size=15, weight="bold"), height=40, command=self.toggle_bot)
        self.toggle_btn.grid(row=6, column=0, columnspan=2, sticky="ew")
        
        self.refresh_windows()

    def get_all_windows(self):
        titles = set()
        def enum_windows_proc(hwnd, lParam):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title: titles.add(title)
            return True
        win32gui.EnumWindows(enum_windows_proc, None)
        return sorted(list(titles))

    def refresh_windows(self):
        windows = self.get_all_windows()
        target = "胜利女神"
        if any(target in w for w in windows):
            windows.sort(key=lambda x: target not in x) 
        self.window_optionmenu.configure(values=windows)
        if windows: self.window_optionmenu.set(windows[0])

    def log_message(self, message):
        self.after(0, self._append_log, message)

    def _append_log(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def toggle_bot(self):
        if self.current_bot is None or not self.current_bot.is_running:
            target_window = self.window_optionmenu.get()
            script_type = self.script_optionmenu.get()
            
            if not target_window:
                self.log_message("❌ 请先选择窗口！")
                return

            self.log_message(f"初始化后台引擎... 目标窗口: {target_window}")
            
            if script_type == "跑酷 (Parkour)":
                self.current_bot = ParkourBot()
                
            self.current_bot.start_bot(
                window_title=target_window, 
                log_callback=self.log_message,
                ui_reset_callback=self.reset_ui_safely
            )
            
            self.toggle_btn.configure(text="⏹️ 停止脚本", fg_color="#C8504B", hover_color="#8A3633")
            self.window_optionmenu.configure(state="disabled")
            self.script_optionmenu.configure(state="disabled")
        else:
            self.current_bot.stop()
            self.log_message("⏹️ 脚本已手动停止。")
            self.reset_ui_safely()
            
    def reset_ui_safely(self):
        self.after(0, self._reset_ui_internal)

    def _reset_ui_internal(self):
        self.toggle_btn.configure(text="▶️ 启动脚本", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"])
        self.window_optionmenu.configure(state="normal")
        self.script_optionmenu.configure(state="normal")