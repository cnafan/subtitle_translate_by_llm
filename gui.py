import os
import time
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit,
                             QProgressBar, QFileDialog, QMessageBox,
                             QComboBox, QCheckBox, QSpinBox)
from PyQt6.QtGui import QFont
from worker import TranslationWorker
import config

# Hardcoded default model ID, used for internal config saving/loading/worker creation
DEFAULT_MODEL_ID = "Qwen2.5-3B-Instruct-AWQ"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("本地LLM字幕批量翻译工具 (vLLM API并发版)")
        self.resize(900, 750)
        self.worker = None

        self._model_id = DEFAULT_MODEL_ID

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(10)

        # --- 1. 配置区域 ---
        config_group = QWidget()
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(0, 0, 0, 0)

        # Model Display
        model_display_layout = QHBoxLayout()
        self.model_label_display = QLabel(f"API 模型 ID: <b>{self._model_id}</b>")
        model_display_layout.addWidget(self.model_label_display)
        model_display_layout.addStretch()
        config_layout.addLayout(model_display_layout)

        # 文件夹路径 (字幕所在目录)
        h_layout_folder = QHBoxLayout()
        self.input_folder = QLineEdit()
        self.input_folder.setPlaceholderText("选择包含 SRT 字幕的文件夹")
        btn_folder = QPushButton("选择文件夹")
        btn_folder.clicked.connect(self.select_folder)
        h_layout_folder.addWidget(QLabel("字幕文件夹:"))
        h_layout_folder.addWidget(self.input_folder)
        h_layout_folder.addWidget(btn_folder)
        config_layout.addLayout(h_layout_folder)

        # 高级设置
        h_layout_adv = QHBoxLayout()

        # Concurrency Level
        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 32)
        self.spin_concurrency.setValue(8)
        self.spin_concurrency.setToolTip("同时发送的 API 请求数量。")

        # 上下文 (显示)
        self.combo_ctx = QComboBox()
        self.combo_ctx.addItems(["2048", "4096", "8192"])
        self.combo_ctx.setEnabled(False)

        # GPU (显示)
        self.input_gpu = QLineEdit("-1")
        self.input_gpu.setPlaceholderText("由服务器控制")
        self.input_gpu.setFixedWidth(100)
        self.input_gpu.setEnabled(False)

        # [新增] 双语字幕复选框
        self.check_bilingual = QCheckBox("生成双语字幕")
        self.check_bilingual.setToolTip("勾选后，输出文件将包含【中文翻译 + 英文原文】")

        self.check_verbose = QCheckBox("启用详细日志")
        self.check_verbose.setChecked(True)

        h_layout_adv.addWidget(QLabel("并发数:"))
        h_layout_adv.addWidget(self.spin_concurrency)
        h_layout_adv.addSpacing(15)
        h_layout_adv.addWidget(self.check_bilingual)  # 加入布局
        h_layout_adv.addSpacing(15)
        h_layout_adv.addWidget(self.check_verbose)
        h_layout_adv.addStretch()

        # 为了布局紧凑，上下文和GPU信息可以放这里或者简化，这里保留但简化显示

        config_layout.addLayout(h_layout_adv)
        layout.addWidget(config_group)

        # --- 2. 日志区域 ---
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        layout.addWidget(QLabel("运行日志:"))
        layout.addWidget(self.text_log)

        # --- 3. 进度条与按钮 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        h_layout_btns = QHBoxLayout()
        self.btn_start = QPushButton("开始批量翻译")
        self.btn_start.setMinimumHeight(45)
        self.btn_start.setStyleSheet("background-color: #2c3e50; color: white; font-weight: bold; font-size: 14px;")
        self.btn_start.clicked.connect(self.start_processing)

        self.btn_stop = QPushButton("停止")
        self.btn_stop.setMinimumHeight(45)
        self.btn_stop.setStyleSheet("background-color: #c0392b; color: white; font-size: 14px;")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_processing)

        h_layout_btns.addWidget(self.btn_start)
        h_layout_btns.addWidget(self.btn_stop)
        layout.addLayout(h_layout_btns)

    def log(self, message):
        timestamp = time.strftime("[%H:%M:%S]", time.localtime())
        self.text_log.append(f"{timestamp} {message}")
        sb = self.text_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    # --- 事件处理 ---

    def load_settings(self):
        cfg = config.load_config()
        self._model_id = cfg.get('model_path', DEFAULT_MODEL_ID)
        self.model_label_display.setText(f"API 模型 ID: <b>{self._model_id}</b>")
        self.input_folder.setText(cfg.get('folder_path', ''))
        self.spin_concurrency.setValue(cfg.get('concurrency_level', 8))
        self.input_gpu.setText(str(cfg.get('gpu_layers', '-1')))
        self.check_verbose.setChecked(cfg.get('verbose_log', True))

        # [加载] 双语设置
        self.check_bilingual.setChecked(cfg.get('bilingual', False))

        self.log(f"配置已加载。")

    def save_settings(self):
        cfg = {
            'model_path': self._model_id,
            'folder_path': self.input_folder.text().strip(),
            'context_size': 4096,
            'gpu_layers': -1,
            'verbose_log': self.check_verbose.isChecked(),
            'concurrency_level': self.spin_concurrency.value(),
            'bilingual': self.check_bilingual.isChecked()  # [保存] 双语设置
        }
        config.save_config(cfg)

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择字幕文件夹")
        if folder_path:
            self.input_folder.setText(folder_path)

    def start_processing(self):
        model_id = self._model_id
        folder = self.input_folder.text().strip()
        concurrency = self.spin_concurrency.value()

        if not folder or not os.path.exists(folder):
            QMessageBox.warning(self, "错误", "字幕文件夹路径无效")
            return

        self.save_settings()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.input_folder.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log("--- 启动后台线程 (vLLM API) ---")
        self.log(f"并发: {concurrency} | 双语模式: {'开' if self.check_bilingual.isChecked() else '关'}")

        ctx = 4096
        gpu = -1
        verbose = self.check_verbose.isChecked()
        bilingual = self.check_bilingual.isChecked()  # 获取复选框状态

        # 传入 bilingual 参数
        self.worker = TranslationWorker(model_id, folder, ctx, gpu, verbose, concurrency, bilingual)
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
        self.log("--- 任务结束 ---")
        self.reset_ui_state()
        QMessageBox.information(self, "完成", "任务已结束")

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