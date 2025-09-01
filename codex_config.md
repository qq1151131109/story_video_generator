# Codex 配置文档

## 基本信息
- **统一配置key**: `cr_5aaee576f9cf30c172371cabc838c17f6a0b7ac56152f339784aaf0f0bd25914`
- **API Base URL**: `https://code2.ylsagi.io/openai`
- **文档地址**: https://doc.ylsagi.com/zh/codex/doc.html

## 环境配置

### 1. VSCode 插件安装
在 VSCode 扩展商店搜索 "codex" 并安装官方插件。

### 2. VSCode 设置配置
在 VSCode 的 settings.json 中添加以下配置：

```json
{
  "chatgpt.apiBase": "https://code2.ylsagi.io/openai",
  "chatgpt.apiKey": "cr_5aaee576f9cf30c172371cabc838c17f6a0b7ac56152f339784aaf0f0bd25914"
}
```

### 3. 配置验证
1. 重启 VSCode
2. 打开命令面板 (Ctrl+Shift+P)
3. 输入 "codex" 相关命令进行测试
4. 确认能正常连接到服务

## 使用说明

### 基本功能
- 代码补全
- 代码解释
- 代码生成
- 代码重构

### 快捷键
- 代码补全: Tab
- 打开聊天: Ctrl+Shift+P -> "ChatGPT"

## 故障排除

1. **连接失败**
   - 检查网络连接
   - 确认 API key 正确
   - 验证 API Base URL

2. **插件不工作**
   - 重启 VSCode
   - 检查插件是否启用
   - 查看输出窗口的错误信息

## 注意事项
- 确保网络畅通
- API key 请妥善保管
- 定期检查配置是否生效