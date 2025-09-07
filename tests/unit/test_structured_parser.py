#!/usr/bin/env python3
"""
测试结构化解析器功能 - 不依赖API
"""

import json
import asyncio
import sys
from pathlib import Path

# 添加项目根路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.robust_output_parser import RobustStructuredOutputParser
from utils.structured_output_models import SceneSplitOutput

def test_structured_parser():
    """测试结构化解析器"""
    print("🧪 测试结构化解析器功能")
    
    # 创建解析器
    parser = RobustStructuredOutputParser(SceneSplitOutput)
    
    # 测试数据 - 模拟LLM输出的各种格式
    test_cases = [
        # 完整的JSON格式
        '''
        ```json
        {
            "scenes": [
                {"sequence": 1, "content": "皇帝登基大典，文武百官朝拜", "duration": 3.0},
                {"sequence": 2, "content": "制定统一文字政策会议", "duration": 3.0},
                {"sequence": 3, "content": "军队整训准备征战", "duration": 3.0},
                {"sequence": 4, "content": "统一货币制度实施", "duration": 3.0},
                {"sequence": 5, "content": "万里长城建设场面", "duration": 3.0}
            ]
        }
        ```
        ''',
        # 带有多余文本的格式
        '''
        根据您的要求，我将故事分割为5个场景：
        
        ```json
        {
            "scenes": [
                {"sequence": 1, "content": "秦王政统一六国前的准备工作", "duration": 3.0},
                {"sequence": 2, "content": "攻打韩国的激烈战斗", "duration": 3.0},
                {"sequence": 3, "content": "灭赵国的决定性战役", "duration": 3.0},
                {"sequence": 4, "content": "统一文字货币的政策", "duration": 3.0},
                {"sequence": 5, "content": "称帝庆典盛大场面", "duration": 3.0}
            ]
        }
        ```
        
        这样分割确保了每个场景都包含重要情节点。
        ''',
        # 格式错误但可修复的JSON
        '''
        {
            scenes: [
                {sequence: 1, content: '皇帝登基场面', duration: 3.0},
                {sequence: 2, content: '制定法律条文', duration: 3.0},
                {sequence: 3, content: '军队训练场景', duration: 3.0},
                {sequence: 4, content: '经济改革措施', duration: 3.0},
                {sequence: 5, content: '文化统一政策', duration: 3.0},
            ]
        }
        '''
    ]
    
    success_count = 0
    for i, test_text in enumerate(test_cases):
        try:
            print(f"\n📝 测试案例 {i+1}:")
            print(f"输入长度: {len(test_text)} 字符")
            
            result = parser.parse(test_text)
            
            if hasattr(result, 'scenes') and len(result.scenes) >= 5:
                print(f"✅ 解析成功: {len(result.scenes)} 个场景")
                for j, scene in enumerate(result.scenes[:3]):  # 显示前3个
                    print(f"   场景{scene.sequence}: {scene.content[:50]}...")
                success_count += 1
            else:
                print(f"⚠️ 解析不完整: {result}")
                
        except Exception as e:
            print(f"❌ 解析失败: {e}")
    
    print(f"\n📊 测试结果: {success_count}/{len(test_cases)} 成功")
    
    # 测试错误恢复
    print("\n🔧 测试错误恢复...")
    try:
        broken_json = "这不是有效的JSON格式"
        fallback_result = parser.parse(broken_json)
        print(f"✅ 错误恢复成功: {type(fallback_result).__name__}")
        if hasattr(fallback_result, 'scenes'):
            print(f"   降级场景数量: {len(fallback_result.scenes)}")
    except Exception as e:
        print(f"❌ 错误恢复失败: {e}")

if __name__ == "__main__":
    test_structured_parser()