# Subtitle Translate by LLM (Qt Version) 🎬

这是一个基于 PyQt6 构建的本地 LLM 批量字幕翻译工具。它通过连接本地运行的 vLLM API 服务，利用大语言模型（如 Qwen2.5）对 SRT 字幕文件进行高质量、上下文感知的翻译。

## ✨ 主要特性

-   **本地 LLM 推理**：使用 vLLM 作为后端，支持流式输出和高并发推理，不仅速度快且完全保护隐私。
-   **上下文感知**：翻译时会参考前一段和后一段字幕的语境，有效解决代词指代不明和语气不连贯的问题。
-   **双语字幕支持**：可选择生成“中文译文 + 英文原文”的双语字幕。
-   **高并发处理**：支持自定义并发请求数量，大幅提升批量翻译速度。
-   **智能断点续传**：自动扫描文件夹，跳过已经翻译完成的文件。
-   **影视级翻译提示词**：内置针对影视字幕优化的 Prompt，追求口语化、极简主义和意译优先。
-   **友好 GUI 界面**：实时显示运行日志和翻译进度。

## 🛠️ 环境要求

-   **操作系统**: Windows (建议搭配 WSL2 运行 vLLM 服务器)
-   **Python**: 3.10+
-   **vLLM 服务**: 需要在本地或 WSL 中运行 vLLM API 服务（默认端口 30000）。

## 🚀 快速开始

### 1. 安装依赖

在项目目录下执行：

```bash
pip install -r requirements.txt
pip install openai  # 核心逻辑依赖 openai 库连接 vLLM
```

### 2. 启动 vLLM 服务器

在 WSL 或 Linux 环境下启动 vLLM (以 Qwen2.5-7B-Instruct 为例)：

```bash
# 请确保你的显存能够运行该模型
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct-AWQ \
    --port 30000 \
    --trust-remote-code
```

### 3. 运行项目

执行主程序：

```bash
python main.py
```

## 📖 使用指南

1.  **选择文件夹**：点击“选择文件夹”，定位到存放 `.srt` 字幕文件的目录。
2.  **设置并发数**：根据你的显存和模型大小调整并发数（默认 8）。
3.  **双语模式**：如果需要双语字幕，勾选“生成双语字幕”。
4.  **开始翻译**：点击“开始批量翻译”，程序将自动扫描并逐个处理文件。
5.  **查看结果**：翻译后的文件将保存在原目录下。

## ⚙️ 配置文件

项目的配置信息（如最后一次使用的路径、并发数等）将自动保存在 `translator_config.json` 中。

## 📝 技术细节

-   **核心驱动**: `PyQt6`, `vLLM (OpenAI API compatible)`, `pysrt`
-   **默认模型**: `Qwen2.5-7B-Instruct-AWQ` (可根据实际部署情况修改)
-   **Prompt 策略**: 
    -   严禁翻译腔，追求地道口语化。
    -   参考上下午语境。
    -   字幕格式严格保持。

## 🤝 贡献建议

欢迎提交 Issue 或 Pull Request 来改进翻译 Prompt 或增加更多字幕格式（如 ASS/VTT）的支持。

---
*Powered by LLM & Python*
