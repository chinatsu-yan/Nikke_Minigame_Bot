import cv2
import numpy as np
import time
import win32gui
import threading
import pydirectinput 
from core.base_bot import BaseBot

class ParkourBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.CURRENT_LEVEL = 1  
        self.GAME_IS_RUNNING = False 

        self.REF_LVL_X, self.REF_LVL_Y, self.REF_LVL_W, self.REF_LVL_H = 905, 15, 205, 69
        self.REF_TIMER_X, self.REF_TIMER_Y, self.REF_TIMER_W, self.REF_TIMER_H = 1550, 20, 50, 50
        self.REF_ROI_X, self.REF_ROI_Y, self.REF_ROI_W, self.REF_ROI_H = 1075, 964, 640, 115

    def start_bot(self, window_title, log_callback, ui_reset_callback):
        if not self.start_engine(window_title, log_callback, ui_reset_callback): return
        t_main = threading.Thread(target=self._parkour_loop, daemon=True)
        self.threads.append(t_main)
        t_main.start()

    def _parkour_loop(self):
        REF_MIN_OBJ_AREA = 50 
        REF_LONG_JUMP_W = 41  
        
        lower_yellow = np.array([15, 100, 100])
        upper_yellow = np.array([40, 255, 255])
        
        SHOW_DEBUG_WINDOW = False  
        
        game_started = False
        game_start_time = 0
        last_jump_time = 0
        base_cooldown = 0.01 
        
        baseline_level_img = None
        frame_counter = 0
        
        is_level_animating = False  
        level_anim_start_time = 0   

        while not self.stop_event.is_set():
            if not self.hwnd:
                time.sleep(1) 
                continue
                
            client_rect = win32gui.GetClientRect(self.hwnd)
            cw, ch = client_rect[2], client_rect[3]
            
            tx, ty, tw, th, _ = self.map_2560x1440(self.REF_TIMER_X, self.REF_TIMER_Y, self.REF_TIMER_W, self.REF_TIMER_H, cw, ch)
            lx, ly, lw, lh, _ = self.map_2560x1440(self.REF_LVL_X, self.REF_LVL_Y, self.REF_LVL_W, self.REF_LVL_H, cw, ch)
            rx, ry, rw, rh, scale_ratio = self.map_2560x1440(self.REF_ROI_X, self.REF_ROI_Y, self.REF_ROI_W, self.REF_ROI_H, cw, ch)

            full_img = self.capture_bg(self.hwnd)
            if full_img is None or full_img.size == 0: 
                time.sleep(0.01)
                continue
            
            roi_img = full_img[max(0,ry):ry+rh, max(0,rx):rx+rw]
            timer_img = full_img[max(0,ty):ty+th, max(0,tx):tx+tw]
            lvl_img = full_img[max(0,ly):ly+lh, max(0,lx):lx+lw]
            
            debug_view = full_img.copy() if SHOW_DEBUG_WINDOW else None

            if not game_started:
                baseline_level_img = None  
                is_level_animating = False
                if timer_img is not None and timer_img.size > 0:
                    gray = cv2.cvtColor(timer_img, cv2.COLOR_BGR2GRAY)
                    if np.max(gray) > 220: 
                        game_started = True
                        game_start_time = time.time()
                        self.CURRENT_LEVEL = 1
                        self.GAME_IS_RUNNING = True 
                        if self.log_callback: self.log_callback("🏃 跑酷引擎启动！")
                time.sleep(0.02) 
                continue 

            # 熔断器
            if time.time() - game_start_time > 165:
                game_started = False
                self.GAME_IS_RUNNING = False 
                if self.log_callback: self.log_callback("🛑 跑酷时间到，重置状态。")
                continue

            frame_counter += 1
            if frame_counter % 5 == 0:  
                gray_lvl = cv2.cvtColor(lvl_img, cv2.COLOR_BGR2GRAY)
                _, thresh_lvl = cv2.threshold(gray_lvl, 150, 255, cv2.THRESH_BINARY_INV)
                
                if baseline_level_img is None:
                    baseline_level_img = thresh_lvl.copy()
                elif is_level_animating:
                    if time.time() - level_anim_start_time > 0.5:
                        baseline_level_img = thresh_lvl.copy()
                        is_level_animating = False
                else:
                    diff = self.safe_absdiff_mean(thresh_lvl, baseline_level_img)
                    if diff > 5.0:
                        self.CURRENT_LEVEL += 1
                        if self.log_callback: self.log_callback(f"📈 等级提升: Lv.{self.CURRENT_LEVEL}")
                        
                        is_level_animating = True
                        level_anim_start_time = time.time()
            
            hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
            
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel), cv2.MORPH_CLOSE, kernel)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            should_jump = False
            current_cooldown = base_cooldown 
            jump_type_str = "" 
            
            real_min_area = REF_MIN_OBJ_AREA * (scale_ratio ** 2)
            real_long_jump_w = REF_LONG_JUMP_W * scale_ratio
            
            valid_boxes = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w * h > real_min_area:
                    valid_boxes.append((x / rw, x, y, w, h))
            
            valid_boxes.sort(key=lambda b: b[0])
            level_factor = self.CURRENT_LEVEL - 1
            
            for box in valid_boxes:
                obj_rel_pos, x, y, w, h = box
                fx, fy = rx + x, ry + y 

                if h > rh * 0.55:
                    trigger_ratio = 0.34
                    jump_type_str = f"高:{trigger_ratio:.3f}"
                    current_cooldown = 0.01
                elif w > real_long_jump_w:
                    trigger_ratio = min(0.18 + (level_factor * 0.005), 0.23)  
                    jump_type_str = f"长:{trigger_ratio:.2f}"
                    current_cooldown = 0.01
                else:
                    trigger_ratio = min(0.18 + (level_factor * 0.005), 0.23) 
                    jump_type_str = f"普:{trigger_ratio:.2f}"
                    current_cooldown = 0.01

                if obj_rel_pos <= trigger_ratio:
                    should_jump = True
                    if SHOW_DEBUG_WINDOW:
                        cv2.rectangle(debug_view, (fx, fy), (fx+w, fy+h), (0, 255, 0), 2)
                else:
                    if SHOW_DEBUG_WINDOW:
                        cv2.rectangle(debug_view, (fx, fy), (fx+w, fy+h), (0, 0, 255), 2)
                        
                if should_jump:
                    break
            
            current_time = time.time()
            if should_jump and (current_time - last_jump_time) > current_cooldown:
                log_msg = f"[{time.strftime('%H:%M:%S')}] ⚠️ 跳！ | Lv.{self.CURRENT_LEVEL} | {jump_type_str}"
                if self.log_callback: self.log_callback(log_msg)
                pydirectinput.press('space')
                last_jump_time = current_time

            if SHOW_DEBUG_WINDOW:
                cv2.rectangle(debug_view, (tx, ty), (tx+tw, ty+th), (0, 255, 0), 2)
                cv2.putText(debug_view, "TIMER ACTIVE", (tx, ty-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.rectangle(debug_view, (lx, ly), (lx+lw, ly+lh), (255, 0, 0), 2)
                cv2.putText(debug_view, "LEVEL", (lx, ly-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
                cv2.rectangle(debug_view, (rx, ry), (rx+rw, ry+rh), (0, 255, 255), 2)
                cv2.putText(debug_view, "RADAR ROI", (rx, ry-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

                current_dynamic_trigger = min(0.16 + (level_factor * 0.004), 0.20)
                trigger_x_abs = rx + int(rw * current_dynamic_trigger)
                cv2.line(debug_view, (trigger_x_abs, ry), (trigger_x_abs, ry + rh), (255, 0, 255), 2)

                debug_view_resized = cv2.resize(debug_view, (1280, 720))
                cv2.imshow("Parkour Global Radar", debug_view_resized)
                cv2.waitKey(1) 
            else:
                time.sleep(0.002)

        cv2.destroyAllWindows()