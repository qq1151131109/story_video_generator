"""
统一字幕引擎 - 整合所有字幕处理功能
集成文本分割、时间对齐、格式生成、样式渲染于一体
"""
import os
import re
import time
import subprocess
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from abc import ABC, abstractmethod

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from utils.subtitle_utils import SubtitleUtils


@dataclass
class SubtitleSegment:
    """统一的字幕片段数据结构"""
    text: str                           # 字幕文本
    start_time: float                   # 开始时间（秒）
    end_time: float                     # 结束时间（秒）
    duration: float                     # 持续时间（秒）
    style: str = "main"                 # 样式标识
    position: str = "bottom"            # 位置(bottom/center/top)
    confidence: float = 1.0             # 置信度(0.0-1.0)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据


@dataclass
class SubtitleStyle:
    """字幕样式配置"""
    name: str                           # 样式名称
    font_size: int                      # 字体大小
    font_color: str                     # 字体颜色(#FFFFFF)
    border_color: str                   # 边框颜色
    border_width: int                   # 边框宽度
    background_enabled: bool = False    # 是否启用背景框
    background_color: str = "black@0.7" # 背景框颜色
    font_family: str = "Arial"          # 字体族
    position: str = "bottom"            # 默认位置
    alignment: int = 2                  # 对齐方式(1=左,2=中,3=右)
    margin_v: int = 80                  # 垂直边距
    fade_enabled: bool = False          # 淡入淡出
    fade_duration: float = 0.2          # 淡入淡出时长


@dataclass
class SubtitleRequest:
    """统一字幕处理请求"""
    text: str                           # 原始文本
    duration: float                     # 总时长
    language: str = "zh"                # 语言代码
    style_name: str = "main"            # 使用的样式
    max_chars_per_line: int = 25        # 每行最大字符数
    audio_file: Optional[str] = None    # 音频文件(用于对齐)
    alignment_method: str = "auto"      # 对齐方法(auto/tts/whisperx/estimate)
    output_format: str = "srt"          # 输出格式


@dataclass
class SubtitleResult:
    """字幕处理结果"""
    success: bool                       # 是否成功
    segments: List[SubtitleSegment]     # 字幕段落列表
    total_duration: float               # 总时长
    method_used: str                    # 使用的处理方法
    confidence_score: float             # 平均置信度
    processing_time: float              # 处理时间
    file_paths: Dict[str, str] = field(default_factory=dict)  # 生成的文件路径
    error_message: str = ""             # 错误信息
    stats: Dict[str, Any] = field(default_factory=dict)      # 统计信息


class SubtitleRenderer(ABC):
    """字幕渲染器抽象基类"""
    
    @abstractmethod
    def render_to_video(self, video_path: str, segments: List[SubtitleSegment], 
                       output_path: str, style: SubtitleStyle) -> bool:
        """将字幕渲染到视频"""
        pass
    
    @abstractmethod
    def get_renderer_info(self) -> Dict[str, Any]:
        """获取渲染器信息"""
        pass


