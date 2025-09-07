#!/usr/bin/env python3
"""
并发配置检查工具 - 诊断RunningHub视频生成并发问题
"""

import json
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager


def check_concurrency_settings():
    """检查所有影响并发的配置"""
    print("🔍 RunningHub并发配置诊断工具")
    print("=" * 50)
    
    try:
        config = ConfigManager()
        
        print("📋 1. 核心并发配置:")
        print("---")
        general_concurrent = config.get('general.max_concurrent_tasks', '未设置')
        print(f"• general.max_concurrent_tasks: {general_concurrent}")
        print(f"• 实际video并发限制: {max(1, min(general_concurrent if isinstance(general_concurrent, int) else 3, 10))}")
        print(f"• 实际image并发限制: {general_concurrent}")
        
        print()
        print("📋 2. 环境变量检查:")
        print("---")
        env_vars = ['MAX_CONCURRENT_TASKS', 'MAX_API_CONCURRENT', 'RUNNINGHUB_API_KEY']
        for var in env_vars:
            value = os.environ.get(var, '未设置')
            if var == 'RUNNINGHUB_API_KEY' and value != '未设置':
                value = value[:10] + '...' if len(value) > 10 else value
            print(f"• {var}: {value}")
        
        print()
        print("📋 3. JSON批量配置检查:")
        print("---")
        # 检查是否有批量配置文件
        batch_files = list(Path('.').glob('*.json'))
        if batch_files:
            for batch_file in batch_files[:3]:  # 只检查前3个
                try:
                    with open(batch_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if 'stories' in data:
                        settings = data.get('settings', {})
                        concurrent = settings.get('concurrent', '未设置')
                        print(f"• {batch_file}: concurrent = {concurrent}")
                except:
                    pass
        else:
            print("• 未找到JSON批量配置文件")
        
        print()
        print("📋 4. 并发层级说明:")
        print("---")
        print("• 故事级并发: 控制同时生成多少个故事")
        print("  - 命令行批量: --concurrent 参数")
        print("  - JSON批量: settings.concurrent 字段")
        print()
        print("• 场景级并发: 控制单个故事内场景视频的并发数")
        print("  - 配置: general.max_concurrent_tasks")
        print("  - 硬限制: 1-10个")
        print()
        
        print("🎯 5. 推荐设置:")
        print("---")
        api_key = config.get_api_key('runninghub')
        if api_key:
            print("• ✅ RunningHub API密钥已配置")
            print("• 推荐场景并发: 5-8个 (取决于API限制)")
            print("• 推荐故事并发: 2-3个 (避免API过载)")
        else:
            print("• ❌ RunningHub API密钥未配置")
            print("• 需要先配置有效的API密钥")
        
        print()
        print("🔧 6. 优化建议:")
        print("---")
        if general_concurrent < 5:
            print("• 建议增加 general.max_concurrent_tasks 到 5-8")
        if general_concurrent > 10:
            print("• 建议降低 general.max_concurrent_tasks 到 10以内")
        
        print("• 如果API频繁超时: 降低并发数")
        print("• 如果生成太慢: 适当增加并发数")
        print("• 测试最佳设置: 从3开始逐步增加")
        
    except Exception as e:
        print(f"❌ 配置检查失败: {e}")
        return False
    
    return True


if __name__ == "__main__":
    check_concurrency_settings()