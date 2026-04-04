import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from gui import MainWindow


def main():
    app = QApplication(sys.argv)

    # 设置全局默认字体 (优先使用更现代的无衬线字体)
    font = QFont("Segoe UI", 10)
    if "PingFang SC" in QFont().families():
         font = QFont("PingFang SC", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()