"""
双重图像视频合成器 - 实现原Coze工作流的双重图像系统
支持场景图像（背景）+ 主角图像（透明背景前景）的多层合成
"""
import subprocess
import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging
import json

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from content.scene_splitter import Scene
from media.image_generator import GeneratedImage
from media.character_image_generator import CharacterImageResult

@dataclass 
class DualImageVideoRequest:
    """双重图像视频合成请求"""
    scenes: List[Scene]                              # 场景列表
    scene_images: List[GeneratedImage]               # 场景背景图像列表
    character_image_result: CharacterImageResult    # 主角图像结果
    audio_file: Optional[str]                       # 音频文件路径
    subtitle_file: Optional[str]                    # 字幕文件路径
    output_path: str                                # 输出视频路径
    video_resolution: str = "1080x1920"            # 视频分辨率（TikTok竖屏）
    title_subtitle_file: Optional[str] = None       # 标题字幕文件路径

@dataclass
class DualImageVideoResult:
    """双重图像视频合成结果"""
    success: bool                    # 是否成功
    output_video_path: str          # 输出视频路径
    video_duration: float           # 视频时长
    file_size_mb: float            # 文件大小（MB）
    processing_time: float         # 处理时间
    scene_count: int               # 场景数量
    has_character_overlay: bool    # 是否包含主角叠加
    error_message: str = ""        # 错误信息

