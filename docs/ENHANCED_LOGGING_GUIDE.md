# 📊 增强型日志系统使用指南

## 🎯 系统概述

新的增强型日志系统专为**快速问题定位和排查**而设计，具备以下特性：

### ✨ 核心特性
- 🔍 **结构化日志** - JSON格式，便于分析和查询
- 📊 **智能错误聚合** - 自动统计错误频率，避免日志污染
- ⚡ **性能追踪** - API调用时间、处理耗时自动记录
- 🔐 **敏感信息掩码** - 自动屏蔽API密钥等敏感数据
- 🎯 **快速问题定位** - 通过上下文快速锁定问题根源
- 📈 **分级日志管理** - 不同类型日志分别存储，提高效率

### 📁 日志文件结构
```
output/logs/
├── story_generator.log  # 主日志（INFO+）
├── errors.log          # 错误日志（ERROR+）
├── performance.log     # 性能日志（API调用、耗时操作）
└── debug.log           # 调试日志（可选，DEBUG级别）
```

## 🚀 基础使用

### 1. 初始化日志系统
```python
from utils.logger import setup_logging

# 自动使用增强型日志系统
log_manager = setup_logging()
logger = log_manager.get_logger('my_component')

# 基础日志记录（与原系统相同）
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")
```

### 2. 在服务类中使用
```python
class MyService:
    def __init__(self):
        self.log_manager = setup_logging()
        self.logger = self.log_manager.get_logger('my_service')
    
    def do_something(self):
        self.logger.info("开始执行操作")
        # 你的业务逻辑
        self.logger.info("操作完成")
```

## 🔧 高级功能

### 1. 性能追踪
```python
# 自动追踪操作耗时
with log_manager.performance_tracker(logger, 'database_query'):
    result = database.query("SELECT * FROM users")
    # 系统会自动记录执行时间到performance.log

# 手动记录API调用性能
log_manager.log_api_call(
    logger, 
    method='POST', 
    url='https://api.openai.com/v1/chat/completions',
    status_code=200,
    response_time=1.23,
    error=None  # 成功时为None
)
```

### 2. 错误处理（带上下文）
```python
try:
    risky_operation()
except Exception as e:
    # 记录带上下文的错误，便于排查
    log_manager.log_error_with_context(
        logger, e, 
        context={
            'user_id': '12345',
            'operation': 'generate_video',
            'input_theme': '康熙大帝',
            'current_step': 'media_generation'
        }
    )
```

### 3. 结构化日志输出
所有日志都以JSON格式输出到文件：
```json
{
  "timestamp": "2025-09-07T11:05:37.862030",
  "level": "ERROR", 
  "component": "media_pipeline",
  "function": "generate_image",
  "message": "Image generation failed",
  "context": {
    "provider": "runninghub",
    "prompt": "古代中国皇宫场景",
    "error_code": "API_TIMEOUT"
  },
  "performance": {
    "duration": 30.5,
    "success": false
  }
}
```

## 📊 日志分析工具

### 快速分析命令
```bash
# 生成完整分析报告
python tools/log_analyzer.py

# 分析最近6小时的日志
python tools/log_analyzer.py --hours 6

# 只分析错误
python tools/log_analyzer.py --errors

# 只分析性能
python tools/log_analyzer.py --performance

# 检查系统健康状态
python tools/log_analyzer.py --health
```

### 分析报告示例
```
============================================================
📊 故事视频生成器 - 日志分析报告
📅 分析时间范围: 最近 24 小时
🕐 生成时间: 2025-09-07 11:07:47
============================================================

🏥 系统健康状态: WARNING
⚠️  警告:
   • main日志文件较大: 25.3MB
   • 检测到12个慢操作

🚨 错误分析:
   总错误数: 45
   独特错误: 8
   错误趋势: 错误数量快速增加
   🔥 高频错误:
      • ConnectionError: API连接超时: 23次
      • ValueError: 无效的提示词格式: 12次
      • RuntimeError: 视频合成失败: 6次

⚡ 性能分析:
   API调用数: 156
   操作数: 45
   平均API响应时间: 2.34s
   慢操作数: 12
   API成功率: 87.2%
   🐌 慢API:
      • https://api.runninghub.cn/workflow: 15.67s (23次调用)
      • https://api.openai.com/v1/chat: 3.45s (89次调用)
============================================================
```

## 🛠️ 问题排查指南

### 1. 常见问题定位流程

#### 📍 **步骤1: 快速健康检查**
```bash
python tools/log_analyzer.py --health
```
- 系统状态一目了然
- 自动发现常见问题（日志过大、错误率高等）

#### 📍 **步骤2: 错误分析**
```bash
python tools/log_analyzer.py --errors --hours 2
```
- 查看最近错误趋势
- 识别高频错误模式
- 获取错误上下文信息

#### 📍 **步骤3: 性能分析**
```bash  
python tools/log_analyzer.py --performance --hours 6
```
- 识别慢API和瓶颈操作
- 分析成功率变化
- 找出性能退化原因

#### 📍 **步骤4: 详细日志检查**
```bash
# 查看结构化错误日志
cat output/logs/errors.log | jq '.'

# 查看性能日志中的API调用
cat output/logs/performance.log | jq 'select(.performance.method)'

# 搜索特定错误
grep "ConnectionError" output/logs/errors.log
```

