# 历史故事生成器

基于原Coze工作流的完整Python实现，支持多语言历史故事的批量生产。经过大幅优化，系统更加稳定高效。

## ✨ 特性

- 🌍 **多语言支持** - 中文、英语、西班牙语，完整的国际化框架
- 🤖 **智能内容生成** - 基于DeepSeek-V3的文案、场景分割、角色分析  
- 🎨 **最新图像生成** - Gemini 2.5 Flash、RunningHub、DALL-E等多提供商支持
- 🔊 **高质量音频** - MiniMax中文优质语音、Azure TTS等多提供商TTS
- 🎬 **视频处理** - WhisperX精确字幕对齐、增强动画效果、完整合成流水线
- 🚀 **批量处理** - 异步并发，支持大规模生产，完整的批处理报告
- 💾 **智能缓存** - 避免重复API调用，大幅节省成本
- 🎯 **服务化架构** - 清晰的StoryVideoService，便于维护和扩展
- 🔍 **质量保证** - 移除fallback机制，确保输出质量
- 📊 **完整监控** - 分模块日志、性能报告、错误追踪

## 🏗️ 系统架构

```
历史故事生成器/
├── core/                    # 核心框架
│   ├── config_manager.py    # 配置管理（基于原工作流参数）
│   └── cache_manager.py     # 缓存系统（内存+磁盘）
├── services/                # 服务层（新增）
│   └── story_video_service.py # 故事视频生成服务（服务化架构）
├── content/                 # 内容生成模块
│   ├── script_generator.py  # 文案生成（DeepSeek-V3）
│   ├── scene_splitter.py    # 场景分割（8个3秒场景）
│   ├── character_analyzer.py # 角色分析
│   ├── image_prompt_generator.py # 图像提示词生成
│   ├── theme_extractor.py   # 主题提取器
│   └── content_pipeline.py  # 内容生成流水线
├── media/                   # 媒体生成模块
│   ├── image_generator.py   # 图像生成（Gemini 2.5/RunningHub/DALL-E/Stability）
│   ├── audio_generator.py   # 音频合成（MiniMax/Azure TTS/ElevenLabs/OpenAI）
│   ├── character_image_generator.py # 角色图像生成
│   ├── cutout_processor.py  # 图像抠图处理
│   ├── whisper_alignment.py # WhisperX字幕对齐
│   └── media_pipeline.py    # 媒体生成流水线
├── video/                   # 视频处理模块（大幅优化）
│   ├── subtitle_processor.py # 字幕处理（智能分割+时间同步）
│   ├── subtitle_engine.py   # 字幕渲染引擎
│   ├── subtitle_alignment_manager.py # 字幕对齐管理器
│   ├── enhanced_animation_processor.py # 增强动画处理器
│   ├── dual_image_compositor.py # 双图像合成器
│   └── video_composer.py    # 视频合成器
├── utils/                   # 工具模块
│   ├── file_manager.py      # 文件管理
│   ├── logger.py           # 日志系统
│   ├── i18n.py             # 国际化支持
│   ├── llm_client_manager.py # LLM客户端管理
│   └── subtitle_utils.py   # 字幕工具类
├── tools/                   # 工具脚本
│   ├── configure_apis.py    # API配置工具
│   ├── load_env.py         # 环境变量加载
│   ├── optimize.py         # 性能优化工具
│   └── validate_setup.py   # 环境验证工具
├── tests/                   # 测试模块
│   ├── end_to_end_test.py  # 端到端测试
│   ├── quick_video_test.py # 快速视频测试
│   └── verify_final_video.py # 视频验证测试
├── docs/                    # 文档目录
│   ├── FALLBACK_REMOVAL_SUMMARY.md # Fallback机制移除总结
│   ├── WORKFLOW_DIAGRAM.md  # 工作流程图
│   └── *.md                # 其他技术文档
├── config/                  # 配置文件
│   ├── settings.json        # 主配置
│   ├── themes/             # 多语言主题库
│   └── prompts/            # 多语言提示词模板
└── reference/               # 参考资料
    ├── analysis/           # 工作流分析文档
    ├── Flux文生图_api.json  # Flux API参考
    └── 沉浸式历史故事*.txt   # 原工作流文件
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- FFmpeg (用于视频处理)
- GPU (可选，用于WhisperX加速)

### 2. 安装指南

#### 基础安装
```bash
pip install -r requirements.txt
```

#### WhisperX功能（可选）
WhisperX提供word-level精确字幕对齐，大幅提升字幕质量：
```bash
# 安装WhisperX及其依赖
pip install whisperx torch torchaudio transformers librosa soundfile phonemizer