class DualImageCompositor:
    """
    双重图像视频合成器
    
    实现原Coze工作流的双重图像合成机制：
    1. 场景图像轨道：每个分镜一张背景图，带缩放动画
    2. 主角图像轨道：透明背景主角图，复用全视频，特殊动画
    3. 多轨道同步：音频、字幕、背景音乐等
    4. 动画效果：场景图像奇偶交替缩放，主角图像开场动画
    """
    
    def __init__(self, config_manager: ConfigManager, file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.video')
        
        # 检查FFmpeg是否可用
        self._check_ffmpeg()
        
        # 视频配置
        self.video_config = self.config.get_video_config()
        self.fps = 30
        self.video_codec = "libx264"
        self.audio_codec = "aac"
        
        self.logger.info("DualImageCompositor initialized with FFmpeg support")
    
    def _check_ffmpeg(self):
        """检查FFmpeg是否可用"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            self.logger.info("FFmpeg is available for dual image composition")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error("FFmpeg not found. Please install FFmpeg first.")
            raise RuntimeError("FFmpeg is required for dual image composition")
    
    async def compose_dual_image_video_async(self, request: DualImageVideoRequest) -> DualImageVideoResult:
        """
        异步双重图像视频合成
        
        Args:
            request: 合成请求
        
        Returns:
            DualImageVideoResult: 合成结果
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting dual image video composition: {len(request.scenes)} scenes")
            
            # 创建临时工作目录
            temp_dir = self.file_manager.get_output_path('temp', 'dual_image_composition')
            temp_dir = Path(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 验证输入
            self._validate_inputs(request)
            
            # 步骤1: 创建场景背景视频
            scene_videos = await self._create_scene_background_videos(request, temp_dir)
            
            # 步骤2: 创建主角叠加视频（如果有透明背景图）
            character_overlay_video = None
            if (request.character_image_result and 
                request.character_image_result.success and 
                request.character_image_result.cutout_result):
                character_overlay_video = await self._create_character_overlay_video(
                    request, temp_dir)
            
            # 步骤3: 合并所有场景背景视频
            merged_background_video = await self._merge_scene_videos(scene_videos, temp_dir)
            
            # 步骤4: 叠加主角图像（如果有）
            if character_overlay_video:
                video_with_character = await self._overlay_character_on_background(
                    merged_background_video, character_overlay_video, temp_dir)
            else:
                video_with_character = merged_background_video
                self.logger.info("No character overlay available, using background video only")
            
            # 步骤5: 添加音频
            if request.audio_file and Path(request.audio_file).exists():
                video_with_audio = await self._add_audio_track(
                    video_with_character, request.audio_file, temp_dir)
            else:
                video_with_audio = video_with_character
                self.logger.info("No audio file provided, creating silent video")
            
            # 步骤6: 添加字幕（支持双字幕轨道）
            if (request.subtitle_file and Path(request.subtitle_file).exists()) or \
               (request.title_subtitle_file and Path(request.title_subtitle_file).exists()):
                final_video = await self._add_dual_subtitle_tracks(
                    video_with_audio, request.subtitle_file, request.title_subtitle_file, request.output_path)
            else:
                # 直接复制到最终路径
                final_video = request.output_path
                subprocess.run(['cp', str(video_with_audio), final_video], check=True)
                self.logger.info("No subtitle files provided, skipping subtitle overlay")
            
            # 获取视频信息
            video_info = self._get_video_info(final_video)
            
            # 创建结果对象
            result = DualImageVideoResult(
                success=True,
                output_video_path=final_video,
                video_duration=video_info['duration'],
                file_size_mb=video_info['file_size_mb'],
                processing_time=time.time() - start_time,
                scene_count=len(request.scenes),
                has_character_overlay=character_overlay_video is not None
            )
            
            self.logger.info(f"Dual image video composition completed: {result.processing_time:.2f}s, "
                           f"{result.file_size_mb:.1f}MB, {result.video_duration:.1f}s duration")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Dual image video composition failed: {e}"
            self.logger.error(error_msg)
            
            return DualImageVideoResult(
                success=False,
                output_video_path="",
                video_duration=0.0,
                file_size_mb=0.0,
                processing_time=processing_time,
                scene_count=0,
                has_character_overlay=False,
                error_message=error_msg
            )
    
    def _validate_inputs(self, request: DualImageVideoRequest):
        """验证输入参数"""
        if not request.scenes:
            raise ValueError("No scenes provided")
        
        if not request.scene_images:
            raise ValueError("No scene images provided")
        
        if len(request.scenes) != len(request.scene_images):
            raise ValueError(f"Scene count ({len(request.scenes)}) != image count ({len(request.scene_images)})")
        
        # 检查场景图像文件是否存在
        for i, image in enumerate(request.scene_images):
            if not image or not image.file_path or not Path(image.file_path).exists():
                raise ValueError(f"Scene image {i+1} not found: {image.file_path if image else 'None'}")
    
    async def _create_scene_background_videos(self, request: DualImageVideoRequest, 
                                            temp_dir: Path) -> List[Path]:
        """
        创建场景背景视频（带动画效果）
        
        基于原Coze工作流的动画规则：
        - 奇偶交替的缩放方向（1.0→1.5, 1.5→1.0）
        """
        scene_videos = []
        resolution = request.video_resolution
        
        for i, (scene, image) in enumerate(zip(request.scenes, request.scene_images)):
            scene_video = temp_dir / f"scene_bg_{i+1}.mp4"
            duration = scene.duration_seconds
            
            # 决定缩放方向（奇偶交替）
            if i % 2 == 0:
                # 偶数场景：1.0→1.5 （放大）
                zoom_start = 1.0
                zoom_end = 1.5
            else:
                # 奇数场景：1.5→1.0 （缩小）
                zoom_start = 1.5
                zoom_end = 1.0
            
            # 计算总帧数
            total_frames = int(duration * self.fps)
            
            # FFmpeg缩放动画滤镜
            zoom_filter = (
                f"zoompan=z='min(zoom+({zoom_end-zoom_start})/{total_frames},{zoom_end})'"
                f":d={total_frames}:s={resolution}"
            )
            
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', str(image.file_path),
                '-filter_complex', 
                f'scale={resolution}:force_original_aspect_ratio=decrease,'
                f'pad={resolution}:(ow-iw)/2:(oh-ih)/2,'
                f'{zoom_filter}',
                '-t', str(duration),
                '-pix_fmt', 'yuv420p',
                '-r', str(self.fps),
                '-c:v', self.video_codec,
                str(scene_video)
            ]
            
            result = await self._run_ffmpeg_async(cmd)
            if result.returncode == 0:
                scene_videos.append(scene_video)
                self.logger.info(f"Created scene background video {i+1}: zoom {zoom_start}→{zoom_end}")
            else:
                raise Exception(f"Failed to create scene video {i+1}: {result.stderr}")
        
        return scene_videos
    
    async def _create_character_overlay_video(self, request: DualImageVideoRequest, 
                                            temp_dir: Path) -> Path:
        """
        创建主角叠加视频
        
        基于原Coze工作流的主角动画规则：
        - 2.0→1.2→1.0的开场动画
        - 放大2倍显示突出主角
        - 透明背景叠加在整个视频上
        """
        character_overlay_video = temp_dir / "character_overlay.mp4"
        
        # 获取透明背景主角图像
        character_image_path = request.character_image_result.cutout_result.local_file_path
        if not character_image_path or not Path(character_image_path).exists():
            raise ValueError(f"Character cutout image not found: {character_image_path}")
        
        # 计算总视频时长
        total_duration = sum(scene.duration_seconds for scene in request.scenes)
        resolution = request.video_resolution
        
        # 主角动画：2.0→1.2→1.0，然后保持1.0
        # 开场动画占前30%的时长
        animation_duration = min(total_duration * 0.3, 3.0)  # 最多3秒动画
        
        # 创建复杂的缩放动画
        # 第一阶段：2.0→1.2 (前50%动画时长)
        # 第二阶段：1.2→1.0 (后50%动画时长)
        # 第三阶段：保持1.0 (剩余时长)
        
        animation_frames = int(animation_duration * self.fps)
        total_frames = int(total_duration * self.fps)
        
        # 构建缩放表达式
        zoom_expr = f"if(lt(n,{animation_frames//2}),2.0-0.8*n/{animation_frames//2},if(lt(n,{animation_frames}),1.2-0.2*(n-{animation_frames//2})/{animation_frames//2},1.0))"
        
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', str(character_image_path),
            '-filter_complex',
            f'scale={resolution}:force_original_aspect_ratio=decrease,'
            f'pad={resolution}:(ow-iw)/2:(oh-ih)/2,'
            f'zoompan=z=\'{zoom_expr}\':d={total_frames}:s={resolution}',
            '-t', str(total_duration),
            '-pix_fmt', 'yuva420p',  # 支持透明度
            '-r', str(self.fps),
            '-c:v', 'libx264',
            '-preset', 'medium',
            str(character_overlay_video)
        ]
        
        result = await self._run_ffmpeg_async(cmd)
        if result.returncode == 0:
            self.logger.info(f"Created character overlay video: {animation_duration:.1f}s animation, {total_duration:.1f}s total")
            return character_overlay_video
        else:
            raise Exception(f"Failed to create character overlay video: {result.stderr}")
    
    async def _merge_scene_videos(self, scene_videos: List[Path], temp_dir: Path) -> Path:
        """合并所有场景背景视频"""
        merged_video = temp_dir / 'merged_background.mp4'
        
        # 创建concat文件
        concat_file = temp_dir / 'scene_concat.txt'
        with open(concat_file, 'w') as f:
            for video in scene_videos:
                f.write(f"file '{video.absolute()}'\n")
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',
            str(merged_video)
        ]
        
        result = await self._run_ffmpeg_async(cmd)
        if result.returncode == 0:
            self.logger.info(f"Merged {len(scene_videos)} scene videos into background")
            return merged_video
        else:
            raise Exception(f"Failed to merge scene videos: {result.stderr}")
    
    async def _overlay_character_on_background(self, background_video: Path, 
                                             character_video: Path, temp_dir: Path) -> Path:
        """将主角视频叠加到背景视频上"""
        output_video = temp_dir / 'video_with_character.mp4'
        
        # 使用overlay滤镜进行叠加合成
        cmd = [
            'ffmpeg', '-y',
            '-i', str(background_video),  # 背景视频
            '-i', str(character_video),   # 主角视频
            '-filter_complex', 
            '[1:v]scale=iw*0.5:ih*0.5[character_resized];'  # 主角图像缩放50%
            '[0:v][character_resized]overlay=x=(W-w)/2:y=(H-h)/2',  # 居中叠加
            '-c:v', self.video_codec,
            '-preset', 'medium',
            '-crf', '23',
            str(output_video)
        ]
        
        result = await self._run_ffmpeg_async(cmd)
        if result.returncode == 0:
            self.logger.info("Successfully overlaid character on background")
            return output_video
        else:
            raise Exception(f"Failed to overlay character: {result.stderr}")
    
    async def _add_audio_track(self, video_file: Path, audio_file: str, temp_dir: Path) -> Path:
        """添加音频轨道"""
        output_video = temp_dir / 'video_with_audio.mp4'
        
        cmd = [
            'ffmpeg', '-y',
            '-i', str(video_file),
            '-i', audio_file,
            '-c:v', 'copy',
            '-c:a', self.audio_codec,
            '-map', '0:v:0',  # 视频流
            '-map', '1:a:0',  # 音频流
            str(output_video)
        ]
        
        result = await self._run_ffmpeg_async(cmd)
        if result.returncode == 0:
            self.logger.info("Successfully added audio track")
            return output_video
        else:
            raise Exception(f"Failed to add audio: {result.stderr}")
    
    async def _add_dual_subtitle_tracks(self, video_file: Path, subtitle_file: str, 
                                       title_subtitle_file: str, output_path: str) -> str:
        """添加双字幕轨道（内容字幕+标题字幕）"""
        video_filters = []
        
        # 获取字幕配置
        subtitle_config = self.config.get('subtitle', {})
        main_font_size = subtitle_config.get('main_font_size', 10)
        title_font_size = subtitle_config.get('title_font_size', 40)
        margin_v = subtitle_config.get('margin_v', 288)
        outline = subtitle_config.get('outline', 2)
        alignment = subtitle_config.get('alignment', 2)
        main_color = subtitle_config.get('main_color', '#FFFFFF').replace('#', '')
        border_color = subtitle_config.get('main_border_color', '#000000').replace('#', '')
        
        # 添加内容字幕（基于原工作流优化）
        if subtitle_file and Path(subtitle_file).exists():
            subtitle_style = (f"FontSize={main_font_size},"
                            f"PrimaryColour=&H{main_color},"
                            f"OutlineColour=&H{border_color},"
                            f"Outline={outline}")
            video_filters.append(f"subtitles='{subtitle_file}':force_style='{subtitle_style}'")
            self.logger.info(f"Content subtitle track prepared (FontSize={main_font_size})")
        
        # 添加标题字幕（居中显示，大字体）
        if title_subtitle_file and Path(title_subtitle_file).exists():
            title_style = (f"FontSize={title_font_size},"
                          f"PrimaryColour=&H{main_color},"
                          f"OutlineColour=&H{border_color},"
                          f"Outline={outline},"
                          f"Alignment=2")  # 居中对齐
            video_filters.append(f"subtitles='{title_subtitle_file}':force_style='{title_style}'")
            self.logger.info(f"Title subtitle track prepared (FontSize={title_font_size})")
        
        if video_filters:
            # 构建滤镜链
            filter_chain = "[0:v]" + "[0:v]".join(video_filters) + "[v]"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', str(video_file),
                '-filter_complex', filter_chain,
                '-map', '[v]',
                '-map', '0:a',
                '-c:a', 'copy',
                '-preset', 'medium',
                str(output_path)
            ]
            
            result = await self._run_ffmpeg_async(cmd)
            if result.returncode == 0:
                subtitle_count = len(video_filters)
                self.logger.info(f"Successfully added {subtitle_count} subtitle tracks")
                return str(output_path)
            else:
                raise Exception(f"Failed to add subtitles: {result.stderr}")
        else:
            # 没有字幕文件，直接复制
            subprocess.run(['cp', str(video_file), str(output_path)], check=True)
            self.logger.info("No valid subtitle files, video copied without subtitles")
            return str(output_path)
    
    async def _run_ffmpeg_async(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """异步执行FFmpeg命令"""
        self.logger.debug(f"Running FFmpeg: {' '.join(cmd[:5])}...")
        
        # 使用asyncio执行子进程
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # 创建与subprocess.CompletedProcess兼容的结果对象
        class AsyncResult:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self.stdout = stdout.decode() if stdout else ""
                self.stderr = stderr.decode() if stderr else ""
        
        return AsyncResult(process.returncode, stdout, stderr)
    
    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """获取视频信息"""
        try:
            # 获取视频时长
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            duration = float(info['format']['duration'])
            file_size = int(info['format']['size']) / (1024 * 1024)  # MB
            
            return {
                'duration': duration,
                'file_size_mb': file_size
            }
        
        except Exception as e:
            self.logger.warning(f"Failed to get video info: {e}")
            # 退化方案：使用文件大小
            file_size = Path(video_path).stat().st_size / (1024 * 1024)
            return {
                'duration': 0.0,
                'file_size_mb': file_size
            }
    
    def compose_dual_image_video_sync(self, request: DualImageVideoRequest) -> DualImageVideoResult:
        """
        同步双重图像视频合成（对异步方法的包装）
        """
        return asyncio.run(self.compose_dual_image_video_async(request))
    
    def get_composition_stats(self) -> Dict[str, Any]:
        """获取合成器统计信息"""
        return {
            'video_config': self.video_config,
            'fps': self.fps,
            'video_codec': self.video_codec,
            'audio_codec': self.audio_codec,
            'ffmpeg_available': True  # 已在init中检查
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"DualImageCompositor(codec={self.video_codec}, fps={self.fps})"