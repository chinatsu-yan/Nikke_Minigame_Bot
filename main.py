import sys
import ctypes
from gui.app import App

def is_admin():
    try:
        # 检查是否拥有管理员权限
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if __name__ == "__main__":
    if is_admin():
        # 如果已经是管理员，正常拉起 UI
        app = App()
        app.mainloop()
    else:
        # 如果不是管理员，重新以管理员身份运行当前脚本/程序
        print("请求管理员权限中...")
        ctypes.windll.shell32.ShellExecuteW(
            None, 
            "runas", 
            sys.executable, 
            " ".join(sys.argv), 
            None, 
            1
        )
        sys.exit()