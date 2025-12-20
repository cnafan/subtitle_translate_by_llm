import time
import traceback
import re
import pysrt
import sys
import os
from pathlib import Path

# 尝试导入 openai 客户端库
try:
    from openai import OpenAI, APIConnectionError

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class LLMEngine:
    def __init__(self, log_callback=None):
        self.client = None
        # [更新] 默认模型 ID 修改为 7B
        self.model_name = "Qwen2.5-7B-Instruct-AWQ"
        self.log = log_callback if log_callback else print
        self.device = "api"

    def load_model(self, model_input, context_size, gpu_layers, verbose=True):
        """
        初始化 API 连接 (vLLM 模式)
        """
        if not OPENAI_AVAILABLE:
            self.log("错误: 未检测到 openai 库。")
            self.log("请运行: pip install openai")
            raise ImportError("未检测到 openai 库")

        self.log("正在尝试连接本地 vLLM 服务 (WSL/Port 30000)...")

        # [关键修复 1: 适配 vLLM 启动端口] 端口改为 30000
        base_url = "http://localhost:30000/v1"

        try:
            # 初始化客户端
            self.client = OpenAI(base_url=base_url, api_key="vllm")

            # 测试连接并列出模型
            try:
                models_list = self.client.models.list()
                self.log(f"成功连接到本地 vLLM 服务: {base_url}")
                available_models = [m.id for m in models_list.data]
                self.log(f"vLLM 可用的模型标识符: {available_models}")

                if not models_list.data:
                    self.log("警告: vLLM 服务返回的模型列表为空。")
                    self.log("请确保 vLLM 启动参数 --model 指定的名称正确。")

            except Exception as e:
                self.log(f"连接服务成功但获取模型列表异常: {e}")

        except Exception as e:
            self.log(f"!!! 连接失败 !!! 错误: {e}")
            self.log("请确保 vLLM API 服务器在 WSL 端已启动，并监听端口 30000。")
            raise RuntimeError("无法连接到本地 LLM 服务")

        # --- 模型名称处理 ---
        # [修复点] 如果 model_input 为空，使用硬编码的默认值 (7B)
        self.model_name = model_input if model_input else "Qwen2.5-7B-Instruct-AWQ"

        self.log(f"当前使用的模型名称: {self.model_name}")
        self.log("提示: 推理任务将由 vLLM 在 WSL 端的 GPU 上执行。")

    def translate_text(self, text, previous_text=None, next_text=None):
        """
        翻译单段文本 (支持上下文感知与Few-Shot增强)
        """
        if not self.client:
            raise RuntimeError("API 客户端未连接")

        # 构建带有上下文的 Prompt
        user_content = f"待翻译字幕:\n{text}"

        context_info = []
        if previous_text:
            context_info.append(f"上文语境: {previous_text}")
        if next_text:
            context_info.append(f"下文语境: {next_text}")

        if context_info:
            context_block = "\n".join(context_info)
            user_content = f"参考语境:\n{context_block}\n\n{user_content}"

        # [深度优化] System Prompt
        system_prompt = (
            "你是一位资深影视字幕翻译专家，擅长将英文字幕翻译成地道、简洁、沉浸式的简体中文。\n"
            "### 核心原则：\n"
            "1. **口语化**：译文必须像中国人日常说话，严禁翻译腔。例如 'I guess' 译为 '我想' 或 '大概'，而不是 '我猜'。\n"
            "2. **语境感知**：参考上下午判断代词（he/it）指代。语气要符合人物关系（如朋友间的随意、上下级的正式）。\n"
            "3. **极简主义**：字幕一闪而过，译文越短越好。能用两个字绝不用四个字。\n"
            "4. **意译优先**：遇到成语、俚语或双关，翻译其**言外之意**，而非字面意思。\n"
            "5. **格式严格**：直接输出译文，**不要**加引号，**不要**包含原文，**不要**写'译文：'。\n\n"
            "### 优秀翻译示例 (Few-Shot)：\n"
            "Input: It's on the house.\nContext: (Bartender serving a drink)\nOutput: 算我的。\n\n"
            "Input: I'm seeing someone.\nContext: (Girl talking to a pursuer)\nOutput: 我有对象了。\n\n"
            "Input: Copy that.\nContext: (Soldiers on radio)\nOutput: 收到。\n\n"
            "Input: You have to be kidding me.\nContext: (Shocked by bad news)\nOutput: 开什么玩笑。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            # 调用 API
            output = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.2,
                top_p=0.9,
                max_tokens=256,
            )
            content = output.choices[0].message.content

        except Exception as e:
            raise RuntimeError(f"API 请求失败: {e}")

        # --- 后处理清理 ---
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        content = content.replace("译文：", "").replace("翻译：", "")
        if (content.startswith('"') and content.endswith('"')) or \
                (content.startswith('“') and content.endswith('”')):
            content = content[1:-1]

        return content


class SRTProcessor:
    @staticmethod
    def scan_files(folder_path):
        """
        递归扫描所有 SRT 文件
        1. 排除本身是翻译结果的文件 (.zh.srt)
        2. [新增] 排除已经存在对应翻译文件的源文件 (跳过已完成)
        """
        path = Path(folder_path)
        all_files = list(path.rglob("*.srt"))

        # 1. 过滤掉本身就是翻译结果的文件
        source_files = [f for f in all_files if not f.name.endswith(".zh.srt")]

        target_files = []
        for src in source_files:
            # 计算预期的输出文件名 (逻辑需与 worker.py 保存逻辑一致)
            src_str = str(src)
            if src_str.lower().endswith('.en.srt'):
                output_path = Path(src_str[:-7] + '.srt')
            else:
                output_path = src.with_suffix('.srt')

            # 2. 如果输出文件不存在，才加入待处理列表
            if not output_path.exists():
                target_files.append(src)
            # else:
            #     print(f"Skipping existing: {src.name}") # 可选：调试用

        return target_files

    @staticmethod
    def read_file(file_path):
        """读取单个 SRT 文件内容，并返回字幕列表"""
        try:
            return pysrt.open(str(file_path))
        except Exception:
            # 尝试 utf-8 编码
            return pysrt.open(str(file_path), encoding='utf-8')