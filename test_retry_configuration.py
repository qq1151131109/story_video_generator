#!/usr/bin/env python3
"""
测试新的重试配置功能
验证从配置文件读取重试次数和延迟时间
"""

import sys
import json
from pathlib import Path
sys.path.append('.')

def test_retry_configuration():
    """测试重试配置读取和应用"""
    
    print("🧪 测试新的重试配置功能")
    print("=" * 60)
    
    # 1. 检查配置文件
    config_file = Path("config/settings.json")
    if not config_file.exists():
        print("❌ 配置文件不存在")
        return
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 检查重试相关配置
    media_config = config.get('media', {})
    max_retries = media_config.get('max_retries', 'Not found')
    retry_delays = media_config.get('retry_delays', 'Not found')
    retry_keywords = media_config.get('retry_keywords', 'Not found')
    
    print(f"📋 当前重试配置:")
    print(f"  🔄 最大重试次数: {max_retries}")
    print(f"  ⏰ 重试延迟序列: {retry_delays}")
    print(f"  🔍 重试关键词: {retry_keywords}")
    
    # 2. 计算总的最大等待时间
    if isinstance(retry_delays, list):
        total_delay = sum(retry_delays)
        max_attempts = max_retries + 1 if isinstance(max_retries, int) else "Unknown"
        print(f"\n📊 重试策略分析:")
        print(f"  🎯 总尝试次数: {max_attempts}")
        print(f"  ⏱️ 最大总等待时间: {total_delay}秒 ({total_delay/60:.1f}分钟)")
        print(f"  📈 延迟模式: 递增式 ({retry_delays[0]}s → {retry_delays[-1]}s)")
    
    # 3. 模拟重试逻辑
    print(f"\n🔍 模拟重试时间线:")
    if isinstance(retry_delays, list) and isinstance(max_retries, int):
        cumulative_time = 0
        for attempt in range(max_retries + 1):
            if attempt == 0:
                print(f"  尝试 {attempt + 1}/{max_retries + 1}: 立即开始 (t=0s)")
            else:
                delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
                cumulative_time += delay
                print(f"  尝试 {attempt + 1}/{max_retries + 1}: 等待{delay}s后重试 (t={cumulative_time}s)")
    
    # 4. 对比旧配置
    print(f"\n📈 配置对比 (旧 vs 新):")
    print(f"  重试次数: 2 → {max_retries} (增加 {max_retries - 2 if isinstance(max_retries, int) else 'N/A'}次)")
    print(f"  延迟策略: 线性递增(30s,60s,90s) → 配置化({retry_delays})")
    print(f"  关键词数量: 5个 → {len(retry_keywords) if isinstance(retry_keywords, list) else 'N/A'}个")
    
    # 5. 验证配置合理性
    print(f"\n✅ 配置验证:")
    issues = []
    
    if not isinstance(max_retries, int) or max_retries < 1:
        issues.append("❌ max_retries 必须是大于0的整数")
    elif max_retries > 10:
        issues.append("⚠️ max_retries 过大可能导致长时间等待")
    
    if not isinstance(retry_delays, list) or len(retry_delays) == 0:
        issues.append("❌ retry_delays 必须是非空列表")
    elif sum(retry_delays) > 600:  # 10分钟
        issues.append("⚠️ 重试总等待时间超过10分钟")
    
    if not isinstance(retry_keywords, list) or len(retry_keywords) == 0:
        issues.append("❌ retry_keywords 必须是非空列表")
    
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  ✅ 所有配置项都合理")
    
    print(f"\n" + "=" * 60)
    print("🎯 重试配置测试完成！")
    print("💡 建议: 根据实际网络环境和API稳定性调整重试参数")

if __name__ == "__main__":
    test_retry_configuration()