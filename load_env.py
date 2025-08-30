"""
加载环境变量
"""
from pathlib import Path
import os

def load_env_file(env_file: str = '.env'):
    """手动加载.env文件"""
    env_path = Path(env_file)
    if not env_path.exists():
        print(f"Environment file not found: {env_file}")
        return
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # 移除引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                os.environ[key] = value
    
    print(f"Loaded environment variables from {env_file}")

if __name__ == "__main__":
    load_env_file()
    print("Available OpenRouter keys:")
    for key, value in os.environ.items():
        if 'OPENROUTER' in key:
            print(f"{key}: {value[:10]}..." if len(value) > 10 else f"{key}: {value}")