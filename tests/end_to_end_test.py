#!/usr/bin/env python3
"""
端到端视频生成测试
输入：标题
输出：完整视频
"""

import asyncio
import sys
from pathlib import Path
import time
import json
import subprocess
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from tools.load_env import load_env_file
load_env_file()

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from utils.logger import setup_logging
from content.script_generator import ScriptGenerator, ScriptGenerationRequest
from content.scene_splitter import SceneSplitter, SceneSplitRequest
from media.image_generator import ImageGenerator, ImageGenerationRequest
from media.audio_generator import AudioGenerator, AudioGenerationRequest
from video.subtitle_processor import SubtitleProcessor, SubtitleRequest, SubtitleSegment
from video.video_composer import VideoComposer

async def generate_complete_video(title: str, language: str = "zh") -> bool:
    """
    完整视频生成流程
    
    Args:
        title: 视频标题/主题
        language: 语言代码 (zh/en/es)
    
    Returns:
        bool: 是否成功生成
    """
    print(f"🎬 端到端视频生成测试")
    print(f"📋 输入标题: {title}")
    print(f"🌍 语言: {language}")
    print("=" * 60)
    
    start_total_time = time.time()
    
    # 初始化组件
    print("📋 初始化系统组件...")
    config = ConfigManager()
    cache = CacheManager()
    file_manager = FileManager()
    setup_logging()
    
    script_generator = ScriptGenerator(config, cache, file_manager)
    scene_splitter = SceneSplitter(config, cache, file_manager)
    image_generator = ImageGenerator(config, cache, file_manager)
    audio_generator = AudioGenerator(config, cache, file_manager)
    subtitle_processor = SubtitleProcessor(config, file_manager)
    video_composer = VideoComposer(config, file_manager)
    
    print("✅ 系统初始化完成")
    print()
    
    try:
        # 步骤1: 生成文案
        print("🖋️ 步骤1: 生成历史故事文案")
        print("-" * 40)
        
        script_request = ScriptGenerationRequest(
            theme=title,
            language=language,
            style="horror",
            target_length=300,  # 减少长度加快生成
            include_title=True
        )
        
        print("⏳ 正在生成文案...")
        script_start = time.time()
        script_result = await script_generator.generate_script_async(script_request)
        script_time = time.time() - script_start
        
        print(f"✅ 文案生成完成! 耗时: {script_time:.1f}秒")
        print(f"📝 标题: {script_result.title}")
        print(f"📝 字数: {script_result.word_count}")
        print()
        
        # 步骤2: 分割场景
        print("🎬 步骤2: 分割视频场景")
        print("-" * 40)
        
        scene_request = SceneSplitRequest(
            script_content=script_result.content,
            language=language,
            target_scene_count=3,  # 减少场景数量
            scene_duration=6.0
        )
        
        print("⏳ 正在分割场景...")
        scene_start = time.time()
        scene_result = await scene_splitter.split_scenes_async(scene_request)
        scene_time = time.time() - scene_start
        
        print(f"✅ 场景分割完成! 耗时: {scene_time:.1f}秒")
        print(f"🎥 场景数量: {len(scene_result.scenes)}")
        print(f"⏱️ 总时长: {scene_result.total_duration}秒")
        print()
        
        # 步骤3: 并行生成图像
        print("🎨 步骤3: 生成场景图像")
        print("-" * 40)
        
        image_tasks = []
        for i, scene in enumerate(scene_result.scenes):
            image_request = ImageGenerationRequest(
                prompt=scene.image_prompt,
                style="古代历史",
                width=1024,
                height=768
            )
            task = image_generator.generate_image_async(image_request)
            image_tasks.append((i + 1, task))
        
        print("⏳ 正在并行生成所有场景图像...")
        image_start = time.time()
        
        images = []
        results = await asyncio.gather(*[task for _, task in image_tasks], return_exceptions=True)
        
        for i, (scene_num, result) in enumerate(zip([num for num, _ in image_tasks], results)):
            if isinstance(result, Exception):
                print(f"❌ 场景{scene_num}图像生成异常: {result}")
                images.append(None)
            elif result and result.file_path:
                print(f"✅ 场景{scene_num}图像生成成功: {Path(result.file_path).name}")
                images.append(result)
            else:
                print(f"⚠️ 场景{scene_num}图像生成失败，将使用黑色背景")
                images.append(None)
        
        image_time = time.time() - image_start
        successful_images = len([img for img in images if img])
        print(f"📊 图像生成完成! 耗时: {image_time:.1f}秒 (成功: {successful_images}/{len(images)})")
        print()
        
        # 步骤4: 生成音频
        print("🔊 步骤4: 生成语音音频")
        print("-" * 40)
        
        # 合并所有场景文本
        full_text = " ".join([scene.content for scene in scene_result.scenes])
        
        audio_request = AudioGenerationRequest(
            text=full_text,
            language=language,
            voice_style="悬疑解说",
            speed=1.0
        )
        
        print("⏳ 正在生成语音...")
        audio_start = time.time()
        audio_result = await audio_generator.generate_audio_async(audio_request)
        audio_time = time.time() - audio_start
        
        if audio_result and audio_result.file_path:
            print(f"✅ 音频生成成功! 耗时: {audio_time:.1f}秒")
            print(f"📊 音频时长: {audio_result.duration_seconds:.1f}秒")
            print(f"📁 文件: {Path(audio_result.file_path).name}")
        else:
            print("❌ 音频生成失败")
            return False
        print()
        
        # 步骤5: 生成字幕
        print("📝 步骤5: 生成同步字幕")
        print("-" * 40)
        
        all_subtitle_segments = []
        
        if audio_result.subtitles:
            print(f"✅ 使用TTS精确时间戳 ({len(audio_result.subtitles)}个片段)")
            for audio_sub in audio_result.subtitles:
                subtitle_segment = SubtitleSegment(
                    text=audio_sub.text,
                    start_time=audio_sub.start_time,
                    end_time=audio_sub.end_time,
                    duration=audio_sub.duration
                )
                all_subtitle_segments.append(subtitle_segment)
        else:
            print("⚠️ TTS未返回时间戳，使用音频时长智能分配")
            total_audio_duration = audio_result.duration_seconds
            total_chars = sum(len(scene.content) for scene in scene_result.scenes)
            current_time = 0.0
            
            for scene in scene_result.scenes:
                scene_char_weight = len(scene.content) / total_chars if total_chars > 0 else 1.0 / len(scene_result.scenes)
                scene_duration = total_audio_duration * scene_char_weight
                
                subtitle_request = SubtitleRequest(
                    text=scene.subtitle_text or scene.content,
                    scene_duration=scene_duration,
                    language=language,
                    max_line_length=20,
                    style="main"
                )
                
                segments = subtitle_processor.process_subtitle(subtitle_request)
                for segment in segments:
                    segment.start_time += current_time
                    segment.end_time += current_time
                    all_subtitle_segments.append(segment)
                
                current_time += scene_duration
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        subtitle_file = file_manager.get_output_path('subtitles', f'end_to_end_{timestamp}.srt')
        saved_subtitle = subtitle_processor.save_subtitle_file(all_subtitle_segments, subtitle_file)
        
        print(f"✅ 字幕生成完成: {Path(saved_subtitle).name} ({len(all_subtitle_segments)}段)")
        print()
        
        # 步骤6: 合成视频
        print("🎞️ 步骤6: 合成最终视频")
        print("-" * 40)
        
        output_video = file_manager.get_output_path('videos', f'end_to_end_{timestamp}.mp4')
        
        print("⏳ 正在合成视频...")
        video_start = time.time()
        final_video = video_composer.create_video(
            scenes=scene_result.scenes,
            images=images,
            audio_file=audio_result.file_path,
            subtitle_file=saved_subtitle,
            output_path=output_video,
            audio_duration=audio_result.duration_seconds
        )
        video_time = time.time() - video_start
        
        if final_video:
            print(f"✅ 视频合成成功! 耗时: {video_time:.1f}秒")
            print()
            
            # 获取视频详细信息
            try:
                result = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-print_format', 'json',
                    '-show_format', '-show_streams', str(final_video)
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    info = json.loads(result.stdout)
                    duration = float(info['format']['duration'])
                    file_size = int(info['format']['size']) / 1024 / 1024
                    
                    for stream in info['streams']:
                        if stream['codec_type'] == 'video':
                            width = stream.get('width')
                            height = stream.get('height')
                            fps = stream.get('r_frame_rate', 'Unknown')
                            break
                    
                    # 总结报告
                    total_time = time.time() - start_total_time
                    
                    print("🎉 端到端视频生成完成!")
                    print("=" * 60)
                    print(f"🎯 输入标题: {title}")
                    print(f"📝 生成标题: {script_result.title}")
                    print(f"📹 视频文件: {Path(final_video).name}")
                    print(f"📁 保存位置: {final_video}")
                    print(f"⏱️ 视频时长: {duration:.1f}秒")
                    print(f"📺 分辨率: {width}x{height}")
                    print(f"🎬 帧率: {fps}")
                    print(f"💾 文件大小: {file_size:.1f}MB")
                    print(f"🎥 场景数: {len(scene_result.scenes)}")
                    print(f"🖼️ 图像: {successful_images}/{len(images)}")
                    print(f"🔊 音频: ✅ ({audio_result.duration_seconds:.1f}秒)")
                    print(f"📝 字幕: ✅ ({len(all_subtitle_segments)}段)")
                    print(f"⏳ 总耗时: {total_time:.1f}秒")
                    print(f"   📝 文案: {script_time:.1f}秒")
                    print(f"   🎬 场景: {scene_time:.1f}秒")  
                    print(f"   🎨 图像: {image_time:.1f}秒")
                    print(f"   🔊 音频: {audio_time:.1f}秒")
                    print(f"   🎞️ 合成: {video_time:.1f}秒")
                    print()
                    
                    return True
            
            except Exception as e:
                print(f"⚠️ 无法获取视频信息: {e}")
                print(f"🎉 视频生成成功: {final_video}")
                return True
        else:
            print("❌ 视频合成失败")
            return False
            
    except Exception as e:
        print(f"❌ 生成过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    if len(sys.argv) > 1:
        title = sys.argv[1]
    else:
        title = "明朝东厂与西厂的权力斗争"
    
    language = sys.argv[2] if len(sys.argv) > 2 else "zh"
    
    success = await generate_complete_video(title, language)
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("✅ 端到端测试成功!")
        sys.exit(0)
    else:
        print("❌ 端到端测试失败!")
        sys.exit(1)