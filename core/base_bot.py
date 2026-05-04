import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import win32api
import ctypes
import threading
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) 
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  
    except Exception:
        pass

class BaseBot:
    def __init__(self):
        self.target_window = ""
        self.hwnd = None
        self.is_running = False
        self.stop_event = threading.Event()
        self.threads = []
        self.ui_reset_callback = None
        self.log_callback = None
        
        self.REF_W = 2560
        self.REF_H = 1440

    def get_hwnd(self, title_keyword):
        hwnd_list = []
        def enum_windows_proc(hwnd, lParam):
            if win32gui.IsWindowVisible(hwnd) and title_keyword in win32gui.GetWindowText(hwnd):
                hwnd_list.append(hwnd)
            return True
        win32gui.EnumWindows(enum_windows_proc, None)
        return hwnd_list[0] if hwnd_list else None

    def capture_bg(self, hwnd, crop_rect=None):
        if not hwnd or win32gui.IsIconic(hwnd): 
            return None
            
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            w, h = right - left, bottom - top
            if w <= 0 or h <= 0: 
                return None

            client_rect = win32gui.GetClientRect(hwnd)
            client_w, client_h = client_rect[2], client_rect[3]
            
            point = win32gui.ClientToScreen(hwnd, (0, 0))
            border_x = max(0, point[0] - left)
            title_y = max(0, point[1] - top)

            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
            saveDC.SelectObject(saveBitMap)

            ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)

            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            img = np.frombuffer(bmpstr, dtype='uint8')
            img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)

            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)

            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            img = img[title_y:title_y+client_h, border_x:border_x+client_w]

            if crop_rect:
                x, y, cw, ch = crop_rect
                img = img[y:y+ch, x:x+cw]
            return img
        except Exception as e:
            return None

    def map_2560x1440(self, ref_x, ref_y, ref_w, ref_h, client_w, client_h):
        if client_w <= 0 or client_h <= 0: return 0, 0, 1, 1
        
        target_ratio = self.REF_W / self.REF_H
        current_ratio = client_w / client_h

        if current_ratio > target_ratio + 0.01:   
            real_h = client_h
            real_w = int(client_h * target_ratio)
            offset_x = (client_w - real_w) // 2
            offset_y = 0
        elif current_ratio < target_ratio - 0.01: 
            real_w = client_w
            real_h = int(client_w / target_ratio)
            offset_x = 0
            offset_y = (client_h - real_h) // 2
        else:                                     
            real_w, real_h = client_w, client_h
            offset_x, offset_y = 0, 0

        scale_x = real_w / self.REF_W
        scale_y = real_h / self.REF_H

        x = offset_x + int(ref_x * scale_x)
        y = offset_y + int(ref_y * scale_y)
        w = max(1, int(ref_w * scale_x))
        h = max(1, int(ref_h * scale_y))
        
        return x, y, w, h, scale_x

    def send_key_bg(self, hwnd, key_code):
        if not hwnd: return
        scan_code = win32api.MapVirtualKey(key_code, 0)
        lparam_down = 1 | (scan_code << 16)
        lparam_up = 1 | (scan_code << 16) | (1 << 30) | (1 << 31)
        
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, key_code, lparam_down)
        time.sleep(0.05) 
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, key_code, lparam_up)

    def safe_absdiff_mean(self, img1, img2):
        if img1 is None or img2 is None: return 0.0
        img1_safe, img2_safe = img1.astype(np.uint8), img2.astype(np.uint8)
        if img1_safe.shape != img2_safe.shape:
            img1_safe = cv2.resize(img1_safe, (img2_safe.shape[1], img2_safe.shape[0]))
        return np.mean(cv2.absdiff(img1_safe, img2_safe))

    def start_engine(self, window_title, log_callback, ui_reset_callback):
        self.target_window = window_title
        self.log_callback = log_callback
        self.ui_reset_callback = ui_reset_callback
        self.hwnd = self.get_hwnd(window_title)
        
        if not self.hwnd:
            self.log_callback("❌ 未找到游戏窗口！")
            return False

        self.stop_event.clear()
        self.is_running = True
        return True

    def stop(self):
        self.stop_event.set()
        self.is_running = False
        if self.ui_reset_callback:
            self.ui_reset_callback()