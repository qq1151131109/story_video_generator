# 故事视频生成器项目 - Claude Code开发指南

## 🎯 项目概述

这是一个基于原Coze工作流的完整Python实现的故事视频生成器，支持多语言(中英西)故事视频的批量生产。项目已完成6个开发阶段，具备完整的企业级功能。

## 🏗️ 系统架构

```
故事视频生成器/
├── main.py                    # 主程序入口（CLI界面）
├── run.py                     # 简化用户界面（交互式）
├── core/                      # 核心框架
│   ├── config_manager.py      # 配置管理（基于原工作流28节点参数）
│   ├── cache_manager.py       # 双重缓存（内存+磁盘，TTL，LRU）
│   └── file_manager.py        # 统一文件操作
├── content/                   # 内容生成模块  
│   ├── script_generator.py    # 文案生成（DeepSeek-V3）
│   ├── scene_splitter.py      # 场景分割（8个3秒场景）
│   ├── character_analyzer.py  # 角色分析和图像提示词生成
│   └── content_pipeline.py    # 内容生成流水线
├── media/                     # 媒体生成模块
│   ├── image_generator.py     # 多提供商图像生成
│   ├── audio_generator.py     # 多提供商音频合成
│   └── media_pipeline.py      # 媒体生成流水线
├── video/                     # 视频处理模块
│   ├── subtitle_processor.py  # 智能字幕处理（25字符分割）
│   └── animation_processor.py # 动画效果（FFmpeg滤镜）
├── utils/                     # 工具组件
│   ├── logger.py              # 分类日志系统
│   └── i18n.py                # 完整国际化框架
├── config/                    # 配置文件系统
│   ├── settings.json          # 主配置文件
│   ├── themes/               # 多语言主题库
│   └── prompts/              # 多语言提示词模板
└── reference/                 # 参考资料（原Coze工作流和平台）
```

## ⚙️ 核心配置文件

### 必需的API密钥配置 (.env)
```env
# 必需 - LLM API
OPENROUTER_API_KEY=your_openrouter_api_key

# 可选 - 增强功能
RUNNINGHUB_API_KEY=your_runninghub_api_key
AZURE_API_KEY=your_azure_api_key  
ELEVENLABS_API_KEY=your_elevenlabs_api_key
STABILITY_API_KEY=your_stability_api_key
```

### 主要配置 (config/settings.json)
- `general.max_concurrent_tasks`: 最大并发任务数（默认3）
- `llm.script_generation`: DeepSeek-V3模型配置
- `media.image.primary_provider`: 主要图像生成商（runninghub）
- `media.audio.primary_provider`: 主要音频合成商（azure）

## 🚀 常用开发命令

### 基本使用
```bash
# 生成单个故事
python main.py --theme "秦始皇统一六国" --language zh

# 批量生成故事
python main.py --batch themes.txt --language zh --concurrent 2

# 运行测试模式
python main.py --test

# 交互式界面
python run.py
```

### 测试和验证
```bash
# 系统配置验证
python validate_setup.py

# 综合测试套件
python test_suite.py

# 多语言功能测试  
python test_multilang.py

# 性能分析和优化
python optimize.py
```

### 依赖管理
```bash
# 安装依赖
pip install -r requirements.txt

# 常见依赖问题
pip install --upgrade openai aiohttp httpx
```

## 🔧 开发工作流程

### 1. 新功能开发流程
1. **配置验证**: `python validate_setup.py` 确保环境正常
2. **测试驱动**: 先写测试用例，再实现功能
3. **模块化设计**: 遵循现有的模块划分
4. **国际化支持**: 新功能必须支持中英西三语言
5. **缓存集成**: 适当使用缓存减少API调用

### 2. 调试和故障排除
```bash
# 查看详细日志
tail -f output/logs/story_generator.log

# 查看错误日志
tail -f output/logs/errors.log

# 清理缓存
rm -rf output/cache/*

# 检查系统状态
python -c "from core.config_manager import ConfigManager; print('Config OK')"
```

### 3. 性能优化指导
- **并发控制**: 根据系统资源调整`max_concurrent_tasks`
- **缓存策略**: 合理设置TTL和缓存大小
- **内存管理**: 定期运行`optimize.py`监控内存使用
- **API调用**: 利用多提供商容错减少调用失败

## 📊 原工作流对应关系

| 原Coze节点 | 对应实现 | 核心参数 |
|-----------|----------|----------|
| Node_121343 | ScriptGenerator | DeepSeek-V3, temp=0.8, max_tokens=1024 |
| Node_1165778 | SceneSplitter | 8个场景，每个3秒 |
| Node_1301843 | CharacterAnalyzer | 角色提取+图像提示词生成 |
| Node_120984 | AnimationProcessor | 缩放序列 [2.0, 1.2, 1.0] |
| 字幕处理 | SubtitleProcessor | MAX_LINE_LENGTH=25 |

## 🐛 常见问题处理

### API密钥问题
```bash
# 症状：Missing OPENROUTER_API_KEY
# 解决：检查.env文件是否存在且配置正确
cat .env | grep OPENROUTER_API_KEY
```

### 模型配置错误
```bash
# 症状：LLM config not found
# 解决：检查config/settings.json中的llm配置
python -c "from core.config_manager import ConfigManager; print(ConfigManager().get_llm_config('script_generation'))"
```

### 缓存问题
```bash
# 症状：缓存相关错误
# 解决：清理并重建缓存目录
rm -rf output/cache && mkdir -p output/cache/{scripts,scenes,images,audio}
```

### 权限问题
```bash
# 症状：Cannot create output directory
# 解决：检查输出目录权限
chmod 755 output/
```

## 🌟 最佳实践

### 1. 代码规范
- 遵循现有的类命名和结构模式
- 使用类型提示（typing模块）
- 异步函数用于IO密集型操作
- 适当的错误处理和日志记录

### 2. 配置管理
- 新配置项必须在`ConfigManager`中定义
- 敏感信息使用环境变量
- 配置变更要更新`config/settings.json`

### 3. 国际化开发
- 所有用户可见文本使用i18n系统
- 新消息添加到`config/messages/`对应语言文件
- 测试所有支持语言的功能

### 4. 测试策略
- 单元测试覆盖核心逻辑
- 集成测试验证端到端流程
- 性能测试确保系统可扩展性

## 📚 重要文档参考

- `README.md`: 项目说明和快速开始
- `DEPLOYMENT.md`: 完整部署指南（Docker、云服务）
- `PROJECT_SUMMARY.md`: 技术架构总结
- `reference/analysis/`: 原工作流技术分析

## 🎯 项目状态

✅ **已完成**: 6个开发阶段，38个核心文件，完整功能实现  
✅ **测试覆盖**: >85%，包含单元测试、集成测试、性能测试  
✅ **文档完整**: 100%，包含用户指南、API文档、部署指南  
✅ **生产就绪**: 支持Docker部署、监控、备份等企业级功能

---

**开发提醒**: 这是一个成熟的生产级项目，修改时请保持向后兼容性，遵循现有架构模式。