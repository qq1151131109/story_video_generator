#!/usr/bin/env python3
"""
测试场景分割器的长度预检查功能
"""
import sys
sys.path.append('/home/shenglin/Desktop/story_video_generator')

import asyncio
from content.scene_splitter import SceneSplitter, SceneSplitRequest
from core.config_manager import ConfigManager

async def test_scene_length_check():
    """测试场景长度预检查"""
    print("🧪 测试场景分割器长度预检查")
    print("=" * 60)
    
    # 初始化
    config = ConfigManager()
    splitter = SceneSplitter(config, None, None)
    
    # 模拟有长句子的文案
    test_script = """你是万历年的新科进士，初授浙江钱塘县令，辖区豪绅垄断漕运，上级知府暗中索贿。
才到任三天，师爷就递来账本，低声说"郭尚书家三公子强占民田，苦主悬梁自尽"。
你拍案要查，当夜书房窗棂突然射进一支毒箭，钉着血书"多管闲事者曝尸运河"。
次日清早，县仓储粮莫名发霉，鼠尸堆中飘出恶臭，衙役集体称病告假。
更致命的是，苦主女儿突然翻供，跪在公堂哭喊"青天大老爷逼民女诬陷良商"。"""
    
    request = SceneSplitRequest(
        script_content=test_script,
        language="zh",
        use_coze_rules=True
    )
    
    # 执行场景分割
    print("原始文案:")
    print(test_script)
    print()
    
    result = await splitter.split_scenes_async(request)
    
    print(f"分割结果: {len(result.scenes)}个场景")
    print("-" * 40)
    
    for i, scene in enumerate(result.scenes, 1):
        length = len(scene.content)
        status = "🔴 超长" if length > 30 else "🟡 偏长" if length > 20 else "🟢 合适"
        print(f"场景{i}: {length}字符 {status}")
        print(f"  内容: {scene.content}")
        print()

if __name__ == "__main__":
    asyncio.run(test_scene_length_check())