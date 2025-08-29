# 历史故事生成器

基于原Coze工作流的完整Python实现，支持多语言历史故事的批量生产。

## ✨ 特性

- 🌍 **多语言支持** - 中文、英语、西班牙语
- 🤖 **智能内容生成** - 基于DeepSeek-V3的文案、场景分割、角色分析  
- 🎨 **多媒体生成** - 图像生成、音频合成、视频处理
- 🚀 **批量处理** - 异步并发，支持大规模生产
- 💾 **智能缓存** - 避免重复API调用，大幅节省成本
- 🔄 **多提供商容错** - 主备提供商自动切换
- 📊 **完整日志** - 分模块日志，便于监控调试

## 🏗️ 系统架构

```
历史故事生成器/
├── core/                    # 核心框架
│   ├── config_manager.py    # 配置管理（基于原工作流参数）
│   └── cache_manager.py     # 缓存系统（内存+磁盘）
├── content/                 # 内容生成模块
│   ├── script_generator.py  # 文案生成（DeepSeek-V3）
│   ├── scene_splitter.py    # 场景分割（8个3秒场景）
│   ├── character_analyzer.py # 角色分析
│   └── content_pipeline.py  # 内容生成流水线
├── media/                   # 媒体生成模块
│   ├── image_generator.py   # 图像生成（RunningHub/OpenAI/Stability）
│   ├── audio_generator.py   # 音频合成（Azure TTS/ElevenLabs/OpenAI）
│   └── media_pipeline.py    # 媒体生成流水线
├── video/                   # 视频处理模块
│   ├── subtitle_processor.py # 字幕处理（智能分割+时间同步）
│   └── animation_processor.py # 动画效果（对应原工作流动画配置）
├── utils/                   # 工具模块
│   ├── file_manager.py      # 文件管理
│   └── logger.py           # 日志系统
├── config/                  # 配置文件
│   ├── settings.json        # 主配置
│   ├── themes/             # 多语言主题库
│   └── prompts/            # 多语言提示词模板
└── reference/               # 参考资料
    ├── analysis/           # 工作流分析文档
    ├── ContentCreationPlatform/ # 原平台代码
    └── 沉浸式历史故事*.txt   # 原工作流文件
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- FFmpeg (用于视频处理)

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 环境变量配置

创建 `.env` 文件并配置API密钥：

```env
# LLM API (必需)
OPENROUTER_API_KEY=your_openrouter_api_key

# 图像生成 API (可选，支持多个)
RUNNINGHUB_API_KEY=your_runninghub_api_key
STABILITY_API_KEY=your_stability_api_key

# 音频生成 API (可选，支持多个)
AZURE_API_KEY=your_azure_api_key  
ELEVENLABS_API_KEY=your_elevenlabs_api_key
```

### 4. 运行示例

```bash
# 生成单个故事
python main.py --theme "秦始皇统一六国的传奇故事" --language zh

# 批量生成故事
python main.py --batch themes.txt --language zh --concurrent 2

# 测试模式
python main.py --test

# 交互式模式
python main.py
```

## 📖 使用指南

### 基础用法

```python
import asyncio
from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from content.content_pipeline import ContentPipeline, ContentGenerationRequest

# 初始化组件
config = ConfigManager()
cache = CacheManager()
files = FileManager()

# 创建内容生成流水线
content_pipeline = ContentPipeline(config, cache, files)

# 生成内容
request = ContentGenerationRequest(
    theme="唐太宗贞观之治的盛世传奇",
    language="zh",
    style="horror",
    target_length=800
)

result = await content_pipeline.generate_content_async(request)
print(f"Generated: {result.script.title}")
```

### 高级用法 - 完整流水线

```python
from content.content_pipeline import ContentPipeline
from media.media_pipeline import MediaPipeline

# 内容生成
content_result = await content_pipeline.generate_content_async(content_request)

# 媒体生成  
media_request = MediaGenerationRequest(
    scenes=content_result.scenes.scenes,
    characters=content_result.characters.characters,
    language="zh"
)
media_result = await media_pipeline.generate_media_async(media_request)

# 保存所有文件
content_files = content_pipeline.save_complete_content(content_result)
media_files = media_pipeline.save_media_files(media_result)
```

## ⚙️ 配置说明

### 主配置文件 (`config/settings.json`)

```json
{
  "general": {
    "output_dir": "output",
    "supported_languages": ["zh", "en", "es"],
    "max_concurrent_tasks": 3
  },
  "llm": {
    "script_generation": {
      "model": "deepseek-v3", 
      "temperature": 0.8,
      "max_tokens": 1024
    }
  },
  "media": {
    "image": {
      "primary_provider": "runninghub",
      "resolution": "1024x768",
      "quality": "high"
    },
    "audio": {
      "primary_provider": "azure",
      "voice_speed": 1.2,
      "voice_volume": 1.0
    }
  }
}
```

### 支持的提供商

**图像生成:**
- RunningHub (主要) - 对应原工作流配置
- OpenAI DALL-E (备用)
- Stability AI (备用)

**音频合成:**
- Azure TTS (主要) - 悬疑解说音色
- ElevenLabs (备用) - 高质量语音
- OpenAI TTS (备用)

## 🔧 原工作流对应关系

| 原工作流节点 | 对应实现 | 配置参数 |
|------------|---------|---------|
| Node_121343 | ScriptGenerator | DeepSeek-V3, temp=0.8, max_tokens=1024 |
| Node_1165778 | SceneSplitter | 8个场景，每个3秒 |
| Node_1301843 | CharacterAnalyzer | 角色分析和图像提示词生成 |
| Node_120984 | AnimationProcessor | 缩放序列 [2.0, 1.2, 1.0] |
| 字幕配置 | SubtitleProcessor | MAX_LINE_LENGTH=25，分割优先级 |

## 📊 成本优化

- **智能缓存** - 相同请求自动使用缓存结果
- **批量处理** - 并发生成，提高效率
- **多提供商** - 成本和质量平衡选择
- **成本估算** - 生成前预估API调用成本

## 🐛 故障排除

### 常见问题

1. **API密钥错误**
   ```
   Missing OPENROUTER_API_KEY environment variable
   ```
   解决：检查 `.env` 文件中的API密钥配置

2. **模型配置错误**
   ```
   LLM config not found for task type: script_generation
   ```
   解决：检查 `config/settings.json` 中的模型配置

3. **文件权限错误**
   ```
   Cannot create output directory
   ```
   解决：确保有输出目录的写权限

### 调试模式

启用详细日志：

```python
from utils.logger import setup_logging

logger = setup_logging(log_level="DEBUG")
```

## 🤝 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- 基于原Coze工作流设计
- 使用DeepSeek-V3作为核心LLM
- 感谢所有媒体生成API提供商

---

**注意**: 本系统需要多个API服务支持，请确保有足够的API配额。建议先在测试模式下验证系统功能。