class SubtitleEngine:
    """
    统一字幕引擎
    
    整合所有字幕处理功能：
    - 文本智能分割(多语言)
    - 时间对齐(WhisperX/TTS/估算)
    - 格式生成(SRT/ASS/VTT)
    - 样式渲染(剪映/传统)
    - 标题处理(开场标题)
    """
    
    def __init__(self, config_manager: ConfigManager, file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.subtitle_engine')
        
        # 加载配置
        self.subtitle_config = self._load_subtitle_config()
        
        # 初始化样式库
        self.styles = self._load_subtitle_styles()
        
        # 初始化渲染器
        self.renderers = self._load_renderers()
        
        # 对齐组件（延迟初始化）
        self._alignment_manager = None
        
        self.logger.info("SubtitleEngine initialized with unified architecture")
    
    def _load_subtitle_config(self) -> Dict[str, Any]:
        """加载统一字幕配置"""
        config = self.config.get('subtitle', {})
        
        return {
            # 文本分割配置 - 升级版
            'max_line_length': config.get('max_chars_per_line', 10),  # 使用新配置
            'max_lines': config.get('max_lines', 2),
            'max_text_width': config.get('max_text_width', 580),  # 更新为580px
            'video_width': config.get('video_width', 720),
            'safe_margin': config.get('safe_margin', 40),
            'enable_pixel_validation': config.get('enable_pixel_validation', True),
            'force_split_threshold': config.get('force_split_threshold', 15),
            'smart_punctuation_split': config.get('smart_punctuation_split', True),
            
            # 时间对齐配置
            'max_duration_per_subtitle': config.get('max_duration_per_subtitle', 3.0),
            'min_subtitle_duration': config.get('min_subtitle_duration', 0.5),
            'min_gap_between_subtitles': config.get('min_gap_between_subtitles', 0.1),
            
            # 渲染配置
            'default_renderer': config.get('default_renderer', 'jianying'),
            'enable_fade_effects': config.get('enable_fade_effects', True),
            
            # 字体配置
            'font_detection_paths': config.get('font_detection_paths', [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/mnt/c/Windows/Fonts/msyh.ttc",
                "/System/Library/Fonts/PingFang.ttc"
            ])
        }
    
    def _load_subtitle_styles(self) -> Dict[str, SubtitleStyle]:
        """加载预定义字幕样式"""
        config = self.config.get('subtitle', {})
        
        return {
            'main': SubtitleStyle(
                name='main',
                font_size=config.get('main_font_size', 48),
                font_color=config.get('main_color', '#FFFFFF'),
                border_color=config.get('main_border_color', '#000000'),
                border_width=config.get('outline', 3),
                background_enabled=False,
                position='bottom',
                alignment=2,
                margin_v=config.get('margin_v', 80)
            ),
            
            'jianying': SubtitleStyle(
                name='jianying',
                font_size=config.get('main_font_size', 48),
                font_color=config.get('main_color', '#FFFFFF'),
                border_color=config.get('main_border_color', '#000000'),
                border_width=config.get('outline', 3),
                background_enabled=True,
                background_color="black@0.7",
                font_family="思源黑体",
                position='bottom',
                alignment=2,
                margin_v=config.get('margin_v', 80),
                fade_enabled=True,
                fade_duration=0.2
            ),
            
            'title': SubtitleStyle(
                name='title',
                font_size=config.get('title_font_size', 40),
                font_color=config.get('title_color', '#FFFFFF'),
                border_color=config.get('title_border_color', '#000000'),
                border_width=config.get('outline', 2),
                background_enabled=False,
                font_family=config.get('title_font', '书南体'),
                position='center',
                alignment=2,
                margin_v=config.get('title_margin_v', 200)
            )
        }
    
    def _load_renderers(self) -> Dict[str, SubtitleRenderer]:
        """加载字幕渲染器"""
        # 暂时返回空字典，渲染功能集成到引擎内部
        return {}
    
    def process_subtitles(self, request: SubtitleRequest) -> SubtitleResult:
        """
        统一字幕处理接口
        
        Args:
            request: 字幕处理请求
            
        Returns:
            SubtitleResult: 处理结果
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Processing subtitles: {request.text[:50]}... ({request.language})")
            
            # 步骤1: 智能文本分割
            text_segments = self._split_text_intelligently(
                request.text, 
                request.language,
                request.max_chars_per_line
            )
            
            # 步骤2: 时间对齐
            aligned_segments = self._align_timestamps(
                text_segments,
                request.duration,
                request.audio_file,
                request.alignment_method,
                request.language
            )
            
            # 步骤3: 应用样式
            styled_segments = self._apply_styles(aligned_segments, request.style_name)
            
            # 步骤4: 优化时间间隔
            optimized_segments = self._optimize_timing(styled_segments)
            
            # 计算统计信息
            stats = self._calculate_stats(optimized_segments)
            
            # 创建结果
            result = SubtitleResult(
                success=True,
                segments=optimized_segments,
                total_duration=optimized_segments[-1].end_time if optimized_segments else 0.0,
                method_used=f"Split+Align+Style({request.style_name})",
                confidence_score=sum(seg.confidence for seg in optimized_segments) / len(optimized_segments) if optimized_segments else 0.0,
                processing_time=time.time() - start_time,
                stats=stats
            )
            
            self.logger.info(f"Subtitle processing completed: {len(optimized_segments)} segments in {result.processing_time:.2f}s")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Subtitle processing failed: {e}"
            self.logger.error(error_msg)
            
            return SubtitleResult(
                success=False,
                segments=[],
                total_duration=0.0,
                method_used="failed",
                confidence_score=0.0,
                processing_time=processing_time,
                error_message=error_msg
            )
    
    def _split_text_intelligently(self, text: str, language: str, max_chars: int) -> List[str]:
        """智能文本分割 - 统一入口(像素级升级版)"""
        # 获取升级后的配置参数
        max_pixel_width = self.subtitle_config.get('max_text_width', 580)
        font_size = self.config.get('subtitle', {}).get('main_font_size', 48)
        enable_pixel_validation = self.subtitle_config.get('enable_pixel_validation', True)
        
        # 使用配置中的max_chars_per_line而不是传入的max_chars
        actual_max_chars = self.subtitle_config.get('max_line_length', 10)
        
        return SubtitleUtils.split_text_by_rules(
            text, actual_max_chars, language, max_pixel_width, font_size, enable_pixel_validation
        )
    
    def _align_timestamps(self, text_segments: List[str], total_duration: float, 
                         audio_file: Optional[str], method: str, language: str) -> List[SubtitleSegment]:
        """统一时间对齐接口"""
        
        # 根据对齐方法选择策略
        if method == "auto":
            # 自动选择最佳对齐方法
            if audio_file and Path(audio_file).exists():
                # 有音频文件，尝试高级对齐
                if self.subtitle_config.get('prefer_whisperx', False):
                    segments = self._try_whisperx_alignment(text_segments, audio_file, language)
                    if segments:
                        return segments
                
                # WhisperX失败，尝试音频基础对齐
                return self._estimate_alignment_from_audio(text_segments, total_duration)
            else:
                # 无音频文件，使用文本估算
                return self._estimate_alignment_from_text(text_segments, total_duration)
        
        elif method == "whisperx":
            return self._try_whisperx_alignment(text_segments, audio_file, language) or \
                   self._estimate_alignment_from_text(text_segments, total_duration)
        
        elif method == "tts":
            # TTS对齐需要从外部传入时间戳
            return self._estimate_alignment_from_text(text_segments, total_duration)
        
        elif method == "estimate":
            return self._estimate_alignment_from_text(text_segments, total_duration)
        
        else:
            self.logger.warning(f"Unknown alignment method: {method}, using text estimation")
            return self._estimate_alignment_from_text(text_segments, total_duration)
    
    def _try_whisperx_alignment(self, text_segments: List[str], audio_file: str, language: str) -> Optional[List[SubtitleSegment]]:
        """尝试WhisperX精确对齐"""
        try:
            # 这里需要集成原来的WhisperX逻辑
            # 现在先返回None，表示不可用
            self.logger.info("WhisperX alignment not implemented in unified engine")
            return None
            
        except Exception as e:
            self.logger.error(f"WhisperX alignment failed: {e}")
            return None
    
    def _estimate_alignment_from_audio(self, text_segments: List[str], total_duration: float) -> List[SubtitleSegment]:
        """基于音频长度的智能对齐"""
        return self._estimate_alignment_from_text(text_segments, total_duration)
    
    def _estimate_alignment_from_text(self, text_segments: List[str], total_duration: float) -> List[SubtitleSegment]:
        """基于文本长度的估算对齐"""
        if not text_segments:
            return []
        
        segments = []
        total_chars = sum(len(seg) for seg in text_segments)
        current_time = 0.0
        
        for i, text in enumerate(text_segments):
            # 按文本长度比例分配时间
            if total_chars > 0:
                segment_duration = (len(text) / total_chars) * total_duration
            else:
                segment_duration = total_duration / len(text_segments)
            
            # 限制最大/最小时长
            min_duration = self.subtitle_config['min_subtitle_duration']
            max_duration = self.subtitle_config['max_duration_per_subtitle']
            segment_duration = max(min_duration, min(segment_duration, max_duration))
            
            # 最后一段精确对齐到总时长
            if i == len(text_segments) - 1:
                end_time = total_duration
            else:
                end_time = current_time + segment_duration
            
            segment = SubtitleSegment(
                text=text,
                start_time=current_time,
                end_time=end_time,
                duration=end_time - current_time,
                confidence=0.7  # 估算对齐中等置信度
            )
            segments.append(segment)
            current_time = end_time
        
        return segments
    
    def _apply_styles(self, segments: List[SubtitleSegment], style_name: str) -> List[SubtitleSegment]:
        """应用字幕样式"""
        if style_name not in self.styles:
            self.logger.warning(f"Style '{style_name}' not found, using 'main'")
            style_name = 'main'
        
        style = self.styles[style_name]
        
        # 应用样式到所有段落
        for segment in segments:
            segment.style = style_name
            segment.position = style.position
        
        return segments
    
    def _optimize_timing(self, segments: List[SubtitleSegment]) -> List[SubtitleSegment]:
        """优化字幕时间间隔"""
        if not segments:
            return []
        
        min_gap = self.subtitle_config['min_gap_between_subtitles']
        optimized = []
        
        for i, segment in enumerate(segments):
            if i == 0:
                optimized.append(segment)
                continue
            
            # 检查与前一个段落的间隔
            prev_end = optimized[i-1].end_time
            if segment.start_time - prev_end < min_gap:
                # 调整开始时间
                new_start = prev_end + min_gap
                new_duration = max(segment.duration, self.subtitle_config['min_subtitle_duration'])
                new_end = new_start + new_duration
                
                segment.start_time = new_start
                segment.end_time = new_end
                segment.duration = new_duration
            
            optimized.append(segment)
        
        return optimized
    
    def _calculate_stats(self, segments: List[SubtitleSegment]) -> Dict[str, Any]:
        """计算字幕统计信息"""
        if not segments:
            return {}
        
        total_chars = sum(len(seg.text) for seg in segments)
        total_duration = max(seg.end_time for seg in segments)
        
        return {
            'segment_count': len(segments),
            'total_characters': total_chars,
            'total_duration': total_duration,
            'avg_chars_per_segment': total_chars / len(segments),
            'avg_duration_per_segment': total_duration / len(segments),
            'chars_per_second': total_chars / total_duration if total_duration > 0 else 0,
            'avg_confidence': sum(seg.confidence for seg in segments) / len(segments)
        }
    
    def save_subtitle_file(self, segments: List[SubtitleSegment], output_path: str, 
                          format: str = "srt") -> str:
        """保存字幕文件"""
        try:
            if format.lower() == "srt":
                content = self._generate_srt(segments)
            elif format.lower() == "ass":  
                content = self._generate_ass(segments)
            elif format.lower() == "vtt":
                content = self._generate_vtt(segments)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            # 确保正确的文件扩展名
            output_path = Path(output_path)
            if output_path.suffix.lower() != f".{format.lower()}":
                output_path = output_path.with_suffix(f".{format.lower()}")
            
            success = self.file_manager.save_text(content, str(output_path))
            
            if success:
                self.logger.info(f"Saved {format.upper()} file: {output_path}")
                return str(output_path)
            else:
                raise Exception(f"Failed to save file: {output_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to save subtitle file: {e}")
            raise
    
    def _generate_srt(self, segments: List[SubtitleSegment]) -> str:
        """生成SRT格式内容"""
        srt_content = []
        
        for i, segment in enumerate(segments, 1):
            start_time = SubtitleUtils.format_srt_time(segment.start_time)
            end_time = SubtitleUtils.format_srt_time(segment.end_time)
            
            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(segment.text)
            srt_content.append("")  # 空行分隔
        
        return '\n'.join(srt_content)
    
    def _generate_ass(self, segments: List[SubtitleSegment]) -> str:
        """生成ASS格式内容"""
        # ASS头部
        ass_header = """[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,0,2,10,10,80,1
Style: Title,Arial,40,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,2,10,10,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        ass_content = [ass_header.strip()]
        
        for segment in segments:
            start_time = SubtitleUtils.format_ass_time(segment.start_time)
            end_time = SubtitleUtils.format_ass_time(segment.end_time)
            
            style_name = segment.style.capitalize()
            event = f"Dialogue: 0,{start_time},{end_time},{style_name},,0,0,0,,{segment.text}"
            ass_content.append(event)
        
        return '\n'.join(ass_content)
    
    def _generate_vtt(self, segments: List[SubtitleSegment]) -> str:
        """生成VTT格式内容"""
        vtt_content = ["WEBVTT", ""]
        
        for i, segment in enumerate(segments, 1):
            start_time = SubtitleUtils.format_vtt_time(segment.start_time)
            end_time = SubtitleUtils.format_vtt_time(segment.end_time)
            
            vtt_content.append(f"{i}")
            vtt_content.append(f"{start_time} --> {end_time}")
            vtt_content.append(segment.text)
            vtt_content.append("")
        
        return '\n'.join(vtt_content)
    
    def render_to_video(self, video_path: str, segments: List[SubtitleSegment], 
                       output_path: str, renderer_name: str = None, 
                       style_name: str = None) -> bool:
        """
        将字幕渲染到视频
        
        Args:
            video_path: 输入视频路径
            segments: 字幕段落列表  
            output_path: 输出视频路径
            renderer_name: 渲染器名称(jianying/traditional)
            style_name: 样式名称
            
        Returns:
            bool: 是否成功
        """
        # 选择渲染方式
        if renderer_name is None:
            renderer_name = self.subtitle_config.get('default_renderer', 'jianying')
        
        # 选择样式
        if style_name is None:
            style_name = segments[0].style if segments else 'main'
        
        if style_name not in self.styles:
            self.logger.warning(f"Style '{style_name}' not found, using 'main'")
            style_name = 'main'
        
        style = self.styles[style_name]
        
        try:
            if renderer_name == 'jianying':
                return self._render_jianying_style(video_path, segments, output_path, style)
            elif renderer_name == 'traditional':
                return self._render_traditional_style(video_path, segments, output_path, style)
            else:
                self.logger.error(f"Unknown renderer: {renderer_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Video rendering error: {e}")
            return False
    
    def _render_jianying_style(self, video_path: str, segments: List[SubtitleSegment], 
                              output_path: str, style: SubtitleStyle) -> bool:
        """剪映风格渲染（集成版）"""
        try:
            self.logger.info("Rendering Jianying-style subtitles")
            
            # 获取字体路径
            font_path = self._detect_chinese_font()
            
            # 构建drawtext滤镜链
            drawtext_filters = []
            
            for segment in segments:
                # 智能分行处理
                lines = self._smart_text_wrap_jianying(segment.text, style)
                display_text = '\n'.join(lines)  # ✅ 使用真正的换行符
                
                # 构建drawtext参数
                params = []
                
                if font_path:
                    params.append(f"fontfile='{font_path}'")
                
                # 文本转义
                escaped_text = display_text.replace("'", "\\'").replace(":", "\\:")
                params.append(f"text='{escaped_text}'")
                params.append(f"fontsize={style.font_size}")
                params.append(f"fontcolor={style.font_color.replace('#', '')}")
                
                # 描边
                params.append(f"borderw={style.border_width}")
                params.append(f"bordercolor={style.border_color.replace('#', '')}")
                
                # 背景框（剪映特色）
                if style.background_enabled:
                    params.append("box=1")
                    params.append(f"boxcolor={style.background_color}")
                    params.append("boxborderw=12")
                
                # 位置
                params.append("x=(w-text_w)/2")
                params.append(f"y=h-text_h-{style.margin_v}")
                
                # 时间控制
                time_expr = f"between(t,{segment.start_time:.3f},{segment.end_time:.3f})"
                params.append(f"enable='{time_expr}'")
                
                # 淡入淡出
                if style.fade_enabled:
                    fade_dur = style.fade_duration
                    alpha_expr = (
                        f"'if(lt(t,{segment.start_time:.3f}+{fade_dur}), "
                        f"(t-{segment.start_time:.3f})/{fade_dur}, "
                        f"if(gt(t,{segment.end_time:.3f}-{fade_dur}), "
                        f"({segment.end_time:.3f}-t)/{fade_dur}, 1))'"
                    )
                    params.append(f"alpha={alpha_expr}")
                
                drawtext_filters.append("drawtext=" + ":".join(params))
            
            if not drawtext_filters:
                self.logger.warning("No drawtext filters created")
                return False
            
            # 构建完整滤镜链
            filter_chain = "[0:v]" + ",".join(drawtext_filters) + "[v]"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-filter_complex', filter_chain,
                '-map', '[v]',
                '-map', '0:a',
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-preset', 'fast',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info("Jianying subtitles rendered successfully")
                return True
            else:
                self.logger.error(f"Jianying rendering failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Jianying rendering error: {e}")
            return False
    
    def _render_traditional_style(self, video_path: str, segments: List[SubtitleSegment], 
                                 output_path: str, style: SubtitleStyle) -> bool:
        """传统风格渲染"""
        try:
            self.logger.info("Rendering traditional-style subtitles")
            
            # 创建临时SRT文件
            temp_srt = self._create_temp_srt_file(segments)
            
            # 构建样式字符串
            subtitle_style = (f"FontSize={style.font_size},"
                            f"PrimaryColour=&H{style.font_color.replace('#', '')},"
                            f"OutlineColour=&H{style.border_color.replace('#', '')},"
                            f"Outline={style.border_width}")
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', f"subtitles='{temp_srt}':force_style='{subtitle_style}'",
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-preset', 'medium',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 清理临时文件
            try:
                Path(temp_srt).unlink()
            except:
                pass
            
            if result.returncode == 0:
                self.logger.info("Traditional subtitles rendered successfully")
                return True
            else:
                self.logger.error(f"Traditional rendering failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Traditional rendering error: {e}")
            return False
    
    def _smart_text_wrap_jianying(self, text: str, style: SubtitleStyle, max_width: int = 640) -> List[str]:
        """剪映风格智能换行"""
        # 简化版本的文本换行
        lines = []
        max_chars_per_line = max_width // style.font_size  # 估算每行字符数
        max_chars_per_line = max(8, min(max_chars_per_line, 20))
        
        # 使用统一的文本分割工具
        from utils.subtitle_utils import SubtitleUtils
        return SubtitleUtils.split_text_by_rules(text, max_chars_per_line, 'zh')
    
    def _create_temp_srt_file(self, segments: List[SubtitleSegment]) -> str:
        """创建临时SRT文件"""
        temp_file = self.file_manager.get_output_path('temp', 'unified_subtitle.srt')
        content = self._generate_srt(segments)
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return temp_file
    
    def _detect_chinese_font(self) -> Optional[str]:
        """检测中文字体"""
        for font_path in self.subtitle_config['font_detection_paths']:
            if os.path.exists(font_path):
                return font_path
        return None
    
    def create_title_subtitles(self, title: str, duration: float = 3.0, 
                              start_time: float = 0.0) -> List[SubtitleSegment]:
        """创建标题字幕（2字标题）"""
        # 验证标题格式
        if not self._validate_title(title):
            raise ValueError(f"Invalid title: '{title}' - must be 2 Chinese characters")
        
        title_segment = SubtitleSegment(
            text=title,
            start_time=start_time,
            end_time=start_time + duration,
            duration=duration,
            style='title',
            position='center',
            confidence=1.0
        )
        
        return [title_segment]
    
    def _validate_title(self, title: str) -> bool:
        """验证标题格式"""
        if not title:
            return False
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', title)
        return len(chinese_chars) == 2
    
    def get_engine_info(self) -> Dict[str, Any]:
        """获取引擎信息"""
        return {
            'engine_version': '2.0.0',
            'supported_languages': ['zh', 'en', 'es'],
            'supported_formats': ['srt', 'ass', 'vtt'],
            'available_styles': list(self.styles.keys()),
            'available_renderers': list(self.renderers.keys()),
            'alignment_methods': ['auto', 'whisperx', 'tts', 'estimate'],
            'config': self.subtitle_config
        }
    
    def cleanup(self):
        """清理资源"""
        if self._alignment_manager:
            self._alignment_manager.cleanup()
            self._alignment_manager = None
        
        for renderer in self.renderers.values():
            if hasattr(renderer, 'cleanup'):
                renderer.cleanup()
        
        self.logger.info("SubtitleEngine cleaned up")
    
    def __str__(self) -> str:
        return f"SubtitleEngine(styles={len(self.styles)}, renderers={len(self.renderers)})"