"""
图像生成器 - 多提供商图像生成支持
支持Gemini 2.5 Flash Image Preview、RunningHub、OpenAI DALL-E、Stability AI等提供商
"""
import asyncio
import aiohttp
import base64
import os
import random
import time
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import logging
from dataclasses import dataclass
from PIL import Image
import io
import hashlib

from core.config_manager import ConfigManager
from utils.file_manager import FileManager

@dataclass
class ImageGenerationRequest:
    """图像生成请求"""
    prompt: str                    # 图像提示词
    negative_prompt: str = ""      # 负面提示词
    style: str = "ancient_horror"  # 风格
    width: int = 1024             # 宽度
    height: int = 1024            # 高度（修改为1024x1024）
    quality: str = "high"         # 质量 (high, standard)
    steps: int = 40               # 采样步数
    model_id: Optional[int] = 8   # 模型ID（RunningHub）
    scene_id: Optional[str] = None # 场景唯一标识符（防止图像重复）

@dataclass
class GeneratedImage:
    """生成的图像"""
    image_data: bytes             # 图像数据
    prompt: str                   # 使用的提示词
    width: int                    # 宽度
    height: int                   # 高度
    file_size: int                # 文件大小
    provider: str                 # 提供商
    model: str                    # 使用的模型
    generation_time: float        # 生成耗时
    file_path: Optional[str] = None  # 保存的文件路径
    remote_url: Optional[str] = None  # 远程URL（用于抠图等后续处理）

