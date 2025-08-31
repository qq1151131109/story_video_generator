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
from content.theme_extractor import ThemeExtractor, ThemeExtractRequest
from media.image_generator import ImageGenerator, ImageGenerationRequest
from media.audio_generator import AudioGenerator, AudioGenerationRequest, GeneratedAudio
from media.character_image_generator import CharacterImageGenerator, CharacterImageRequest
from video.subtitle_processor import SubtitleProcessor, SubtitleRequest, SubtitleSegment
from video.title_subtitle_processor import TitleSubtitleProcessor, TitleSubtitleRequest
# 旧动画处理器已移除，演示改用增强动画处理器
from video.enhanced_animation_processor import EnhancedAnimationProcessor, AnimationRequest
from video.dual_image_compositor import DualImageCompositor, DualImageVideoRequest
from video.jianying_subtitle_renderer import JianyingSubtitleRenderer
from media.image_generator import GeneratedImage



class VideoComposer:
    """视频合成器 - 使用FFmpeg合成最终视频"""
    
    def __init__(self, config_manager: ConfigManager, file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.video')
        
        # 获取视频分辨率配置
        video_config = self.config.get_video_config()
        self.video_resolution = video_config.resolution
        self.width, self.height = map(int, self.video_resolution.split('x'))
        self.logger.info(f"Using video resolution: {self.video_resolution}")
        
        # 初始化剪映风格字幕渲染器
        self.jianying_renderer = JianyingSubtitleRenderer(config_manager, file_manager)
        
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
    
    def _create_fallback_video(self, temp_dir, scene_number, duration, scene_videos):
        """创建黑色背景的fallback视频"""
        fallback_video = temp_dir / f"scene_{scene_number}_fallback.mp4"
        cmd_fallback = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c=black:s={self.video_resolution}:d={duration}',
            '-pix_fmt', 'yuv420p',
            str(fallback_video)
        ]
        result = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result.returncode == 0:
            scene_videos.append(fallback_video)
            self.logger.info(f"Created fallback video {scene_number}: {fallback_video}")
        else:
            self.logger.error(f"Failed to create fallback video {scene_number}: {result.stderr}")
    
    def create_video(self, scenes, images, audio_file, subtitle_file, output_path, audio_duration=None, title_subtitle_file=None, use_jianying_style=True):
        """创建视频文件"""
        try:
            # 创建临时工作目录
            temp_dir = self.file_manager.get_output_path('temp', 'video_creation')
            temp_dir = Path(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 计算实际场景时长
            if audio_duration and audio_duration > 0:
                # 基于音频时长重新分配场景时长
                total_chars = sum(len(scene.content) for scene in scenes)
                actual_scene_durations = []
                
                for scene in scenes:
                    if total_chars > 0:
                        char_weight = len(scene.content) / total_chars
                        scene_duration = audio_duration * char_weight
                    else:
                        scene_duration = audio_duration / len(scenes)
                    actual_scene_durations.append(scene_duration)
                    
                self.logger.info(f"Using audio-based scene durations: {[f'{d:.1f}s' for d in actual_scene_durations]}")
            else:
                # 使用原始场景时长
                actual_scene_durations = [scene.duration_seconds for scene in scenes]
                self.logger.info("Using original scene durations")
            
            # 第1步: 为每个场景创建视频片段
            scene_videos = []
            for i, (scene, image, duration) in enumerate(zip(scenes, images, actual_scene_durations)):
                scene_video = temp_dir / f"scene_{i+1}.mp4"
                
                if image and image.file_path and Path(image.file_path).exists():
                    # 使用FFmpeg创建场景视频（图片+动画）- 根据配置分辨率
                    cmd = [
                        'ffmpeg', '-y',
                        '-loop', '1',
                        '-i', str(image.file_path),
                        '-filter_complex', 
                        f'scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,zoompan=z=\'min(zoom+0.0015,1.5)\':d={int(duration*30)}:s={self.video_resolution}',
                        '-t', str(duration),
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
                        # 图片处理失败，创建黑色背景备用视频
                        self._create_fallback_video(temp_dir, i+1, duration, scene_videos)
                else:
                    # 没有图片，直接创建黑色背景视频
                    self._create_fallback_video(temp_dir, i+1, duration, scene_videos)
            
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
            
            # 第3步: 添加音频（使用音频时长）
            video_with_audio = temp_dir / 'video_with_audio.mp4'
            if audio_file and Path(audio_file).exists():
                cmd_audio = [
                    'ffmpeg', '-y',
                    '-i', str(merged_video),
                    '-i', str(audio_file),
                    '-c:v', 'copy',
                    '-c:a', 'aac'
                ]
                
                # 如果提供了音频时长，使用音频时长；否则移除-shortest让FFmpeg自动处理
                if audio_duration and audio_duration > 0:
                    cmd_audio.extend(['-t', str(audio_duration)])
                
                cmd_audio.append(str(video_with_audio))
                
                result = subprocess.run(cmd_audio, capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info("Audio added successfully")
                else:
                    self.logger.warning(f"Failed to add audio: {result.stderr}")
                    shutil.copy(merged_video, video_with_audio)
            else:
                self.logger.info("No audio file, using silent video")
                shutil.copy(merged_video, video_with_audio)
            
            # 第4步: 添加字幕（剪映风格 vs 传统风格）
            if use_jianying_style and subtitle_file and Path(subtitle_file).exists():
                # 🎬 使用剪映风格硬编码字幕
                self.logger.info("Applying Jianying-style hard-coded subtitles...")
                success = self.jianying_renderer.apply_jianying_subtitles_to_video(
                    str(video_with_audio), 
                    str(subtitle_file), 
                    str(output_path)
                )
                
                if success:
                    self.logger.info("✅ Jianying-style subtitles applied successfully!")
                    style_info = self.jianying_renderer.get_style_info()
                    self.logger.info(f"Style features: {', '.join(style_info['features'])}")
                else:
                    self.logger.error("❌ Failed to apply Jianying-style subtitles, falling back to traditional style")
                    use_jianying_style = False  # 降级到传统方式
            
            if not use_jianying_style:
                # 🎞️ 传统字幕方式（软字幕）
                video_filters = []
                
                # 获取字幕配置
                subtitle_config = self.config.get('subtitle', {})
                main_font_size = subtitle_config.get('main_font_size', 10)
                title_font_size = subtitle_config.get('title_font_size', 40) 
                outline = subtitle_config.get('outline', 2)
                main_color = subtitle_config.get('main_color', '#FFFFFF').replace('#', '')
                border_color = subtitle_config.get('main_border_color', '#000000').replace('#', '')
                
                # 添加内容字幕
                if subtitle_file and Path(subtitle_file).exists():
                    subtitle_style = (f"FontSize={main_font_size},"
                                    f"PrimaryColour=&H{main_color},"
                                    f"OutlineColour=&H{border_color},"
                                    f"Outline={outline}")
                    video_filters.append(f"subtitles='{subtitle_file}':force_style='{subtitle_style}'")
                    self.logger.info(f"Traditional subtitle track added (FontSize={main_font_size})")
                
                # 添加标题字幕
                if title_subtitle_file and Path(title_subtitle_file).exists():
                    title_style = (f"FontSize={title_font_size},"
                                  f"PrimaryColour=&H{main_color},"
                                  f"OutlineColour=&H{border_color},"
                                  f"Outline={outline},"
                                  f"Alignment=2")
                    video_filters.append(f"subtitles='{title_subtitle_file}':force_style='{title_style}'")
                    self.logger.info(f"Traditional title track added (FontSize={title_font_size})")
                
                if video_filters:
                    # 应用传统字幕滤镜
                    filter_str = "[0:v]" + "[0:v]".join(video_filters) + "[v]"
                    
                    cmd_subtitle = [
                        'ffmpeg', '-y',
                        '-i', str(video_with_audio),
                        '-filter_complex', filter_str,
                        '-map', '[v]',
                        '-map', '0:a',
                        '-c:a', 'copy',
                        str(output_path)
                    ]
                    
                    result = subprocess.run(cmd_subtitle, capture_output=True, text=True)
                    if result.returncode == 0:
                        subtitle_count = len(video_filters)
                        self.logger.info(f"Traditional subtitles added successfully ({subtitle_count} tracks)")
                    else:
                        self.logger.warning(f"Failed to add traditional subtitles: {result.stderr}")
                        shutil.copy(video_with_audio, output_path)
                else:
                    self.logger.info("No subtitle files, copying video without subtitles")
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
    theme_extractor = ThemeExtractor(config, cache, file_manager)
    image_generator = ImageGenerator(config, cache, file_manager)
    character_image_generator = CharacterImageGenerator(config, cache, file_manager)
    audio_generator = AudioGenerator(config, cache, file_manager)
    subtitle_processor = SubtitleProcessor(config, file_manager)
    title_subtitle_processor = TitleSubtitleProcessor(file_manager)
    video_composer = VideoComposer(config, file_manager)
    dual_image_compositor = DualImageCompositor(config, file_manager)
    
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
        
        # 步骤1.5: 提取主题标题
        print("🏷️  步骤1.5: 提取主题标题")
        print("-" * 40)
        print("⏳ 正在提取核心主题...")
        
        theme_request = ThemeExtractRequest(
            content=script_result.content,
            language=language
        )
        
        theme_result = await theme_extractor.extract_theme_async(theme_request)
        
        if theme_result.success:
            print(f"✅ 主题提取完成! 标题: {theme_result.title}")
            extracted_title = theme_result.title
        else:
            print(f"❌ 主题提取失败: {theme_result.error_message}")
            print("⚠️  将使用默认标题")
            extracted_title = "历史"
        
        print()
        
        # 步骤2: 分割场景
        print("🎬 步骤2: 分割视频场景")
        print("-" * 40)
        print("⏳ 正在分割场景...")
        
        scene_request = SceneSplitRequest(
            script_content=script_result.content,
            language=language,
            use_coze_rules=True,  # 使用Coze工作流规则：第一句单独，后续每2句一段
            target_scene_count=4,  # 减少场景数以加快生成 (仅当use_coze_rules=False时使用)
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
        
        # 生成时间戳用于唯一标识
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        images = []
        for i, scene in enumerate(scene_result.scenes, 1):
            print(f"⏳ 正在生成场景{i}图像...")
            
            # 为每个场景生成唯一ID，确保不会重复使用缓存的图像
            scene_id = f"{theme.replace(' ', '_')}_{timestamp}_scene_{i}"
            
            image_request = ImageGenerationRequest(
                prompt=scene.image_prompt,
                style="古代历史",
                width=1024,
                height=768,
                scene_id=scene_id  # 添加场景唯一标识符
            )
            
            try:
                image_result = await image_generator.generate_image_async(image_request)
                if image_result and image_result.file_path:
                    images.append(image_result)
                    print(f"✅ 场景{i}图像生成成功: {Path(image_result.file_path).name}")
                else:
                    images.append(None)
                    print(f"❌ 场景{i}图像生成失败，将使用黑色背景")
            except Exception as e:
                print(f"❌ 场景{i}图像生成异常: {e}")
                images.append(None)
        
        print()
        
        # 步骤3.5: 生成主角图像（双重图像系统）
        print("👤 步骤3.5: 生成主角图像")
        print("-" * 40)
        print("⏳ 正在生成主角图像...")
        
        character_image_result = None
        try:
            character_request = CharacterImageRequest(
                story_content=script_result.content,
                language=language,
                style="ancient"
            )
            
            character_image_result = await character_image_generator.generate_character_image_async(character_request)
            
            if character_image_result and character_image_result.success:
                print(f"✅ 主角图像生成成功!")
                if character_image_result.original_image:
                    print(f"🎨 原始图像: {Path(character_image_result.original_image.file_path).name}")
                if character_image_result.cutout_result and character_image_result.cutout_result.success:
                    print(f"✂️  透明背景图: {Path(character_image_result.cutout_result.local_file_path).name}")
                    print("🎬 将使用双重图像系统合成视频")
                else:
                    print("⚠️  抠图处理失败，将使用单一场景图像")
            else:
                print(f"❌ 主角图像生成失败: {character_image_result.error_message if character_image_result else '未知错误'}")
                print("⚠️  将使用传统单图像模式")
        except Exception as e:
            print(f"❌ 主角图像生成异常: {e}")
            print("⚠️  将使用传统单图像模式")
        
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
        
        # 步骤5: 生成同步字幕
        print("📝 步骤5: 生成同步字幕文件")
        print("-" * 40)
        print("⏳ 正在生成同步字幕...")
        
        all_subtitle_segments = []
        
        # 检查是否有TTS返回的精确时间戳
        if audio_result and audio_result.subtitles:
            print(f"✅ 使用TTS返回的精确时间戳 ({len(audio_result.subtitles)}个字幕段)")
            all_subtitle_segments = []
            
            # 转换AudioSubtitle为SubtitleSegment
            for audio_sub in audio_result.subtitles:
                subtitle_segment = SubtitleSegment(
                    text=audio_sub.text,
                    start_time=audio_sub.start_time,
                    end_time=audio_sub.end_time,
                    duration=audio_sub.duration
                )
                all_subtitle_segments.append(subtitle_segment)
                
        else:
            # 使用基于音频时长的智能分配
            print("⚠️  TTS未返回时间戳，使用音频时长智能分配")
            
            if audio_result and audio_result.duration_seconds > 0:
                total_audio_duration = audio_result.duration_seconds
                print(f"📊 音频总时长: {total_audio_duration:.1f}秒")
            else:
                # 备用估算
                total_chars = sum(len(scene.content) for scene in scene_result.scenes)
                total_audio_duration = (total_chars / 5.0) / 1.0  # 估算语速
                print(f"⚠️  使用估算音频时长: {total_audio_duration:.1f}秒")
            
            # 基于文本权重分配时间
            total_chars = sum(len(scene.content) for scene in scene_result.scenes)
            current_time = 0.0
            
            for scene in scene_result.scenes:
                # 计算该场景的时长比例
                scene_char_weight = len(scene.content) / total_chars if total_chars > 0 else 1.0 / len(scene_result.scenes)
                scene_duration = total_audio_duration * scene_char_weight
                
                subtitle_request = SubtitleRequest(
                    text=scene.subtitle_text or scene.content,
                    scene_duration=scene_duration,  # 使用计算出的时长
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
        
        # 步骤5.5: 生成标题字幕
        print("🏷️  步骤5.5: 生成标题字幕")
        print("-" * 40)
        print("⏳ 正在生成标题字幕...")
        
        title_subtitle_request = TitleSubtitleRequest(
            title=extracted_title,
            display_duration=3.0,  # 开头显示3秒
            start_time=0.0,
            language=language
        )
        
        title_result = title_subtitle_processor.process_title_subtitle(title_subtitle_request)
        
        if title_result.success:
            # 保存标题字幕文件
            title_subtitle_file = file_manager.get_output_path(
                'subtitles', 
                f"title_{timestamp}.srt"
            )
            
            saved_title_subtitle = title_subtitle_processor.save_title_subtitle_file(
                title_result.title_segments,
                title_subtitle_file,
                format="srt"
            )
            
            print(f"✅ 标题字幕生成完成: {Path(saved_title_subtitle).name}")
            print(f"🏷️  标题文字: {extracted_title}")
        else:
            print(f"❌ 标题字幕生成失败: {title_result.error_message}")
            saved_title_subtitle = None
        
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
        audio_duration = audio_result.duration_seconds if audio_result else None
        
        # 根据是否有主角图像选择合成方式
        if (character_image_result and character_image_result.success and 
            character_image_result.cutout_result and character_image_result.cutout_result.success):
            # 使用双重图像系统合成
            print("🎬 使用双重图像系统进行视频合成...")
            
            dual_image_request = DualImageVideoRequest(
                scenes=scene_result.scenes,
                scene_images=images,
                character_image_result=character_image_result,
                audio_file=audio_file,
                subtitle_file=saved_subtitle,
                output_path=output_video,
                video_resolution=self.video_resolution,  # 从配置读取分辨率
                title_subtitle_file=saved_title_subtitle
            )
            
            try:
                dual_result = await dual_image_compositor.compose_dual_image_video_async(dual_image_request)
                if dual_result.success:
                    final_video = dual_result.output_video_path
                    print(f"✅ 双重图像视频合成成功!")
                    print(f"🎭 场景图像轨道: {len(images)}个背景图")
                    print(f"👤 主角图像轨道: 透明背景叠加")
                else:
                    raise Exception(dual_result.error_message)
            except Exception as e:
                print(f"❌ 双重图像合成失败: {e}")
                print("⚠️  回退到传统单图像模式")
                final_video = video_composer.create_video(
                    scenes=scene_result.scenes,
                    images=images,
                    audio_file=audio_file,
                    subtitle_file=saved_subtitle,
                    output_path=output_video,
                    audio_duration=audio_duration,
                    title_subtitle_file=saved_title_subtitle
                )
        else:
            # 使用传统单图像系统合成
            print("🎬 使用传统单图像系统进行视频合成...")
            final_video = video_composer.create_video(
                scenes=scene_result.scenes,
                images=images,
                audio_file=audio_file,
                subtitle_file=saved_subtitle,
                output_path=output_video,
                audio_duration=audio_duration,
                title_subtitle_file=saved_title_subtitle
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