### 2. 典型问题场景

#### 🚨 **API调用失败**
**症状**: 大量ConnectionError或HTTP 4xx/5xx错误
```bash
# 1. 检查API错误统计
python tools/log_analyzer.py --errors --hours 1

# 2. 查看具体API调用记录
cat output/logs/performance.log | jq 'select(.performance.success == false)'

# 3. 检查API密钥配置
grep "Unauthorized\|Invalid" output/logs/errors.log
```

#### 🐌 **性能问题**
**症状**: 操作耗时过长，用户体验差
```bash
# 1. 识别慢操作
python tools/log_analyzer.py --performance

# 2. 查看超过10秒的操作
cat output/logs/performance.log | jq 'select(.performance.duration > 10)'

# 3. 分析API响应时间趋势
cat output/logs/performance.log | jq '.performance.response_time'
```

#### 💥 **系统崩溃/异常**
**症状**: 程序异常退出或功能中断
```bash
# 1. 查看最新的致命错误
tail -20 output/logs/errors.log | jq 'select(.level == "ERROR")'

# 2. 检查异常堆栈
cat output/logs/errors.log | jq '.exception.traceback[]'

# 3. 查看错误上下文
cat output/logs/errors.log | jq '.context'
```

## ⚙️ 配置调优

### 日志级别配置
编辑 `config/settings.json`:
```json
{
  "logging": {
    "console_level": "INFO",    // 控制台输出级别
    "file_level": "DEBUG",      // 文件记录级别
    "max_file_size_mb": 5,      // 单文件最大大小
    "backup_count": 3,          // 保留的轮转文件数
    "files": {
      "debug": {
        "enabled": true         // 开启调试日志
      }
    }
  }
}
```

### 过滤噪音日志
```json
{
  "logging": {
    "filters": {
      "exclude_patterns": [
        "HTTP Request: GET",      // 排除GET请求日志
        "Connection pool is full", // 排除连接池警告
        "Heartbeat received"      // 排除心跳日志
      ]
    }
  }
}
```

## 📋 最佳实践

### 1. 日志记录规范
- ✅ **使用语义化的消息**: `logger.info("开始生成视频，主题: 康熙大帝")`
- ✅ **添加关键上下文**: 用户ID、操作类型、输入参数
- ✅ **记录操作结果**: 成功/失败、耗时、输出大小
- ❌ **避免记录敏感信息**: API密钥、用户密码等

### 2. 错误处理规范
```python
# ✅ 好的错误处理
try:
    result = api_call()
except APITimeoutError as e:
    log_manager.log_error_with_context(
        logger, e,
        context={
            'api_endpoint': 'https://api.example.com',
            'timeout_duration': 30,
            'retry_count': 3
        }
    )
    
# ❌ 不好的错误处理  
except Exception as e:
    logger.error(f"出错了: {e}")
```

### 3. 性能监控规范
```python
# ✅ 监控关键操作
with log_manager.performance_tracker(logger, 'video_generation'):
    video_path = generate_video(theme, language)

# ✅ 监控API调用
response = requests.post(url, json=data)
log_manager.log_api_call(
    logger, 'POST', url, 
    status_code=response.status_code,
    response_time=response.elapsed.total_seconds()
)
```

### 4. 定期维护
```bash
# 每周运行健康检查
python tools/log_analyzer.py --health

# 清理超过7天的旧日志
find output/logs -name "*.log.*" -mtime +7 -delete

# 生成月度性能报告
python tools/log_analyzer.py --hours 720 > monthly_report.txt
```

## 🔄 从旧系统迁移

新系统已完全向后兼容，无需修改现有代码：

```python
# 现有代码继续工作
from utils.logger import setup_logging
log_manager = setup_logging()
logger = log_manager.get_logger('component')
logger.info("这条日志会使用增强型系统输出")
```

## 🆘 故障排除

### 1. 日志文件未生成
- 检查 `output/logs` 目录权限
- 确认配置文件 `config/settings.json` 中的日志配置

### 2. 结构化日志格式错误
- 检查配置中的 `log_format` 设置
- 确认日志消息中无非法字符

### 3. 性能日志为空
- 确认代码中使用了 `performance_tracker` 或 `log_api_call`
- 检查性能日志文件的 `enabled` 配置

### 4. 错误未记录到errors.log
- 确认使用了 `log_error_with_context` 方法
- 检查logger的 `propagate` 设置（应为 True）

---

## 💡 技术支持

如遇到问题，请按以下顺序排查：

1. **运行诊断**: `python tools/log_analyzer.py --health`
2. **查看最新错误**: `tail -10 output/logs/errors.log`
3. **检查配置**: 确认 `config/settings.json` 中的日志配置
4. **重启应用**: 重新启动应用以应用最新配置

**快速问题定位命令**:
```bash
# 一键诊断最近1小时的问题
python tools/log_analyzer.py --hours 1 | grep -E "(ERROR|WARNING|🚨|⚠️)"
```

---

*🎉 恭喜！你现在拥有了一个强大的日志系统，能够快速定位和解决任何问题！*