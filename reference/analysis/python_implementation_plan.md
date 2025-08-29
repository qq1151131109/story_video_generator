# 历史故事批量生产 - Python本地实现计划

## 项目概述

基于对Coze工作流"沉浸式历史故事"的深度分析，以及ContentCreationPlatform现有实现的理解，制定一个本地Python实现方案，用于批量生产历史故事短视频。

## 实现策略

### 核心设计理念
- **简化部署**：单文件独立运行，最小化依赖
- **批量优化**：针对批量生产场景优化，支持并发处理
- **高度可配置**：JSON配置文件，灵活调整参数
- **成本控制**：优化API调用次数，支持本地缓存
- **质量稳定**：固化模板和提示词，确保输出质量

## 技术架构

### 系统架构图

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   主题配置      │    │   批量处理器     │    │   输出管理器     │
│  - 主题列表     │───▶│  - 任务调度     │───▶│  - 文件组织     │
│  - 参数设置     │    │  - 并发控制     │    │  - 格式转换     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   内容生成器     │    │   媒体生成器     │    │   视频合成器     │
│  - 文案生成     │    │  - 图像生成     │    │  - 多轨道合成   │
│  - 分镜分割     │    │  - 语音合成     │    │  - 字幕叠加     │
│  - 提示词优化   │    │  - 音效处理     │    │  - 关键帧动画   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 模块划分

#### 1. 核心引擎 (`core/`)
```python
story_engine.py          # 主引擎，协调所有模块
batch_processor.py       # 批量处理器，任务调度和并发控制
config_manager.py        # 配置管理器，参数加载和验证
cache_manager.py         # 缓存管理器，避免重复计算
```

#### 2. 内容生成 (`content/`)
```python
script_generator.py      # 文案生成器（基于现有实现）
scene_splitter.py        # 分镜分割器（规则+AI混合）
prompt_optimizer.py      # 提示词优化器（本地化实现）
theme_extractor.py       # 主题词提取器（2字标题生成）
```

#### 3. 媒体生成 (`media/`)
```python
image_generator.py       # 图像生成器（集成多个API）
voice_synthesizer.py     # 语音合成器（TTS服务集成）
audio_processor.py       # 音频处理器（音效、背景音乐）
character_generator.py   # 主角图像生成器（含抠图）
```

#### 4. 视频合成 (`video/`)
```python
video_composer.py        # 视频合成器（FFmpeg封装）
subtitle_renderer.py     # 字幕渲染器（多层字幕系统）
keyframe_animator.py     # 关键帧动画器（缩放效果）
audio_mixer.py           # 音频混音器（多轨道混音）
```

#### 5. 工具库 (`utils/`)
```python
api_clients.py           # API客户端集成
file_manager.py          # 文件管理工具
format_converter.py      # 格式转换工具
progress_tracker.py      # 进度追踪器
```

## 详细实现方案

### 1. 项目结构

```
story_generator/
├── config/
│   ├── settings.json           # 主配置文件
│   ├── themes.json            # 主题库配置
│   ├── prompts.json           # 提示词模板
│   └── api_config.json        # API配置
├── core/
│   ├── __init__.py
│   ├── story_engine.py        # 主引擎
│   ├── batch_processor.py     # 批量处理器
│   ├── config_manager.py      # 配置管理
│   └── cache_manager.py       # 缓存管理
├── content/
│   ├── __init__.py
│   ├── script_generator.py    # 文案生成
│   ├── scene_splitter.py      # 分镜分割
│   ├── prompt_optimizer.py    # 提示词优化
│   └── theme_extractor.py     # 主题提取
├── media/
│   ├── __init__.py
│   ├── image_generator.py     # 图像生成
│   ├── voice_synthesizer.py   # 语音合成
│   ├── audio_processor.py     # 音频处理
│   └── character_generator.py # 主角生成
├── video/
│   ├── __init__.py
│   ├── video_composer.py      # 视频合成
│   ├── subtitle_renderer.py   # 字幕渲染
│   ├── keyframe_animator.py   # 关键帧动画
│   └── audio_mixer.py         # 音频混音
├── utils/
│   ├── __init__.py
│   ├── api_clients.py         # API客户端
│   ├── file_manager.py        # 文件管理
│   ├── format_converter.py    # 格式转换
│   └── progress_tracker.py    # 进度追踪
├── output/                    # 输出目录
│   ├── videos/               # 最终视频
│   ├── assets/               # 素材文件
│   │   ├── images/          # 生成的图片
│   │   ├── audios/          # 音频文件
│   │   └── temp/            # 临时文件
│   └── logs/                 # 日志文件
├── requirements.txt
├── main.py                   # 入口文件
└── README.md
```

