"""
图像生成器 - 多提供商图像生成支持
支持RunningHub、OpenAI DALL-E、Stability AI等提供商
"""
import asyncio
import aiohttp
import base64
import time
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import logging
from dataclasses import dataclass
from PIL import Image
import io
import hashlib

from ..core.config_manager import ConfigManager
from ..core.cache_manager import CacheManager  
from ..utils.file_manager import FileManager

@dataclass
class ImageGenerationRequest:
    """图像生成请求"""
    prompt: str                    # 图像提示词
    negative_prompt: str = ""      # 负面提示词
    style: str = "ancient_horror"  # 风格
    width: int = 1024             # 宽度
    height: int = 768             # 高度
    quality: str = "high"         # 质量 (high, standard)
    steps: int = 40               # 采样步数
    model_id: Optional[int] = 8   # 模型ID（RunningHub）

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

class ImageGenerator:
    """
    图像生成器 - 支持多个提供商
    
    支持的提供商：
    1. RunningHub - 主要提供商（对应原工作流）
    2. OpenAI DALL-E - 备用
    3. Stability AI - 备用
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 cache_manager: CacheManager, file_manager: FileManager):
        self.config = config_manager
        self.cache = cache_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.media')
        
        # 获取媒体配置
        self.media_config = config_manager.get_media_config()
        self.image_config = config_manager.get('media.image', {})
        
        # API密钥
        self.api_keys = {
            'runninghub': config_manager.get_api_key('runninghub'),
            'openai': config_manager.get_api_key('openrouter'),  # 使用OpenRouter访问OpenAI
            'stability': config_manager.get_api_key('stability')
        }
        
        # 提供商优先级
        self.primary_provider = self.image_config.get('primary_provider', 'runninghub')
        self.fallback_providers = self.image_config.get('fallback_providers', ['openai', 'stability'])
        
        # 默认样式提示词
        self._load_style_prompts()
        
        self.logger.info(f"Image generator initialized with primary provider: {self.primary_provider}")
    
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
                                 provider: Optional[str] = None) -> GeneratedImage:
        """
        异步生成图像
        
        Args:
            request: 图像生成请求
            provider: 指定提供商（可选）
        
        Returns:
            GeneratedImage: 生成的图像
        """
        start_time = time.time()
        
        try:
            # 检查缓存
            cache_key = self.cache.get_cache_key({
                'prompt': request.prompt,
                'negative_prompt': request.negative_prompt,
                'width': request.width,
                'height': request.height,
                'style': request.style,
                'steps': request.steps
            })
            
            cached_result = self.cache.get('images', cache_key)
            if cached_result:
                self.logger.info(f"Cache hit for image generation: {request.prompt[:50]}...")
                cached_result['generation_time'] = time.time() - start_time
                return GeneratedImage(**cached_result)
            
            # 构建完整提示词
            full_prompt = self._build_full_prompt(request)
            
            # 选择提供商
            providers_to_try = [provider] if provider else [self.primary_provider] + self.fallback_providers
            
            last_error = None
            for provider_name in providers_to_try:
                if not self.api_keys.get(provider_name):
                    self.logger.warning(f"No API key for provider: {provider_name}")
                    continue
                
                try:
                    self.logger.info(f"Generating image with {provider_name}: {request.prompt[:50]}...")
                    
                    if provider_name == 'runninghub':
                        result = await self._generate_with_runninghub(request, full_prompt)
                    elif provider_name == 'openai':
                        result = await self._generate_with_openai(request, full_prompt)
                    elif provider_name == 'stability':
                        result = await self._generate_with_stability(request, full_prompt)
                    else:
                        continue
                    
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
                    
                    self.cache.set('images', cache_key, cache_data)
                    
                    # 记录日志
                    self.config.get_logger('story_generator').log_media_generation(
                        media_type='image',
                        provider=provider_name,
                        processing_time=result.generation_time,
                        file_size=result.file_size
                    )
                    
                    self.logger.info(f"Generated image successfully with {provider_name}: {result.file_size / 1024:.1f}KB in {result.generation_time:.2f}s")
                    
                    return result
                    
                except Exception as e:
                    self.logger.error(f"Failed to generate image with {provider_name}: {e}")
                    last_error = e
                    continue
            
            # 所有提供商都失败了
            raise Exception(f"All image providers failed. Last error: {last_error}")
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Image generation failed after {processing_time:.2f}s: {e}")
            
            # 记录错误日志
            self.config.get_logger('story_generator').log_media_generation(
                media_type='image',
                provider='unknown',
                processing_time=processing_time,
                success=False
            )
            
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
        使用RunningHub生成图像
        
        对应原工作流的图像生成配置
        """
        start_time = time.time()
        
        # RunningHub API配置
        api_url = "https://api.runninghub.ai/v1/images/generations"
        
        payload = {
            "prompt": full_prompt,
            "negative_prompt": request.negative_prompt,
            "model_id": request.model_id or self.image_config.get('model_id', 8),
            "width": request.width,
            "height": request.height,
            "steps": request.steps,
            "guidance_scale": 7.5,
            "scheduler": "DPMSolverMultistep",
            "quality": request.quality,
            "response_format": "b64_json"
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_keys['runninghub']}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"RunningHub API error {response.status}: {error_text}")
                
                result = await response.json()
                
                if 'data' not in result or not result['data']:
                    raise Exception("No image data in RunningHub response")
                
                # 解码图像数据
                image_b64 = result['data'][0]['b64_json']
                image_data = base64.b64decode(image_b64)
                
                return GeneratedImage(
                    image_data=image_data,
                    prompt=full_prompt,
                    width=request.width,
                    height=request.height,
                    file_size=len(image_data),
                    provider='runninghub',
                    model=f"model_{request.model_id}",
                    generation_time=time.time() - start_time
                )
    
    async def _generate_with_openai(self, request: ImageGenerationRequest, 
                                  full_prompt: str) -> GeneratedImage:
        """使用OpenAI DALL-E生成图像"""
        start_time = time.time()
        
        # OpenAI DALL-E API配置
        api_url = f"{self.config.get_llm_config('script_generation').api_base}/images/generations"
        
        # DALL-E支持的尺寸
        dalle_sizes = {
            (1024, 1024): "1024x1024",
            (1792, 1024): "1792x1024", 
            (1024, 1792): "1024x1792"
        }
        
        # 选择最接近的支持尺寸
        size = dalle_sizes.get((request.width, request.height), "1024x1024")
        
        payload = {
            "prompt": full_prompt,
            "model": "dall-e-3",
            "size": size,
            "quality": "hd" if request.quality == "high" else "standard",
            "response_format": "b64_json",
            "n": 1
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_keys['openai']}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
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
                    model='dall-e-3',
                    generation_time=time.time() - start_time
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
                    generation_time=time.time() - start_time
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
                                  max_concurrent: int = 3) -> List[GeneratedImage]:
        """
        批量生成图像
        
        Args:
            requests: 图像生成请求列表
            max_concurrent: 最大并发数
        
        Returns:
            List[GeneratedImage]: 生成的图像列表
        """
        self.logger.info(f"Starting batch image generation: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(request: ImageGenerationRequest) -> GeneratedImage:
            async with semaphore:
                return await self.generate_image_async(request)
        
        # 执行并发生成
        tasks = [generate_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch image generation failed for request {i}: {result}")
                failed_count += 1
            else:
                successful_results.append(result)
        
        self.logger.info(f"Batch image generation completed: {len(successful_results)} successful, {failed_count} failed")
        
        return successful_results
    
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
        cache_stats = self.cache.get_cache_stats()
        
        return {
            'providers': {
                'primary': self.primary_provider,
                'fallback': self.fallback_providers,
                'available_keys': [k for k, v in self.api_keys.items() if v]
            },
            'cache_stats': cache_stats.get('disk_cache', {}).get('images', {}),
            'config': {
                'resolution': self.media_config.image_resolution,
                'quality': self.media_config.image_quality
            }
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ImageGenerator(primary={self.primary_provider}, fallback={self.fallback_providers})"