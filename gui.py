import os
import time
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit,
                             QProgressBar, QFileDialog, QMessageBox,
                             QComboBox, QCheckBox, QSpinBox, QFrame)
from PyQt6.QtGui import QFont, QColor, QPalette
from PyQt6.QtCore import Qt
from worker import TranslationWorker
import config

# Apple-inspired Minimalist Dark Theme Stylesheet
STYLESHEET = """
QMainWindow {
    background-color: #1C1C1E;
}

QWidget {
    color: #FFFFFF;
    font-family: "SF Pro Display", -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

QLabel {
    font-weight: 400;
    color: #FFFFFF;
}

.SectionCard {
    background-color: #2C2C2E;
    border: none;
    border-radius: 16px;
}

.HeaderLabel {
    font-size: 18px;
    font-weight: 600;
    color: #FFFFFF;
    margin-bottom: 4px;
}

QLineEdit, QSpinBox, QComboBox {
    background-color: #3A3A3C;
    border: 1px solid #48484A;
    border-radius: 10px;
    padding: 12px 16px;
    color: #FFFFFF;
    selection-background-color: #0A84FF;
    selection-color: #FFFFFF;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #0A84FF;
}

QProgressBar {
    background-color: #3A3A3C;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: transparent;
    height: 8px;
}

QProgressBar::chunk {
    background-color: #0A84FF;
    border-radius: 4px;
}

QTextEdit {
    background-color: #2C2C2E;
    border: 1px solid #38383A;
    border-radius: 16px;
    padding: 16px;
    font-family: "SF Mono", "Menlo", "Consolas", monospace;
    font-size: 13px;
    color: #EBEBF5;
    line-height: 1.5;
}

QPushButton {
    background-color: #3A3A3C;
    border: none;
    border-radius: 12px;
    padding: 12px 24px;
    font-weight: 600;
    color: #FFFFFF;
}

QPushButton:hover {
    background-color: #48484A;
}

QPushButton:pressed {
    background-color: #545456;
}

QPushButton#btnStart {
    background-color: #0A84FF;
    color: #FFFFFF;
}

QPushButton#btnStart:hover {
    background-color: #409CFF;
}

QPushButton#btnStart:pressed {
    background-color: #007AFF;
}

QPushButton#btnStop {
    background-color: #FF453A;
    color: #FFFFFF;
}

QPushButton#btnStop:hover {
    background-color: #FF6961;
}

QPushButton#btnStop:pressed {
    background-color: #D70015;
}

QPushButton:disabled {
    background-color: #2C2C2E;
    color: #48484A;
}

QCheckBox {
    spacing: 12px;
    color: #EBEBF5;
}

QCheckBox::indicator {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    border: 2px solid #48484A;
    background-color: #2C2C2E;
}

QCheckBox::indicator:checked {
    background-color: #0A84FF;
    border: 2px solid #0A84FF;
    image: url(check_mark.png); /* Note: if we had a checkmark image */
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 4px;
}

QScrollBar::handle:vertical {
    background: #48484A;
    min-height: 40px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #636366;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Subtitle Translator")
        self.resize(1000, 850)
        self.setStyleSheet(STYLESHEET)
        self.worker = None

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # --- Title Section ---
        header_section = QHBoxLayout()
        title_label = QLabel("字幕 AI 翻译")
        title_label.setStyleSheet("font-size: 28px; font-weight: 700; color: #FFFFFF;")
        header_section.addWidget(title_label)
        header_section.addStretch()
        main_layout.addLayout(header_section)

        # --- API Configuration Card ---
        api_card = QFrame()
        api_card.setProperty("class", "SectionCard")
        api_layout = QVBoxLayout(api_card)
        api_layout.setContentsMargins(20, 20, 20, 20)
        api_layout.setSpacing(16)

        api_header = QLabel("API 服务配置")
        api_header.setProperty("class", "HeaderLabel")
        api_layout.addWidget(api_header)

        api_inputs = QHBoxLayout()
        v_box_url = QVBoxLayout()
        label_url = QLabel("API Endpoint")
        label_url.setStyleSheet("color: #8E8E93; font-size: 11px; text-transform: uppercase; font-weight: 700;")
        v_box_url.addWidget(label_url)
        self.input_api_url = QLineEdit()
        self.input_api_url.setPlaceholderText("http://localhost:1234/v1")
        v_box_url.addWidget(self.input_api_url)

        v_box_model = QVBoxLayout()
        label_model = QLabel("Model ID")
        label_model.setStyleSheet("color: #8E8E93; font-size: 11px; text-transform: uppercase; font-weight: 700;")
        v_box_model.addWidget(label_model)
        self.input_model_id = QLineEdit()
        self.input_model_id.setPlaceholderText("qwen3.5-9b")
        v_box_model.addWidget(self.input_model_id)

        api_inputs.addLayout(v_box_url, 3)
        api_inputs.addLayout(v_box_model, 2)
        api_layout.addLayout(api_inputs)
        main_layout.addWidget(api_card)

        # --- Files & Generation Card ---
        file_card = QFrame()
        file_card.setProperty("class", "SectionCard")
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(20, 20, 20, 20)
        file_layout.setSpacing(16)

        file_header = QLabel("文件与生成选项")
        file_header.setProperty("class", "HeaderLabel")
        file_layout.addWidget(file_header)

        path_layout = QHBoxLayout()
        self.input_folder = QLineEdit()
        self.input_folder.setPlaceholderText("字幕所在文件夹路径")
        btn_folder = QPushButton("选择文件夹")
        btn_folder.setFixedWidth(120)
        btn_folder.clicked.connect(self.select_folder)
        path_layout.addWidget(self.input_folder)
        path_layout.addWidget(btn_folder)
        file_layout.addLayout(path_layout)

        # Advanced Settings
        adv_layout = QHBoxLayout()
        adv_layout.setSpacing(25)
        
        concur_box = QHBoxLayout()
        c_label = QLabel("并发数:")
        c_label.setStyleSheet("color: #8E8E93;")
        concur_box.addWidget(c_label)
        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 64)
        self.spin_concurrency.setFixedWidth(75)
        concur_box.addWidget(self.spin_concurrency)
        adv_layout.addLayout(concur_box)

        self.check_bilingual = QCheckBox("双语输出")
        self.check_overwrite = QCheckBox("覆盖已有")
        self.check_verbose = QCheckBox("详细日志")
        self.check_verbose.setChecked(True)

        adv_layout.addWidget(self.check_bilingual)
        adv_layout.addWidget(self.check_overwrite)
        adv_layout.addWidget(self.check_verbose)
        adv_layout.addStretch()

        file_layout.addLayout(adv_layout)
        main_layout.addWidget(file_card)

        # --- Console & Processing ---
        log_header = QLabel("处理进度与控制台")
        log_header.setProperty("class", "HeaderLabel")
        main_layout.addWidget(log_header)

        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        main_layout.addWidget(self.text_log)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        h_layout_btns = QHBoxLayout()
        h_layout_btns.setSpacing(15)
        self.btn_start = QPushButton("开始翻译任务")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.setMinimumHeight(54)
        self.btn_start.clicked.connect(self.start_processing)

        self.btn_stop = QPushButton("停止")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setMinimumHeight(54)
        self.btn_stop.setFixedWidth(120)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_processing)

        h_layout_btns.addWidget(self.btn_start)
        h_layout_btns.addWidget(self.btn_stop)
        main_layout.addLayout(h_layout_btns)

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        # Cleaner text logs for dark theme
        clean_msg = message.replace("<b>", "").replace("</b>", "").replace("<span style='color: #ef4444;'>", "").replace("<span style='color: #10b981;'>", "").replace("</span>", "")
        # Add subtle colors for logs if needed (optional)
        if "完成" in message or "成功" in message:
            display_msg = f"<span style='color: #30D158;'>[{timestamp}] {clean_msg}</span>"
        elif "错误" in message or "失败" in message:
            display_msg = f"<span style='color: #FF453A;'>[{timestamp}] {clean_msg}</span>"
        else:
            display_msg = f"<span style='color: #EBEBF5;'>[{timestamp}] {clean_msg}</span>"
            
        self.text_log.append(display_msg)
        sb = self.text_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def load_settings(self):
        cfg = config.load_config()
        self.input_api_url.setText(cfg.get('api_base_url', 'http://127.0.0.1:1234/api/v1/chat'))
        self.input_model_id.setText(cfg.get('api_model', 'qwen3.5-9b'))
        self.input_folder.setText(cfg.get('folder_path', ''))
        self.spin_concurrency.setValue(cfg.get('concurrency_level', 4))
        self.check_verbose.setChecked(cfg.get('verbose_log', True))
        self.check_bilingual.setChecked(cfg.get('bilingual', False))
        self.check_overwrite.setChecked(cfg.get('overwrite_existing', False))
        self.log("系统就绪。")

    def save_settings(self):
        cfg = {
            'api_base_url': self.input_api_url.text().strip(),
            'api_model': self.input_model_id.text().strip(),
            'folder_path': self.input_folder.text().strip(),
            'context_size': 20000,
            'batch_size': 50,
            'gpu_layers': -1,
            'verbose_log': self.check_verbose.isChecked(),
            'concurrency_level': self.spin_concurrency.value(),
            'bilingual': self.check_bilingual.isChecked(),
            'overwrite_existing': self.check_overwrite.isChecked()
        }
        config.save_config(cfg)

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择字幕文件夹")
        if folder_path:
            self.input_folder.setText(folder_path)

    def start_processing(self):
        api_url = self.input_api_url.text().strip()
        model_id = self.input_model_id.text().strip()
        folder = self.input_folder.text().strip()
        concurrency = self.spin_concurrency.value()

        if not api_url or not folder or not os.path.exists(folder):
            QMessageBox.warning(self, "配置错误", "请检查配置信息。")
            return

        self.save_settings()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.input_folder.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log(f"任务启动 - 并发: {concurrency}")

        ctx = 20000
        gpu = -1
        verbose = self.check_verbose.isChecked()
        bilingual = self.check_bilingual.isChecked()
        overwrite = self.check_overwrite.isChecked()

        self.worker = TranslationWorker(api_url, model_id, folder, ctx, gpu, verbose, concurrency, bilingual, overwrite)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.error_signal.connect(self.on_error)
        self.worker.start()

    def stop_processing(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.log("正在停止任务...")
            self.btn_stop.setEnabled(False)

    def on_finished(self):
        self.log("任务全部完成。")
        self.reset_ui_state()
        QMessageBox.information(self, "完成", "所有任务已处理完毕。")

    def on_error(self, msg):
        self.log(f"错误: {msg}")
        self.reset_ui_state()
        QMessageBox.critical(self, "错误", msg)

    def reset_ui_state(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.input_folder.setEnabled(True)

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)