### 2. 核心配置文件

#### `config/settings.json`
```json
{
  "general": {
    "output_dir": "output",
    "temp_dir": "output/temp",
    "log_level": "INFO",
    "max_concurrent_tasks": 3
  },
  "content": {
    "script_max_length": 1024,
    "scene_split_strategy": "ai_with_fallback",
    "max_scenes_per_story": 8
  },
  "media": {
    "image": {
      "resolution": "1024x768",
      "quality": "high",
      "style": "ancient_horror"
    },
    "audio": {
      "voice_speed": 1.2,
      "voice_volume": 1.0,
      "background_music_volume": 0.3
    }
  },
  "video": {
    "resolution": "1920x1080",
    "fps": 30,
    "format": "mp4",
    "enable_subtitles": true,
    "enable_keyframes": true
  },
  "cache": {
    "enabled": true,
    "ttl_hours": 24,
    "max_size_mb": 1024
  }
}
```

#### `config/themes.json`
```json
{
  "theme_categories": {
    "战争历史": [
      "三国演义赤壁之战",
      "秦始皇统一六国",
      "项羽乌江自刎",
      "汉武帝抗击匈奴"
    ],
    "宫廷秘史": [
      "武则天登基称帝",
      "杨贵妃安史之乱",
      "慈禧太后垂帘听政",
      "康熙平定三藩"
    ],
    "民间传说": [
      "包青天审案传说",
      "济公活佛传说",
      "白蛇传说",
      "梁山伯祝英台"
    ]
  },
  "batch_config": {
    "themes_per_batch": 5,
    "concurrent_processing": 3
  }
}
```

### 3. 主引擎实现

#### `core/story_engine.py`
```python
import asyncio
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path

from .config_manager import ConfigManager
from .cache_manager import CacheManager
from .batch_processor import BatchProcessor
from ..content.script_generator import ScriptGenerator
from ..content.scene_splitter import SceneSplitter
from ..media.image_generator import ImageGenerator
from ..media.voice_synthesizer import VoiceSynthesizer
from ..video.video_composer import VideoComposer

@dataclass
class StoryRequest:
    """故事生成请求"""
    theme: str
    title: str
    output_name: str
    custom_params: Optional[Dict] = None

class StoryEngine:
    """
    历史故事生成引擎
    
    完整实现Coze工作流的本地化版本
    支持批量处理和并发控制
    """
    
    def __init__(self, config_path: str = "config/settings.json"):
        self.config = ConfigManager(config_path)
        self.cache = CacheManager(self.config.get_cache_config())
        self.batch_processor = BatchProcessor(self.config)
        
        # 初始化各个生成器
        self.script_generator = ScriptGenerator(self.config)
        self.scene_splitter = SceneSplitter(self.config)
        self.image_generator = ImageGenerator(self.config)
        self.voice_synthesizer = VoiceSynthesizer(self.config)
        self.video_composer = VideoComposer(self.config)
        
        self.logger = logging.getLogger(__name__)
    
    async def generate_story(self, request: StoryRequest) -> Dict:
        """
        生成单个故事视频
        
        Args:
            request: 故事生成请求
            
        Returns:
            生成结果字典
        """
        try:
            self.logger.info(f"开始生成故事: {request.theme}")
            
            # 步骤1: 生成文案
            script_result = await self.script_generator.generate(
                theme=request.theme,
                cache_key=f"script_{request.theme}"
            )
            
            # 步骤2: 分镜分割
            scenes = await self.scene_splitter.split_story(
                content=script_result["script"],
                cache_key=f"scenes_{request.theme}"
            )
            
            # 步骤3: 批量生成媒体
            media_results = await self.batch_processor.process_scenes(
                scenes=scenes,
                generators={
                    "image": self.image_generator,
                    "voice": self.voice_synthesizer
                }
            )
            
            # 步骤4: 合成视频
            video_path = await self.video_composer.compose(
                scenes=media_results,
                title=script_result.get("title", request.theme),
                output_name=request.output_name
            )
            
            return {
                "status": "success",
                "theme": request.theme,
                "video_path": video_path,
                "scenes_count": len(scenes),
                "duration": sum(s.get("duration", 0) for s in media_results)
            }
            
        except Exception as e:
            self.logger.error(f"生成故事失败 {request.theme}: {str(e)}")
            return {
                "status": "failed",
                "theme": request.theme,
                "error": str(e)
            }
    
    async def batch_generate(self, themes: List[str], 
                           output_prefix: str = "story") -> List[Dict]:
        """
        批量生成故事视频
        
        Args:
            themes: 主题列表
            output_prefix: 输出文件名前缀
            
        Returns:
            批量生成结果列表
        """
        requests = [
            StoryRequest(
                theme=theme,
                title=theme,
                output_name=f"{output_prefix}_{i:03d}_{theme[:10]}"
            )
            for i, theme in enumerate(themes, 1)
        ]
        
        return await self.batch_processor.process_batch(
            requests=requests,
            processor=self.generate_story
        )
```

