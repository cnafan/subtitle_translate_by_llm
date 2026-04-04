import traceback
import concurrent.futures
import time
from PyQt6.QtCore import QThread, pyqtSignal
from core_logic import LLMEngine, SRTProcessor
from system_utils import PreventSleepContext
import pysrt
import os
import config


class TranslationWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, api_base_url, model_id, target_folder, context_size, gpu_layers, verbose_log, concurrency_level, bilingual, overwrite):
        super().__init__()
        self.api_base_url = api_base_url
        self.model_id = model_id
        self.target_folder = target_folder
        self.context_size = context_size
        self.gpu_layers = gpu_layers
        self.verbose_log = verbose_log
        self.concurrency_level = concurrency_level
        self.bilingual = bilingual
        self.overwrite = overwrite
        self.is_running = True
        self.llm_engine = LLMEngine(log_callback=self.emit_log)
        self._executor = None

    def emit_log(self, msg):
        self.log_signal.emit(msg)

    def check_stop(self):
        return not self.is_running

    def process_file(self, file_path):
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

        # 从配置中获取 Batch Size，默认为 20
        cfg = config.load_config()
        batch_size = cfg.get('batch_size', 20)
        
        # 准备分块任务
        batches = []
        for i in range(0, total_items, batch_size):
            end_idx = min(i + batch_size, total_items)
            batch_texts = [sub.text for sub in subs[i:end_idx]]
            batches.append((i, batch_texts))

        results_map = {}
        is_completed = True

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency_level) as executor:
            self._executor = executor
            
            # 提交 Batch 任务
            # 注意：batch_start_index 使用 1-based 为 LLM 友好
            future_to_batch = {
                executor.submit(self.llm_engine.translate_batch, texts, start_idx + 1): (start_idx, texts)
                for start_idx, texts in batches
            }

            for future in concurrent.futures.as_completed(future_to_batch):
                if not self.is_running:
                    is_completed = False
                    break
                
                start_idx, original_texts = future_to_batch[future]
                try:
                    translated_texts = future.result()
                    
                    # 将结果填入 results_map
                    for offset, trans in enumerate(translated_texts):
                        idx = start_idx + offset
                        results_map[idx] = trans
                    
                    # 更新进度日志
                    done_count = len(results_map)
                    percent = (done_count / total_items) * 100
                    self.emit_log(f"[{percent:.1f}%] {file_path.name}: 已完成 {done_count}/{total_items} 行")
                    self.progress_signal.emit(int(percent))

                except Exception as e:
                    self.emit_log(f"处理 Batch (起始索引 {start_idx}) 时出错: {e}")
                    # 出错则使用原文兜底
                    for offset, orig in enumerate(original_texts):
                        idx = start_idx + offset
                        results_map[idx] = orig

        self._executor = None

        # 3. 重建字幕文件 (支持双语)
        if is_completed and results_map:
            new_subs = pysrt.SubRipFile()
            for i in range(total_items):
                sub = subs[i]
                translated_text = results_map.get(i, sub.text)

                if self.bilingual:
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
            self.emit_log(f"  -> 已保存: {os.path.basename(output_path_str)} (耗时: {elapsed:.1f}s)")
            return True
        else:
            self.emit_log(f"  -> 文件 {file_path.name} 任务中断或数据为空，未保存。")
            return False

    def run(self):
        try:
            self.llm_engine.load_model(
                self.api_base_url,
                self.model_id,
                self.context_size,
                self.gpu_layers,
                self.verbose_log
            )

            files = SRTProcessor.scan_files(self.target_folder, overwrite=self.overwrite)
            if not files:
                self.emit_log("未找到需要翻译的 .srt 文件。")
                self.finished_signal.emit()
                return

            self.emit_log(f"共发现 {len(files)} 个待处理文件。")
            self.emit_log(f"并发级别: {self.concurrency_level} | 双语模式: {'开启' if self.bilingual else '关闭'}")

            total_files = len(files)

            with PreventSleepContext():
                for index, srt_file in enumerate(files):
                    if not self.is_running:
                        break

                    self.emit_log(f"[{index + 1}/{total_files}] 正在处理: {srt_file.name}")
                    self.process_file(srt_file)

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