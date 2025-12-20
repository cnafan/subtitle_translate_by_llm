import traceback
import concurrent.futures
import time
from PyQt6.QtCore import QThread, pyqtSignal
from core_logic import LLMEngine, SRTProcessor
import pysrt
import os


class TranslationWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, model_id, target_folder, context_size, gpu_layers, verbose_log, concurrency_level, bilingual):
        super().__init__()
        self.model_id = model_id
        self.target_folder = target_folder
        self.context_size = context_size
        self.gpu_layers = gpu_layers
        self.verbose_log = verbose_log
        self.concurrency_level = concurrency_level
        self.bilingual = bilingual  # [新增] 接收双语参数
        self.is_running = True
        self.llm_engine = LLMEngine(log_callback=self.emit_log)
        self._executor = None

    def emit_log(self, msg):
        self.log_signal.emit(msg)

    def check_stop(self):
        return not self.is_running

    def process_file_concurrently(self, file_path):
        try:
            subs = SRTProcessor.read_file(str(file_path))
        except Exception as e:
            self.emit_log(f"读取文件 {file_path.name} 失败: {e}")
            return False

        total_items = len(subs)
        start_time = time.time()

        if total_items == 0:
            self.emit_log(f"文件 {file_path.name} 为空，跳过。")
            return True

        futures = []
        results_map = {}
        is_completed = True

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency_level) as executor:
            self._executor = executor

            # 1. 提交任务
            for i, sub in enumerate(subs):
                if not self.is_running:
                    executor.shutdown(wait=False, cancel_futures=True)
                    is_completed = False
                    break

                original_text = sub.text.replace('\n', ' ')
                if not original_text.strip():
                    continue

                # 提取上下文
                prev_text = None
                if i > 0:
                    prev_text = subs[i - 1].text.replace('\n', ' ')

                next_text = None
                if i < total_items - 1:
                    next_text = subs[i + 1].text.replace('\n', ' ')

                future = executor.submit(
                    self.llm_engine.translate_text,
                    original_text,
                    prev_text,
                    next_text
                )
                futures.append((i, sub, future))

            # 2. 实时收集结果
            if is_completed:
                for index, sub, future in futures:
                    if not self.is_running:
                        is_completed = False
                        break

                    current_count = index + 1
                    percent = (current_count / total_items) * 100

                    try:
                        translated_text = future.result()
                        results_map[index] = (sub, translated_text)

                        preview = (translated_text[:30] + '..') if len(translated_text) > 30 else translated_text
                        self.emit_log(f"[{percent:.1f}%] {file_path.name}: {current_count}/{total_items} -> {preview}")

                    except concurrent.futures.CancelledError:
                        is_completed = False
                        break
                    except Exception as e:
                        self.emit_log(
                            f"[{percent:.1f}%] {file_path.name}: 第 {current_count} 行翻译出错: {e}。保留原文。")
                        results_map[index] = (sub, sub.text)

                    file_progress = int(percent)
                    self.progress_signal.emit(file_progress)

        self._executor = None

        # 3. 重建字幕文件 (支持双语)
        if is_completed and results_map:
            new_subs = pysrt.SubRipFile()
            sorted_indices = sorted(results_map.keys())

            for i in sorted_indices:
                sub, translated_text = results_map[i]

                # [核心逻辑] 根据双语开关组合文本
                if self.bilingual:
                    # 格式：中文在上，英文在下 (符合大多数阅读习惯)
                    final_text = f"{translated_text}\n{sub.text}"
                else:
                    final_text = translated_text

                new_sub = pysrt.SubRipItem(
                    index=i + 1,
                    start=sub.start,
                    end=sub.end,
                    text=final_text
                )
                new_subs.append(new_sub)

            file_str = str(file_path)
            if file_str.lower().endswith('.en.srt'):
                output_path_str = file_str[:-7] + '.srt'
            else:
                output_path_str = str(file_path.with_suffix('.srt'))

            new_subs.save(output_path_str, encoding='utf-8')

            elapsed = time.time() - start_time
            output_name = output_path_str.split(os.sep)[-1]
            self.emit_log(f"  -> 已保存: {output_name} (耗时: {elapsed:.1f}s)")
            return True
        else:
            self.emit_log(f"  -> 文件 {file_path.name} 任务中断或数据为空，未保存。")
            return False

    def run(self):
        try:
            self.llm_engine.load_model(
                self.model_id,
                self.context_size,
                self.gpu_layers,
                self.verbose_log
            )

            files = SRTProcessor.scan_files(self.target_folder)
            if not files:
                self.emit_log("未找到需要翻译的 .srt 文件。")
                self.finished_signal.emit()
                return

            self.emit_log(f"共发现 {len(files)} 个待处理文件。")
            self.emit_log(f"并发级别: {self.concurrency_level} | 双语模式: {'开启' if self.bilingual else '关闭'}")

            total_files = len(files)

            for index, srt_file in enumerate(files):
                if not self.is_running:
                    break

                self.emit_log(f"[{index + 1}/{total_files}] 正在处理: {srt_file.name}")
                self.process_file_concurrently(srt_file)

                progress = int(((index + 1) / total_files) * 100)
                self.progress_signal.emit(progress)

            self.emit_log("任务序列结束。")
            self.finished_signal.emit()

        except Exception as e:
            self.error_signal.emit(f"运行时严重错误: {str(e)}")
            traceback.print_exc()

    def stop(self):
        self.is_running = False
        self.emit_log("接收到停止信号，正在尝试终止进行中的 API 请求...")
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None