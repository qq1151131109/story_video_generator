#!/usr/bin/env python3
"""
API配置更新工具 - 更新配置文件以使用最优API
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

def update_llm_config():
    """更新LLM配置以使用最优模型"""
    
    # 加载环境变量
    load_dotenv()
    
    config_path = Path("config/settings.json")
    
    if not config_path.exists():
        print("❌ 配置文件不存在")
        return
    
    # 读取配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 根据可用API密钥优化配置
    available_apis = {
        'openrouter': bool(os.getenv('OPENROUTER_API_KEY')),
        'openai': bool(os.getenv('OPENAI_API_KEY')), 
        'deepseek': bool(os.getenv('DEEPSEEK_API_KEY')),
        'qwen': bool(os.getenv('QWEN_API_KEY'))
    }
    
    print("🔑 检测到的API密钥:")
    for api, available in available_apis.items():
        status = "✅" if available else "❌"
        print(f"  {status} {api}")
    
    # 优先级配置：OpenRouter > OpenAI > DeepSeek > Qwen
    primary_config = None
    
    if available_apis['openrouter']:
        primary_config = {
            "model": "google/gemini-2.0-flash-001",  # 使用低价高性能模型
            "api_base": "${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}",
            "api_key": "${OPENROUTER_API_KEY}"
        }
        print("🚀 主力配置: OpenRouter (Gemini 2.0 Flash)")
        
    elif available_apis['openai']:
        primary_config = {
            "model": "${OPENAI_MODEL:-gpt-5-mini}",
            "api_base": "${OPENAI_BASE_URL:-https://api.gptsapi.net/v1}", 
            "api_key": "${OPENAI_API_KEY}"
        }
        print("🔄 备用配置: OpenAI")
        
    elif available_apis['deepseek']:
        primary_config = {
            "model": "${DEEPSEEK_MODEL:-deepseek-chat}",
            "api_base": "${DEEPSEEK_BASE_URL:-https://api.deepseek.com}",
            "api_key": "${DEEPSEEK_API_KEY}"
        }
        print("💎 备用配置: DeepSeek")
        
    elif available_apis['qwen']:
        primary_config = {
            "model": "${QWEN_MODEL:-qwen-turbo}",
            "api_base": "${QWEN_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}",
            "api_key": "${QWEN_API_KEY}"
        }
        print("🌟 备用配置: Qwen")
    
    if not primary_config:
        print("❌ 没有可用的API密钥，无法更新配置")
        return
    
    # 更新所有LLM配置项
    llm_tasks = ['script_generation', 'theme_extraction', 'scene_splitting', 
                 'image_prompt_generation', 'character_analysis']
    
    for task in llm_tasks:
        if task in config['llm']:
            # 保留原有的temperature和max_tokens
            temp = config['llm'][task].get('temperature', 0.8)
            max_tokens = config['llm'][task].get('max_tokens', 1024)
            
            config['llm'][task].update({
                **primary_config,
                'temperature': temp,
                'max_tokens': max_tokens
            })
    
    # 增加并发数以充分利用多个API
    if sum(available_apis.values()) >= 2:
        config['general']['max_concurrent_tasks'] = 6
        print("🚄 检测到多个API，并发数提升至6")
    
    # 保存更新后的配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 配置已更新: {config_path}")
    
    # 显示推荐的模型使用策略
    print("\n💡 推荐模型使用策略:")
    
    if available_apis['openrouter']:
        print("  📝 LLM模型:")
        print("    🆓 免费模型: qwen/qwen3-coder:free (中文内容)")
        print("    💰 低价模型: google/gemini-2.0-flash-001 (综合最佳)")
        print("    💎 高端模型: google/gemini-2.5-flash (付费高质量)")
        print("  🎨 图像生成:")
        print("    🆓 免费版本: google/gemini-2.5-flash-image-preview:free")
        print("    💎 付费版本: google/gemini-2.5-flash-image-preview ($0.00003/图像)")
    
    if available_apis['deepseek']:
        print("  🇨🇳 中文专用: DeepSeek (deepseek-chat)")
        
    if available_apis['qwen']:
        print("  🌏 阿里云: Qwen (qwen-turbo)")
    
    print("\n🚀 Gemini 2.5 Flash Image Preview 特色功能:")
    print("  💬 对话式图像生成和编辑")
    print("  🎯 角色一致性保持")
    print("  ✏️ 精确的局部编辑")
    print("  🧠 结合世界知识生成更准确图像")

def main():
    """主函数"""
    print("历史故事生成器 - API配置优化工具")
    print("=" * 50)
    
    # 检查并更新配置
    update_llm_config()
    
    print("\n🎯 配置完成！现在可以运行:")
    print("  python main.py --test          # 测试模式")
    print("  python run.py                  # 交互式界面")

if __name__ == "__main__":
    main()