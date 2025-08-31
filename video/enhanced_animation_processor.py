"""
增强动画效果处理器 - TikTok风格Ken Burns效果
基于原工作流升级，支持多样化动画模式和全屏显示
"""
import time
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import logging
from dataclasses import dataclass
import json
import random
import math

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
    ken_burns_params: Dict[str, Any] = None  # Ken Burns效果参数

@dataclass
class AnimationRequest:
    """动画处理请求"""
    image_path: str            # 图像路径
    duration_seconds: float    # 动画时长
    animation_type: str = "智能选择"  # 动画类型
    is_character: bool = False # 是否是角色图像

class EnhancedAnimationProcessor:
    """
    增强动画效果处理器 - TikTok风格Ken Burns效果
    
    升级原工作流配置以支持：
    - 多样化Ken Burns动画模式（8种）
    - 1024x1024图像适配720x1280视频
    - 智能动画选择算法
    - 增强视觉冲击力
    - 场景缩放范围：[1.0, 2.0] (增强)
    - 主角缩放序列：[2.5, 1.8, 1.2, 1.0] (渐进式)
    """
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.logger = logging.getLogger('story_generator.video')
        
        # 获取动画配置
        self.animation_config = config_manager.get('animation', {})
        # 简化动作白名单（可通过配置覆盖）
        self.allowed_simple_modes = self.animation_config.get('allowed_modes', [
            'center_zoom_in', 'center_zoom_out', 'move_left', 'move_right', 'move_up', 'move_down'
        ])
        
        # Ken Burns动画模式映射
        self.ken_burns_modes = {
            '中心放大': 'zoom_in_center',
            '左侧缩小': 'zoom_out_left', 
            '右移缩放': 'pan_right_zoom',
            '对角缩放': 'diagonal_zoom',
            '平滑漂移': 'smooth_drift',
            '螺旋缩放': 'spiral_zoom',
            '波浪移动': 'wave_motion',
            '随机探索': 'random_explore'
        }
        
        # 缩放参数优化（适配1024x1024→720x1280）
        self.enhanced_zoom_ranges = [
            (1.0, 2.0),   # 大幅缩放（TikTok风格）
            (1.5, 1.0),   # 缩小回退
            (1.2, 1.8),   # 中等缩放
            (1.1, 2.2),   # 超级放大
            (1.3, 1.1),   # 轻微变化
            (0.8, 1.6),   # 从缩小开始
        ]
        
        # 移动路径参数
        self.movement_patterns = {
            'static': (0, 0),           # 静态
            'drift_right': (0.15, 0),   # 右漂移（增强）
            'drift_left': (-0.15, 0),   # 左漂移
            'drift_up': (0, -0.15),     # 上漂移
            'drift_down': (0, 0.15),    # 下漂移
            'diagonal_ne': (0.1, -0.1), # 东北对角
            'diagonal_sw': (-0.1, 0.1), # 西南对角
            'circular': (0.08, 0.08),   # 圆形运动
        }
        
        # 主角动画配置（增强版）
        self.character_scale_sequence = [2.5, 1.8, 1.2, 1.0]  # 更渐进的缩放
        self.character_scale_timing = [0, 400000, 800000]  # 微秒时间点
        
        # 缓动类型
        self.easing = self.animation_config.get('easing', 'linear')
        
        self.logger.info("Enhanced Animation Processor initialized with 8 Ken Burns modes")
    
    def create_scene_animation(self, request: AnimationRequest, scene_index: int = 0) -> AnimationClip:
        """
        创建场景动画 - TikTok风格Ken Burns效果
        
        Args:
            request: 动画请求
            scene_index: 场景索引，用于选择动画模式
        
        Returns:
            AnimationClip: 动画片段
        """
        try:
            # 🎯 简化模式选择（优先使用简单模式）
            mode = self._select_ken_burns_mode(scene_index)
            if mode in ['center_zoom_in', 'zoom_in_center']:
                return self._create_ken_burns_zoom_in_center(request, scene_index)
            if mode == 'center_zoom_out':
                return self._create_center_zoom_out(request, scene_index)
            if mode == 'move_left':
                return self._create_pan_move(request, scene_index, axis='x', direction=-1)
            if mode == 'move_right':
                return self._create_pan_move(request, scene_index, axis='x', direction=1)
            if mode == 'move_up':
                return self._create_pan_move(request, scene_index, axis='y', direction=-1)
            if mode == 'move_down':
                return self._create_pan_move(request, scene_index, axis='y', direction=1)
            
            # 兼容旧模式
            if mode == 'zoom_out_left':
                return self._create_ken_burns_zoom_out_left(request, scene_index)
            if mode == 'pan_right_zoom':
                return self._create_ken_burns_pan_right_zoom(request, scene_index)
            if mode == 'diagonal_zoom':
                return self._create_ken_burns_diagonal_zoom(request, scene_index)
            if mode == 'smooth_drift':
                return self._create_ken_burns_smooth_drift(request, scene_index)
            if mode == 'spiral_zoom':
                return self._create_ken_burns_spiral_zoom(request, scene_index)
            if mode == 'wave_motion':
                return self._create_ken_burns_wave_motion(request, scene_index)
            if mode == 'random_explore':
                return self._create_ken_burns_random_explore(request, scene_index)
            
            # 默认
            return self._create_ken_burns_zoom_in_center(request, scene_index)
                
        except Exception as e:
            self.logger.error(f"Failed to create Ken Burns animation: {e}")
            # 返回基础动画
            return self._create_basic_ken_burns(request)
    
    def _select_ken_burns_mode(self, scene_index: int) -> str:
        """在简化动作集合中轮换选择（可通过配置覆盖）"""
        modes = self.allowed_simple_modes if self.allowed_simple_modes else ['center_zoom_in']
        return modes[scene_index % len(modes)]
    
    def _create_ken_burns_zoom_in_center(self, request: AnimationRequest, scene_index: int) -> AnimationClip:
        """Ken Burns - 中心放大动画（TikTok风格增强版）"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        # 使用配置的简单缩放范围（更慢更稳）
        cfg_range = self.animation_config.get('scene_scale_range', [1.0, 1.15])
        if isinstance(cfg_range, (list, tuple)) and len(cfg_range) == 2:
            start_scale, end_scale = float(cfg_range[0]), float(cfg_range[1])
        else:
            start_scale, end_scale = 1.0, 1.15
        
        # 创建平滑的中心放大动画
        keyframes = [
            # 开始：起始缩放
            Keyframe(time_microseconds=0, scale=start_scale, x_offset=0, y_offset=0, opacity=1.0),
            # 结束：目标缩放（中心点不变）
            Keyframe(time_microseconds=duration_us, scale=end_scale, x_offset=0, y_offset=0, opacity=1.0)
        ]
        
        # Ken Burns参数
        ken_burns_params = {
            'mode': 'zoom_in_center',
            'zoom_start': start_scale,
            'zoom_end': end_scale,
            'pan_x': 0,
            'pan_y': 0,
            'focus_point': 'center'
        }
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="ken_burns_zoom_in_center",
            ken_burns_params=ken_burns_params
        )

    def _create_center_zoom_out(self, request: AnimationRequest, scene_index: int) -> AnimationClip:
        """简化版中心缩小动画"""
        duration_us = int(request.duration_seconds * 1_000_000)
        cfg_range = self.animation_config.get('scene_scale_range', [1.0, 1.15])
        if isinstance(cfg_range, (list, tuple)) and len(cfg_range) == 2:
            start_scale, end_scale = float(cfg_range[1]), float(cfg_range[0])  # 反向
        else:
            start_scale, end_scale = 1.15, 1.0
        keyframes = [
            Keyframe(time_microseconds=0, scale=start_scale, x_offset=0, y_offset=0, opacity=1.0),
            Keyframe(time_microseconds=duration_us, scale=end_scale, x_offset=0, y_offset=0, opacity=1.0)
        ]
        params = {
            'mode': 'center_zoom_out',
            'zoom_start': start_scale,
            'zoom_end': end_scale
        }
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="center_zoom_out",
            ken_burns_params=params
        )

    def _create_pan_move(self, request: AnimationRequest, scene_index: int, axis: str, direction: int) -> AnimationClip:
        """简化版平移动作（不缩放或极小缩放）"""
        duration_us = int(request.duration_seconds * 1_000_000)
        # 使用1.0缩放，留给平移空间由滤镜scale*2来保证
        keyframes = [
            Keyframe(time_microseconds=0, scale=1.0, x_offset=0, y_offset=0, opacity=1.0),
            Keyframe(time_microseconds=duration_us, scale=1.0, x_offset=0, y_offset=0, opacity=1.0)
        ]
        mode_map = {('x', -1): 'move_left', ('x', 1): 'move_right', ('y', -1): 'move_up', ('y', 1): 'move_down'}
        params = {
            'mode': mode_map.get((axis, direction), 'move_left'),
            'axis': axis,
            'direction': direction
        }
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing='linear',
            animation_type="simple_pan",
            ken_burns_params=params
        )
    
    def _create_ken_burns_zoom_out_left(self, request: AnimationRequest, scene_index: int) -> AnimationClip:
        """Ken Burns - 左侧缩小动画"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        # 从放大开始缩小到正常，同时向左移动
        keyframes = [
            Keyframe(time_microseconds=0, scale=1.8, x_offset=0.1, y_offset=0, opacity=1.0),
            Keyframe(time_microseconds=duration_us, scale=1.0, x_offset=-0.1, y_offset=0, opacity=1.0)
        ]
        
        ken_burns_params = {
            'mode': 'zoom_out_left',
            'zoom_start': 1.8,
            'zoom_end': 1.0,
            'pan_start_x': 0.1,
            'pan_end_x': -0.1,
            'focus_point': 'left'
        }
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="ken_burns_zoom_out_left",
            ken_burns_params=ken_burns_params
        )
    
    def _create_ken_burns_pan_right_zoom(self, request: AnimationRequest, scene_index: int) -> AnimationClip:
        """Ken Burns - 右移缩放动画"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        keyframes = [
            Keyframe(time_microseconds=0, scale=1.2, x_offset=-0.15, y_offset=0, opacity=1.0),
            Keyframe(time_microseconds=duration_us, scale=1.7, x_offset=0.15, y_offset=0, opacity=1.0)
        ]
        
        ken_burns_params = {
            'mode': 'pan_right_zoom',
            'zoom_start': 1.2,
            'zoom_end': 1.7,
            'movement': 'drift_right',
            'focus_point': 'right'
        }
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="ken_burns_pan_right_zoom",
            ken_burns_params=ken_burns_params
        )
    
    def _create_ken_burns_diagonal_zoom(self, request: AnimationRequest, scene_index: int) -> AnimationClip:
        """Ken Burns - 对角缩放动画"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        keyframes = [
            Keyframe(time_microseconds=0, scale=1.0, x_offset=-0.1, y_offset=0.1, opacity=1.0),
            Keyframe(time_microseconds=duration_us, scale=1.9, x_offset=0.1, y_offset=-0.1, opacity=1.0)
        ]
        
        ken_burns_params = {
            'mode': 'diagonal_zoom',
            'zoom_start': 1.0,
            'zoom_end': 1.9,
            'movement': 'diagonal_ne',
            'focus_point': 'diagonal'
        }
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="ken_burns_diagonal_zoom",
            ken_burns_params=ken_burns_params
        )
    
    def _create_ken_burns_smooth_drift(self, request: AnimationRequest, scene_index: int) -> AnimationClip:
        """Ken Burns - 平滑漂移动画"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        # 轻微缩放 + 平滑漂移
        keyframes = [
            Keyframe(time_microseconds=0, scale=1.1, x_offset=0, y_offset=-0.05, opacity=1.0),
            Keyframe(time_microseconds=duration_us//2, scale=1.3, x_offset=0.05, y_offset=0, opacity=1.0),
            Keyframe(time_microseconds=duration_us, scale=1.2, x_offset=0, y_offset=0.05, opacity=1.0)
        ]
        
        ken_burns_params = {
            'mode': 'smooth_drift',
            'zoom_start': 1.1,
            'zoom_end': 1.2,
            'movement': 'smooth_path',
            'focus_point': 'drift'
        }
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing='ease_in_out',
            animation_type="ken_burns_smooth_drift",
            ken_burns_params=ken_burns_params
        )
    
    def _create_ken_burns_spiral_zoom(self, request: AnimationRequest, scene_index: int) -> AnimationClip:
        """Ken Burns - 螺旋缩放动画"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        # 创建螺旋路径关键帧
        keyframes = []
        num_frames = 4  # 4个关键帧形成螺旋
        
        for i in range(num_frames + 1):
            t = i / num_frames
            time_us = int(t * duration_us)
            
            # 螺旋参数
            angle = t * 2 * math.pi * 0.3  # 不到一个完整圆
            radius = 0.08 * (1 - t)  # 半径逐渐缩小
            
            x_offset = radius * math.cos(angle)
            y_offset = radius * math.sin(angle)
            scale = 1.2 + 0.6 * t  # 从1.2缩放到1.8
            
            keyframes.append(Keyframe(
                time_microseconds=time_us,
                scale=scale,
                x_offset=x_offset,
                y_offset=y_offset,
                opacity=1.0
            ))
        
        ken_burns_params = {
            'mode': 'spiral_zoom',
            'zoom_start': 1.2,
            'zoom_end': 1.8,
            'movement': 'spiral',
            'focus_point': 'spiral_center'
        }
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="ken_burns_spiral_zoom",
            ken_burns_params=ken_burns_params
        )
    
    def _create_ken_burns_wave_motion(self, request: AnimationRequest, scene_index: int) -> AnimationClip:
        """Ken Burns - 波浪移动动画"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        keyframes = []
        num_frames = 5
        
        for i in range(num_frames + 1):
            t = i / num_frames
            time_us = int(t * duration_us)
            
            # 波浪运动
            wave_x = 0.1 * math.sin(t * math.pi * 2)
            wave_y = 0.05 * math.sin(t * math.pi * 4)  # 不同频率的Y轴波动
            scale = 1.3 + 0.4 * math.sin(t * math.pi)  # 缩放也呈波浪形
            
            keyframes.append(Keyframe(
                time_microseconds=time_us,
                scale=scale,
                x_offset=wave_x,
                y_offset=wave_y,
                opacity=1.0
            ))
        
        ken_burns_params = {
            'mode': 'wave_motion',
            'zoom_start': 1.3,
            'zoom_end': 1.3,
            'movement': 'wave',
            'focus_point': 'wave_center'
        }
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="ken_burns_wave_motion",
            ken_burns_params=ken_burns_params
        )
    
    def _create_ken_burns_random_explore(self, request: AnimationRequest, scene_index: int) -> AnimationClip:
        """Ken Burns - 随机探索动画"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        # 随机生成3-4个关键帧
        num_keyframes = random.randint(3, 4)
        keyframes = []
        
        for i in range(num_keyframes + 1):
            t = i / num_keyframes
            time_us = int(t * duration_us)
            
            # 随机参数（但保持在合理范围内）
            scale = random.uniform(1.1, 2.0)
            x_offset = random.uniform(-0.12, 0.12)
            y_offset = random.uniform(-0.1, 0.1)
            
            keyframes.append(Keyframe(
                time_microseconds=time_us,
                scale=scale,
                x_offset=x_offset,
                y_offset=y_offset,
                opacity=1.0
            ))
        
        ken_burns_params = {
            'mode': 'random_explore',
            'zoom_start': keyframes[0].scale,
            'zoom_end': keyframes[-1].scale,
            'movement': 'random',
            'focus_point': 'random'
        }
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="ken_burns_random_explore",
            ken_burns_params=ken_burns_params
        )
    
    def _create_basic_ken_burns(self, request: AnimationRequest) -> AnimationClip:
        """创建基础Ken Burns动画（容错版本）"""
        duration_us = int(request.duration_seconds * 1_000_000)
        
        keyframes = [
            Keyframe(time_microseconds=0, scale=1.0, opacity=1.0),
            Keyframe(time_microseconds=duration_us, scale=1.5, opacity=1.0)
        ]
        
        ken_burns_params = {
            'mode': 'basic_zoom',
            'zoom_start': 1.0,
            'zoom_end': 1.5
        }
        
        return AnimationClip(
            duration_seconds=request.duration_seconds,
            keyframes=keyframes,
            easing=self.easing,
            animation_type="ken_burns_basic",
            ken_burns_params=ken_burns_params
        )
    
    def create_character_animation(self, request: AnimationRequest) -> AnimationClip:
        """
        创建角色动画（增强版主角缩放序列）
        """
        try:
            duration_microseconds = int(request.duration_seconds * 1_000_000)
            
            keyframes = []
            
            # 使用增强的主角缩放序列
            for i, scale in enumerate(self.character_scale_sequence):
                if i < len(self.character_scale_timing):
                    time_us = self.character_scale_timing[i]
                else:
                    # 剩余关键帧均匀分布
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
            
            ken_burns_params = {
                'mode': 'character_enhanced',
                'scale_sequence': self.character_scale_sequence,
                'timing': self.character_scale_timing
            }
            
            return AnimationClip(
                duration_seconds=request.duration_seconds,
                keyframes=keyframes,
                easing=self.easing,
                animation_type="character_enhanced_sequence",
                ken_burns_params=ken_burns_params
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create character animation: {e}")
            return self._create_basic_ken_burns(request)
    
    def generate_enhanced_ffmpeg_filter(self, animation_clip: AnimationClip, 
                                       video_resolution: Tuple[int, int] = (720, 1280)) -> str:
        """
        生成增强版FFmpeg滤镜字符串 - 支持Ken Burns效果
        
        Args:
            animation_clip: 动画片段
            video_resolution: 视频分辨率 (width, height)
        
        Returns:
            str: FFmpeg滤镜字符串
        """
        try:
            if not animation_clip.keyframes or not animation_clip.ken_burns_params:
                return self._generate_basic_filter(video_resolution)
            
            video_width, video_height = video_resolution
            params = animation_clip.ken_burns_params
            
            # 根据模式生成对应的zoompan滤镜
            mode = params.get('mode')
            if mode in ['zoom_in_center', 'center_zoom_in']:
                return self._generate_zoom_in_center_filter(params, video_resolution, animation_clip.duration_seconds)
            elif mode == 'center_zoom_out':
                return self._generate_center_zoom_out_filter(params, video_resolution, animation_clip.duration_seconds)
            elif mode == 'zoom_out_left':
                return self._generate_zoom_out_left_filter(params, video_resolution, animation_clip.duration_seconds)
            elif mode == 'pan_right_zoom':
                return self._generate_pan_right_zoom_filter(params, video_resolution, animation_clip.duration_seconds)
            elif mode == 'diagonal_zoom':
                return self._generate_diagonal_zoom_filter(params, video_resolution, animation_clip.duration_seconds)
            elif mode in ['move_left', 'move_right', 'move_up', 'move_down']:
                return self._generate_simple_pan_filter(params, video_resolution, animation_clip.duration_seconds)
            elif params.get('mode') in ['smooth_drift', 'spiral_zoom', 'wave_motion']:
                return self._generate_complex_motion_filter(animation_clip, video_resolution)
            else:
                return self._generate_basic_zoom_filter(params, video_resolution, animation_clip.duration_seconds)
                
        except Exception as e:
            self.logger.error(f"Failed to generate enhanced FFmpeg filter: {e}")
            return self._generate_basic_filter(video_resolution)
    
    def _generate_zoom_in_center_filter(self, params: Dict, resolution: Tuple[int, int], duration: float) -> str:
        """生成中心放大滤镜"""
        width, height = resolution
        zoom_start = params.get('zoom_start', 1.0)
        zoom_end = params.get('zoom_end', 1.1)
        frames = int(duration * 30)  # 30fps
        
        # 使用zoompan滤镜实现平滑中心缩放
        return (f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,"
                f"crop={width*2}:{height*2},"
                f"zoompan=z='min({zoom_start}+({zoom_end}-{zoom_start})*on/{frames},{zoom_end})'"
                f":d={frames}:s={width}x{height}:fps=30")

    def _generate_center_zoom_out_filter(self, params: Dict, resolution: Tuple[int, int], duration: float) -> str:
        """生成中心缩小滤镜"""
        width, height = resolution
        zoom_start = params.get('zoom_start', 1.1)
        zoom_end = params.get('zoom_end', 1.0)
        frames = int(duration * 30)
        return (f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,"
                f"crop={width*2}:{height*2},"
                f"zoompan=z='max({zoom_start}-({zoom_start}-{zoom_end})*on/{frames},{zoom_end})'"
                f":d={frames}:s={width}x{height}:fps=30")
    
    def _generate_zoom_out_left_filter(self, params: Dict, resolution: Tuple[int, int], duration: float) -> str:
        """生成左侧缩小滤镜"""
        width, height = resolution
        frames = int(duration * 30)
        
        return (f"scale={width*3}:{height*3}:force_original_aspect_ratio=increase,"
                f"crop={width*3}:{height*3},"
                f"zoompan=z='1.8-0.8*on/{frames}'"
                f":x='iw*(0.1-0.2*on/{frames})'"
                f":d={frames}:s={width}x{height}:fps=30")
    
    def _generate_pan_right_zoom_filter(self, params: Dict, resolution: Tuple[int, int], duration: float) -> str:
        """生成右移缩放滤镜"""
        width, height = resolution
        frames = int(duration * 30)
        
        return (f"scale={width*3}:{height*3}:force_original_aspect_ratio=increase,"
                f"crop={width*3}:{height*3},"
                f"zoompan=z='1.2+0.5*on/{frames}'"
                f":x='iw*(-0.15+0.3*on/{frames})'"
                f":d={frames}:s={width}x{height}:fps=30")

    def _generate_simple_pan_filter(self, params: Dict, resolution: Tuple[int, int], duration: float) -> str:
        """生成简单平移动作（不缩放，缓慢）"""
        width, height = resolution
        frames = int(duration * 30)
        mode = params.get('mode')
        # 先放大到2x保证平移不露边，再用zoompan以z=1保持不变，仅移动x/y
        base = f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,crop={width*2}:{height*2},"
        # 在z=1、输入尺寸为(2w,2h)、输出尺寸为(w,h)时，可见窗口最大平移范围：dx = (2w - w) = w，dy = (2h - h) = h
        # 使用完整范围 0..dx 或 0..dy，确保始终可见且不会被钳制
        if mode == 'move_left':
            # 右 -> 左：从最右(=dx)移动到最左(=0)
            x = f"{width}*(1 - on/{frames})"
            y = "0"
        elif mode == 'move_right':
            # 左 -> 右：从最左(=0)移动到最右(=dx)
            x = f"{width}*(on/{frames})"
            y = "0"
        elif mode == 'move_up':
            # 下 -> 上：从最下(=dy)移动到最上(=0)
            x = "0"
            y = f"{height}*(1 - on/{frames})"
        else:  # move_down
            # 上 -> 下：从最上(=0)移动到最下(=dy)
            x = "0"
            y = f"{height}*(on/{frames})"
        return (base +
                f"zoompan=z='1.0':x='{x}':y='{y}':d={frames}:s={width}x{height}:fps=30")
    
    def _generate_diagonal_zoom_filter(self, params: Dict, resolution: Tuple[int, int], duration: float) -> str:
        """生成对角缩放滤镜"""
        width, height = resolution
        frames = int(duration * 30)
        
        return (f"scale={width*3}:{height*3}:force_original_aspect_ratio=increase,"
                f"crop={width*3}:{height*3},"
                f"zoompan=z='1.0+0.9*on/{frames}'"
                f":x='iw*(-0.1+0.2*on/{frames})'"
                f":y='ih*(0.1-0.2*on/{frames})'"
                f":d={frames}:s={width}x{height}:fps=30")
    
    def _generate_complex_motion_filter(self, animation_clip: AnimationClip, resolution: Tuple[int, int]) -> str:
        """生成复杂运动滤镜（用于螺旋、波浪等）"""
        width, height = resolution
        duration = animation_clip.duration_seconds
        frames = int(duration * 30)
        
        # 对于复杂运动，使用基础缩放 + 后期可以添加更复杂的表达式
        return (f"scale={width*3}:{height*3}:force_original_aspect_ratio=increase,"
                f"crop={width*3}:{height*3},"
                f"zoompan=z='1.3+0.4*sin(2*PI*on/{frames})'"
                f":x='iw*0.1*sin(4*PI*on/{frames})'"
                f":y='ih*0.05*sin(8*PI*on/{frames})'"
                f":d={frames}:s={width}x{height}:fps=30")
    
    def _generate_basic_zoom_filter(self, params: Dict, resolution: Tuple[int, int], duration: float) -> str:
        """生成基础缩放滤镜"""
        width, height = resolution
        zoom_start = params.get('zoom_start', 1.0)
        zoom_end = params.get('zoom_end', 1.5)
        frames = int(duration * 30)
        
        return (f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,"
                f"crop={width*2}:{height*2},"
                f"zoompan=z='min({zoom_start}+({zoom_end}-{zoom_start})*on/{frames},{zoom_end})'"
                f":d={frames}:s={width}x{height}:fps=30")
    
    def _generate_basic_filter(self, resolution: Tuple[int, int]) -> str:
        """生成基础滤镜（容错版本）"""
        width, height = resolution
        return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    
    def batch_create_enhanced_animations(self, requests: List[AnimationRequest]) -> List[AnimationClip]:
        """
        批量创建增强动画
        """
        self.logger.info(f"Batch creating {len(requests)} enhanced Ken Burns animations")
        
        animations = []
        
        for i, request in enumerate(requests):
            try:
                if request.is_character:
                    animation = self.create_character_animation(request)
                else:
                    animation = self.create_scene_animation(request, scene_index=i)
                animations.append(animation)
                
                # 记录动画类型
                mode = animation.ken_burns_params.get('mode', 'unknown') if animation.ken_burns_params else 'basic'
                self.logger.info(f"Scene {i+1}: {mode} animation created")
                
            except Exception as e:
                self.logger.error(f"Failed to create enhanced animation {i}: {e}")
                animations.append(self._create_basic_ken_burns(request))
        
        return animations
    
    def get_animation_stats(self) -> Dict[str, Any]:
        """获取增强动画配置统计信息"""
        return {
            'ken_burns_modes': list(self.ken_burns_modes.keys()),
            'enhanced_zoom_ranges': self.enhanced_zoom_ranges,
            'movement_patterns': list(self.movement_patterns.keys()),
            'character_scale_sequence': self.character_scale_sequence,
            'character_scale_timing': self.character_scale_timing,
            'easing': self.easing,
            'supported_animations': len(self.ken_burns_modes)
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"EnhancedAnimationProcessor(ken_burns_modes={len(self.ken_burns_modes)}, easing={self.easing})"