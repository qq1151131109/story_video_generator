#!/usr/bin/env python3
"""
测试结构化输出功能
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.llm_client_manager import LangChainLLMManager
from core.config_manager import ConfigManager

async def test_structured_output():
    """测试结构化输出功能"""
    print("🧪 测试结构化输出功能")
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    try:
        # 初始化管理器
        config = ConfigManager()
        llm_manager = LangChainLLMManager(config)
        
        print("✅ LLM Manager 初始化成功")
        
        # 测试场景分割结构化输出
        print("\n🎬 测试场景分割结构化输出...")
        
        system_prompt = """你是专业的故事场景分割专家。将输入的故事分割为多个场景，每个场景3秒钟。

返回JSON格式：
{
  "scenes": [
    {
      "sequence": 1,
      "content": "场景描述",
      "duration": 3.0
    }
  ]
}"""
        
        user_prompt = "请将以下故事分割为5个场景：一位古代皇帝统一天下的故事。每个场景应该包含不同的重要情节点。"
        
        result = await llm_manager.generate_structured_output(
            task_type='scene_splitting',
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_retries=1
        )
        
        if hasattr(result, 'scenes'):
            print(f"✅ 结构化输出成功：{len(result.scenes)} 个场景")
            for i, scene in enumerate(result.scenes[:3]):  # 显示前3个
                print(f"   场景{scene.sequence}: {scene.content[:50]}...")
        else:
            print(f"⚠️ 降级输出：{str(result)[:100]}...")
            
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_structured_output())