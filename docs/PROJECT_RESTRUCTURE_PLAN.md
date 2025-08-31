# 项目重构整理计划

## 🎯 目标
- 清理根目录，只保留核心文件
- 统一测试文件管理
- 优化工具和配置文件组织
- 清理不必要的文件和缓存

## 📁 新的目录结构

```
story_video_generator/
├── main.py                    # 唯一入口文件
├── run.py                     # 交互式入口（保留）
├── requirements.txt           # 基础依赖
├── requirements-whisperx.txt  # 可选依赖
├── README.md                  # 项目说明
│
├── core/                      # 核心框架 ✅
├── content/                   # 内容生成 ✅
├── media/                     # 媒体处理 ✅
├── video/                     # 视频合成 ✅
├── utils/                     # 工具函数 ✅
├── config/                    # 配置文件 ✅
│
├── tools/                     # 🆕 工具脚本目录
│   ├── configure_apis.py      # API配置工具
│   ├── validate_setup.py      # 环境验证工具
│   ├── optimize.py            # 性能优化工具
│   └── load_env.py            # 环境加载工具
│
├── demos/                     # 🆕 演示文件目录
│   ├── basic_demo.py          # 基础演示
│   └── full_video_demo.py     # 完整演示
│
├── tests/                     # 🆕 测试文件目录
│   ├── end_to_end_test.py     # 端到端测试
│   ├── quick_video_test.py    # 快速测试
│   └── verify_final_video.py  # 视频验证测试
│
├── docs/                      # 🆕 文档目录
│   ├── API_SETUP_SUMMARY.md
│   ├── DEPLOYMENT.md
│   ├── PROJECT_SUMMARY.md
│   ├── WORKFLOW_DIAGRAM.md
│   └── test_report.md
│
└── output/                    # 输出目录 ✅
    ├── cache/                 # 缓存（需清理）
    ├── temp/                  # 临时文件（需清理）
    └── [其他保留]
```

## 🔄 具体整理步骤

### 1. 创建新目录结构
```bash
mkdir -p tools demos tests docs
```

### 2. 移动工具文件
```bash
mv configure_apis.py tools/
mv validate_setup.py tools/
mv optimize.py tools/
mv load_env.py tools/
```

### 3. 移动演示文件
```bash
mv basic_demo.py demos/
mv full_video_demo.py demos/
```

### 4. 移动测试文件
```bash
mv end_to_end_test.py tests/
mv quick_video_test.py tests/
mv verify_final_video.py tests/
```

### 5. 移动文档文件
```bash
mv API_SETUP_SUMMARY.md docs/
mv DEPLOYMENT.md docs/
mv PROJECT_SUMMARY.md docs/
mv WORKFLOW_DIAGRAM.md docs/
mv test_report.md docs/
```

### 6. 清理不必要的文件
```bash
# 清理缓存
rm -rf output/cache/*
rm -rf output/temp/*

# 清理测试文件
rm test_subtitle.mp4
rm *.cache 2>/dev/null || true
```

### 7. 更新导入路径
需要修改的文件：
- `main.py` - 更新 `full_video_demo` 导入
- 其他引用移动文件的地方

## 📋 文件分类总结

### ✅ 保留在根目录
- `main.py` - 主程序
- `run.py` - 交互式入口
- `README.md`, `CLAUDE.md` - 核心文档
- `requirements*.txt` - 依赖文件
- 核心业务目录 (core/, content/, media/, video/, utils/, config/)

### 📁 移动到子目录
- **tools/** - 工具脚本 (4个文件)
- **demos/** - 演示程序 (2个文件) 
- **tests/** - 测试文件 (3个文件)
- **docs/** - 文档文件 (5个文件)

### 🗑️ 清理删除
- 缓存文件 (output/cache/*)
- 临时文件 (output/temp/*)
- 无用测试视频 (test_*.mp4)

## 🎯 预期效果

**根目录清理前**: 25+ 个文件  
**根目录清理后**: 8 个文件 + 6 个业务目录

**提升**:
- ✅ 根目录整洁，核心文件一目了然
- ✅ 按功能分类，便于维护
- ✅ 测试、工具、文档独立管理
- ✅ 减少不必要的缓存文件
- ✅ 更好的项目专业性