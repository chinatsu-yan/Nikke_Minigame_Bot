import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import win32api
import ctypes
import threading
import time

class BaseBot:
    def __init__(self):
        self.target_window = ""
        self.hwnd = None
        self.is_running = False
        self.stop_event = threading.Event()
        self.threads = []
        self.ui_reset_callback = None
        self.log_callback = None

    def get_hwnd(self, title_keyword):
        hwnd_list = []
        def enum_windows_proc(hwnd, lParam):
            if win32gui.IsWindowVisible(hwnd) and title_keyword in win32gui.GetWindowText(hwnd):
                hwnd_list.append(hwnd)
            return True
        win32gui.EnumWindows(enum_windows_proc, None)
        return hwnd_list[0] if hwnd_list else None

    def capture_bg(self, hwnd, crop_rect=None):
        if not hwnd: return None
        
        if win32gui.IsIconic(hwnd):
            return None
            
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        w, h = right - left, bottom - top
        
        if w <= 0 or h <= 0:
            return None

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
        if crop_rect:
            x, y, cw, ch = crop_rect
            img = img[y:y+ch, x:x+cw]
        return img

    def send_key_bg(self, hwnd, key_code):
        """
        发送纯净的带硬件扫描码的后台按键
        """
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