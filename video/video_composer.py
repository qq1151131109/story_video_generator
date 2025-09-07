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
                image_prompt=scene.image_prompt or scene.content,  # 使用场景的图像提示词
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
                    audio_duration=None, title_subtitle_file=None, use_jianying_style=True,
                    character_images=None, integrated_mode=False):
        """创建视频文件 - 支持一体化模式（预生成视频+角色图像）"""
        try:
            # 创建唯一临时工作目录（避免并发冲突）
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            temp_dir = self.file_manager.get_output_path('temp', f'video_creation_{unique_id}')
            temp_dir = Path(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created unique temp directory: {temp_dir}")
            
            # 一体化模式处理：images参数包含预生成的视频文件
            if integrated_mode:
                self.logger.info("🎬 使用一体化模式：角色图像+预生成场景视频")
                return await self._create_video_integrated_mode(
                    scenes, images, character_images, audio_file, subtitle_file, 
                    output_path, temp_dir, audio_duration, use_jianying_style
                )
            
            # 传统模式处理
            self.logger.info("🎬 使用传统模式：图像生成+动画处理")
            
            # ❌ 错误的逻辑：没有音频应该报错，而不是使用默认时长
            if not audio_duration or audio_duration <= 0:
                raise ValueError("❌ 音频文件是必需的！原始Coze工作流要求按音频片段时长分配场景时长，没有音频无法正确生成视频。")
            
            # TODO: 🚧 当前是错误的按总音频时长+字符占比分配的逻辑
            # 正确的逻辑应该是：按每个音频片段的实际时长分配对应场景的时长
            # 需要从音频生成阶段获取每个音频片段的duration_list
            
            # 临时使用字符占比分配（待重构为按音频片段时长分配）
            total_chars = sum(len(scene.content) for scene in scenes)
            actual_scene_durations = []
            
            for scene in scenes:
                if total_chars > 0:
                    char_weight = len(scene.content) / total_chars
                    scene_duration = audio_duration * char_weight
                else:
                    scene_duration = audio_duration / len(scenes)
                actual_scene_durations.append(scene_duration)
                
            self.logger.warning(f"⚠️  当前使用临时的字符占比分配: {[f'{d:.1f}s' for d in actual_scene_durations]}")
            self.logger.warning("🚧 需要重构为按音频片段时长分配的正确逻辑")
            
            # 第1步: 为每个场景创建视频片段（支持双模式）
            scene_videos = []
            
            # 混合异步/同步处理：图生视频用异步，传统动画用同步 - 每个场景支持重试
            for i, (scene, image, duration) in enumerate(zip(scenes, images, actual_scene_durations)):
                scene_video = None
                max_scene_retries = 3  # 每个场景最多重试3次
                
                for attempt in range(max_scene_retries):
                    try:
                        if image and image.file_path and Path(image.file_path).exists():
                            # 判断使用哪种动画模式
                            use_i2v = self._should_use_i2v_for_scene(scene, i)
                            
                            if use_i2v:
                                # 图生视频模式（异步） - 依赖重试机制
                                if attempt > 0:
                                    self.logger.info(f"🔄 Retrying I2V for scene {i+1}, attempt {attempt + 1}")
                                scene_video = await self._create_i2v_scene_video(scene, image, duration, i, temp_dir)
                                if scene_video and scene_video.exists():
                                    scene_videos.append(scene_video)
                                    self.logger.info(f"✅ I2V video created for scene {i+1} (attempt {attempt + 1})")
                                    break
                                else:
                                    raise Exception(f"I2V video generation failed for scene {i+1} - no video file created")
                            else:
                                # 传统动画模式（同步）
                                if attempt > 0:
                                    self.logger.info(f"🔄 Retrying traditional animation for scene {i+1}, attempt {attempt + 1}")
                                scene_video = self._create_traditional_scene_video(scene, image, duration, i, temp_dir)
                                if scene_video and scene_video.exists():
                                    scene_videos.append(scene_video)
                                    self.logger.info(f"✅ Traditional animation created for scene {i+1} (attempt {attempt + 1})")
                                    break
                                else:
                                    raise Exception(f"Traditional animation failed for scene {i+1} - no video file created")
                        else:
                            raise Exception(f"No valid image for scene {i+1}")
                            
                    except Exception as e:
                        if attempt < max_scene_retries - 1:
                            wait_time = (attempt + 1) * 10  # 10s, 20s, 30s...
                            self.logger.warning(f"⏰ Scene {i+1} attempt {attempt + 1} failed: {e}")
                            self.logger.info(f"🔄 Retrying scene {i+1} in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            self.logger.error(f"❌ Scene {i+1} failed after {max_scene_retries} attempts: {e}")
                            # 最终失败后抛出异常，让上层处理
                            raise Exception(f"Scene {i+1} generation failed after {max_scene_retries} attempts: {e}")
            
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
    
    async def _create_video_integrated_mode(self, scenes, scene_videos, character_images, 
                                          audio_file, subtitle_file, output_path, temp_dir, 
                                          audio_duration, use_jianying_style):
        """
        一体化模式：直接使用预生成的场景视频+角色图像作为首帧
        
        Args:
            scenes: 场景列表
            scene_videos: 预生成的场景视频文件路径列表
            character_images: 角色图像文件路径列表
            audio_file: 音频文件路径
            subtitle_file: 字幕文件路径
            output_path: 输出路径
            temp_dir: 临时目录
            audio_duration: 音频时长
            use_jianying_style: 是否使用剪映风格字幕
        """
        try:
            self.logger.info(f"一体化模式视频合成: {len(scene_videos)} 场景视频 + {len(character_images) if character_images else 0} 角色图像")
            
            # 准备所有视频片段列表
            all_video_segments = []
            
            # 1. 添加角色图像作为首帧（如果存在）
            if character_images and character_images[0]:
                character_video = await self._create_character_intro_video(
                    character_images[0], temp_dir, duration=2.0  # 角色图像显示2秒
                )
                if character_video:
                    all_video_segments.append(character_video)
                    self.logger.info(f"✅ 角色首帧视频已创建: {character_video}")
            
            # 2. 添加所有场景视频
            for i, video_path in enumerate(scene_videos):
                if video_path and Path(video_path).exists():
                    all_video_segments.append(video_path)
                    self.logger.info(f"✅ 场景{i+1}视频已添加: {Path(video_path).name}")
                else:
                    self.logger.warning(f"❌ 场景{i+1}视频不存在: {video_path}")
            
            if not all_video_segments:
                raise ValueError("没有可用的视频片段进行合成")
            
            # 3. 拼接所有视频片段
            concat_video = temp_dir / "concatenated_video.mp4"
            await self._concatenate_videos(all_video_segments, concat_video)
            
            # 4. 添加音频轨道
            if audio_file and Path(audio_file).exists():
                video_with_audio = temp_dir / "video_with_audio.mp4"
                await self._add_audio_track(concat_video, audio_file, video_with_audio)
            else:
                video_with_audio = concat_video
            
            # 5. 添加字幕
            if subtitle_file and Path(subtitle_file).exists():
                await self._apply_subtitles_to_video(
                    video_with_audio, subtitle_file, output_path, use_jianying_style
                )
            else:
                # 无字幕，直接复制最终视频
                import shutil
                shutil.copy2(video_with_audio, output_path)
            
            self.logger.info(f"🎉 一体化模式视频合成完成: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"一体化模式视频合成失败: {e}")
            raise
    
    async def _create_character_intro_video(self, character_image_path, temp_dir, duration=2.0):
        """
        从角色图像创建开场视频片段
        """
        try:
            character_video = temp_dir / "character_intro.mp4"
            
            # 使用FFmpeg从图像创建短视频
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', str(character_image_path),
                '-t', str(duration),
                '-vf', 'scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                str(character_video)
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0 and character_video.exists():
                self.logger.info(f"角色开场视频创建成功: {character_video}")
                return character_video
            else:
                self.logger.error(f"角色开场视频创建失败: {stderr.decode()}")
                return None
                
        except Exception as e:
            self.logger.error(f"创建角色开场视频时出错: {e}")
            return None
    
    async def _concatenate_videos(self, video_list, output_path):
        """
        拼接多个视频文件
        """
        try:
            # 创建FFmpeg concat文件
            concat_file = output_path.parent / f"concat_{output_path.stem}.txt"
            
            with open(concat_file, 'w', encoding='utf-8') as f:
                for video_path in video_list:
                    # 确保使用绝对路径
                    abs_path = Path(video_path).resolve()
                    # 检查文件是否存在
                    if not abs_path.exists():
                        self.logger.error(f"视频文件不存在: {abs_path}")
                        continue
                    # 转义路径中的特殊字符
                    escaped_path = str(abs_path).replace("'", "\\'").replace("\\", "\\\\")
                    f.write(f"file '{escaped_path}'\n")
                    self.logger.debug(f"添加到concat文件: {escaped_path}")
            
            # 检查concat文件是否有有效内容
            if not concat_file.exists() or concat_file.stat().st_size == 0:
                self.logger.error("concat文件为空或不存在")
                raise RuntimeError("没有有效的视频文件可以拼接")
            
            # 记录concat文件内容用于调试
            with open(concat_file, 'r', encoding='utf-8') as f:
                concat_content = f.read()
                self.logger.debug(f"concat文件内容:\n{concat_content}")
            
            # 使用FFmpeg concat协议拼接视频
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',  # 直接复制，不重新编码
                str(output_path)
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0 and output_path.exists():
                self.logger.info(f"视频拼接完成: {output_path}")
                # 清理临时concat文件
                concat_file.unlink(missing_ok=True)
            else:
                self.logger.error(f"视频拼接失败: {stderr.decode()}")
                raise RuntimeError("视频拼接失败")
                
        except Exception as e:
            self.logger.error(f"视频拼接时出错: {e}")
            raise
    
    async def _add_audio_track(self, video_path, audio_path, output_path):
        """
        为视频添加音频轨道
        """
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', str(video_path),
                '-i', str(audio_path),
                '-c:v', 'copy',  # 视频流直接复制
                '-c:a', 'aac',   # 音频重新编码为AAC
                '-shortest',     # 以较短的流为准
                str(output_path)
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0 and output_path.exists():
                self.logger.info(f"音频轨道添加完成: {output_path}")
            else:
                self.logger.error(f"音频轨道添加失败: {stderr.decode()}")
                raise RuntimeError("音频轨道添加失败")
                
        except Exception as e:
            self.logger.error(f"添加音频轨道时出错: {e}")
            raise
    
    async def _apply_subtitles_to_video(self, video_path, subtitle_file, output_path, use_jianying_style):
        """
        为视频应用字幕
        """
        try:
            # 读取字幕文件
            subtitle_segments = self._parse_subtitle_file(subtitle_file)
            
            if not subtitle_segments:
                self.logger.warning("字幕文件为空，跳过字幕渲染")
                import shutil
                shutil.copy2(video_path, output_path)
                return
            
            # 选择渲染风格
            renderer_name = 'jianying' if use_jianying_style else 'traditional'
            style_name = 'jianying' if use_jianying_style else 'main'
            
            # 使用统一引擎渲染
            success = self.subtitle_engine.render_to_video(
                str(video_path),
                subtitle_segments,
                str(output_path),
                renderer_name,
                style_name
            )
            
            if success:
                self.logger.info(f"✅ 字幕应用成功，使用{renderer_name}渲染器")
            else:
                self.logger.error(f"❌ 字幕渲染失败，使用{renderer_name}渲染器")
                # 无字幕版本作为备选
                import shutil
                shutil.copy2(video_path, output_path)
                
        except Exception as e:
            self.logger.error(f"应用字幕时出错: {e}")
            # 无字幕版本作为备选
            import shutil
            shutil.copy2(video_path, output_path)