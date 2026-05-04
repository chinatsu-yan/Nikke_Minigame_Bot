import cv2
import numpy as np
import time
import win32gui
import win32con
import threading
import pydirectinput 
from core.base_bot import BaseBot

class ParkourBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.CURRENT_LEVEL = 1  
        self.GAME_IS_RUNNING = False 

    def level_monitor_thread(self):
        REL_LVL_X, REL_LVL_Y, REL_LVL_W, REL_LVL_H = 0.38, 0.05, 0.08, 0.048  
        baseline_img = None 
        
        while not self.stop_event.is_set():
            if not self.GAME_IS_RUNNING or not self.hwnd:
                baseline_img = None
                time.sleep(0.1)
                continue
                
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            win_width, win_height = right - left, bottom - top
            
            crop_rect = (
                int(win_width * REL_LVL_X), int(win_height * REL_LVL_Y), 
                int(win_width * REL_LVL_W), int(win_height * REL_LVL_H)
            )
            
            img = self.capture_bg(self.hwnd, crop_rect)
            if img is None: continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
            
            if baseline_img is None:
                baseline_img = thresh.copy()
                time.sleep(0.1)
                continue

            if self.safe_absdiff_mean(thresh, baseline_img) > 5.0:
                self.CURRENT_LEVEL += 1
                if self.log_callback: self.log_callback(f"📈 等级提升: Lv.{self.CURRENT_LEVEL}")
                time.sleep(0.5)
                
                img_new = self.capture_bg(self.hwnd, crop_rect)
                _, baseline_img = cv2.threshold(cv2.cvtColor(img_new, cv2.COLOR_BGR2GRAY), 150, 255, cv2.THRESH_BINARY_INV)
            else:
                time.sleep(0.1) 

    def start_bot(self, window_title, log_callback, ui_reset_callback):
        if not self.start_engine(window_title, log_callback, ui_reset_callback):
            return
            
        t = threading.Thread(target=self.level_monitor_thread, daemon=True)
        self.threads.append(t)
        t.start()
        
        t_main = threading.Thread(target=self._parkour_loop, daemon=True)
        self.threads.append(t_main)
        t_main.start()

    def _parkour_loop(self):
        BASE_REL_X, REL_Y, REL_W, REL_H = 0.42, 0.67, 0.25, 0.08 
        lower_yellow = np.array([15, 100, 100])
        upper_yellow = np.array([40, 255, 255])
        REL_TIMER_X, REL_TIMER_Y = 0.6197, 0.0710  
        SHOW_DEBUG_WINDOW = False 
        
        game_started = False
        game_start_time = 0
        last_jump_time = 0
        base_cooldown = 0.01 

        while not self.stop_event.is_set():
            if not self.hwnd:
                time.sleep(1) 
                continue
                
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            win_width, win_height = right - left, bottom - top
            
            if not game_started:
                timer_crop = (int(win_width * REL_TIMER_X), int(win_height * REL_TIMER_Y), 5, 5)
                img = self.capture_bg(self.hwnd, timer_crop)
                if img is None: continue

                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                if np.mean(gray) > 150: 
                    game_started = True
                    game_start_time = time.time()
                    self.CURRENT_LEVEL = 1
                    self.GAME_IS_RUNNING = True 
                time.sleep(0.05) 
                continue 

            if time.time() - game_start_time > 165:
                game_started = False
                self.GAME_IS_RUNNING = False 
                continue

            roi_crop = (
                int(win_width * BASE_REL_X), int(win_height * REL_Y), 
                int(win_width * REL_W), int(win_height * REL_H)
            )

            img = self.capture_bg(self.hwnd, roi_crop)
            if img is None: continue

            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
            
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel), cv2.MORPH_CLOSE, kernel)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            should_jump = False
            current_cooldown = base_cooldown 
            jump_type_str = "" 
            
            valid_boxes = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w * h > 50:
                    valid_boxes.append((BASE_REL_X + (x / win_width), x, y, w, h))
            
            valid_boxes.sort(key=lambda b: b[0])
            level_factor = self.CURRENT_LEVEL - 1
            
            for box in valid_boxes:
                obj_abs_ratio, x, y, w, h = box
                if h > roi_crop[3] * 0.55: 
                    trigger_ratio = 0.505
                    jump_type_str = f"高:{trigger_ratio:.3f}"
                    current_cooldown = 0.01
                elif w > win_width * 0.016:  
                    trigger_ratio = min(0.46 + (level_factor * 0.001), 0.47)
                    jump_type_str = f"长:{trigger_ratio:.2f}"
                    current_cooldown = 0.01 
                else:
                    trigger_ratio = min(0.46 + (level_factor * 0.001), 0.47)
                    jump_type_str = f"普:{trigger_ratio:.2f}"
                    current_cooldown = 0.01 

                if obj_abs_ratio <= trigger_ratio:
                    should_jump = True
                if should_jump:
                    break
            
            current_time = time.time()
            if should_jump and (current_time - last_jump_time) > current_cooldown:
                log_msg = f"[{time.strftime('%H:%M:%S')}] ⚠️ 跳！ | Lv.{self.CURRENT_LEVEL} | {jump_type_str}"
                if self.log_callback: self.log_callback(log_msg)
                
                pydirectinput.press('space')
                last_jump_time = current_time

            if SHOW_DEBUG_WINDOW:
                cv2.imshow("Vision & Analysis", img)
                cv2.waitKey(1) 

        cv2.destroyAllWindows()