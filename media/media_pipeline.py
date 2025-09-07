"""
媒体生成流水线 - 整合图像和音频生成
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from content.scene_splitter import Scene, SceneSplitResult
from content.character_analyzer import Character, CharacterAnalysisResult
from media.image_generator import ImageGenerator, ImageGenerationRequest, GeneratedImage
from media.audio_generator import AudioGenerator, AudioGenerationRequest, GeneratedAudio
from media.text_to_video_generator import TextToVideoGenerator, TextToVideoRequest, TextToVideoResult

@dataclass
class MediaGenerationRequest:
    """媒体生成流水线请求"""
    scenes: List[Scene]              # 场景列表
    characters: List[Character]      # 角色列表
    main_character: Optional[Character]  # 主角
    language: str                    # 语言代码
    script_title: str               # 文案标题
    full_script: str                # 完整文案
    audio_segments: Optional[List[Dict[str, Any]]] = None  # 音频片段信息（新增）

@dataclass
class SceneMedia:
    """场景媒体资源"""
    scene: Scene                     # 场景信息
    image: Optional[GeneratedImage] = None           # 场景图像（传统模式）
    audio: Optional[GeneratedAudio] = None           # 场景音频
    video: Optional[TextToVideoResult] = None        # 一体化视频（新模式）
    
@dataclass
class MediaGenerationResult:
    """媒体生成流水线结果"""
    scene_media: List[SceneMedia]    # 场景媒体列表
    character_images: Dict[str, GeneratedImage]  # 角色图像
    title_audio: Optional[GeneratedAudio]  # 标题音频
    background_music_path: Optional[str]   # 背景音乐路径
    total_processing_time: float     # 总处理时间
    request: MediaGenerationRequest  # 原始请求

class MediaPipeline:
    """
    媒体生成流水线
    
    功能：
    1. 为每个场景生成图像和音频
    2. 为主要角色生成图像  
    3. 生成标题音频
    4. 处理背景音乐
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.media')
        
        # 初始化生成器
        self.image_generator = ImageGenerator(config_manager, file_manager)
        self.audio_generator = AudioGenerator(config_manager, file_manager)
        
        # 检查是否启用一体化文生视频
        self.enable_integrated_generation = self._check_integrated_generation_support()
        
        if self.enable_integrated_generation:
            try:
                self.text_to_video_generator = TextToVideoGenerator(config_manager, file_manager)
                self.logger.info("TextToVideoGenerator initialized successfully")
            except Exception as e:
                raise RuntimeError(f"TextToVideoGenerator initialization failed: {e}. Please check RunningHub API configuration.")
        else:
            raise RuntimeError("Integrated generation is disabled. Please enable 'media.enable_integrated_generation' in configuration.")
        
        # 获取配置
        self.media_config = config_manager.get('media', {})
        self.image_config = self.media_config.get('image', {})
        self.audio_config = self.media_config.get('audio', {})
        
        generation_mode = "integrated text-to-video" if self.enable_integrated_generation else "traditional image+audio"
        self.logger.info(f"Media pipeline initialized with {generation_mode} generation")
    
    def _check_integrated_generation_support(self) -> bool:
        """检查是否支持一体化文生视频生成"""
        try:
            # 检查RunningHub API密钥
            runninghub_key = self.config.get_api_key('runninghub')
            if not runninghub_key:
                self.logger.info("RunningHub API key not configured, using traditional mode")
                return False
            
            # 检查配置中是否启用一体化模式
            enable_integrated = self.config.get('media.enable_integrated_generation', True)
            if not enable_integrated:
                self.logger.info("Integrated generation disabled in configuration")
                return False
            
            self.logger.info("Integrated text-to-video generation enabled")
            return True
            
        except Exception as e:
            self.logger.warning(f"Error checking integrated generation support: {e}")
            return False
    
    async def generate_media_async(self, request: MediaGenerationRequest) -> MediaGenerationResult:
        """
        异步媒体生成流水线
        
        Args:
            request: 媒体生成请求
        
        Returns:
            MediaGenerationResult: 生成结果
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting media generation pipeline: {len(request.scenes)} scenes, {len(request.characters)} characters")
            
            # 并行任务列表
            tasks = []
            
            # 任务1：生成场景媒体（一体化文生视频模式）
            scene_task = self._generate_integrated_scene_media(
                request.scenes, 
                request.language, 
                request.audio_segments  # 传递音频片段信息
            )
            tasks.append(('scenes', scene_task))
            
            # 任务2：生成角色图像
            if request.characters:
                character_task = self._generate_character_images(request.characters, request.language)
                tasks.append(('characters', character_task))
            
            # 任务3：生成标题音频
            if request.script_title:
                title_task = self._generate_title_audio(request.script_title, request.language)
                tasks.append(('title', title_task))
            
            # 并行执行所有任务
            self.logger.info("Executing media generation tasks in parallel...")
            results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
            
            # 处理结果
            scene_media = []
            character_images = {}
            title_audio = None
            
            for i, (task_type, result) in enumerate(zip([task[0] for task in tasks], results)):
                if isinstance(result, Exception):
                    self.logger.error(f"Media generation task '{task_type}' failed: {result}")
                    if task_type == 'scenes':
                        raise result  # 场景媒体是必需的
                    continue
                
                if task_type == 'scenes':
                    scene_media = result
                elif task_type == 'characters':
                    character_images = result
                elif task_type == 'title':
                    title_audio = result
            
            # 处理背景音乐（如果需要）
            background_music_path = await self._prepare_background_music(request)
            
            # 创建结果对象
            total_time = time.time() - start_time
            result = MediaGenerationResult(
                scene_media=scene_media,
                character_images=character_images,
                title_audio=title_audio,
                background_music_path=background_music_path,
                total_processing_time=total_time,
                request=request
            )
            
            self.logger.info(f"Media generation completed in {total_time:.2f}s")
            self.logger.info(f"Generated: {len(scene_media)} scene media, {len(character_images)} character images")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Media generation pipeline failed after {processing_time:.2f}s: {e}")
            raise
    
    async def _generate_scene_media(self, scenes: List[Scene], language: str) -> List[SceneMedia]:
        """生成场景媒体（仅图像）- 音频由主程序统一生成"""
        self.logger.info(f"Generating images for {len(scenes)} scenes...")
        
        # 只处理图像请求，避免重复音频生成
        image_requests = []
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 获取动画策略以确定图片分辨率
        animation_strategy = self.config.get('video.animation_strategy', 'traditional')
        
        for idx, scene in enumerate(scenes, start=1):
            # 图像请求 - 使用自适应分辨率
            prompt = scene.image_prompt if scene.image_prompt else f"历史场景：{scene.content}"
            
            # 🎯 自适应分辨率：根据动画策略选择分辨率
            width, height = self.image_generator.get_adaptive_resolution(animation_strategy)
            
            image_req = ImageGenerationRequest(
                prompt=prompt,
                style="ancient_horror",
                width=width,
                height=height,
                scene_id=f"scene_{idx}_{timestamp}"
            )
            image_requests.append((scene, image_req))
        
        # 使用批量生成方法（带并发控制） 
        max_concurrent = self.config.get('general.max_concurrent_tasks', 5)
        self.logger.info(f"🇮🇲 Using {max_concurrent} concurrent image generations")
        
        # 批量生成图像（返回与输入同序，失败为None）
        image_gen_requests = [req for _, req in image_requests]
        generated_images = await self.image_generator.batch_generate_images(
            image_gen_requests, max_concurrent, animation_strategy=animation_strategy
        )
        
        # 组合结果 - 只包含图像，音频由主程序统一处理
        scene_media = []
        
        for i, scene in enumerate(scenes):
            try:
                # 只检查图像生成是否成功
                image = generated_images[i] if i < len(generated_images) else None
                
                if image:
                    # 🔧 SceneMedia暂时使用None作为audio，避免重复生成
                    scene_media.append(SceneMedia(
                        scene=scene,
                        image=image,
                        audio=None  # 音频由主程序统一生成
                    ))
                    self.logger.info(f"Scene {i+1} image generation successful")
                else:
                    self.logger.error(f"Scene {i+1} image generation failed")
                    
            except Exception as e:
                self.logger.error(f"Scene {i+1} media combination failed: {e}")
        
        self.logger.info(f"Generated {len(scene_media)} complete scene media out of {len(scenes)} scenes")
        return scene_media
    
    async def _generate_integrated_scene_media(self, scenes: List[Scene], language: str, 
                                             audio_segments: Optional[List[Dict[str, Any]]] = None) -> List[SceneMedia]:
        """使用一体化文生视频生成场景媒体
        
        Args:
            scenes: 场景列表
            language: 语言代码
            audio_segments: 音频片段列表，格式为 [{'duration': float, 'scene_id': int, ...}]
        """
        if not self.text_to_video_generator:
            raise RuntimeError("TextToVideoGenerator not available, cannot generate videos. Please check RunningHub API configuration.")
        
        if not audio_segments:
            raise RuntimeError("❌ 音频片段信息是必需的！按照原始Coze工作流，必须先生成音频片段来确定场景时长，然后生成对应时长的视频。")
        
        self.logger.info(f"Generating integrated text-to-videos for {len(scenes)} scenes with audio-based durations...")
        
        # 检查音频片段与场景数量是否匹配
        if len(audio_segments) != len(scenes):
            raise RuntimeError(f"音频片段数量({len(audio_segments)})与场景数量({len(scenes)})不匹配")
        
        # 准备文生视频请求
        video_requests = []
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for idx, (scene, audio_segment) in enumerate(zip(scenes, audio_segments), start=1):
            # 使用场景的图像提示词和视频提示词
            image_prompt = scene.image_prompt if scene.image_prompt else f"历史场景：{scene.content}"
            video_prompt = scene.video_prompt if scene.video_prompt else ""
            
            # 🎵 使用音频片段的实际时长
            scene_duration = audio_segment['duration']
            self.logger.info(f"Scene {idx} duration from audio: {scene_duration:.2f}s")
            
            # 一体化模式固定使用720x1280分辨率（工作流优化分辨率）
            video_req = TextToVideoRequest(
                image_prompt=image_prompt,   # 文生图提示词 (场景描述)
                video_prompt=video_prompt,   # 图生视频提示词 (动作描述) 
                negative_prompt="blurry, low quality, distorted, bad anatomy",
                width=720,
                height=1280,
                fps=31,
                duration=scene_duration,  # 🎵 使用音频实际时长
                style="ancient_horror",
                scene_id=f"scene_{idx}_{timestamp}"
            )
            video_requests.append((scene, video_req))
        
        # 使用批量生成方法（带并发控制）
        # ✅ 统一并发控制：与图像生成使用相同的配置
        max_concurrent = self.config.get('general.max_concurrent_tasks', 5)
        # 最小保障：不低于1，不高于10（合理范围） 
        max_concurrent = max(1, min(max_concurrent, 10))
        self.logger.info(f"🚀 Using {max_concurrent} concurrent video generations (unified with image generation)")
        
        # 批量生成一体化视频
        video_gen_requests = [req for _, req in video_requests]
        
        try:
            generated_videos = await self.text_to_video_generator.batch_generate_videos_v2(
                video_gen_requests, max_concurrent
            )
        except Exception as e:
            # 一体化视频生成完全失败
            error_msg = f"Integrated text-to-video generation completely failed: {e}"
            self.logger.error(error_msg)
            
            # 统一错误处理，不再使用fallback
            is_network_error = "Cannot connect to host" in str(e) or "Connection" in str(e)
            
            if is_network_error:
                raise RuntimeError(f"RunningHub API connection failed. Please check:\n"
                                 f"1. Network connectivity to api.runninghub.cn\n"
                                 f"2. RunningHub API key validity\n"
                                 f"3. Firewall settings\n"
                                 f"Original error: {e}")
            else:
                raise RuntimeError(error_msg)
        
        # 检查生成结果 - 允许部分失败，但提供警告
        successful_videos = [v for v in generated_videos if v is not None]
        failed_count = len(scenes) - len(successful_videos)
        
        if not successful_videos:
            raise RuntimeError(f"All {len(scenes)} integrated video generations failed. "
                             f"Please check RunningHub API configuration and network connectivity.")
        
        if failed_count > 0:
            success_rate = len(successful_videos) / len(scenes) * 100
            self.logger.warning(f"⚠️ 媒体生成部分成功：{len(successful_videos)}/{len(scenes)} ({success_rate:.1f}%)")
            self.logger.warning(f"💔 {failed_count}个场景的视频生成失败，最终视频将缺少这些场景")
            
            if success_rate < 60:
                self.logger.error("🚨 成功率过低，建议检查：")
                self.logger.error("   1. RunningHub API密钥和网络连接")
                self.logger.error("   2. 降低并发数设置")
                self.logger.error("   3. 简化故事内容描述")
        
        # 组合结果 - 根据原始索引正确映射成功的场景
        scene_media = []
        success_indices = {getattr(video, 'original_scene_index', i): video for i, video in enumerate(successful_videos)}
        
        for i, scene in enumerate(scenes):
            try:
                # 检查这个场景索引是否有对应的成功视频
                if i in success_indices:
                    video_result = success_indices[i]
                else:
                    # 这个场景的视频生成失败，跳过
                    self.logger.warning(f"⏭️ 跳过场景{i+1}：'{scene.content[:30]}...' (视频生成失败)")
                    continue
                
                if video_result:
                    # 使用一体化视频结果创建SceneMedia
                    scene_media.append(SceneMedia(
                        scene=scene,
                        image=None,  # 一体化模式不需要单独的图像
                        audio=None,  # 音频仍由主程序统一生成
                        video=video_result  # 一体化视频结果
                    ))
                    self.logger.info(f"Scene {i+1} integrated video generation successful: "
                                   f"{video_result.file_size/1024:.1f}KB, {video_result.duration:.1f}s")
                else:
                    self.logger.error(f"Scene {i+1} integrated video generation failed")
                    
            except Exception as e:
                self.logger.error(f"Scene {i+1} integrated media combination failed: {e}")
        
        success_rate = len(scene_media) / len(scenes) * 100
        self.logger.info(f"Generated {len(scene_media)} integrated scene videos out of {len(scenes)} scenes ({success_rate:.1f}% success rate)")
        
        # 如果成功率太低，给出警告
        if success_rate < 50:
            self.logger.warning(f"Low success rate ({success_rate:.1f}%) for integrated video generation. "
                              f"Consider checking API limits and network stability.")
        
        return scene_media
    
    
    
    
    async def _generate_character_images(self, characters: List[Character], 
                                       language: str) -> Dict[str, GeneratedImage]:
        """生成角色图像 - 仅生成主角色图像（匹配原始Coze工作流设计）"""
        if not characters:
            return {}
        
        # 选择主角色：优先选择标记为主角的，否则选择第一个角色
        main_character = None
        for character in characters:
            if hasattr(character, 'is_main') and character.is_main:
                main_character = character
                break
        
        if not main_character:
            main_character = characters[0]  # 默认第一个角色为主角
        
        self.logger.info(f"Generating image for main character: {main_character.name}")
        
        if not main_character.image_prompt:
            self.logger.warning(f"Main character {main_character.name} has no image prompt")
            return {}
        
        # 准备主角色图像请求
        media_config = self.config.get_media_config()
        width, height = map(int, media_config.image_resolution.split('x'))
        
        request = ImageGenerationRequest(
            prompt=main_character.image_prompt,
            style="ancient_horror",
            width=width,
            height=height
        )
        
        # 生成主角色图像
        try:
            generated_images = await self.image_generator.batch_generate_images(
                [request], max_concurrent=1
            )
            
            if generated_images and generated_images[0]:
                character_images = {main_character.name: generated_images[0]}
                self.logger.info(f"Main character image generated: {main_character.name}")
                return character_images
            else:
                self.logger.error(f"Main character image generation failed: {main_character.name}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Main character image generation error: {e}")
            return {}
    
    
    async def _generate_title_audio(self, title: str, language: str) -> GeneratedAudio:
        """生成标题音频"""
        self.logger.info(f"Generating title audio: {title}")
        
        # 获取主要音频提供商
        primary_provider = self.audio_config.get('primary_provider', 'minimax')
        
        # 根据提供商选择voice_id
        if primary_provider == 'minimax':
            voice_id = self.audio_config.get('minimax_voice', 'male-qn-qingse')
        else:
            voice_id = self.audio_config.get('voice_id', 'pNInz6obpgDQGcFmaJgB')
        
        request = AudioGenerationRequest(
            text=title,
            language=language,
            voice_id=voice_id,
            speed=self.audio_config.get('voice_speed', 1.2),
            volume=self.audio_config.get('voice_volume', 1.0)
        )
        
        return await self.audio_generator.generate_audio_async(request, provider=primary_provider)
    
    async def _prepare_background_music(self, request: MediaGenerationRequest) -> Optional[str]:
        """准备背景音乐"""
        # 这里可以实现背景音乐的处理逻辑
        # 例如从预设音乐库中选择合适的背景音乐
        # 对应原工作流的开场音效配置
        
        opening_sound_duration = self.audio_config.get('opening_sound_duration', 4884897)  # 微秒
        background_music_volume = self.audio_config.get('background_music_volume', 0.3)
        
        # 这里简单返回None，在实际实现中可以处理背景音乐文件
        return None
    
    def generate_media_sync(self, request: MediaGenerationRequest) -> MediaGenerationResult:
        """
        同步媒体生成流水线（对异步方法的包装）
        
        Args:
            request: 媒体生成请求
        
        Returns:
            MediaGenerationResult: 生成结果
        """
        return asyncio.run(self.generate_media_async(request))
    
    async def batch_generate_media(self, requests: List[MediaGenerationRequest], 
                                 max_concurrent: int = 5) -> List[MediaGenerationResult]:
        """
        批量媒体生成
        
        Args:
            requests: 媒体生成请求列表
            max_concurrent: 最大并发数
        
        Returns:
            List[MediaGenerationResult]: 生成结果列表
        """
        self.logger.info(f"Starting batch media generation: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(request: MediaGenerationRequest) -> MediaGenerationResult:
            async with semaphore:
                return await self.generate_media_async(request)
        
        # 执行并发生成
        tasks = [generate_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch media generation failed for request {i}: {result}")
                failed_count += 1
            else:
                successful_results.append(result)
        
        self.logger.info(f"Batch media generation completed: {len(successful_results)} successful, {failed_count} failed")
        
        return successful_results
    
    def save_media_files(self, result: MediaGenerationResult, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        保存所有媒体文件
        
        Args:
            result: 媒体生成结果
            output_dir: 输出目录（可选）
        
        Returns:
            Dict[str, Any]: 保存的文件路径信息
        """
        saved_files = {
            'scene_images': [],
            'scene_audio': [],
            'character_images': {},
            'title_audio': None,
            'manifest': None
        }
        
        try:
            # 保存场景媒体
            for i, scene_media in enumerate(result.scene_media):
                # 保存场景图像
                image_path = self.image_generator.save_image(
                    scene_media.image, 
                    output_dir, 
                    f"scene_{i+1:02d}_image.png"
                )
                saved_files['scene_images'].append(image_path)
                
                # 保存场景音频
                audio_path = self.audio_generator.save_audio(
                    scene_media.audio,
                    output_dir,
                    f"scene_{i+1:02d}_audio.mp3"
                )
                saved_files['scene_audio'].append(audio_path)
            
            # 保存角色图像
            for char_name, char_image in result.character_images.items():
                char_path = self.image_generator.save_image(
                    char_image,
                    output_dir,
                    f"character_{char_name.replace(' ', '_')}.png"
                )
                saved_files['character_images'][char_name] = char_path
            
            # 保存标题音频
            if result.title_audio:
                title_path = self.audio_generator.save_audio(
                    result.title_audio,
                    output_dir,
                    "title_audio.mp3"
                )
                saved_files['title_audio'] = title_path
            
            # 保存媒体清单
            manifest_data = {
                'metadata': {
                    'language': result.request.language,
                    'scene_count': len(result.scene_media),
                    'character_count': len(result.character_images),
                    'total_processing_time': result.total_processing_time,
                    'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
                },
                'scenes': [
                    {
                        'sequence': sm.scene.sequence,
                        'duration': sm.scene.duration_seconds,
                        'image_file': Path(saved_files['scene_images'][i]).name,
                        'audio_file': Path(saved_files['scene_audio'][i]).name,
                        'image_size': sm.image.file_size,
                        'audio_size': sm.audio.file_size
                    }
                    for i, sm in enumerate(result.scene_media)
                ],
                'characters': [
                    {
                        'name': char_name,
                        'image_file': Path(image_path).name,
                        'image_size': result.character_images[char_name].file_size
                    }
                    for char_name, image_path in saved_files['character_images'].items()
                ]
            }
            
            if not output_dir:
                manifest_filename = self.file_manager.generate_filename(
                    content=result.request.script_title,
                    prefix=f"media_manifest_{result.request.language}",
                    extension="json"
                )
                manifest_path = self.file_manager.get_output_path('manifests', manifest_filename)
            else:
                manifest_path = Path(output_dir) / f"media_manifest_{int(time.time())}.json"
            
            success = self.file_manager.save_json(manifest_data, manifest_path)
            if success:
                saved_files['manifest'] = str(manifest_path)
                self.logger.info(f"Saved media manifest to: {manifest_path}")
            
            total_files = (len(saved_files['scene_images']) + 
                          len(saved_files['scene_audio']) + 
                          len(saved_files['character_images']) +
                          (1 if saved_files['title_audio'] else 0))
            
            self.logger.info(f"Saved {total_files} media files")
            
            return saved_files
            
        except Exception as e:
            self.logger.error(f"Failed to save media files: {e}")
            return saved_files
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """获取流水线统计信息"""
        return {
            'components': {
                'image_generator': self.image_generator.get_generation_stats(),
                'audio_generator': self.audio_generator.get_generation_stats()
            },
            # 缓存已删除
            'config': {
                'image': self.image_config,
                'audio': self.audio_config
            }
        }
    
    def estimate_costs(self, request: MediaGenerationRequest) -> Dict[str, Any]:
        """估算生成成本"""
        # 这里可以实现成本估算逻辑
        scene_count = len(request.scenes)
        character_count = len(request.characters)
        
        # 简单的成本估算示例
        estimated_costs = {
            'images': {
                'scene_images': scene_count * 0.02,  # 假设每张图片$0.02
                'character_images': character_count * 0.02
            },
            'audio': {
                'scene_audio': scene_count * 0.01,  # 假设每段音频$0.01
                'title_audio': 0.01 if request.script_title else 0
            }
        }
        
        total_cost = (sum(estimated_costs['images'].values()) + 
                     sum(estimated_costs['audio'].values()))
        
        estimated_costs['total'] = total_cost
        
        return estimated_costs
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"MediaPipeline(image_gen={self.image_generator}, audio_gen={self.audio_generator})"