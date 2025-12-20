import json
import os

CONFIG_FILE = "translator_config.json"

DEFAULT_CONFIG = {
    'model_path': '',
    'folder_path': '',
    'context_size': 4096,
    'gpu_layers': -1,
    'verbose_log': True,
    'concurrency_level': 8,
    'bilingual': False  # [新增] 双语字幕开关默认关闭
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