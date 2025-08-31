#!/usr/bin/env python3
"""
测试场景分割器防止合并超长句子的功能
"""
import sys
sys.path.append('/home/shenglin/Desktop/story_video_generator')

import asyncio
from content.scene_splitter import SceneSplitter, SceneSplitRequest
from core.config_manager import ConfigManager

async def test_scene_merge_prevention():
    """测试防止合并超长句子"""
    print("🧪 测试场景合并防止机制")
    print("=" * 60)
    
    # 初始化
    config = ConfigManager()
    splitter = SceneSplitter(config, None, None)
    
    # 模拟有多个短句但合并后会超长的文案
    test_script = """第一句比较短。第二句也很短。第三句会让合并变得很长很长很长。第四句是正常长度。第五句稍长一些但还好。第六句又是一个很长很长的句子导致合并超限。第七句短。"""
    
    request = SceneSplitRequest(
        script_content=test_script,
        language="zh",
        use_coze_rules=True
    )
    
    print("测试文案:")
    print(test_script)
    print()
    
    # 先看看句子分割情况
    sentences = []
    current_sentence = ""
    
    for char in test_script:
        current_sentence += char
        if char in ['。', '！', '？']:
            if current_sentence.strip():
                sentences.append(current_sentence.strip())
            current_sentence = ""
    
    if current_sentence.strip():
        sentences.append(current_sentence.strip())
    
    print("句子分割:")
    for i, sentence in enumerate(sentences, 1):
        print(f"  {i}: {sentence} ({len(sentence)}字符)")
    print()
    
    # 模拟原逻辑(每2句一组)和新逻辑的对比
    print("模拟合并逻辑:")
    print("第一句单独 -> 场景1")
    remaining_sentences = sentences[1:]
    
    for i in range(0, len(remaining_sentences), 2):
        scene_sentences = remaining_sentences[i:i+2]
        scene_content = ''.join(scene_sentences)
        scene_num = i//2 + 2
        
        print(f"场景{scene_num}: {len(scene_content)}字符", end="")
        if len(scene_content) > 30 and len(scene_sentences) > 1:
            print(" 🔴 超长 -> 分离为两个场景")
            print(f"  → 场景{scene_num}A: {scene_sentences[0]} ({len(scene_sentences[0])}字符)")
            if len(scene_sentences) > 1:
                print(f"  → 场景{scene_num}B: {scene_sentences[1]} ({len(scene_sentences[1])}字符)")
        else:
            print(" 🟢 合适")
            print(f"  → 场景{scene_num}: {scene_content}")
    
    print()
    
    # 实际执行测试
    result = await splitter.split_scenes_async(request)
    
    print(f"实际分割结果: {len(result.scenes)}个场景")
    print("-" * 40)
    
    for i, scene in enumerate(result.scenes, 1):
        length = len(scene.content)
        status = "🔴 超长" if length > 30 else "🟡 偏长" if length > 20 else "🟢 合适"
        print(f"场景{i}: {length}字符 {status}")
        print(f"  内容: {scene.content}")
        print()

if __name__ == "__main__":
    asyncio.run(test_scene_merge_prevention())