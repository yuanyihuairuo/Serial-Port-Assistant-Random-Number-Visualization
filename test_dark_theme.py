
import sys
from PyQt6.QtWidgets import QApplication
try:
    exec(open('serial_random_optimized.py').read())
    print('应用程序加载成功 - 深色主题已应用')
except ImportError as e:
    print(f'缺少依赖: {e}')
except Exception as e:
    print(f'运行时错误: {e}')

