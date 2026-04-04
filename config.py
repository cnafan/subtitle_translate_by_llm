import json
import os

CONFIG_FILE = "translator_config.json"

DEFAULT_CONFIG = {
    'api_base_url': 'http://127.0.0.1:1234/api/v1/chat',
    'api_model': 'qwen3.5-9b',
    'folder_path': '',
    'context_size': 20000,
    'batch_size': 20,
    'gpu_layers': -1,
    'verbose_log': True,
    'concurrency_level': 4,
    'bilingual': False,
    'overwrite_existing': False
}


def load_config():
    """加载配置，如果文件不存在或损坏则返回默认值"""
    try:
        if not os.path.exists(CONFIG_FILE):
            return DEFAULT_CONFIG.copy()

        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # 简单的合并策略，确保新增加的字段有默认值
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config_data):
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")