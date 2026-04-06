import time
import traceback
import re
import pysrt
import sys
import os
import requests
import json
from pathlib import Path

class LLMEngine:
    def __init__(self, log_callback=None):
        self.api_base_url = "http://127.0.0.1:1234/api/v1/chat"
        self.model_name = "qwen3.5-9b"
        self.log = log_callback if log_callback else print
        self.session_log_path = None # 用于记录原始 Prompt 和 Response 的详细日志文件路径

    def _write_session_log(self, data_type, content):
        """记录详细调试信息到会话日志文件"""
        if not self.session_log_path:
            return
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        try:
            with open(self.session_log_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*20} {timestamp} {data_type} {'='*20}\n")
                f.write(content)
                f.write("\n")
        except Exception as e:
            self.log(f"无法写入会话日志: {e}")

    def load_model(self, api_base_url, model_id, context_size, gpu_layers, verbose=True):
        """
        初始化 API 配置
        """
        self.api_base_url = api_base_url
        self.model_name = model_id
        self.log(f"已配置 API 终端: {self.api_base_url}")
        self.log(f"当前使用的模型名称: {self.model_name}")

    def translate_batch(self, texts, batch_start_index=1):
        """
        批量翻译文本块，利用模型的大上下文提升连贯性
        """
        if not texts:
            return []

        # 调试信息缓冲区，用于确保 Request/Response 在日志中成对出现
        debug_info = []
        batch_id = f"Batch {batch_start_index}-{batch_start_index + len(texts) - 1}"

        # 构建批量任务 Prompt
        input_lines = []
        for i, text in enumerate(texts):
            clean_text = text.replace('\n', ' ').strip()
            input_lines.append(f"<{batch_start_index + i}> {clean_text}")
        
        input_content = "\n".join(input_lines)

        system_prompt = (
            "你是一流的资深影视字幕翻译专家，擅长处理各种现代美剧、电影中的口语、俚语和文化双关语。\n"
            "### 翻译核心准则：\n"
            "1. **信达雅与地道化**：译文必须极其自然，坚决杜绝任何“机翻感”。优先采用中文母语者在日常口语或戏剧冲突中的表达方式，对俚语 (Slang) 和习语 (Idiom) 进行等效置换，而非直译。\n"
            "2. **语境高度感知**：这是连续剧集的内容，请务必联系前后文逻辑。注意语体色彩 (Tone) 的一致性，根据角色性格（如泼辣、儒雅、痞气）调整遣词造句。\n"
            "3. **专有名词与术语**：保持**人名、地名、特定缩写、未汉化的品牌名**为英文原文。除非该词在中文语境下已有统一标准的译名，否则请保留原文以防解析偏差。\n"
            "4. **影视化表达**：字幕应短小精悍、有爆发力且易于快速阅读。避免冗长的从句，翻译应兼具节奏美与冲击力。\n"
            "5. **格式金科玉律**：**严禁回显原文！严禁包含英文！** 仅输出: <编号> 翻译后的中文。每一行必须以编号开头，且不得包含任何解释或多余的标点符号。**\n\n"
            "### 解析示例：\n"
            "Input:\n<1> You're really pushin' it, man.\n<2> Cut me some slack!\n"
            "Output:\n<1> 哥们，你可别得寸进尺。\n<2> 饶了我吧！"
        )
        user_input = f"请翻译以下连续字幕：\n{input_content}"

        payload = {
            "model": self.model_name,
            "system_prompt": system_prompt,
            "input": user_input
        }

        debug_info.append(f"\n>>> [{batch_id}] PROMPT INPUT")
        debug_info.append(f"System: {system_prompt}")
        debug_info.append(f"User: {user_input}")

        content = ""
        try:
            response = requests.post(
                self.api_base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300
            )
            response.raise_for_status()
            res_json = response.json()
            
            debug_info.append(f"\n<<< [{batch_id}] RAW RESPONSE")
            debug_info.append(json.dumps(res_json, ensure_ascii=False, indent=2))

            if "choices" in res_json and len(res_json["choices"]) > 0:
                choice = res_json["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]
                elif "text" in choice:
                    content = choice["text"]
                else:
                    content = str(choice)
            elif "response" in res_json:
                content = res_json["response"]
            elif "content" in res_json:
                content = res_json["content"]
            elif "message" in res_json and "content" in res_json["message"]:
                content = res_json["message"]["content"]
            else:
                content = str(res_json)

            if "'}]," in content or '"}],' in content:
                content = re.sub(r"['\"]\}\],.*$", "", content, flags=re.DOTALL)
            elif "}," in content and "'stats'" in content:
                content = re.sub(r"\},.*'stats'.*$", "", content, flags=re.DOTALL)

        except Exception as e:
            self.log(f"API 请求失败: {e}")
            debug_info.append(f"\n!!! [{batch_id}] API ERROR: {e}")
            self._write_session_log(f"Full Batch Debug ({batch_id})", "\n".join(debug_info))
            raise RuntimeError(f"API 请求失败: {e}")

        # 解析返回结果
        results = {}
        content = content.replace('\\n', '\n')
        
        first_tag_pattern = rf'<\s*{batch_start_index}\s*[>\]\)]'
        if not re.search(first_tag_pattern, content):
            next_tag_search = re.search(r'<\s*(\d+)\s*[>\]\)]', content)
            if next_tag_search:
                content = f"<{batch_start_index}> " + content
            else:
                content = f"<{batch_start_index}> " + content

        matches = re.finditer(r'<\s*(\d+)\s*[>\]\)\:：]\s*(.*?)(?=<\s*\d+\s*[>\]\)\:：]|$)', content, re.DOTALL)
        for match in matches:
            try:
                idx = int(match.group(1))
                val = match.group(2).strip()
                val = re.sub(r'^(译文|翻译|Chinese|Result|Output)[:：\s]*', '', val, flags=re.IGNORECASE)
                if (val.startswith('"') and val.endswith('"')) or (val.startswith('“') and val.endswith('”')):
                    val = val[1:-1].strip()
                results[idx] = val
            except Exception:
                continue

        final_list = []
        for i in range(len(texts)):
            real_idx = batch_start_index + i
            original_text = texts[i].strip()
            
            if real_idx in results:
                val = results[real_idx]
                cleaned_original = original_text.replace('\n', ' ').strip()
                if cleaned_original and (cleaned_original.lower() in val.lower()):
                    pattern = re.escape(cleaned_original)
                    val = re.sub(pattern, '', val, flags=re.IGNORECASE).strip()
                    val = val.strip(' .:：')
                    if not val:
                        val = results[real_idx] 
                final_list.append(val)
            else:
                # 给 GUI 显示用简短版，给日志记录用完整版
                short_text = (original_text[:40] + '...') if len(original_text) > 40 else original_text
                error_msg_gui = f"警告: 编号 <{real_idx}> 解析失败，使用原文代替: [{short_text}]"
                self.log(error_msg_gui)
                
                # 记录到会话日志的必须是完整信息
                debug_info.append(f"\n??? [{batch_id}] PARSING FAILURE (ID: {real_idx})")
                debug_info.append(f"Original Text: {original_text}")
                debug_info.append(f"Reason: Index {real_idx} not found in parsed results dictionary.")
                final_list.append(texts[i])

        # 最后将汇总的调试信息一次性写入日志
        self._write_session_log(f"Full Batch Debug ({batch_id})", "\n".join(debug_info))
        return final_list

    def translate_text(self, text, previous_text=None, next_text=None):
        """兼容旧版调用逻辑"""
        res = self.translate_batch([text])
        return res[0] if res else text


class SRTProcessor:
    @staticmethod
    def scan_files(folder_path, overwrite=False):
        """递归扫描所有 .en.srt 文件"""
        path = Path(folder_path)
        # 仅检测后缀为 .en.srt 的文件作为待处理任务
        source_files = list(path.rglob("*.en.srt"))

        if overwrite:
            return source_files

        target_files = []
        for src in source_files:
            src_str = str(src)
            # 对应的翻译输出路径通常是将 .en.srt 替换为 .srt
            output_path_str = src_str[:-7] + '.srt'
            output_path = Path(output_path_str)

            if not output_path.exists():
                target_files.append(src)

        return target_files

    @staticmethod
    def read_file(file_path):
        """读取单个 SRT 文件内容"""
        try:
            return pysrt.open(str(file_path))
        except Exception:
            return pysrt.open(str(file_path), encoding='utf-8')