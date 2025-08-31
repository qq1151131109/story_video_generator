# 安装指南

## 📦 完整安装

```bash
# 安装所有依赖（包括WhisperX精确字幕对齐）
pip install -r requirements.txt
```

这将安装运行故事视频生成器所需的所有依赖，包括可选的WhisperX功能。

## 🚀 快速开始

安装完成后：

```bash
# 配置API密钥 (必需)
cp .env.example .env
# 编辑.env文件，添加你的OPENROUTER_API_KEY

# 运行示例
python main.py --theme "秦始皇统一六国" --language zh
```

## ⚙️ 可选功能

### WhisperX精确对齐
- **用途**: 提供word-level精确字幕时间戳
- **替代**: 不启用时自动使用TTS时间戳分割
- **首次运行**: 会下载1-3GB模型文件
- **配置**: 在`config/settings.json`中设置`whisperx.enabled: true`

### GPU加速 (可选)
如果有NVIDIA GPU，可以安装GPU版本的torch：

```bash
pip install torch torchaudio --extra-index-url https://download.pytorch.org/whl/cu118
```

## 🔧 系统依赖

确保系统已安装：
- **Python 3.8+**
- **FFmpeg** (用于视频处理)
  ```bash
  # Ubuntu/Debian
  sudo apt install ffmpeg
  
  # macOS
  brew install ffmpeg
  
  # Windows
  # 下载并安装 https://ffmpeg.org/download.html
  ```

## ❓ 常见问题

**Q: 安装失败怎么办？**
A: 先安装基本版本 `pip install -r requirements.txt`，如需WhisperX再单独安装

**Q: WhisperX安装失败？**
A: 可以跳过，系统会自动使用TTS时间戳方案

**Q: 视频生成失败？**
A: 检查FFmpeg是否正确安装：`ffmpeg -version`