# GPU支持（推荐）
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

#### 环境验证
```bash
# 验证安装和配置
python tools/validate_setup.py

# API配置向导
python tools/configure_apis.py
```

### 3. 环境变量配置

创建 `.env` 文件并配置API密钥：

```env
# LLM API (必需) - 用于内容生成
OPENROUTER_API_KEY=your_openrouter_api_key

# 图像生成 API (至少配置一个)
RUNNINGHUB_API_KEY=your_runninghub_api_key    # 推荐：高质量中文支持
GEMINI_API_KEY=your_gemini_api_key            # Gemini 2.5 Flash
OPENAI_API_KEY=your_openai_api_key            # DALL-E支持
STABILITY_API_KEY=your_stability_api_key      # Stable Diffusion

# 音频生成 API (至少配置一个)
MINIMAX_API_KEY=your_minimax_api_key          # 推荐：高质量中文语音
AZURE_API_KEY=your_azure_api_key              # Azure TTS
ELEVENLABS_API_KEY=your_elevenlabs_api_key    # 高质量英语语音
OPENAI_API_KEY=your_openai_api_key            # OpenAI TTS
```

### 4. 运行示例

#### 基础用法
```bash
# 生成单个故事
python main.py --theme "秦始皇统一六国的传奇故事" --language zh

# 批量生成故事
python main.py --batch themes.txt --language zh --concurrent 2

# 测试模式（快速验证）
python main.py --test

# 交互式模式
python main.py
```

#### 高级用法
```bash
# 指定输出目录
python main.py --theme "汉武帝北击匈奴" --output-dir custom_output

# 启用详细日志
python main.py --theme "唐太宗贞观之治" --verbose

# 使用服务化架构的演示
python demos/full_video_demo.py

# 端到端测试
python tests/end_to_end_test.py
```

## 🎬 工作流程图

详细的系统工作流程请查看：[WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md)

包含完整的：
- 🎯 系统架构总览
- 📝 内容生成流水线详解  
- 🎨 媒体生成流程图
- 🎞️ 视频处理时序图
- 🔄 API容错和缓存机制
- 📊 性能监控流程

## 📖 使用指南

### 基础用法 - 服务化架构

```python
import asyncio
from services.story_video_service import StoryVideoService

async def main():
    # 初始化服务
    service = StoryVideoService()
    
    # 生成完整的历史故事视频
    result = await service.generate_story_video(
        theme="唐太宗贞观之治的盛世传奇",
        language="zh"
    )
    
    print(f"视频生成完成: {result['video_path']}")
    print(f"生成时间: {result['generation_time']:.2f}秒")

# 运行
asyncio.run(main())
```

### 分步骤控制 - 内容+媒体分离

```python
from services.story_video_service import StoryVideoService

async def generate_with_control():
    service = StoryVideoService()
    
    # 第一步：生成内容
    content_result = await service.generate_content(
        theme="秦始皇统一六国的传奇故事",
        language="zh"
    )
    
    # 查看生成的场景
    for i, scene in enumerate(content_result.scenes.scenes):
        print(f"场景 {i+1}: {scene.description}")
    
    # 第二步：生成媒体
    media_result = await service.generate_media(
        content_result.scenes.scenes,
        content_result.characters.characters,
        language="zh"
    )
    
    # 第三步：合成视频
    video_path = await service.compose_video(
        scenes=content_result.scenes.scenes,
        audio_files=media_result.audio_files,
        image_files=media_result.image_files,
        language="zh"
    )
    
    return video_path

# 运行
video_path = asyncio.run(generate_with_control())
print(f"视频路径: {video_path}")
```

### 批量处理示例