### 4. API集成策略

基于平台现有的实现，我们需要集成以下API服务：

#### 图像生成 - 多API支持
```python
# media/image_generator.py
class ImageGenerator:
    def __init__(self, config):
        self.providers = {
            "runninghub": RunningHubClient(config.get_api_key("runninghub")),
            "openai": OpenAIClient(config.get_api_key("openai")),
            "stability": StabilityClient(config.get_api_key("stability"))
        }
        self.primary_provider = config.get("image.primary_provider", "runninghub")
        self.rembg_client = RemBGClient(config.get_api_key("rembg"))
    
    async def generate_image(self, prompt: str, style: str = "ancient_horror") -> str:
        """生成图像，支持失败切换"""
        for provider_name in [self.primary_provider] + list(self.providers.keys()):
            if provider_name == self.primary_provider:
                continue
            try:
                provider = self.providers[provider_name]
                return await provider.generate(prompt, style)
            except Exception as e:
                self.logger.warning(f"Provider {provider_name} failed: {e}")
        raise Exception("All image providers failed")
    
    async def generate_character_image(self, story_content: str) -> Dict[str, str]:
        """生成主角图像并抠图"""
        # 基于故事内容分析主角特征
        character_prompt = self._analyze_character(story_content)
        
        # 生成图像
        image_url = await self.generate_image(character_prompt)
        
        # 抠图处理
        nobg_url = await self.rembg_client.remove_background(image_url)
        
        return {
            "original": image_url,
            "no_background": nobg_url
        }
```

#### 语音合成 - 多TTS支持
```python
# media/voice_synthesizer.py
class VoiceSynthesizer:
    def __init__(self, config):
        self.providers = {
            "azure": AzureTTSClient(config.get_api_key("azure")),
            "openai": OpenAITTSClient(config.get_api_key("openai")),
            "elevenlabs": ElevenLabsClient(config.get_api_key("elevenlabs"))
        }
        self.voice_mapping = {
            "suspense": "7468512265134932019",  # 悬疑解说音色ID
            "historical": "historical_narrator",
            "dramatic": "dramatic_voice"
        }
```

### 5. 批量处理优化

#### 并发控制和错误恢复
```python
# core/batch_processor.py
class BatchProcessor:
    def __init__(self, config):
        self.max_concurrent = config.get("general.max_concurrent_tasks", 3)
        self.retry_times = config.get("general.retry_times", 2)
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
    
    async def process_batch(self, requests: List[StoryRequest], 
                          processor: callable) -> List[Dict]:
        """批量处理请求，支持并发控制和错误恢复"""
        
        async def process_with_semaphore(request):
            async with self.semaphore:
                for attempt in range(self.retry_times + 1):
                    try:
                        return await processor(request)
                    except Exception as e:
                        if attempt == self.retry_times:
                            return {"status": "failed", "theme": request.theme, "error": str(e)}
                        await asyncio.sleep(2 ** attempt)  # 指数退避
        
        # 并发执行所有任务
        tasks = [process_with_semaphore(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
        self.logger.info(f"批量处理完成: {success_count}/{len(requests)} 成功")
        
        return results
```

### 6. 输出格式和组织

