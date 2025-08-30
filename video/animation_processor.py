"""
动画效果处理器 - 图像动画和过渡效果
对应原工作流Node_120984的动画配置
"""
import time
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import logging
from dataclasses import dataclass
import json

from core.config_manager import ConfigManager

@dataclass
class Keyframe:
    """关键帧"""
    time_microseconds: int      # 时间点（微秒）
    scale: float               # 缩放值
    x_offset: float = 0.0      # X偏移
    y_offset: float = 0.0      # Y偏移
    opacity: float = 1.0       # 透明度
    rotation: float = 0.0      # 旋转角度

@dataclass
class AnimationClip:
    """动画片段"""
    duration_seconds: float     # 动画时长
    keyframes: List[Keyframe]   # 关键帧列表
    easing: str = "linear"      # 缓动类型
    animation_type: str = "scale"  # 动画类型

@dataclass
class AnimationRequest:
    """动画处理请求"""
    image_path: str            # 图像路径
    duration_seconds: float    # 动画时长
    animation_type: str = "轻微放大"  # 动画类型（对应原工作流）
    is_character: bool = False # 是否是角色图像

class AnimationProcessor:
    """
    动画效果处理器
    
    基于原工作流Node_120984配置：
    - 场景缩放范围：[1.0, 1.5]
    - 主角缩放序列：[2.0, 1.2, 1.0] 在时间点 [0, 533333] 微秒
    - 缓动类型：linear
    - 入场动画：轻微放大，时长100000微秒
    """
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.logger = logging.getLogger('story_generator.video')
        
        # 获取动画配置
        self.animation_config = config_manager.get('animation', {})
        
        # 场景缩放配置
        self.scene_scale_range = self.animation_config.get('scene_scale_range', [1.0, 1.5])
        
        # 主角缩放配置
        self.character_scale_sequence = self.animation_config.get('character_scale_sequence', [2.0, 1.2, 1.0])
        self.character_scale_timing = self.animation_config.get('character_scale_timing', [0, 533333])  # 微秒
        
        # 动画配置
        self.easing = self.animation_config.get('easing', 'linear')
        self.in_animation = self.animation_config.get('in_animation', '轻微放大')
        self.in_animation_duration = self.animation_config.get('in_animation_duration', 100000)  # 微秒
        
        # 动画类型映射
        self.animation_types = {
            '轻微放大': 'zoom_in_slight',
            '放大': 'zoom_in',
            '缩小': 'zoom_out', 
            '淡入': 'fade_in',
            '滑入': 'slide_in',
            '旋转入场': 'rotate_in'
        }
        
        self.logger.info("Animation processor initialized")
    
    def create_scene_animation(self, request: AnimationRequest) -> AnimationClip:
        """
        创建场景动画
        
        Args:
            request: 动画请求
        
        Returns:
            AnimationClip: 动画片段
        """
        try:
            animation_type = self.animation_types.get(request.animation_type, 'zoom_in_slight')
            
            if animation_type == 'zoom_in_slight':
                return self._create_zoom_in_slight_animation(request)
            elif animation_type == 'zoom_in':
                return self._create_zoom_in_animation(request)
            elif animation_type == 'fade_in':
                return self._create_fade_in_animation(request)
            else:
                # 默认使用轻微放大
                return self._create_zoom_in_slight_animation(request)
                
        except Exception as e:
            self.logger.error(f"Failed to create scene animation: {e}")
            # 返回默认动画
            return self._create_default_animation(request)
    
    def create_character_animation(self, request: AnimationRequest) -> AnimationClip:
        """
        创建角色动画（对应原工作流主角缩放序列）
        
        Args:
            request: 动画请求
        
        Returns:
            AnimationClip: 动画片段
        """
        try:
            duration_microseconds = int(request.duration_seconds * 1_000_000)
            
            keyframes = []
            
            # 根据原工作流配置创建关键帧
            for i, scale in enumerate(self.character_scale_sequence):
                if i < len(self.character_scale_timing):
                    time_us = self.character_scale_timing[i]
                else:
                    # 如果时间点不够，均匀分布剩余的关键帧
                    remaining_time = duration_microseconds - self.character_scale_timing[-1]
                    remaining_frames = len(self.character_scale_sequence) - len(self.character_scale_timing)
                    if remaining_frames > 0:
                        time_us = self.character_scale_timing[-1] + (remaining_time * (i - len(self.character_scale_timing) + 1) // remaining_frames)
                    else:
                        time_us = duration_microseconds
                
                keyframe = Keyframe(
                    time_microseconds=time_us,
                    scale=scale,
                    opacity=1.0
                )
                keyframes.append(keyframe)
            
            # 确保最后一帧在动画结束时间
            if keyframes and keyframes[-1].time_microseconds < duration_microseconds:
                final_keyframe = Keyframe(
                    time_microseconds=duration_microseconds,
                    scale=self.character_scale_sequence[-1],
                    opacity=1.0
                )
                keyframes.append(final_keyframe)
            
            return AnimationClip(
                duration_seconds=request.duration_seconds,
                keyframes=keyframes,
                easing=self.easing,
                animation_type="character_sequence"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create character animation: {e}")
            return self._create_default_animation(request)
    
    def _create_zoom_in_slight_animation(self, request: AnimationRequest) -> AnimationClip:
        """创建轻微放大动画（对应原工作流默认动画）"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        # 入场动画时长（对应原工作流100000微秒）
        in_duration_us = min(self.in_animation_duration, duration_us // 2)
        
        keyframes = [
            # 开始：原始大小
            Keyframe(time_microseconds=0, scale=1.0, opacity=1.0),
            # 入场完成：轻微放大
            Keyframe(time_microseconds=in_duration_us, scale=1.1, opacity=1.0),
            # 结束：回到稍大尺寸
            Keyframe(time_microseconds=duration_us, scale=1.05, opacity=1.0)
        ]
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="zoom_in_slight"
        )
    
    def _create_zoom_in_animation(self, request: AnimationRequest) -> AnimationClip:
        """创建放大动画"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        # 使用场景缩放范围
        start_scale = self.scene_scale_range[0]
        end_scale = self.scene_scale_range[1]
        
        keyframes = [
            Keyframe(time_microseconds=0, scale=start_scale, opacity=1.0),
            Keyframe(time_microseconds=duration_us, scale=end_scale, opacity=1.0)
        ]
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="zoom_in"
        )
    
    def _create_fade_in_animation(self, request: AnimationRequest) -> AnimationClip:
        """创建淡入动画"""
        duration_us = int(request.duration_seconds * 1_000_000)
        fade_duration_us = duration_us // 4  # 淡入占1/4时间
        
        keyframes = [
            Keyframe(time_microseconds=0, scale=1.0, opacity=0.0),
            Keyframe(time_microseconds=fade_duration_us, scale=1.0, opacity=1.0),
            Keyframe(time_microseconds=duration_us, scale=1.0, opacity=1.0)
        ]
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="fade_in"
        )
    
    def _create_default_animation(self, request: AnimationRequest) -> AnimationClip:
        """创建默认动画（静态）"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        keyframes = [
            Keyframe(time_microseconds=0, scale=1.0, opacity=1.0),
            Keyframe(time_microseconds=duration_us, scale=1.0, opacity=1.0)
        ]
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing="linear",
            animation_type="static"
        )
    
    def generate_ffmpeg_filter(self, animation_clip: AnimationClip, video_resolution: Tuple[int, int]) -> str:
        """
        生成FFmpeg滤镜字符串
        
        Args:
            animation_clip: 动画片段
            video_resolution: 视频分辨率 (width, height)
        
        Returns:
            str: FFmpeg滤镜字符串
        """
        try:
            if not animation_clip.keyframes:
                return ""
            
            video_width, video_height = video_resolution
            center_x = video_width // 2
            center_y = video_height // 2
            
            # 构建缩放滤镜
            scale_expressions = []
            
            for i, keyframe in enumerate(animation_clip.keyframes):
                time_seconds = keyframe.time_microseconds / 1_000_000
                
                if i == 0:
                    # 第一个关键帧
                    scale_expr = f"if(lt(t,{time_seconds}),{keyframe.scale},{keyframe.scale})"
                elif i == len(animation_clip.keyframes) - 1:
                    # 最后一个关键帧
                    prev_keyframe = animation_clip.keyframes[i-1]
                    prev_time = prev_keyframe.time_microseconds / 1_000_000
                    
                    if self.easing == "linear":
                        # 线性插值
                        scale_expr = f"if(gte(t,{prev_time}),{prev_keyframe.scale}+({keyframe.scale}-{prev_keyframe.scale})*(t-{prev_time})/({time_seconds}-{prev_time}),{keyframe.scale})"
                    else:
                        scale_expr = f"if(gte(t,{time_seconds}),{keyframe.scale},{keyframe.scale})"
                else:
                    # 中间关键帧
                    prev_keyframe = animation_clip.keyframes[i-1]
                    prev_time = prev_keyframe.time_microseconds / 1_000_000
                    
                    if self.easing == "linear":
                        scale_expr = f"if(and(gte(t,{prev_time}),lt(t,{time_seconds})),{prev_keyframe.scale}+({keyframe.scale}-{prev_keyframe.scale})*(t-{prev_time})/({time_seconds}-{prev_time}),{keyframe.scale})"
                    else:
                        scale_expr = f"if(and(gte(t,{prev_time}),lt(t,{time_seconds})),{keyframe.scale},{keyframe.scale})"
                
                scale_expressions.append(scale_expr)
            
            # 组合所有表达式
            if len(scale_expressions) == 1:
                final_scale_expr = scale_expressions[0]
            else:
                final_scale_expr = scale_expressions[0]
                for expr in scale_expressions[1:]:
                    final_scale_expr = expr.replace(f"{animation_clip.keyframes[0].scale}", final_scale_expr)
            
            # 创建FFmpeg滤镜
            # 使用scale2ref来保持纵横比并应用缩放
            filter_parts = []
            
            # 缩放滤镜
            scale_filter = f"scale=iw*({final_scale_expr}):ih*({final_scale_expr}):flags=lanczos"
            filter_parts.append(scale_filter)
            
            # 如果有透明度变化，添加fade滤镜
            opacity_keyframes = [kf for kf in animation_clip.keyframes if kf.opacity != 1.0]
            if opacity_keyframes:
                # 简化处理：如果有透明度变化，添加fade in效果
                first_opacity_kf = opacity_keyframes[0]
                if first_opacity_kf.opacity < 1.0:
                    fade_duration = first_opacity_kf.time_microseconds / 1_000_000
                    fade_filter = f"fade=t=in:st=0:d={fade_duration}"
                    filter_parts.append(fade_filter)
            
            # 居中显示
            pad_filter = f"pad={video_width}:{video_height}:({video_width}-iw)/2:({video_height}-ih)/2"
            filter_parts.append(pad_filter)
            
            return ','.join(filter_parts)
            
        except Exception as e:
            self.logger.error(f"Failed to generate FFmpeg filter: {e}")
            # 返回基本的居中滤镜
            return f"pad={video_resolution[0]}:{video_resolution[1]}:({video_resolution[0]}-iw)/2:({video_resolution[1]}-ih)/2"
    
    def create_transition_effect(self, transition_type: str = "fade", 
                               duration: float = 0.5) -> str:
        """
        创建场景之间的过渡效果
        
        Args:
            transition_type: 过渡类型 (fade, crossfade, slide)
            duration: 过渡时长
        
        Returns:
            str: FFmpeg过渡滤镜
        """
        if transition_type == "fade":
            return f"fade=t=out:st=0:d={duration},fade=t=in:st=0:d={duration}"
        elif transition_type == "crossfade":
            return f"acrossfade=d={duration}"
        else:
            return f"fade=t=out:st=0:d={duration},fade=t=in:st=0:d={duration}"
    
    def batch_create_animations(self, requests: List[AnimationRequest]) -> List[AnimationClip]:
        """
        批量创建动画
        
        Args:
            requests: 动画请求列表
        
        Returns:
            List[AnimationClip]: 动画片段列表
        """
        self.logger.info(f"Batch creating {len(requests)} animations")
        
        animations = []
        
        for i, request in enumerate(requests):
            try:
                if request.is_character:
                    animation = self.create_character_animation(request)
                else:
                    animation = self.create_scene_animation(request)
                animations.append(animation)
            except Exception as e:
                self.logger.error(f"Failed to create animation {i}: {e}")
                animations.append(self._create_default_animation(request))
        
        return animations
    
    def export_animation_data(self, animation_clip: AnimationClip) -> Dict[str, Any]:
        """
        导出动画数据为字典格式
        
        Args:
            animation_clip: 动画片段
        
        Returns:
            Dict[str, Any]: 动画数据
        """
        return {
            'duration_seconds': animation_clip.duration_seconds,
            'easing': animation_clip.easing,
            'animation_type': animation_clip.animation_type,
            'keyframes': [
                {
                    'time_microseconds': kf.time_microseconds,
                    'time_seconds': kf.time_microseconds / 1_000_000,
                    'scale': kf.scale,
                    'x_offset': kf.x_offset,
                    'y_offset': kf.y_offset,
                    'opacity': kf.opacity,
                    'rotation': kf.rotation
                }
                for kf in animation_clip.keyframes
            ]
        }
    
    def get_animation_stats(self) -> Dict[str, Any]:
        """获取动画配置统计信息"""
        return {
            'scene_scale_range': self.scene_scale_range,
            'character_scale_sequence': self.character_scale_sequence,
            'character_scale_timing': self.character_scale_timing,
            'easing': self.easing,
            'in_animation': self.in_animation,
            'in_animation_duration_ms': self.in_animation_duration / 1000,
            'supported_animations': list(self.animation_types.keys())
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"AnimationProcessor(easing={self.easing}, types={len(self.animation_types)})"