```python
import asyncio
from services.story_video_service import StoryVideoService

async def batch_generate():
    service = StoryVideoService()
    
    themes = [
        "汉武帝北击匈奴的英勇传说",
        "唐玄宗开元盛世的辉煌",
        "明成祖朱棣的永乐大典"
    ]
    
    results = []
    for theme in themes:
        try:
            result = await service.generate_story_video(
                theme=theme,
                language="zh"
            )
            results.append(result)
            print(f"✅ 完成: {theme}")
        except Exception as e:
            print(f"❌ 失败: {theme} - {e}")
    
    return results

# 批量生成
results = asyncio.run(batch_generate())
print(f"成功生成 {len(results)} 个视频")
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
- **RunningHub** (推荐) - 高质量中文支持，稳定快速
- **Gemini 2.5 Flash** - Google最新文生图模型，质量优秀
- **DALL-E 3** - OpenAI图像生成，创意性强
- **Stability AI** - Stable Diffusion，开源稳定

**音频合成:**
- **MiniMax TTS** (推荐) - 高质量中文语音合成
- **Azure TTS** - 专业级语音，多语言支持
- **ElevenLabs** - 高质量英语语音，情感丰富
- **OpenAI TTS** - 自然流畅，多语言支持

**字幕对齐:**
- **WhisperX** (推荐) - Word-level精确对齐，质量最高
- 传统的TTS时间戳对齐已移除，确保质量

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
   **解决**：运行 `python tools/configure_apis.py` 配置API密钥

2. **WhisperX安装问题**
   ```
   ModuleNotFoundError: No module named 'whisperx'
   ```
   **解决**：按照安装指南安装WhisperX依赖

3. **字幕对齐失败**
   ```
   WhisperX alignment failed or not available
   ```
   **解决**：检查音频文件格式，确保WhisperX正确安装

4. **图像生成失败**
   ```
   All image providers failed
   ```
   **解决**：检查至少配置一个图像生成API密钥

5. **视频合成错误**
   ```
   FFmpeg not found
   ```
   **解决**：安装FFmpeg并确保在PATH中

### 调试工具

#### 环境验证
```bash
# 全面验证系统配置
python tools/validate_setup.py

# 快速测试
python tests/quick_video_test.py
```

#### 详细日志
```python
from utils.logger import setup_logging

# 启用详细日志
logger = setup_logging(log_level="DEBUG")

# 查看日志文件
# output/logs/story_generator.log
# output/logs/errors.log
```

### 性能优化

#### GPU加速
```bash
# 安装CUDA版本的PyTorch（用于WhisperX）
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

#### 并发设置
```json
{
  "general": {
    "max_concurrent_tasks": 2  // 根据系统资源调整
  }
}
```

## 🤝 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📈 最新更新

### v2.0 重大优化 (2024年8月)
- ✅ **服务化架构**: 引入`StoryVideoService`，提供清晰的API接口
- ✅ **质量保证**: 移除fallback机制，确保输出质量
- ✅ **WhisperX集成**: Word-level精确字幕对齐，大幅提升字幕质量
- ✅ **增强视频处理**: 优化字幕引擎、动画处理、视频合成
- ✅ **完善工具链**: 新增验证工具、配置向导、性能优化脚本
- ✅ **文档完善**: 详细的技术文档和故障排除指南

### 主要技术改进
- 字幕对齐从基础TTS时间戳升级到WhisperX精确对齐
- 视频合成流水线全面优化，支持双图像合成
- 增强的动画处理器，提供更丰富的视觉效果
- 服务化架构设计，便于维护和扩展

## 🙏 致谢

- 基于原Coze工作流设计思路
- 使用DeepSeek-V3作为核心LLM引擎
- WhisperX提供精确字幕对齐技术
- 感谢RunningHub、MiniMax等优质API提供商
- 特别感谢开源社区的技术支持

---

**📋 系统要求**: 本系统需要多个API服务支持，建议先运行 `python tools/validate_setup.py` 验证环境配置。

**🎯 推荐配置**: 配置RunningHub（图像）+ MiniMax（音频）+ WhisperX（字幕）可获得最佳效果。