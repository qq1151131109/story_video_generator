#!/usr/bin/env python3
"""
历史故事生成器 - 基础演示
仅使用本地模拟数据，不依赖API调用
"""

import sys
from pathlib import Path
import json
import time
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from utils.logger import setup_logging
from video.subtitle_processor import SubtitleProcessor, SubtitleProcessorRequest


def main():
    """主演示函数"""
    print("🎬 历史故事生成器 - 基础演示")
    print("=" * 50)
    
    # 初始化系统组件
    print("📋 初始化系统组件...")
    config = ConfigManager()
    file_manager = FileManager()
    setup_logging()
    
    subtitle_processor = SubtitleProcessor(config, file_manager)
    
    print("✅ 系统初始化完成")
    print()
    
    # 步骤1: 模拟生成历史故事内容
    print("🖋️  步骤1: 创建历史故事内容")
    print("-" * 30)
    
    theme = "诸葛亮草船借箭的智慧传说"
    language = "zh"
    
    print(f"主题: {theme}")
    print(f"语言: {language}")
    
    # 模拟的历史故事内容
    story_content = """三国时期，东吴水军强大，孙刘联军急需箭矢。诸葛亮向周瑜立下军令状，三日内造箭十万支。
众人皆疑其不可能，诸葛亮却胸有成竹。他命人准备二十条船，每船扎草人千余，披以青布。
第三日四更，江上大雾弥漫，诸葛亮率船队向曹营进发。擂鼓呐喊声起，曹军以为敌军来攻。
曹操令弓弩手万箭齐发，箭如雨下。待雾散日出，草人身上密密麻麻插满利箭。
诸葛亮大笑：谢丞相赐箭！掉头而去，十万支箭手到擒来。此乃智者借力打力，四两拨千斤之妙法也。"""
    
    print(f"📝 故事内容: {len(story_content)}字")
    print()
    
    # 显示故事内容
    print("📖 故事内容:")
    print("-" * 30)
    print(story_content)
    print()
    
    # 步骤2: 分割场景
    print("🎬 步骤2: 分割视频场景")
    print("-" * 30)
    
    # 手动分割场景
    scenes = [
        {
            "sequence": 1,
            "content": "三国时期，东吴水军强大，孙刘联军急需箭矢。",
            "subtitle_text": "三国时期，东吴水军强大，孙刘联军急需箭矢。",
            "duration_seconds": 4.0,
            "image_prompt": "古代战场，东吴水军船只，江面波涛，暮色苍茫"
        },
        {
            "sequence": 2,
            "content": "诸葛亮向周瑜立下军令状，三日内造箭十万支。",
            "subtitle_text": "诸葛亮向周瑜立下军令状，三日内造箭十万支。",
            "duration_seconds": 4.0,
            "image_prompt": "诸葛亮面对周瑜，军帐内，烛光摇曳，立下军令状"
        },
        {
            "sequence": 3,
            "content": "他命人准备二十条船，每船扎草人千余，披以青布。",
            "subtitle_text": "他命人准备二十条船，每船扎草人千余，披以青布。",
            "duration_seconds": 4.0,
            "image_prompt": "船工制作草人，江边船只，草人密布，青布飘扬"
        },
        {
            "sequence": 4,
            "content": "第三日四更，江上大雾弥漫，诸葛亮率船队向曹营进发。",
            "subtitle_text": "第三日四更，江上大雾弥漫，诸葛亮率船队向曹营进发。",
            "duration_seconds": 4.0,
            "image_prompt": "黎明前的江面，浓雾弥漫，船队在雾中前行，神秘气氛"
        },
        {
            "sequence": 5,
            "content": "擂鼓呐喊声起，曹军以为敌军来攻，万箭齐发如雨下。",
            "subtitle_text": "擂鼓呐喊声起，曹军以为敌军来攻，万箭齐发如雨下。",
            "duration_seconds": 4.0,
            "image_prompt": "曹营弓弩手射箭，箭如雨下，激烈的战斗场面"
        },
        {
            "sequence": 6,
            "content": "雾散日出，草人身上密密麻麻插满利箭，十万支箭手到擒来。",
            "subtitle_text": "雾散日出，草人身上密密麻麻插满利箭，十万支箭手到擒来。",
            "duration_seconds": 4.0,
            "image_prompt": "阳光照射下的草人，密密麻麻的箭矢，诸葛亮满意的笑容"
        }
    ]
    
    print(f"🎥 场景数量: {len(scenes)}")
    total_duration = sum(scene['duration_seconds'] for scene in scenes)
    print(f"⏱️  总时长: {total_duration:.1f}秒")
    print()
    
    # 显示场景信息
    print("📋 场景列表:")
    for scene in scenes:
        print(f"  场景{scene['sequence']}: {scene['content'][:30]}... ({scene['duration_seconds']}秒)")
    print()
    
    # 步骤3: 生成角色信息
    print("🎭 步骤3: 分析故事角色")
    print("-" * 30)
    
    characters = [
        {
            "name": "诸葛亮",
            "role": "主角",
            "description": "蜀汉丞相，智谋超群的军师",
            "appearance": "身着道袍，手持羽扇，面容睿智",
            "personality": "沉着冷静，足智多谋，胸有成竹",
            "image_prompt": "诸葛亮肖像，古代智者，手持羽扇，白色道袍，威严庄重"
        },
        {
            "name": "周瑜",
            "role": "配角",
            "description": "东吴大都督，英俊潇洒的将军",
            "appearance": "身着战袍，英姿飒爽，面貌英俊",
            "personality": "骄傲自负，才华横溢，心胸狭隘",
            "image_prompt": "周瑜肖像，东吴将军，英俊潇洒，红色战袍，威武庄严"
        },
        {
            "name": "曹操",
            "role": "反派",
            "description": "魏国丞相，奸诈多疑的枭雄",
            "appearance": "身着龙袍，面貌威严，目光锐利",
            "personality": "多疑谨慎，雄才大略，奸诈狡猾",
            "image_prompt": "曹操肖像，魏国丞相，威严霸气，黑色龙袍，锐利眼神"
        }
    ]
    
    print(f"👥 识别角色: {len(characters)}个")
    print(f"👑 主角: {characters[0]['name']}")
    
    for i, char in enumerate(characters, 1):
        print(f"  {i}. {char['name']} ({char['role']})")
    print()
    
    # 步骤4: 生成字幕
    print("📝 步骤4: 生成字幕文件")
    print("-" * 30)
    print("⏳ 正在生成字幕...")
    
    all_subtitle_segments = []
    current_time = 0.0
    
    for scene in scenes:
        subtitle_request = SubtitleProcessorRequest(
            text=scene['subtitle_text'],
            scene_duration=scene['duration_seconds'],
            language=language,
            max_line_length=25,
            style="main"
        )
        
        segments = subtitle_processor.process_subtitle(subtitle_request)
        for segment in segments:
            segment.start_time += current_time
            segment.end_time += current_time
            all_subtitle_segments.append(segment)
        
        current_time += scene['duration_seconds']
    
    # 保存字幕文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    subtitle_file = file_manager.get_output_path(
        'subtitles', 
        f"demo_basic_{timestamp}.srt"
    )
    
    saved_subtitle = subtitle_processor.save_subtitle_file(
        all_subtitle_segments, 
        subtitle_file, 
        format="srt"
    )
    
    print(f"✅ 字幕生成完成!")
    print(f"📝 字幕片段: {len(all_subtitle_segments)}个")
    print(f"💾 保存路径: {Path(saved_subtitle).name}")
    print()
    
    # 步骤5: 保存所有结果
    print("💾 步骤5: 保存生成结果")
    print("-" * 30)
    
    # 保存完整的故事数据
    story_data = {
        "story_info": {
            "theme": theme,
            "language": language,
            "generated_at": datetime.now().isoformat(),
            "total_duration": total_duration
        },
        "script": {
            "title": f"{theme}",
            "content": story_content,
            "word_count": len(story_content)
        },
        "characters": characters,
        "scenes": scenes,
        "subtitle_segments": [
            {
                "text": seg.text,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "duration": seg.duration
            }
            for seg in all_subtitle_segments
        ]
    }
    
    # 保存故事数据文件
    story_file = file_manager.get_output_path(
        'scripts',
        f"basic_demo_story_{timestamp}.json"
    )
    
    file_manager.save_json(story_data, story_file)
    print(f"📄 故事数据已保存: {Path(story_file).name}")
    
    # 保存图像提示词文件
    image_prompts = []
    for scene in scenes:
        image_prompts.append({
            "scene": scene['sequence'],
            "content": scene['content'],
            "image_prompt": scene['image_prompt']
        })
    
    # 添加角色图像提示词
    for char in characters:
        image_prompts.append({
            "type": "character",
            "name": char['name'],
            "image_prompt": char['image_prompt']
        })
    
    prompt_file = file_manager.get_output_path(
        'scripts',
        f"image_prompts_{timestamp}.json"
    )
    
    file_manager.save_json({"prompts": image_prompts}, prompt_file)
    print(f"🎨 图像提示词已保存: {Path(prompt_file).name}")
    
    # 保存制作指南
    production_guide = f"""# 历史故事视频制作指南

## 故事信息
- 主题: {theme}
- 语言: {language}
- 总时长: {total_duration}秒
- 场景数: {len(scenes)}个
- 角色数: {len(characters)}个

## 制作步骤

### 1. 图像生成
根据image_prompts文件中的提示词，为每个场景和角色生成对应图像：

""" + "\n".join([f"- 场景{scene['sequence']}: {scene['image_prompt']}" for scene in scenes]) + f"""

### 2. 音频制作
- 使用TTS软件将故事内容转换为音频
- 推荐使用悬疑解说音色
- 语速: 中等偏慢
- 添加适当的背景音乐

### 3. 字幕制作
- 使用生成的SRT字幕文件: {Path(saved_subtitle).name}
- 字幕样式: 白色字体，黑色边框
- 位置: 底部居中

### 4. 视频合成
1. 将每个场景图像设置为{scenes[0]['duration_seconds']}秒时长
2. 添加轻微的缩放动画效果
3. 导入音频文件作为背景音
4. 导入字幕文件并同步时间
5. 添加场景间的淡入淡出过渡效果

### 5. 后期处理
- 色调调整：偏暗色调，营造历史感
- 添加古典滤镜效果
- 调整音频音量平衡
- 输出高清视频文件

## 文件列表
- 故事数据: {Path(story_file).name}
- 图像提示词: {Path(prompt_file).name}
- 字幕文件: {Path(saved_subtitle).name}
"""
    
    guide_file = file_manager.get_output_path(
        'scripts',
        f"production_guide_{timestamp}.md"
    )
    
    with open(guide_file, 'w', encoding='utf-8') as f:
        f.write(production_guide)
    
    print(f"📋 制作指南已保存: {Path(guide_file).name}")
    
    # 最终总结
    print()
    print("📊 生成总结")
    print("=" * 50)
    print(f"🎯 故事主题: {theme}")
    print(f"📝 故事字数: {len(story_content)}")
    print(f"🎭 角色数量: {len(characters)}")
    print(f"🎬 场景数量: {len(scenes)}")
    print(f"⏱️  视频时长: {total_duration}秒")
    print(f"📝 字幕片段: {len(all_subtitle_segments)}")
    print()
    print("📁 生成的文件:")
    print(f"  📄 故事数据: {Path(story_file).name}")
    print(f"  🎨 图像提示词: {Path(prompt_file).name}")
    print(f"  📝 字幕文件: {Path(saved_subtitle).name}")
    print(f"  📋 制作指南: {Path(guide_file).name}")
    print()
    print("🎉 历史故事素材生成完成!")
    print("💡 提示:")
    print("  1. 查看制作指南了解如何制作视频")
    print("  2. 使用图像生成AI根据提示词创建场景图片")
    print("  3. 使用视频编辑软件合成最终视频")
    print("  4. 所有文件保存在output目录中")
    
    return True


if __name__ == "__main__":
    """运行演示"""
    print("🚀 开始运行历史故事基础演示...")
    print()
    
    # 运行主函数
    success = main()
    
    if success:
        print()
        print("✅ 演示运行成功!")
        sys.exit(0)
    else:
        print()
        print("❌ 演示运行失败!")
        sys.exit(1)