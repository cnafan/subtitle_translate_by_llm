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

        # 构建批量任务 Prompt
        input_lines = []
        for i, text in enumerate(texts):
            # 清理文本中的换行，避免格式混乱
            clean_text = text.replace('\n', ' ').strip()
            input_lines.append(f"<{batch_start_index + i}> {clean_text}")
        
        input_content = "\n".join(input_lines)

        system_prompt = (
            "你是一流的影视字幕翻译专家，擅长中英双语。你现在的任务是批量翻译一段连续的字幕。\n"
            "### 核心准则：\n"
            "1. **口语化与自然度**：译文必须地道，严禁机器翻译腔。结合前后文，确保对话连贯、自然。\n"
            "2. **语境感知**：这是一批连续的字幕，请根据整体语境处理人称、缩写和特定称谓。\n"
            "3. **专有名词处理**：由于这是中文场景，请保持**人名、地名、专业术语**为英文原文，不要音译。\n"
            "4. **极简主义**：字幕需易于阅读，译文应简洁精练。\n"
            "5. **格式严格**：**严禁回显原文或输出英文原文**。格式必须为: <编号> 翻译后的中文。**仅输出中文或必要的术语，不要任何额外解释、不要重复编号。**\n\n"
            "### 示例：\n"
            "Input:\n<1> What are you doing here?\n<2> Just looking around.\n"
            "Output:\n<1> 你在这里做什么？\n<2> 随便看看。"
        )

        payload = {
            "model": self.model_name,
            "system_prompt": system_prompt,
            "input": f"请翻译以下连续字幕：\n{input_content}"
        }

        try:
            response = requests.post(
                self.api_base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300
            )
            response.raise_for_status()
            res_json = response.json()
            
            # 适配不同的返回格式
            if "choices" in res_json:
                content = res_json["choices"][0]["message"]["content"]
            elif "response" in res_json:
                content = res_json["response"]
            elif "content" in res_json:
                content = res_json["content"]
            else:
                content = str(res_json)

        except Exception as e:
            self.log(f"API 请求失败: {e}")
            raise RuntimeError(f"API 请求失败: {e}")

        # 解析返回结果
        results = {}
        
        # 预处理：处理某些 API 返回文本中包含字面量 \n 的情况
        content = content.replace('\\n', '\n')
        
        # 如果模型漏掉了第一个编号，尝试手动补全
        first_tag_pattern = rf'<\s*{batch_start_index}\s*>'
        if not re.search(first_tag_pattern, content):
            # 查找是否存在后续编号，如果存在，则将前面的内容视为第一个编号的内容
            next_tag_search = re.search(r'<\s*(\d+)\s*>', content)
            if next_tag_search:
                content = f"<{batch_start_index}> " + content
            else:
                # 只有一段文本且没编号，直接作为第一个
                content = f"<{batch_start_index}> " + content

        # 更加健壮的正则：匹配 <编号> 后面直到下一个 <编号> 或结束的内容
        # 不再强制要求编号前必须有换行符
        matches = re.finditer(r'<\s*(\d+)\s*>\s*(.*?)(?=<\s*\d+\s*>|$)', content, re.DOTALL)
        
        for match in matches:
            try:
                idx = int(match.group(1))
                val = match.group(2).strip()
                # 常见垃圾清理：引号、冒号、空行
                val = re.sub(r'^(译文|翻译|Chinese|Result|Output)[:：\s]*', '', val, flags=re.IGNORECASE)
                if (val.startswith('"') and val.endswith('"')) or (val.startswith('“') and val.endswith('”')):
                    val = val[1:-1].strip()
                results[idx] = val
            except Exception:
                continue

        # 按原始列表顺序返回结果，缺失的补原句
        final_list = []
        for i in range(len(texts)):
            real_idx = batch_start_index + i
            original_text = texts[i].strip()
            
            if real_idx in results:
                val = results[real_idx]
                
                # [Post-Processing] 检查译文中是否回显了原文
                # 如果译文包含了原文，且内容较长，尝试切掉重复部分
                if original_text and (original_text.lower() in val.lower()):
                    # 匹配原文及其前后的空行/符号并剔除
                    pattern = re.escape(original_text)
                    val = re.sub(pattern, '', val, flags=re.IGNORECASE).strip()
                    # 如果剔除后变为空白，则还是用原文
                    if not val:
                        val = results[real_idx] # 降级回原始值

                final_list.append(val)
            else:
                self.log(f"警告: 编号 <{real_idx}> 解析失败，使用原文代替。")
                final_list.append(texts[i])

        return final_list

    def translate_text(self, text, previous_text=None, next_text=None):
        """兼容旧版调用逻辑"""
        res = self.translate_batch([text])
        return res[0] if res else text


class SRTProcessor:
    @staticmethod
    def scan_files(folder_path, overwrite=False):
        """递归扫描所有 SRT 文件"""
        path = Path(folder_path)
        all_files = list(path.rglob("*.srt"))
        source_files = [f for f in all_files if not f.name.endswith(".zh.srt")]

        if overwrite:
            return source_files

        target_files = []
        for src in source_files:
            src_str = str(src)
            if src_str.lower().endswith('.en.srt'):
                output_path = Path(src_str[:-7] + '.srt')
            else:
                output_path = src.with_suffix('.srt')

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