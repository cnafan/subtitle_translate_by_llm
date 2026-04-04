import ctypes
import sys

# Windows API constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def set_keep_awake(keep_awake=True):
    """
    阻止或允许系统进入睡眠模式（仅限 Windows）。
    """
    if sys.platform != "win32":
        return

    try:
        if keep_awake:
            # ES_CONTINUOUS: 设置状态后保持有效，直到下一次调用此函数
            # ES_SYSTEM_REQUIRED: 强制系统处于工作状态（不进入待机）
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        else:
            # 恢复默认状态，允许系统按电源计划进入睡眠
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception as e:
        print(f"设置系统唤醒状态失败: {e}")


class PreventSleepContext:
    """
    上下文管理器，用于在任务执行期间阻止睡眠。
    """

    def __enter__(self):
        set_keep_awake(True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_keep_awake(False)
