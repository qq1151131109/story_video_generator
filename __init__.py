"""
历史故事生成器 - 基于Coze工作流的Python实现

完整的多语言历史故事批量生产系统，支持：
- 多语言文案生成（中文、英语、西班牙语）
- 智能场景分割和角色分析
- 多提供商图像生成（RunningHub、OpenAI、Stability）
- 多提供商音频合成（Azure TTS、ElevenLabs、OpenAI）
- 视频合成和字幕处理
- 企业级缓存和批处理

基于原Coze工作流的28个节点配置，忠实还原所有参数和处理逻辑。
"""

__version__ = "1.0.0"
__author__ = "历史故事生成系统"

# 导入主要组件
from .core.config_manager import ConfigManager
from .utils.file_manager import FileManager
from .utils.logger import setup_logging

# 导入内容生成组件
from .content.content_pipeline import ContentPipeline, ContentGenerationRequest
from .content.script_generator import ScriptGenerator, ScriptGenerationRequest
from .content.scene_splitter import SceneSplitter, SceneSplitRequest
from .content.character_analyzer import CharacterAnalyzer, CharacterAnalysisRequest

# 导入媒体生成组件
from .media.media_pipeline import MediaPipeline, MediaGenerationRequest
from .media.image_generator import ImageGenerator, ImageGenerationRequest
from .media.audio_generator import AudioGenerator, AudioGenerationRequest

# 导入视频处理组件
from .video.subtitle_processor import SubtitleProcessor, SubtitleProcessorRequest
from .video.enhanced_animation_processor import EnhancedAnimationProcessor

__all__ = [
    # 核心组件
    'ConfigManager',
    'FileManager',
    'setup_logging',
    
    # 内容生成
    'ContentPipeline',
    'ContentGenerationRequest',
    'ScriptGenerator',
    'ScriptGenerationRequest',
    'SceneSplitter',
    'SceneSplitRequest',
    'CharacterAnalyzer',
    'CharacterAnalysisRequest',
    
    # 媒体生成
    'MediaPipeline',
    'MediaGenerationRequest',
    'ImageGenerator',
    'ImageGenerationRequest',
    'AudioGenerator',
    'AudioGenerationRequest',
    
    # 视频处理
    'SubtitleProcessor',
    'SubtitleProcessorRequest',
    'EnhancedAnimationProcessor'
]