#### 文件组织结构
```
output/
├── batch_20250829_143022/          # 批次目录（时间戳）
│   ├── videos/                     # 最终视频
│   │   ├── story_001_三国演义赤壁之战.mp4
│   │   ├── story_002_秦始皇统一六国.mp4
│   │   └── ...
│   ├── assets/                     # 素材资源
│   │   ├── scripts/               # 文案文件
│   │   ├── images/                # 生成图片
│   │   ├── audios/                # 音频文件
│   │   └── characters/            # 主角图像
│   ├── metadata/                   # 元数据
│   │   ├── batch_config.json      # 批次配置
│   │   ├── generation_log.json    # 生成日志
│   │   └── statistics.json        # 统计数据
│   └── failed/                     # 失败任务
│       └── retry_queue.json       # 重试队列
```

### 7. 使用方式

#### 命令行接口
```bash
# 单个主题生成
python main.py --theme "三国演义赤壁之战" --output "redcliff_battle"

# 批量生成（从主题文件）
python main.py --batch --themes config/themes.json --category "战争历史"

# 自定义配置批量生成
python main.py --batch --themes themes.txt --config config/custom_settings.json

# 重试失败的任务
python main.py --retry --batch-id batch_20250829_143022
```

#### Python API接口
```python
from story_generator.core.story_engine import StoryEngine, StoryRequest

# 初始化引擎
engine = StoryEngine("config/settings.json")

# 单个生成
request = StoryRequest(
    theme="三国演义赤壁之战",
    title="赤壁之战",
    output_name="redcliff_battle"
)
result = await engine.generate_story(request)

# 批量生成
themes = ["三国演义赤壁之战", "秦始皇统一六国", "项羽乌江自刎"]
results = await engine.batch_generate(themes, "history_stories")
```

## 实施计划

### 阶段一：核心框架搭建（1-2天）
1. ✅ 项目结构搭建
2. ✅ 配置管理系统实现
3. ✅ 日志和缓存系统
4. ✅ 基础工具类开发

### 阶段二：内容生成模块（2-3天）
1. 文案生成器实现（复用平台代码）
2. 分镜分割器开发（规则+AI混合）
3. 提示词优化器本地化
4. 主题提取器实现

### 阶段三：媒体生成模块（3-4天）
1. 图像生成器集成（多API支持）
2. 语音合成器开发
3. 音效处理系统
4. 主角图像生成和抠图

### 阶段四：视频合成模块（2-3天）
1. FFmpeg封装和视频合成
2. 字幕渲染系统
3. 关键帧动画实现
4. 多轨道音频混音

### 阶段五：批量处理和优化（1-2天）
1. 批量处理器完善
2. 并发控制和错误恢复
3. 进度追踪和统计
4. 性能优化和测试

### 阶段六：测试和部署（1天）
1. 端到端测试
2. 文档编写
3. 部署脚本准备
4. 使用指南完善

## 技术要求

### 环境依赖
```bash
# Python 3.10+
# 必需的系统软件
brew install ffmpeg          # macOS
apt-get install ffmpeg       # Ubuntu

# Python包依赖
pip install -r requirements.txt
```

### 主要依赖包
```
# requirements.txt
asyncio>=3.4.3
aiohttp>=3.8.0
aiofiles>=0.8.0
Pillow>=9.0.0
ffmpeg-python>=0.2.0
pydub>=0.25.1
openai>=1.0.0
requests>=2.28.0
python-dotenv>=0.19.0
loguru>=0.6.0
pydantic>=2.0.0
```

## 预期效果

### 性能指标
- **批量处理能力**: 支持同时处理3-5个故事
- **单故事生成时间**: 60-90秒（含媒体生成时间）
- **成功率**: 目标95%以上（含重试机制）
- **资源消耗**: 内存使用 < 2GB

### 输出质量
- **视频时长**: 2-5分钟/故事
- **分辨率**: 1920x1080，30fps
- **音频质量**: 44.1kHz，立体声
- **字幕同步**: 精确到100ms级别

### 成本控制
- **API调用优化**: 通过缓存减少重复调用
- **失败重试**: 智能重试避免资源浪费
- **并发限制**: 合理控制并发避免API限流

这个实现方案充分考虑了批量生产的需求，既保持了原Coze工作流的完整功能，又针对本地部署和批量处理进行了优化。