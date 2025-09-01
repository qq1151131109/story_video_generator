"""
视频合成器 - 使用FFmpeg合成最终视频
专门负责将场景、图像、音频、字幕合成为完整的MP4视频
支持传统动画和图生视频双模式
"""
import re
import subprocess
import shutil
import logging
import asyncio
from pathlib import Path
from typing import List, Optional

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from video.subtitle_engine import SubtitleEngine, SubtitleRequest
from video.enhanced_animation_processor import EnhancedAnimationProcessor, AnimationRequest
from media.image_to_video_generator import ImageToVideoGenerator, ImageToVideoRequest


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
        
        # 初始化图生视频生成器
        self.i2v_generator = ImageToVideoGenerator(config_manager, file_manager)
        
        # 获取动画策略配置
        self.animation_strategy = self.config.get('video.animation_strategy', 'traditional')
        self.i2v_config = self.config.get('video.image_to_video', {})
        
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
    
    def _should_use_i2v_for_scene(self, scene, scene_index: int) -> bool:
        """
        判断某个场景是否应该使用图生视频
        
        Args:
            scene: 场景对象
            scene_index: 场景索引
        
        Returns:
            bool: 是否使用图生视频
        """
        if not self.i2v_config.get('enabled', False):
            return False
        
        # 简化为二选一模式
        return self.animation_strategy == 'image_to_video'
    
    async def _create_i2v_scene_video(self, scene, image, duration: float, scene_index: int, temp_dir: Path) -> Optional[Path]:
        """
        创建图生视频场景视频
        
        Args:
            scene: 场景对象
            image: 图像对象
            duration: 场景时长
            scene_index: 场景索引
            temp_dir: 临时目录
        
        Returns:
            Optional[Path]: 生成的视频文件路径
        """
        try:
            self.logger.info(f"Scene {scene_index+1}: Using image-to-video generation")
            
            # 构建图生视频请求
            i2v_request = ImageToVideoRequest(
                image_path=str(image.file_path),
                desc_prompt=scene.image_prompt or scene.content,  # 使用场景的图像提示词
                duration_seconds=duration,
                width=720,  # 直接使用目标视频分辨率
                height=1280
            )
            
            # 生成图生视频
            i2v_result = await self.i2v_generator.generate_video_async(i2v_request)
            
            # 将生成的视频复制到临时目录（标准化文件名）
            scene_video = temp_dir / f"scene_{scene_index+1}.mp4"
            
            # 如果需要调整时长，使用FFmpeg裁剪
            if abs(duration - i2v_result.duration_seconds) > 0.1:  # 超过0.1秒差异需要调整
                self.logger.info(f"Adjusting I2V video duration: {i2v_result.duration_seconds}s -> {duration}s")
                
                cmd = [
                    'ffmpeg', '-y',
                    '-i', i2v_result.video_path,
                    '-t', str(duration),
                    '-c', 'copy',  # 不重新编码，直接裁剪
                    str(scene_video)
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    self.logger.warning(f"Failed to adjust I2V video duration: {result.stderr}")
                    # 使用原始视频
                    shutil.copy(i2v_result.video_path, scene_video)
            else:
                # 直接复制
                shutil.copy(i2v_result.video_path, scene_video)
            
            self.logger.info(f"I2V scene video created: {scene_video}")
            return scene_video
            
        except Exception as e:
            self.logger.error(f"I2V generation failed for scene {scene_index+1}: {e}")
            
            # 图生视频失败，抛出异常
            raise
    
    def _create_traditional_scene_video(self, scene, image, duration: float, scene_index: int, temp_dir: Path) -> Optional[Path]:
        """
        创建传统动画场景视频
        
        Args:
            scene: 场景对象
            image: 图像对象  
            duration: 场景时长
            scene_index: 场景索引
            temp_dir: 临时目录
        
        Returns:
            Optional[Path]: 生成的视频文件路径
        """
        scene_video = temp_dir / f"scene_{scene_index+1}.mp4"
        
        try:
            # 🎬 使用增强动画处理器创建Ken Burns效果
            animation_request = AnimationRequest(
                image_path=str(image.file_path),
                duration_seconds=duration,
                animation_type="智能选择",
                is_character=False
            )
            
            # 创建Ken Burns动画
            animation_clip = self.animation_processor.create_scene_animation(
                animation_request, scene_index=scene_index)
            
            # 生成增强版FFmpeg滤镜
            animation_filter = self.animation_processor.generate_enhanced_ffmpeg_filter(
                animation_clip, (self.width, self.height))
            
            # 防御性检查：禁止旧表达式混入
            if 't/' in animation_filter:
                self.logger.warning(f"Detected legacy time-based expression in filter; falling back to basic filter for scene {scene_index+1}")
                animation_filter = f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2"
            
            self.logger.info(f"Scene {scene_index+1}: Using {animation_clip.animation_type} traditional animation")
            
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
                self.logger.info(f"Created traditional scene video {scene_index+1}: {scene_video}")
                return scene_video
            else:
                self.logger.error(f"Failed to create traditional scene video {scene_index+1}: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"Traditional animation failed for scene {scene_index+1}: {e}")
            return None
    
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
    
    async def create_video(self, scenes, images, audio_file, subtitle_file, output_path, 
                    audio_duration=None, title_subtitle_file=None, use_jianying_style=True):
        """创建视频文件"""
        try:
            # 创建唯一临时工作目录（避免并发冲突）
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            temp_dir = self.file_manager.get_output_path('temp', f'video_creation_{unique_id}')
            temp_dir = Path(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created unique temp directory: {temp_dir}")
            
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
            
            # 第1步: 为每个场景创建视频片段（支持双模式）
            scene_videos = []
            
            # 混合异步/同步处理：图生视频用异步，传统动画用同步
            for i, (scene, image, duration) in enumerate(zip(scenes, images, actual_scene_durations)):
                if image and image.file_path and Path(image.file_path).exists():
                    # 判断使用哪种动画模式
                    use_i2v = self._should_use_i2v_for_scene(scene, i)
                    
                    if use_i2v:
                        # 图生视频模式（异步）
                        scene_video = await self._create_i2v_scene_video(scene, image, duration, i, temp_dir)
                        if scene_video and scene_video.exists():
                            scene_videos.append(scene_video)
                        else:
                            raise Exception(f"Failed to generate I2V video for scene {i+1}")
                    else:
                        # 传统动画模式（同步）
                        scene_video = self._create_traditional_scene_video(scene, image, duration, i, temp_dir)
                        if scene_video and scene_video.exists():
                            scene_videos.append(scene_video)
                        else:
                            self.logger.error(f"Traditional animation failed for scene {i+1}, creating fallback")
                            self._create_fallback_video(temp_dir, i+1, duration, scene_videos)
                else:
                    # 没有图片，直接创建黑色背景视频
                    self.logger.warning(f"No image for scene {i+1}, creating fallback video")
                    self._create_fallback_video(temp_dir, i+1, duration, scene_videos)
            
            if not scene_videos:
                self.logger.error("No scene videos created")
                return None
            
            # 第2步: 统一编码参数后拼接场景视频
            self.logger.info("Normalizing video segments for consistent encoding...")
            
            # 先将所有片段重编码为统一参数
            normalized_videos = []
            for i, video in enumerate(scene_videos):
                normalized_video = temp_dir / f'normalized_scene_{i+1}.mp4'
                cmd_normalize = [
                    'ffmpeg', '-y',
                    '-i', str(video),
                    '-r', '30',  # 统一帧率
                    '-pix_fmt', 'yuv420p',  # 统一像素格式
                    '-c:v', 'libx264',  # 统一编码器
                    '-crf', '20',  # 统一质量
                    '-preset', 'medium',  # 编码速度
                    str(normalized_video)
                ]
                
                result = subprocess.run(cmd_normalize, capture_output=True, text=True)
                if result.returncode == 0:
                    normalized_videos.append(normalized_video)
                    self.logger.debug(f"Normalized scene {i+1} video")
                else:
                    self.logger.error(f"Failed to normalize scene {i+1} video: {result.stderr}")
                    return None
            
            # 拼接标准化后的视频
            concat_file = temp_dir / 'concat_list.txt'
            with open(concat_file, 'w') as f:
                for video in normalized_videos:
                    f.write(f"file '{video.absolute()}'\n")
            
            merged_video = temp_dir / 'merged_video.mp4'
            cmd_concat = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',  # 现在可以安全使用copy，因为参数已统一
                str(merged_video)
            ]
            
            result = subprocess.run(cmd_concat, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"Failed to merge normalized videos: {result.stderr}")
                return None
            
            # 第3步: 添加音频（使用音频时长）
            video_with_audio = temp_dir / 'video_with_audio.mp4'
            if audio_file and Path(audio_file).exists():
                cmd_audio = [
                    'ffmpeg', '-y',
                    '-i', str(merged_video),
                    '-i', str(audio_file),
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-shortest',  # 使用较短的流长度，避免音视频不同步
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
    
    def create_video_sync(self, scenes, images, audio_file, subtitle_file, output_path, 
                         audio_duration=None, title_subtitle_file=None, use_jianying_style=True):
        """
        同步创建视频（对异步方法的包装）
        
        保持向后兼容性
        """
        return asyncio.run(self.create_video(
            scenes, images, audio_file, subtitle_file, output_path,
            audio_duration, title_subtitle_file, use_jianying_style
        ))