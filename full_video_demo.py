#!/usr/bin/env python3
"""
历史故事生成器 - 完整视频生成演示
这个脚本真正生成一个完整的MP4视频文件
"""

import asyncio
import sys
from pathlib import Path
import json
import time
import subprocess
import shutil
import logging
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from load_env import load_env_file
load_env_file()

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from utils.logger import setup_logging
from content.script_generator import ScriptGenerator, ScriptGenerationRequest
from content.scene_splitter import SceneSplitter, SceneSplitRequest
from content.character_analyzer import CharacterAnalyzer, CharacterAnalysisRequest
from media.image_generator import ImageGenerator, ImageGenerationRequest
from media.audio_generator import AudioGenerator, AudioGenerationRequest, GeneratedAudio
from video.subtitle_processor import SubtitleProcessor, SubtitleRequest
from video.animation_processor import AnimationProcessor, AnimationRequest
from media.image_generator import GeneratedImage



class VideoComposer:
    """视频合成器 - 使用FFmpeg合成最终视频"""
    
    def __init__(self, config_manager: ConfigManager, file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('video_composer')
        
        # 检查FFmpeg是否可用
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """检查FFmpeg是否可用"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            self.logger.info("FFmpeg is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error("FFmpeg not found. Please install FFmpeg first.")
            self.logger.info("Install guide: https://ffmpeg.org/download.html")
    
    def create_video(self, scenes, images, audio_file, subtitle_file, output_path):
        """创建视频文件"""
        try:
            # 创建临时工作目录
            temp_dir = self.file_manager.get_output_path('temp', 'video_creation')
            temp_dir = Path(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 第1步: 为每个场景创建视频片段
            scene_videos = []
            for i, (scene, image) in enumerate(zip(scenes, images)):
                if image and image.file_path and Path(image.file_path).exists():
                    scene_video = temp_dir / f"scene_{i+1}.mp4"
                    
                    # 使用FFmpeg创建场景视频（图片+动画）
                    cmd = [
                        'ffmpeg', '-y',
                        '-loop', '1',
                        '-i', str(image.file_path),
                        '-filter_complex', 
                        f'scale=1440:1080:force_original_aspect_ratio=decrease,pad=1440:1080:(ow-iw)/2:(oh-ih)/2,zoompan=z=\'min(zoom+0.0015,1.5)\':d={int(scene.duration_seconds*30)}:s=1440x1080',
                        '-t', str(scene.duration_seconds),
                        '-pix_fmt', 'yuv420p',
                        '-r', '30',
                        str(scene_video)
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        scene_videos.append(scene_video)
                        self.logger.info(f"Created scene video {i+1}: {scene_video}")
                    else:
                        self.logger.error(f"Failed to create scene video {i+1}: {result.stderr}")
                        # 创建黑色背景的备用视频
                        fallback_video = temp_dir / f"scene_{i+1}_fallback.mp4"
                        cmd_fallback = [
                            'ffmpeg', '-y',
                            '-f', 'lavfi',
                            '-i', f'color=c=black:s=1440x1080:d={scene.duration_seconds}',
                            '-pix_fmt', 'yuv420p',
                            str(fallback_video)
                        ]
                        subprocess.run(cmd_fallback, capture_output=True)
                        scene_videos.append(fallback_video)
            
            if not scene_videos:
                self.logger.error("No scene videos created")
                return None
            
            # 第2步: 拼接所有场景视频
            concat_file = temp_dir / 'concat_list.txt'
            with open(concat_file, 'w') as f:
                for video in scene_videos:
                    f.write(f"file '{video.absolute()}'\n")
            
            merged_video = temp_dir / 'merged_video.mp4'
            cmd_concat = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                str(merged_video)
            ]
            
            result = subprocess.run(cmd_concat, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"Failed to merge videos: {result.stderr}")
                return None
            
            # 第3步: 添加音频
            video_with_audio = temp_dir / 'video_with_audio.mp4'
            if audio_file and Path(audio_file).exists():
                cmd_audio = [
                    'ffmpeg', '-y',
                    '-i', str(merged_video),
                    '-i', str(audio_file),
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-shortest',
                    str(video_with_audio)
                ]
                
                result = subprocess.run(cmd_audio, capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info("Audio added successfully")
                else:
                    self.logger.warning(f"Failed to add audio: {result.stderr}")
                    shutil.copy(merged_video, video_with_audio)
            else:
                self.logger.info("No audio file, using silent video")
                shutil.copy(merged_video, video_with_audio)
            
            # 第4步: 添加字幕
            if subtitle_file and Path(subtitle_file).exists():
                cmd_subtitle = [
                    'ffmpeg', '-y',
                    '-i', str(video_with_audio),
                    '-vf', f"subtitles='{subtitle_file}':force_style='FontSize=24,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2'",
                    '-c:a', 'copy',
                    str(output_path)
                ]
                
                result = subprocess.run(cmd_subtitle, capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info("Subtitles added successfully")
                else:
                    self.logger.warning(f"Failed to add subtitles: {result.stderr}")
                    shutil.copy(video_with_audio, output_path)
            else:
                self.logger.info("No subtitle file, copying video without subtitles")
                shutil.copy(video_with_audio, output_path)
            
            # 清理临时文件
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                self.logger.warning(f"Failed to clean temp directory: {e}")
            
            if Path(output_path).exists():
                file_size = Path(output_path).stat().st_size / 1024 / 1024  # MB
                self.logger.info(f"Video created successfully: {output_path} ({file_size:.1f} MB)")
                return str(output_path)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Video creation failed: {e}")
            import traceback
            traceback.print_exc()
            return None


async def main():
    """主演示函数"""
    print("🎬 历史故事生成器 - 完整视频生成演示")
    print("=" * 60)
    
    # 初始化系统组件
    print("📋 初始化系统组件...")
    config = ConfigManager()
    cache = CacheManager()
    file_manager = FileManager()
    setup_logging()
    
    # 初始化生成器
    script_generator = ScriptGenerator(config, cache, file_manager)
    scene_splitter = SceneSplitter(config, cache, file_manager)
    character_analyzer = CharacterAnalyzer(config, cache, file_manager)
    image_generator = ImageGenerator(config, cache, file_manager)
    audio_generator = AudioGenerator(config, cache, file_manager)
    subtitle_processor = SubtitleProcessor(config, file_manager)
    video_composer = VideoComposer(config, file_manager)
    
    print("✅ 系统初始化完成")
    print()
    
    # 步骤1: 生成历史故事文案
    print("🖋️  步骤1: 生成历史故事文案")
    print("-" * 40)
    
    theme = "秦始皇焚书坑儒的历史真相"
    language = "zh"
    
    print(f"主题: {theme}")
    print(f"语言: {language}")
    print("⏳ 正在生成文案...")
    
    script_request = ScriptGenerationRequest(
        theme=theme,
        language=language,
        style="horror",
        target_length=400,
        include_title=True
    )
    
    try:
        start_time = time.time()
        
        # 生成文案
        script_result = await script_generator.generate_script_async(script_request)
        script_time = time.time() - start_time
        
        print(f"✅ 文案生成完成! 耗时: {script_time:.2f}秒")
        print(f"📝 标题: {script_result.title}")
        print(f"📝 字数: {script_result.word_count}")
        print()
        
        # 步骤2: 分割场景
        print("🎬 步骤2: 分割视频场景")
        print("-" * 40)
        print("⏳ 正在分割场景...")
        
        scene_request = SceneSplitRequest(
            script_content=script_result.content,
            language=language,
            target_scene_count=4,  # 减少场景数以加快生成
            scene_duration=5.0
        )
        
        scene_result = await scene_splitter.split_scenes_async(scene_request)
        
        print(f"✅ 场景分割完成!")
        print(f"🎥 场景数量: {len(scene_result.scenes)}")
        print(f"⏱️  总时长: {scene_result.total_duration:.1f}秒")
        print()
        
        # 步骤3: 生成图像
        print("🎨 步骤3: 生成场景图像")
        print("-" * 40)
        
        images = []
        for i, scene in enumerate(scene_result.scenes, 1):
            print(f"⏳ 正在生成场景{i}图像...")
            
            image_request = ImageGenerationRequest(
                prompt=scene.image_prompt,
                style="古代历史",
                width=1024,
                height=768
            )
            
            try:
                image_result = await image_generator.generate_image_async(image_request)
                if image_result and image_result.file_path:
                    images.append(image_result)
                    print(f"✅ 场景{i}图像生成成功: {image_result.file_path}")
                else:
                    images.append(None)
                    print(f"❌ 场景{i}图像生成失败，将使用黑色背景")
            except Exception as e:
                print(f"❌ 场景{i}图像生成失败: {e}")
                images.append(None)
        
        print()
        
        # 步骤4: 生成音频
        print("🔊 步骤4: 生成语音音频")
        print("-" * 40)
        print("⏳ 正在生成语音...")
        
        # 合并所有场景文本作为完整音频
        full_text = " ".join([scene.content for scene in scene_result.scenes])
        
        audio_request = AudioGenerationRequest(
            text=full_text,
            language=language,
            voice_style="悬疑解说",
            speed=1.0
        )
        
        audio_result = None
        try:
            audio_result = await audio_generator.generate_audio_async(audio_request)
            if audio_result and audio_result.file_path:
                print(f"✅ 音频生成成功: {Path(audio_result.file_path).name}")
            else:
                print("❌ 音频生成失败，将生成无声视频")
        except Exception as e:
            print(f"❌ 音频生成失败: {e}")
        
        print()
        
        # 步骤5: 生成字幕
        print("📝 步骤5: 生成字幕文件")
        print("-" * 40)
        print("⏳ 正在生成字幕...")
        
        all_subtitle_segments = []
        current_time = 0.0
        
        for scene in scene_result.scenes:
            subtitle_request = SubtitleRequest(
                text=scene.subtitle_text or scene.content,
                scene_duration=scene.duration_seconds,
                language=language,
                max_line_length=20,
                style="main"
            )
            
            segments = subtitle_processor.process_subtitle(subtitle_request)
            for segment in segments:
                segment.start_time += current_time
                segment.end_time += current_time
                all_subtitle_segments.append(segment)
            
            current_time += scene.duration_seconds
        
        # 保存字幕文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        subtitle_file = file_manager.get_output_path(
            'subtitles', 
            f"full_demo_{timestamp}.srt"
        )
        
        saved_subtitle = subtitle_processor.save_subtitle_file(
            all_subtitle_segments, 
            subtitle_file, 
            format="srt"
        )
        
        print(f"✅ 字幕生成完成: {Path(saved_subtitle).name}")
        print()
        
        # 步骤6: 合成最终视频
        print("🎞️  步骤6: 合成最终视频")
        print("-" * 40)
        print("⏳ 正在合成视频...")
        
        output_video = file_manager.get_output_path(
            'videos',
            f"story_video_{timestamp}.mp4"
        )
        
        audio_file = audio_result.file_path if audio_result else None
        
        final_video = video_composer.create_video(
            scenes=scene_result.scenes,
            images=images,
            audio_file=audio_file,
            subtitle_file=saved_subtitle,
            output_path=output_video
        )
        
        if final_video:
            print(f"🎉 视频生成成功!")
            print(f"📹 视频文件: {Path(final_video).name}")
            print(f"📁 保存位置: {final_video}")
            
            # 获取视频信息
            try:
                result = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                    '-show_format', '-show_streams', str(final_video)
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    info = json.loads(result.stdout)
                    duration = float(info['format']['duration'])
                    file_size = int(info['format']['size']) / 1024 / 1024
                    
                    print(f"⏱️  视频时长: {duration:.1f}秒")
                    print(f"💾 文件大小: {file_size:.1f} MB")
                    
                    # 查找视频流信息
                    for stream in info['streams']:
                        if stream['codec_type'] == 'video':
                            width = stream.get('width', 'Unknown')
                            height = stream.get('height', 'Unknown') 
                            fps = stream.get('r_frame_rate', 'Unknown')
                            print(f"📺 分辨率: {width}x{height}")
                            print(f"🎬 帧率: {fps}")
                            break
            except:
                pass
            
            # 生成最终报告
            print()
            print("📊 生成总结报告")
            print("=" * 60)
            
            total_time = time.time() - start_time
            
            report = {
                "video_info": {
                    "theme": theme,
                    "language": language,
                    "generated_at": datetime.now().isoformat(),
                    "total_generation_time": total_time,
                    "video_file": str(final_video)
                },
                "content": {
                    "title": script_result.title,
                    "word_count": script_result.word_count,
                    "scene_count": len(scene_result.scenes),
                    "total_duration": scene_result.total_duration
                },
                "media": {
                    "images_generated": len([img for img in images if img]),
                    "audio_generated": audio_result is not None,
                    "subtitle_segments": len(all_subtitle_segments)
                }
            }
            
            report_file = file_manager.get_output_path(
                'scripts',
                f"video_report_{timestamp}.json"
            )
            
            file_manager.save_json(report, report_file)
            
            print(f"🎯 主题: {theme}")
            print(f"📝 标题: {script_result.title}")
            print(f"⏱️  时长: {scene_result.total_duration}秒")
            print(f"🎥 场景: {len(scene_result.scenes)}个")
            print(f"🖼️  图像: {len([img for img in images if img])}/{len(images)}")
            print(f"🔊 音频: {'✅' if audio_result else '❌'}")
            print(f"📝 字幕: {len(all_subtitle_segments)}段")
            print(f"⏳ 总耗时: {total_time:.1f}秒")
            print()
            print(f"🎉 完整历史故事视频已生成完成!")
            print(f"📹 视频文件: {Path(final_video).name}")
            print(f"📄 详细报告: {Path(report_file).name}")
            
            return True
        else:
            print("❌ 视频合成失败")
            return False
            
    except Exception as e:
        print(f"❌ 生成过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    """运行完整视频生成演示"""
    print("🚀 开始运行完整历史故事视频生成...")
    print()
    
    # 运行异步主函数
    success = asyncio.run(main())
    
    if success:
        print()
        print("✅ 完整视频生成成功!")
        sys.exit(0)
    else:
        print()
        print("❌ 视频生成失败!")
        sys.exit(1)