class ImageGenerator:
    """
    图像生成器 - 支持多个提供商
    
    支持的提供商：
    1. RunningHub - 主要提供商（Flux模型，对应原工作流）
    2. OpenAI DALL-E - 备用提供商（通过OpenRouter）
    3. Stability AI - 备用提供商
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.media')
        
        # 获取媒体配置
        self.media_config = config_manager.get_media_config()
        self.image_config = config_manager.get('media.image', {})
        self.video_config = config_manager.get('video', {})
        
        # API密钥
        self.api_keys = {
            'runninghub': config_manager.get_api_key('runninghub')
        }
        
        
        # 提供商优先级
        self.primary_provider = self.image_config.get('primary_provider', 'runninghub')  
        # fallback机制已移除，只使用主要提供商
        
        # 默认样式提示词
        self._load_style_prompts()
        
        self.logger.info(f"Image generator initialized with primary provider: {self.primary_provider}")
        self.logger.info(f"Resolution mode: {self.image_config.get('resolution_mode', 'adaptive')}")
    
    def get_adaptive_resolution(self, animation_strategy: str = None) -> tuple[int, int]:
        """
        根据动画策略获取自适应分辨率
        
        Args:
            animation_strategy: 动画策略 (traditional, image_to_video)
        
        Returns:
            tuple[int, int]: (width, height)
        """
        if self.image_config.get('resolution_mode') != 'adaptive':
            # 固定分辨率模式，使用配置的分辨率
            resolution_str = self.image_config.get('resolution', self.image_config.get('traditional_resolution', '832x1216'))
            width, height = map(int, resolution_str.split('x'))
            return (width, height)
        
        # 自适应分辨率模式 - 简化为二选一
        if not animation_strategy:
            animation_strategy = self.video_config.get('animation_strategy', 'traditional')
        
        if animation_strategy == 'image_to_video':
            # 图生视频模式：720x1280
            resolution_str = self.image_config.get('i2v_resolution', '720x1280')
        else:
            # 传统动画模式：832x1216 (为缩放/平移留空间)
            resolution_str = self.image_config.get('traditional_resolution', '832x1216')
        
        width, height = map(int, resolution_str.split('x'))
        self.logger.debug(f"Adaptive resolution for {animation_strategy}: {width}x{height}")
        return (width, height)
    
    def _load_style_prompts(self):
        """加载样式提示词"""
        self.style_prompts = {
            'ancient_horror': {
                'zh': "古代恐怖风格，白色背景，昏暗色调，暮色中，庄严肃穆，威严庄重，营造紧张氛围，古代服饰，传统服装，线条粗糙，清晰，人物特写，笔触粗糙，高清，高对比度，低饱和度颜色，浅景深",
                'en': "ancient horror style, white background, dim colors, in twilight, solemn atmosphere, majestic and dignified, creating tense atmosphere, ancient clothing, traditional garments, rough lines, clear, character close-up, rough brushstrokes, high definition, high contrast, low saturation colors, shallow depth of field",
                'es': "estilo de horror antiguo, fondo blanco, colores tenues, en el crepúsculo, atmósfera solemne, majestuoso y digno, creando atmósfera tensa, ropa antigua, vestimenta tradicional, líneas rugosas, claro, primer plano del personaje, pinceladas rugosas, alta definición, alto contraste, colores de baja saturación, poca profundidad de campo"
            }
        }
    
    async def generate_image_async(self, request: ImageGenerationRequest, 
                                 provider: Optional[str] = None,
                                 animation_strategy: Optional[str] = None) -> GeneratedImage:
        """
        异步生成图像
        
        Args:
            request: 图像生成请求
            provider: 指定提供商（可选）
            animation_strategy: 动画策略（用于自适应分辨率）
        
        Returns:
            GeneratedImage: 生成的图像
        """
        start_time = time.time()
        
        try:
            # 🎯 自适应分辨率：根据动画策略调整图片尺寸
            if self.image_config.get('resolution_mode') == 'adaptive':
                adaptive_width, adaptive_height = self.get_adaptive_resolution(animation_strategy)
                if adaptive_width != request.width or adaptive_height != request.height:
                    self.logger.info(f"Adaptive resolution: {request.width}x{request.height} -> {adaptive_width}x{adaptive_height} (strategy: {animation_strategy})")
                    request.width = adaptive_width
                    request.height = adaptive_height
            
            # 缓存已禁用 - 每次都生成新图像
            
            # 构建完整提示词
            full_prompt = self._build_full_prompt(request)
            
            # 使用RunningHub生成图像
            provider_name = provider if provider else self.primary_provider
            
            if provider_name != 'runninghub':
                raise ValueError(f"Unsupported image provider: {provider_name}. Only 'runninghub' is supported.")
            
            if not self.api_keys.get('runninghub'):
                raise ValueError("No API key configured for RunningHub")
            
            self.logger.info(f"Generating image with RunningHub: {request.prompt[:50]}...")
            
            # 获取重试配置
            max_retries = self.config.get('general.api_max_retries', 3)
            retry_delay = self.config.get('general.retry_delay', 2)
            
            last_error = None
            for attempt in range(max_retries + 1):  # +1 because we want to try max_retries times plus the initial attempt
                try:
                    if attempt > 0:
                        self.logger.info(f"RunningHub retry attempt {attempt}/{max_retries} for image generation...")
                        await asyncio.sleep(retry_delay * attempt)  # 增量延迟
                    
                    result = await self._generate_with_runninghub(request, full_prompt)
                    
                    # 成功生成，跳出重试循环
                    break
                    
                except Exception as e:
                    last_error = e
                    self.logger.warning(f"RunningHub attempt {attempt + 1} failed: {e}")
                    
                    # 如果是最后一次尝试，抛出错误
                    if attempt == max_retries:
                        self.logger.error(f"RunningHub failed after {max_retries + 1} attempts. Last error: {e}")
                        raise e
                    
                    continue
            
            # 处理生成结果
            # 缓存结果
            cache_data = {
                'image_data': result.image_data,
                'prompt': result.prompt,
                'width': result.width,
                'height': result.height,
                'file_size': result.file_size,
                'provider': result.provider,
                'model': result.model
            }
            
            # 缓存已禁用
            
            # 记录日志
            # 保存图像文件（避免跨任务复用/覆盖：使用场景ID+毫秒时间戳+内容指纹命名）
            custom_filename = None
            try:
                content_digest = hashlib.md5(result.image_data).hexdigest()[:8]
                millis = int(time.time() * 1000)
                if request.scene_id:
                    custom_filename = f"img_{request.scene_id}_{provider_name}_{millis}_{content_digest}.png"
                else:
                    custom_filename = None
            except Exception:
                custom_filename = None
            file_path = self.save_image(result, filename=custom_filename) if custom_filename else self.save_image(result)
            result.file_path = file_path
            
            logger = self.config.get_logger('story_generator')
            logger.info(f"Media generation - Type: image, Provider: {provider_name}, "
                       f"Processing time: {result.generation_time:.2f}s, "
                       f"File size: {result.file_size} bytes")
            
            self.logger.info(f"Generated image successfully with RunningHub: {result.file_size / 1024:.1f}KB in {result.generation_time:.2f}s")
            self.logger.info(f"Image saved to: {file_path}")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Image generation failed after {processing_time:.2f}s: {e}")
            
            # 记录错误日志
            logger = self.config.get_logger('story_generator')
            logger.error(f"Media generation failed - Type: image, Provider: unknown, "
                        f"Processing time: {processing_time:.2f}s")
            
            raise
    
    def _build_full_prompt(self, request: ImageGenerationRequest) -> str:
        """构建完整的提示词"""
        prompt_parts = [request.prompt]
        
        # 添加样式提示词
        if request.style in self.style_prompts:
            # 尝试获取当前语言的样式提示词，默认使用英语
            style_prompt = self.style_prompts[request.style].get('en', '')
            if style_prompt:
                prompt_parts.append(style_prompt)
        
        return ', '.join(prompt_parts)
    
    
    async def _generate_with_runninghub(self, request: ImageGenerationRequest, 
                                      full_prompt: str) -> GeneratedImage:
        """
        使用RunningHub ComfyUI API生成图像
        
        基于用户提供的工作流配置
        """
        start_time = time.time()
        
        # 使用通用工作流创建API而不是快捷创作API
        api_url = "https://www.runninghub.cn/task/openapi/create"
        
        # 🎯 获取RunningHub工作流配置
        rh_config = self.image_config.get('runninghub', {})
        workflow_id = rh_config.get('workflow_id', "1958005140101935106")  # 默认兼容旧版
        prompt_node_id = rh_config.get('prompt_node_id', "39")  # 提示词节点ID
        resolution_node_id = rh_config.get('resolution_node_id', "5")  # 分辨率节点ID
        
        # 构建节点参数 - 只修改正向提示词，负向提示词使用工作流默认值
        node_list = [
            {
                "nodeId": prompt_node_id,
                "fieldName": "text",
                "fieldValue": full_prompt
            }
        ]
        
        # 🔧 只有当配置了分辨率节点ID时才添加分辨率控制
        if resolution_node_id and rh_config.get('supports_custom_resolution', False):
            node_list.extend([
                {
                    "nodeId": resolution_node_id,
                    "fieldName": "width",
                    "fieldValue": request.width
                },
                {
                    "nodeId": resolution_node_id,
                    "fieldName": "height", 
                    "fieldValue": request.height
                }
            ])
            self.logger.info(f"Using custom resolution: {request.width}x{request.height}")
        else:
            self.logger.info(f"Using workflow default resolution (custom resolution not configured)")
        
        payload = {
            "apiKey": self.api_keys['runninghub'],
            "workflowId": workflow_id,
            "nodeInfoList": node_list
        }
        
        headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }
        
        self.logger.info(f"RunningHub request: {full_prompt[:50]}...")
        # 🔒 避免记录包含API密钥的payload
        safe_payload = {k: v for k, v in payload.items() if k != 'apiKey'}
        safe_payload['apiKey'] = '***'
        self.logger.debug(f"RunningHub payload: {safe_payload}")
        
        async with aiohttp.ClientSession() as session:
            # 创建任务
            async with session.post(api_url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"RunningHub task creation failed {response.status}: {error_text}")
                
                result = await response.json()
                
                # 根据API文档，成功时code为0
                if result.get('code') != 0:
                    error_msg = result.get('msg', 'Task creation failed')
                    raise Exception(f"RunningHub task failed: {error_msg}")
                
                # 根据API文档，taskId在data对象中，是整数类型
                task_id = result.get('data', {}).get('taskId')
                if not task_id:
                    raise Exception("No task ID returned from RunningHub")
                
                self.logger.info(f"RunningHub quick-ai-app task created: {task_id}")
                
                # 轮询任务状态直到完成
                status_url = "https://www.runninghub.cn/task/openapi/status"
                status_payload = {"taskId": task_id, "apiKey": self.api_keys['runninghub']}
                
                # 等待任务完成（最多等待120秒）
                for attempt in range(120):
                    await asyncio.sleep(1)
                    
                    try:
                        async with session.post(status_url, json=status_payload, headers=headers) as status_response:
                            if status_response.status == 200:
                                status_result = await status_response.json()
                                
                                if status_result.get('code') == 0:
                                    task_status = status_result.get('data')
                                    
                                    if task_status == 'SUCCESS':
                                        self.logger.info(f"RunningHub task {task_id} completed successfully")
                                        
                                        # 获取真实的生成结果
                                        outputs_url = "https://www.runninghub.cn/task/openapi/outputs"
                                        outputs_payload = {"taskId": task_id, "apiKey": self.api_keys['runninghub']}
                                        
                                        try:
                                            async with session.post(outputs_url, json=outputs_payload, headers=headers) as outputs_response:
                                                if outputs_response.status == 200:
                                                    outputs_result = await outputs_response.json()
                                                    if outputs_result.get('code') == 0:
                                                        outputs = outputs_result.get('data', [])
                                                        
                                                        # 寻找图像URL
                                                        self.logger.debug(f"Processing outputs: {outputs}")
                                                        for i, item in enumerate(outputs):
                                                            self.logger.debug(f"Output item {i}: {type(item)}, {item}")
                                                            if isinstance(item, dict) and 'fileUrl' in item:
                                                                image_url = item['fileUrl']
                                                                self.logger.info(f"Found image URL: {image_url}")
                                                                self.logger.info(f"Setting remote_url to: {item['fileUrl']}")
                                                                
                                                                # 下载真实图像
                                                                async with session.get(image_url) as img_response:
                                                                    if img_response.status == 200:
                                                                        image_data = await img_response.read()
                                                                        
                                                                        return GeneratedImage(
                                                                            image_data=image_data,
                                                                            prompt=full_prompt,
                                                                            width=request.width,
                                                                            height=request.height,
                                                                            file_size=len(image_data),
                                                                            provider='runninghub',
                                                                            model=f"flux_task_{task_id}",
                                                                            generation_time=time.time() - start_time,
                                                                            remote_url=item['fileUrl'] if isinstance(item, dict) and 'fileUrl' in item else (item if isinstance(item, str) else None)
                                                                        )
                                                            elif isinstance(item, str) and item.startswith('http'):
                                                                # 处理字符串格式的URL
                                                                async with session.get(item) as img_response:
                                                                    if img_response.status == 200:
                                                                        image_data = await img_response.read()
                                                                        
                                                                        return GeneratedImage(
                                                                            image_data=image_data,
                                                                            prompt=full_prompt,
                                                                            width=request.width,
                                                                            height=request.height,
                                                                            file_size=len(image_data),
                                                                            provider='runninghub',
                                                                            model=f"flux_task_{task_id}",
                                                                            generation_time=time.time() - start_time,
                                                                            remote_url=item['fileUrl'] if isinstance(item, dict) and 'fileUrl' in item else (item if isinstance(item, str) else None)
                                                                        )
                                                        
                                                        # 如果没有找到图像URL，记录警告
                                                        self.logger.warning(f"No image URL found in outputs: {outputs}")
                                        except Exception as e:
                                            self.logger.error(f"Failed to get real results for task {task_id}: {e}")
                                        
                                        # 如果获取结果失败，抛出异常
                                        raise Exception(f"Failed to get image results for RunningHub task {task_id}")
                                    
                                    elif task_status == 'FAILED':
                                        raise Exception(f"RunningHub task {task_id} failed")
                                    
                                    elif task_status == 'RUNNING' and attempt % 10 == 0:
                                        self.logger.debug(f"RunningHub task {task_id} still running... (attempt {attempt})")
                    
                    except Exception as e:
                        if attempt > 60:  # 60秒后开始记录错误
                            self.logger.debug(f"Status check error (attempt {attempt}): {e}")
                        continue
                
                # 超时处理
                self.logger.warning(f"RunningHub task {task_id} polling timeout after 120 seconds")
                raise Exception(f"RunningHub task {task_id} timeout")
    
    
    

    async def _generate_with_openai(self, request: ImageGenerationRequest, 
                                  full_prompt: str) -> GeneratedImage:
        """使用OpenAI DALL-E生成图像（通过OpenRouter）"""
        start_time = time.time()
        
        # 通过OpenRouter调用DALL-E 3
        api_url = f"{self.config.get_llm_config('script_generation').api_base}/images/generations"
        
        # DALL-E支持的尺寸
        dalle_sizes = {
            (1024, 1024): "1024x1024",
            (1792, 1024): "1792x1024", 
            (1024, 1792): "1024x1792"
        }
        
        # 选择最接近的支持尺寸
        size = dalle_sizes.get((request.width, request.height), "1024x1024")
        
        # 限制提示词长度（DALL-E限制）
        prompt = full_prompt[:4000] if len(full_prompt) > 4000 else full_prompt
        
        payload = {
            "prompt": prompt,
            "model": "openai/dall-e-3",  # OpenRouter中的模型名称
            "size": size,
            "quality": "hd" if request.quality == "high" else "standard",
            "response_format": "b64_json",
            "n": 1
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_keys['openai']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/qq1151131109/story_video_generator",
            "X-Title": "Historical Story Generator"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers, timeout=120) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API error {response.status}: {error_text}")
                
                result = await response.json()
                
                if 'data' not in result or not result['data']:
                    raise Exception("No image data in OpenAI response")
                
                # 解码图像数据
                image_b64 = result['data'][0]['b64_json']
                image_data = base64.b64decode(image_b64)
                
                return GeneratedImage(
                    image_data=image_data,
                    prompt=full_prompt,
                    width=request.width,
                    height=request.height,
                    file_size=len(image_data),
                    provider='openai',
                    model='openai/dall-e-3',
                    generation_time=time.time() - start_time,
                    remote_url=None  # OpenAI不提供持久化URL
                )
    
    async def _generate_with_stability(self, request: ImageGenerationRequest, 
                                     full_prompt: str) -> GeneratedImage:
        """使用Stability AI生成图像"""
        start_time = time.time()
        
        # Stability AI API配置
        api_url = "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image"
        
        payload = {
            "text_prompts": [
                {"text": full_prompt, "weight": 1.0}
            ],
            "width": request.width,
            "height": request.height,
            "steps": request.steps,
            "cfg_scale": 7.5,
            "samples": 1
        }
        
        if request.negative_prompt:
            payload["text_prompts"].append({
                "text": request.negative_prompt, 
                "weight": -1.0
            })
        
        headers = {
            "Authorization": f"Bearer {self.api_keys['stability']}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Stability API error {response.status}: {error_text}")
                
                result = await response.json()
                
                if 'artifacts' not in result or not result['artifacts']:
                    raise Exception("No image data in Stability response")
                
                # 解码图像数据
                image_b64 = result['artifacts'][0]['base64']
                image_data = base64.b64decode(image_b64)
                
                return GeneratedImage(
                    image_data=image_data,
                    prompt=full_prompt,
                    width=request.width,
                    height=request.height,
                    file_size=len(image_data),
                    provider='stability',
                    model='stable-diffusion-v1-6',
                    generation_time=time.time() - start_time,
                    remote_url=None  # Stability AI不提供持久化URL
                )
    
    def generate_image_sync(self, request: ImageGenerationRequest, 
                           provider: Optional[str] = None) -> GeneratedImage:
        """
        同步生成图像（对异步方法的包装）
        
        Args:
            request: 图像生成请求
            provider: 指定提供商（可选）
        
        Returns:
            GeneratedImage: 生成的图像
        """
        return asyncio.run(self.generate_image_async(request, provider))
    
    async def batch_generate_images(self, requests: List[ImageGenerationRequest], 
                                  max_concurrent: int = 5,
                                  animation_strategy: Optional[str] = None) -> List[Optional[GeneratedImage]]:
        """
        批量生成图像
        
        Args:
            requests: 图像生成请求列表
            max_concurrent: 最大并发数
            animation_strategy: 动画策略（用于自适应分辨率）
        
        Returns:
            List[GeneratedImage]: 生成的图像列表
        """
        self.logger.info(f"Starting batch image generation: {len(requests)} requests (strategy: {animation_strategy})")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(request: ImageGenerationRequest) -> GeneratedImage:
            async with semaphore:
                return await self.generate_image_async(request, animation_strategy=animation_strategy)
        
        # 执行并发生成
        tasks = [generate_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常：按输入顺序返回，失败用None占位
        ordered_results: List[Optional[GeneratedImage]] = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch image generation failed for request {i}: {result}")
                ordered_results.append(None)
                failed_count += 1
            else:
                ordered_results.append(result)
        
        self.logger.info(f"Batch image generation completed: {len(requests) - failed_count} successful, {failed_count} failed")
        
        return ordered_results
    
    def save_image(self, image: GeneratedImage, output_dir: Optional[str] = None, 
                   filename: Optional[str] = None) -> str:
        """
        保存生成的图像到文件
        
        Args:
            image: 生成的图像
            output_dir: 输出目录（可选）
            filename: 文件名（可选）
        
        Returns:
            str: 保存的文件路径
        """
        try:
            # 生成文件名
            if not filename:
                filename = self.file_manager.generate_filename(
                    content=image.prompt,
                    prefix=f"image_{image.provider}",
                    extension="png"
                )
            
            # 确定输出路径
            if output_dir:
                filepath = Path(output_dir) / filename
            else:
                filepath = self.file_manager.get_output_path('images', filename)
            
            # 确保目录存在
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存图像文件
            with open(filepath, 'wb') as f:
                f.write(image.image_data)
            
            self.logger.info(f"Saved image to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to save image: {e}")
            raise
    
    def resize_image(self, image_data: bytes, width: int, height: int) -> bytes:
        """
        调整图像尺寸
        
        Args:
            image_data: 原始图像数据
            width: 目标宽度
            height: 目标高度
        
        Returns:
            bytes: 调整后的图像数据
        """
        try:
            # 加载图像
            pil_image = Image.open(io.BytesIO(image_data))
            
            # 调整尺寸
            resized_image = pil_image.resize((width, height), Image.Resampling.LANCZOS)
            
            # 保存到字节流
            output_buffer = io.BytesIO()
            resized_image.save(output_buffer, format='PNG')
            
            return output_buffer.getvalue()
            
        except Exception as e:
            self.logger.error(f"Failed to resize image: {e}")
            raise
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """获取图像生成统计信息"""
        # 缓存已删除
        
        return {
            'providers': {
                'primary': self.primary_provider,
                # fallback机制已移除
                'available_keys': [k for k, v in self.api_keys.items() if v]
            },
            # 缓存已删除
            'config': {
                'resolution': self.media_config.image_resolution,
                'quality': self.media_config.image_quality
            }
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ImageGenerator(primary={self.primary_provider})"