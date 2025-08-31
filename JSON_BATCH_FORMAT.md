# JSON 批量生成配置格式说明

## 概述

系统现在支持通过JSON配置文件进行批量故事生成，提供更灵活的配置和更好的批量管理功能。

## JSON 文件格式

### 完整配置示例

```json
{
  "batch_info": {
    "name": "历史故事批量生成",
    "description": "批量生成多个历史故事视频", 
    "created_at": "2025-08-31",
    "total_stories": 6
  },
  "settings": {
    "default_language": "zh",
    "output_format": "mp4",
    "enable_subtitles": true
  },
  "stories": [
    {
      "id": "story_001",
      "title": "秦始皇统一六国的传奇",
      "language": "zh",
      "style": "horror",
      "priority": 1
    },
    {
      "id": "story_002", 
      "title": "The Rise of the Roman Empire",
      "language": "en",
      "style": "documentary",
      "priority": 2
    }
  ]
}
```

### 字段说明

#### batch_info (批次信息)
- `name`: 批次名称，用于显示和报告
- `description`: 批次描述
- `created_at`: 创建日期
- `total_stories`: 总故事数（可选，系统会自动计算）

#### settings (全局设置)  
- `default_language`: 默认语言代码 ("zh", "en", "es")
- `output_format`: 输出格式 (固定 "mp4")
- `enable_subtitles`: 是否启用字幕 (true/false)

#### stories (故事列表)
每个故事包含以下字段：
- `id`: 唯一标识符，用于跟踪和报告
- `title`: 故事标题/主题
- `language`: 语言代码 ("zh", "en", "es")
- `style`: 视觉风格 ("horror", "documentary", "dramatic")
- `priority`: 优先级 (数字，越小越优先)

## 使用方法

### 1. 创建JSON配置文件
```bash
# 复制示例文件
cp example_batch.json my_stories.json

# 编辑配置
nano my_stories.json
```

### 2. 运行批量生成
```bash
# 使用自定义JSON文件
python main.py --json my_stories.json

# 使用默认配置文件 (config/default_stories.json)
python main.py
```

### 3. 查看生成结果
生成完成后会自动创建详细报告：
- 路径：`output/reports/batch_report_YYYYMMDD_HHMMSS.json`
- 包含每个故事的生成状态、耗时、错误信息等

## 功能特性

### ✅ 支持的功能
- **多语言支持**: 中文(zh)、英文(en)、西班牙语(es)
- **串行生成**: 逐个生成故事，确保系统稳定
- **优先级排序**: 按priority字段排序执行
- **详细进度**: 实时显示每个故事的生成状态  
- **错误处理**: 单个故事失败不影响其他故事
- **生成报告**: 自动生成详细的批量处理报告
- **多提供商容错**: 自动使用备用LLM提供商

### 📊 生成报告格式
```json
{
  "batch_info": {...},
  "settings": {...},
  "summary": {
    "total_stories": 6,
    "success_count": 5,
    "failed_count": 1,
    "success_rate": 83.33,
    "completion_time": "2025-08-31T15:30:45.123456"
  },
  "results": [
    {
      "id": "story_001",
      "title": "秦始皇统一六国的传奇",
      "success": true,
      "duration": 245.6,
      "timestamp": "2025-08-31T15:25:30.123456"
    }
  ]
}
```

## 最佳实践

### 1. 生成模式
- **串行生成**: 系统强制逐个生成故事，确保稳定性和资源合理使用
- **优势**: 避免系统过载、减少API限制风险、保证生成质量

### 2. 优先级规划
- **优先级 1**: 重要/紧急的故事
- **优先级 2**: 常规故事
- **优先级 3**: 测试/实验性故事

### 3. ID命名规范
建议使用有意义的前缀：
- `prod_001`: 生产环境故事
- `test_001`: 测试故事
- `demo_001`: 演示故事

### 4. 错误恢复
如果批量生成中断，可以：
1. 查看报告文件确认完成状态
2. 修改JSON文件移除已完成的故事
3. 重新运行批量生成

## 示例文件

项目中提供了以下示例文件：
- `example_batch.json`: 完整功能演示
- `test_batch.json`: 小型测试用例

## 命令对比

| 功能 | 旧方式 | 新方式 |
|------|--------|--------|
| 单个生成 | `--theme "标题"` | `--theme "标题"` (不变) |
| 批量生成 | `--batch themes.txt` | `--json config.json` |
| 生成模式 | 可选并发 | 强制串行 |
| 多语言 | 单一语言 | JSON中每个故事独立设置 |
| 进度跟踪 | 基础日志 | 详细进度 + 报告 |

通过JSON配置，您可以更灵活地管理批量生成任务，获得更好的控制和反馈。