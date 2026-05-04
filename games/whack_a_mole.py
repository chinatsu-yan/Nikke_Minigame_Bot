import cv2
import numpy as np
import time
import win32gui
import threading
import os
from core.base_bot import BaseBot

class WhackAMoleBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.key_map = [
            0x51, 0x57, 0x45,  # Q, W, E
            0x41, 0x53, 0x44,  # A, S, D
            0x5A, 0x58, 0x43   # Z, X, C
        ]
        self.last_hit_times = [0] * 9
        self.hit_cooldown = 0.1  

        self.first_hit_time = None
        self.time_limit = 180  

        self.bad_template = self._load_template('assets/bad.png')
        self.good_templates = [
            self._load_template('assets/good1.png'),
            self._load_template('assets/good2.png'),
            self._load_template('assets/good3.png')
        ]
        
        self.match_threshold = 0.65 

    def _load_template(self, filepath):
        if not os.path.exists(filepath):
            print(f"⚠️ 警告: 找不到特征图 {filepath}！")
            return None
        return cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)

    def start_bot(self, window_title, log_callback, ui_reset_callback):
        if not self.start_engine(window_title, log_callback, ui_reset_callback): return
        
        self.first_hit_time = None
        
        t_main = threading.Thread(target=self._mole_loop, daemon=True)
        self.threads.append(t_main)
        t_main.start()

    def _mole_loop(self):
        SHOW_DEBUG_WINDOW = False 
        
        REF_GRID_X = 896
        REF_GRID_Y = 600
        REF_GRID_W = 768
        REF_GRID_H = 660
        
        if self.log_callback: self.log_callback("🐹 就绪！等待第一只地鼠冒头触发 3 分钟倒计时...")

        last_cw, last_ch = 0, 0
        scaled_bad_tpl = None
        scaled_good_tpls = []

        while not self.stop_event.is_set():
            if not self.hwnd:
                time.sleep(1) 
                continue
                
            if self.first_hit_time is not None:
                if time.time() - self.first_hit_time >= self.time_limit:
                    if self.log_callback: self.log_callback("⏱️ 3分钟时间已到，脚本自动安全停止！")
                    self.stop()
                    break 

            client_rect = win32gui.GetClientRect(self.hwnd)
            cw, ch = client_rect[2], client_rect[3]
            
            gx, gy, gw, gh, scale_ratio = self.map_2560x1440(REF_GRID_X, REF_GRID_Y, REF_GRID_W, REF_GRID_H, cw, ch)

            if cw != last_cw or ch != last_ch:
                last_cw, last_ch = cw, ch
                if self.log_callback: self.log_callback(f"🔄 检测到窗口变化，特征雷达自动校准至 {scale_ratio:.2f} 倍")
                
                if self.bad_template is not None:
                    tw = max(5, int(self.bad_template.shape[1] * scale_ratio))
                    th = max(5, int(self.bad_template.shape[0] * scale_ratio))
                    scaled_bad_tpl = cv2.resize(self.bad_template, (tw, th))
                
                scaled_good_tpls = []
                for tpl in self.good_templates:
                    if tpl is not None:
                        tw = max(5, int(tpl.shape[1] * scale_ratio))
                        th = max(5, int(tpl.shape[0] * scale_ratio))
                        scaled_good_tpls.append(cv2.resize(tpl, (tw, th)))

            roi_grid = self.capture_bg(self.hwnd, (gx, gy, gw, gh))
            if roi_grid is None: continue

            cell_w = roi_grid.shape[1] // 3
            cell_h = roi_grid.shape[0] // 3
            current_time = time.time()

            for i in range(9):
                row = i // 3
                col = i % 3
                
                x1 = col * cell_w
                y1 = row * cell_h
                x2 = x1 + cell_w
                y2 = y1 + cell_h
                cell_img = roi_grid[y1:y2, x1:x2]
                
                status = self.analyze_hole_by_feature(cell_img, scaled_bad_tpl, scaled_good_tpls)
                
                if status == 1:
                    if current_time - self.last_hit_times[i] > self.hit_cooldown:
                        
                        if self.first_hit_time is None:
                            self.first_hit_time = current_time
                            if self.log_callback: self.log_callback("⏳ 首次击杀确认！已启动内部 3 分钟倒计时锁。")

                        key_code = self.key_map[i]
                        self.send_key_bg(self.hwnd, key_code)
                        self.last_hit_times[i] = current_time
                        
                if SHOW_DEBUG_WINDOW:
                    color = (0, 255, 0) if status == 1 else (0, 0, 255) if status == 2 else (255, 255, 255)
                    cv2.rectangle(roi_grid, (x1, y1), (x2, y2), color, 2)

            if SHOW_DEBUG_WINDOW:
                cv2.imshow("Whack-A-Mole Radar", roi_grid)
                cv2.waitKey(1) 

        cv2.destroyAllWindows()

    def analyze_hole_by_feature(self, cell_img, bad_tpl, good_tpls):
        h, w = cell_img.shape[:2]
        if h == 0 or w == 0: return 0
        
        gray_cell = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)

        if bad_tpl is not None and gray_cell.shape[0] >= bad_tpl.shape[0] and gray_cell.shape[1] >= bad_tpl.shape[1]:
            res = cv2.matchTemplate(gray_cell, bad_tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if max_val > self.match_threshold: return 2 

        for good_tpl in good_tpls:
            if good_tpl is not None and gray_cell.shape[0] >= good_tpl.shape[0] and gray_cell.shape[1] >= good_tpl.shape[1]:
                res = cv2.matchTemplate(gray_cell, good_tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val > self.match_threshold: return 1 

        return 0