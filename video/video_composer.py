"""
视频合成器 - 使用FFmpeg合成最终视频
专门负责将场景、图像、音频、字幕合成为完整的MP4视频
"""
import re
import subprocess
import shutil
import logging
from pathlib import Path
from typing import List, Optional

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from video.subtitle_engine import SubtitleEngine, SubtitleRequest
from video.enhanced_animation_processor import EnhancedAnimationProcessor, AnimationRequest


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
        
        # 初始化统一字幕引擎
        self.subtitle_engine = SubtitleEngine(config_manager, file_manager)
        
        # 初始化增强动画处理器
        self.animation_processor = EnhancedAnimationProcessor(config_manager)
        
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
    
    def create_video(self, scenes, images, audio_file, subtitle_file, output_path, 
                    audio_duration=None, title_subtitle_file=None, use_jianying_style=True):
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
                    # 🎬 使用增强动画处理器创建Ken Burns效果
                    animation_request = AnimationRequest(
                        image_path=str(image.file_path),
                        duration_seconds=duration,
                        animation_type="智能选择",
                        is_character=False
                    )
                    
                    # 创建Ken Burns动画
                    animation_clip = self.animation_processor.create_scene_animation(
                        animation_request, scene_index=i)
                    
                    # 生成增强版FFmpeg滤镜
                    animation_filter = self.animation_processor.generate_enhanced_ffmpeg_filter(
                        animation_clip, (self.width, self.height))
                    # 防御性检查：禁止旧表达式混入
                    if 't/' in animation_filter:
                        self.logger.warning(f"Detected legacy time-based expression in filter; falling back to basic filter for scene {i+1}")
                        animation_filter = f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2"
                    
                    self.logger.info(f"Scene {i+1}: Using {animation_clip.animation_type} animation")
                    
                    # 使用增强动画滤镜创建场景视频
                    cmd = [
                        'ffmpeg', '-y',
                        '-loop', '1',
                        '-i', str(image.file_path),
                        '-filter_complex', animation_filter,
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
            
            # 第4步: 使用统一字幕引擎添加字幕
            subtitle_applied = False
            
            if subtitle_file and Path(subtitle_file).exists():
                try:
                    # 🎯 使用统一字幕引擎
                    self.logger.info("Applying subtitles with unified subtitle engine...")
                    
                    # 从SRT文件加载字幕段落
                    subtitle_segments = self._load_subtitles_from_srt(subtitle_file)
                    
                    if subtitle_segments:
                        # 选择渲染风格
                        renderer_name = 'jianying' if use_jianying_style else 'traditional'
                        style_name = 'jianying' if use_jianying_style else 'main'
                        
                        # 使用统一引擎渲染
                        success = self.subtitle_engine.render_to_video(
                            str(video_with_audio),
                            subtitle_segments,
                            str(output_path),
                            renderer_name,
                            style_name
                        )
                        
                        if success:
                            self.logger.info(f"✅ Subtitles applied successfully with {renderer_name} renderer!")
                            subtitle_applied = True
                        else:
                            self.logger.warning(f"❌ Subtitle rendering failed with {renderer_name} renderer")
                    
                except Exception as e:
                    self.logger.error(f"Unified subtitle engine failed: {e}")
            
            # 添加标题字幕（如果有）
            if subtitle_applied and title_subtitle_file and Path(title_subtitle_file).exists():
                try:
                    self.logger.info("Adding title subtitles...")
                    # 标题字幕需要叠加到已有字幕视频上
                    temp_output = str(Path(output_path).with_suffix('.temp.mp4'))
                    
                    title_segments = self._load_subtitles_from_srt(title_subtitle_file)
                    if title_segments:
                        # 应用标题样式
                        for seg in title_segments:
                            seg.style = 'title'
                        
                        # 渲染标题字幕
                        title_success = self.subtitle_engine.render_to_video(
                            str(output_path),
                            title_segments, 
                            temp_output,
                            'jianying',  # 标题也使用剪映风格
                            'title'
                        )
                        
                        if title_success:
                            # 替换原文件
                            shutil.move(temp_output, output_path)
                            self.logger.info("Title subtitles added successfully")
                        else:
                            self.logger.warning("Failed to add title subtitles")
                            # 清理临时文件
                            if Path(temp_output).exists():
                                Path(temp_output).unlink()
                
                except Exception as e:
                    self.logger.error(f"Title subtitle processing failed: {e}")
            
            # 如果字幕处理失败，复制无字幕视频
            if not subtitle_applied:
                self.logger.info("No subtitles applied, copying video without subtitles")
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
    
    def _load_subtitles_from_srt(self, srt_file: str) -> List:
        """从SRT文件加载字幕段落"""
        try:
            # 导入统一字幕引擎的数据结构
            from video.subtitle_engine import SubtitleSegment
            
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析SRT格式
            srt_pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)\n\n'
            matches = re.findall(srt_pattern, content, re.DOTALL)
            
            segments = []
            for match in matches:
                sequence, start_time_str, end_time_str, text = match
                
                # 解析时间
                start_time = self._parse_srt_time(start_time_str)
                end_time = self._parse_srt_time(end_time_str)
                duration = end_time - start_time
                
                segment = SubtitleSegment(
                    text=text.strip(),
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration
                )
                segments.append(segment)
            
            self.logger.info(f"Loaded {len(segments)} subtitle segments from SRT")
            return segments
            
        except Exception as e:
            self.logger.error(f"Failed to load SRT file: {e}")
            return []
    
    def _parse_srt_time(self, time_str: str) -> float:
        """解析SRT时间格式为秒数"""
        # 格式: "00:02:30,500"
        time_parts = time_str.replace(',', '.').split(':')
        hours = int(time_parts[0])
        minutes = int(time_parts[1])
        seconds = float(time_parts[2])
        
        return hours * 3600 + minutes * 60 + seconds