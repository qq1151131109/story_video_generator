"""
配置管理器 - 完全基于原Coze工作流参数
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

@dataclass
class ModelConfig:
    """LLM模型配置"""
    name: str
    temperature: float
    max_tokens: int
    api_base: str
    api_key: str

@dataclass  
class MediaConfig:
    """媒体生成配置"""
    image_resolution: str = "1024x1024"
    image_quality: str = "high"
    voice_speed: float = 1.2
    voice_volume: float = 1.0
    
@dataclass
class VideoConfig:
    """视频合成配置"""
    resolution: str = "1920x1080"
    fps: int = 30
    format: str = "mp4"

class ConfigManager:
    """
    配置管理器 - 完全基于原Coze工作流参数
    
    基于以下原工作流节点的配置：
    - Node_121343: 文案生成 (DeepSeek-V3, temp=0.8, max_tokens=1024)
    - Node_1199098: 主题提取 (DeepSeek-V3, temp=1.0, max_tokens=512)
    - Node_1165778: 分镜分割 (DeepSeek-V3, temp=0.8, max_tokens=8192)
    - Node_186126: 图像提示词 (DeepSeek-V3-0324, temp=1.0, max_tokens=16384)
    - Node_1301843: 主角分析 (DeepSeek-V3, temp=0.8, max_tokens=8192)
    """
    
    def __init__(self, config_path: str = "config/settings.json"):
        self.config_path = Path(config_path)
        self.config_dir = self.config_path.parent
        self.logger = logging.getLogger(__name__)
        
        # 加载主配置
        self._load_main_config()
        
        # 加载多语言配置
        self._load_language_configs()
        
        # 加载API配置
        self._load_api_configs()
    
    def _load_main_config(self):
        """加载主配置文件"""
        if not self.config_path.exists():
            self._create_default_config()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.logger.info(f"Loaded config from {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            self._create_default_config()
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
    
    def _create_default_config(self):
        """创建默认配置文件（基于原Coze工作流）"""
        default_config = {
            "general": {
                "output_dir": "output",
                "temp_dir": "output/temp", 
                "log_level": "INFO",
                "max_concurrent_tasks": 5,  # 对应原工作流批处理并发数
                "supported_languages": ["zh", "en", "es"],
                "default_language": "zh"
            },
            "llm": {
                # 对应Node_121343配置 - 使用DeepSeek v3.1
                "script_generation": {
                    "model": "deepseek/deepseek-chat-v3.1",
                    "temperature": 0.8,
                    "max_tokens": 1024,
                    "api_base": "${OPENROUTER_API_BASE:-https://openrouter.ai/api/v1}",
                    "api_key": "${OPENROUTER_API_KEY}"
                },
                # 对应Node_1199098配置 - 使用DeepSeek v3.1  
                "theme_extraction": {
                    "model": "deepseek/deepseek-chat-v3.1",
                    "temperature": 1.0,
                    "max_tokens": 512,
                    "api_base": "${OPENROUTER_API_BASE:-https://openrouter.ai/api/v1}",
                    "api_key": "${OPENROUTER_API_KEY}"
                },
                # 对应Node_1165778配置 - 使用DeepSeek v3.1
                "scene_splitting": {
                    "model": "deepseek/deepseek-chat-v3.1", 
                    "temperature": 0.8,
                    "max_tokens": 8192,
                    "api_base": "${OPENROUTER_API_BASE:-https://openrouter.ai/api/v1}",
                    "api_key": "${OPENROUTER_API_KEY}"
                },
                # 对应Node_186126配置 - 使用DeepSeek v3.1
                "image_prompt_generation": {
                    "model": "deepseek/deepseek-chat-v3.1",
                    "temperature": 1.0,
                    "max_tokens": 16384,
                    "api_base": "${OPENROUTER_API_BASE:-https://openrouter.ai/api/v1}",
                    "api_key": "${OPENROUTER_API_KEY}"
                },
                # 对应Node_1301843配置 - 使用DeepSeek v3.1
                "character_analysis": {
                    "model": "deepseek/deepseek-chat-v3.1",
                    "temperature": 0.8, 
                    "max_tokens": 8192,
                    "api_base": "${OPENROUTER_API_BASE:-https://openrouter.ai/api/v1}",
                    "api_key": "${OPENROUTER_API_KEY}"
                }
            },
            "media": {
                "image": {
                    "resolution": "1024x768",  # 对应原工作流custom_ratio
                    "quality": "high",
                    "style": "ancient_horror",
                    "ddim_steps": 40,  # 对应原工作流采样步数
                    "model_id": 8,  # 对应原工作流模型ID
                    "primary_provider": "runninghub",
                    "fallback_providers": ["openai", "stability"]
                },
                "audio": {
                    "voice_id": "7468512265134932019",  # 对应原工作流悬疑解说音色
                    "voice_speed": 1.2,  # 对应原工作流语速
                    "voice_volume": 1.0,  # 对应原工作流音量
                    "background_music_volume": 0.3,
                    "opening_sound_duration": 4884897,  # 对应原工作流开场音效时长(微秒)
                    "primary_provider": "azure",
                    "fallback_providers": ["elevenlabs", "openai"]
                }
            },
            "video": {
                "resolution": "720x1280",  # 移动端竖屏视频标准分辨率
                "fps": 30,
                "format": "mp4",
                "enable_subtitles": True,
                "enable_keyframes": True
            },
            "subtitle": {
                "max_line_length": 18,  # 移动端优化配置
                "split_priority": ["。","！","？","，",",","：",":","、","；",";"," "],
                "main_font_size": 7,  # 对应Node_158201配置
                "title_font_size": 40,  # 对应Node_1182713配置
                "main_color": "#FFFFFF",
                "main_border_color": "#000000", 
                "title_color": "#000000",
                "title_border_color": "#ffffff",
                "title_font": "书南体",  # 对应Node_1182713字体
                "title_letter_spacing": 26  # 对应Node_1182713字间距
            },
            "animation": {
                "scene_scale_range": [1.0, 1.5],  # 对应Node_120984场景缩放
                "character_scale_sequence": [2.0, 1.2, 1.0],  # 对应Node_120984主角缩放
                "character_scale_timing": [0, 533333],  # 对应Node_120984时间点(微秒)
                "easing": "linear",
                "in_animation": "轻微放大",  # 对应原工作流图像动画
                "in_animation_duration": 100000  # 对应原工作流动画时长(微秒)
            },
            "cache": {
                "enabled": True,
                "ttl_hours": 24,
                "max_size_mb": 1024
            }
        }
        
        # 创建配置目录
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入默认配置
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Created default config at {self.config_path}")
    
    def _load_language_configs(self):
        """加载多语言配置"""
        self.language_configs = {}
        themes_dir = self.config_dir / "themes"
        
        if not themes_dir.exists():
            self.logger.warning(f"Themes directory not found: {themes_dir}")
            return
        
        for lang_code in self.get_supported_languages():
            theme_file = themes_dir / f"{lang_code}.json"
            if theme_file.exists():
                try:
                    with open(theme_file, 'r', encoding='utf-8') as f:
                        self.language_configs[lang_code] = json.load(f)
                    self.logger.debug(f"Loaded themes for language: {lang_code}")
                except Exception as e:
                    self.logger.error(f"Failed to load themes for {lang_code}: {e}")
            else:
                self.logger.warning(f"Theme file not found for language: {lang_code}")
    
    def _load_api_configs(self):
        """加载API配置并处理环境变量"""
        self.api_configs = {}
        
        # 从环境变量或配置文件加载API密钥
        self.api_keys = {
            'openrouter': os.getenv('OPENROUTER_API_KEY', ''),
            'minimax': os.getenv('MINIMAX_API_KEY', ''),
            'runninghub': os.getenv('RUNNINGHUB_API_KEY', ''),
            'azure': os.getenv('AZURE_API_KEY', ''),
            'elevenlabs': os.getenv('ELEVENLABS_API_KEY', ''),
            'stability': os.getenv('STABILITY_API_KEY', ''),
            'rembg': os.getenv('REMBG_API_KEY', '')
        }
        
        # 检查必需的API密钥
        required_keys = ['openrouter']  # 至少需要OpenRouter用于LLM
        missing_keys = [key for key in required_keys if not self.api_keys[key]]
        
        if missing_keys:
            self.logger.warning(f"Missing API keys: {missing_keys}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持点分隔路径）"""
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        return self.get('general.supported_languages', ['zh'])
    
    def get_llm_config(self, task_type: str) -> ModelConfig:
        """
        获取LLM配置
        
        Args:
            task_type: 任务类型 (script_generation, theme_extraction, etc.)
        """
        config = self.get(f'llm.{task_type}', {})
        
        if not config:
            raise ValueError(f"LLM config not found for task type: {task_type}")
        
        # 处理环境变量替换
        api_base_raw = config.get('api_base', '')
        if '${' in api_base_raw:
            api_base = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
        else:
            api_base = api_base_raw
            
        api_key_raw = config.get('api_key', '')
        if '${' in api_key_raw:
            api_key = os.getenv('OPENROUTER_API_KEY', '')
        else:
            api_key = api_key_raw
        
        return ModelConfig(
            name=config.get('model'),
            temperature=config.get('temperature'),
            max_tokens=config.get('max_tokens'),
            api_base=api_base,
            api_key=api_key
        )
    
    def get_media_config(self) -> MediaConfig:
        """获取媒体配置"""
        media_config = self.get('media', {})
        
        return MediaConfig(
            image_resolution=media_config.get('image', {}).get('resolution', '1024x1024'),
            image_quality=media_config.get('image', {}).get('quality', 'high'),
            voice_speed=media_config.get('audio', {}).get('voice_speed', 1.2),
            voice_volume=media_config.get('audio', {}).get('voice_volume', 1.0)
        )
    
    def get_video_config(self) -> VideoConfig:
        """获取视频配置"""
        video_config = self.get('video', {})
        
        return VideoConfig(
            resolution=video_config.get('resolution', '720x1280'),
            fps=video_config.get('fps', 30),
            format=video_config.get('format', 'mp4')
        )
    
    def get_theme_list(self, language: str = 'zh', category: Optional[str] = None) -> List[str]:
        """
        获取主题列表
        
        Args:
            language: 语言代码
            category: 主题分类（可选）
        """
        lang_config = self.language_configs.get(language, {})
        theme_categories = lang_config.get('theme_categories', {})
        
        if category:
            return theme_categories.get(category, [])
        else:
            # 返回所有分类的主题
            all_themes = []
            for themes in theme_categories.values():
                all_themes.extend(themes)
            return all_themes
    
    def get_theme_categories(self, language: str = 'zh') -> Dict[str, List[str]]:
        """获取主题分类"""
        lang_config = self.language_configs.get(language, {})
        return lang_config.get('theme_categories', {})
    
    def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        return self.get('cache', {
            'enabled': True,
            'ttl_hours': 24,
            'max_size_mb': 1024
        })
    
    def get_api_key(self, service: str) -> str:
        """获取API密钥"""
        return self.api_keys.get(service, '')
    
    def get_logger(self, logger_name: str):
        """获取logger实例 - 兼容性方法"""
        return logging.getLogger(logger_name)
    
    def validate_config(self) -> List[str]:
        """验证配置完整性"""
        errors = []
        
        # 检查必需的API密钥
        if not self.get_api_key('openrouter'):
            errors.append("Missing OPENROUTER_API_KEY environment variable")
        
        # 检查多语言支持
        supported_langs = self.get_supported_languages()
        for lang in supported_langs:
            if lang not in self.language_configs:
                errors.append(f"Missing language config for: {lang}")
        
        # 检查输出目录
        output_dir = Path(self.get('general.output_dir', 'output'))
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create output directory: {e}")
        
        return errors
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ConfigManager(languages={self.get_supported_languages()}, " \
               f"output_dir={self.get('general.output_dir')})"