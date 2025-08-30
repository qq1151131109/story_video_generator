"""
音频生成器 - 多提供商语音合成支持
支持Azure TTS、ElevenLabs、OpenAI TTS等提供商
"""
import asyncio
import aiohttp
import base64
import time
import json
import os
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import logging
from dataclasses import dataclass
import hashlib

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager

@dataclass
class AudioGenerationRequest:
    """音频生成请求"""
    text: str                     # 要合成的文本
    language: str                 # 语言代码
    voice_id: str = ""           # 音色ID
    voice_style: str = ""        # 语音风格
    speed: float = 1.2           # 语速（对应原工作流）
    volume: float = 1.0          # 音量
    format: str = "mp3"          # 输出格式

@dataclass
class GeneratedAudio:
    """生成的音频"""
    audio_data: bytes            # 音频数据
    text: str                    # 原始文本
    language: str                # 语言
    voice_id: str                # 使用的音色
    duration_seconds: float      # 音频时长
    file_size: int               # 文件大小
    provider: str                # 提供商
    format: str                  # 音频格式
    generation_time: float       # 生成耗时
    file_path: Optional[str] = None  # 保存的文件路径

class AudioGenerator:
    """
    音频生成器 - 支持多个提供商
    
    支持的提供商：
    1. Azure TTS - 主要提供商（对应原工作流悬疑解说音色）
    2. ElevenLabs - 备用（高质量语音）
    3. OpenAI TTS - 备用
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 cache_manager: CacheManager, file_manager: FileManager):
        self.config = config_manager
        self.cache = cache_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.media')
        
        # 获取音频配置
        self.audio_config = config_manager.get('media.audio', {})
        
        # API密钥
        self.api_keys = {
            'minimax': config_manager.get_api_key('minimax'),
            'elevenlabs': config_manager.get_api_key('elevenlabs'),
            'openai': config_manager.get_api_key('openrouter')
        }
        
        # 提供商优先级 - MiniMax作为主要提供商（同步版本）
        self.primary_provider = self.audio_config.get('primary_provider', 'minimax')
        self.fallback_providers = self.audio_config.get('fallback_providers', ['elevenlabs'])
        
        # 语音配置
        self._load_voice_configs()
        
        self.logger.info(f"Audio generator initialized with primary provider: {self.primary_provider}")
    
    def _load_voice_configs(self):
        """加载语音配置"""
        # 语音配置
        self.voice_configs = {
            'minimax': {
                'zh': {
                    'voice_id': 'male-qn-qingse',  # MiniMax中文男声
                    'style': 'audiobook'
                },
                'en': {
                    'voice_id': 'male-en-01',  # MiniMax英文男声  
                    'style': 'audiobook'
                }
            },
            'azure': {
                'zh': {
                    'voice_id': 'zh-CN-XiaoxiaoNeural',  # 中文悬疑音色
                    'style': 'newscast',
                    'role': 'narrator'
                },
                'en': {
                    'voice_id': 'en-US-AriaNeural',
                    'style': 'newscast',
                    'role': 'narrator'
                },
                'es': {
                    'voice_id': 'es-ES-ElviraNeural',
                    'style': 'newscast',
                    'role': 'narrator'
                }
            },
            'elevenlabs': {
                'zh': {'voice_id': 'pNInz6obpgDQGcFmaJgB'},  # 中文音色
                'en': {'voice_id': 'EXAVITQu4vr4xnSDxMaL'},  # 英文音色
                'es': {'voice_id': 'XrExE9yKIg1WjnnlVkGX'}   # 西班牙语音色
            },
            'openai': {
                'voice_id': 'alloy'  # OpenAI统一使用alloy音色
            }
        }
        
        # 默认语音ID（对应原工作流）
        self.default_voice_id = self.audio_config.get('voice_id', '7468512265134932019')
    
    async def generate_audio_async(self, request: AudioGenerationRequest, 
                                 provider: Optional[str] = None) -> GeneratedAudio:
        """
        异步生成音频
        
        Args:
            request: 音频生成请求
            provider: 指定提供商（可选）
        
        Returns:
            GeneratedAudio: 生成的音频
        """
        start_time = time.time()
        
        try:
            # 检查缓存
            cache_key = self.cache.get_cache_key({
                'text': request.text,
                'language': request.language,
                'voice_id': request.voice_id or self.default_voice_id,
                'speed': request.speed,
                'volume': request.volume
            })
            
            cached_result = self.cache.get('audio', cache_key)
            if cached_result:
                self.logger.info(f"Cache hit for audio generation: {request.text[:30]}...")
                cached_result['generation_time'] = time.time() - start_time
                return GeneratedAudio(**cached_result)
            
            # 智能选择提供商：中文使用MiniMax，英文使用ElevenLabs
            if provider:
                providers_to_try = [provider]
            else:
                if request.language == 'zh':
                    providers_to_try = ['minimax'] + self.fallback_providers
                elif request.language == 'en':
                    providers_to_try = ['elevenlabs', 'minimax'] + [p for p in self.fallback_providers if p != 'elevenlabs']
                else:
                    # 其他语言使用默认策略
                    providers_to_try = [self.primary_provider] + self.fallback_providers
            
            last_error = None
            for provider_name in providers_to_try:
                if not self.api_keys.get(provider_name):
                    self.logger.warning(f"No API key for provider: {provider_name}")
                    continue
                
                try:
                    self.logger.info(f"Generating audio with {provider_name}: {request.text[:30]}...")
                    
                    if provider_name == 'minimax':
                        result = await self._generate_with_minimax_sync(request)
                    elif provider_name == 'azure':
                        result = await self._generate_with_azure(request)
                    elif provider_name == 'elevenlabs':
                        result = await self._generate_with_elevenlabs(request)
                    elif provider_name == 'openai':
                        result = await self._generate_with_openai(request)
                    else:
                        continue
                    
                    # 缓存结果
                    cache_data = {
                        'audio_data': result.audio_data,
                        'text': result.text,
                        'language': result.language,
                        'voice_id': result.voice_id,
                        'duration_seconds': result.duration_seconds,
                        'file_size': result.file_size,
                        'provider': result.provider,
                        'format': result.format
                    }
                    
                    self.cache.set('audio', cache_key, cache_data)
                    
                    # 记录日志
                    # 保存音频文件
                    file_path = self.save_audio(result)
                    result.file_path = file_path
                    
                    logger = self.config.get_logger('story_generator')
                    logger.info(f"Media generation - Type: audio, Provider: {provider_name}, "
                               f"Processing time: {result.generation_time:.2f}s, "
                               f"File size: {result.file_size} bytes")
                    
                    self.logger.info(f"Generated audio successfully with {provider_name}: {result.duration_seconds:.1f}s, {result.file_size / 1024:.1f}KB")
                    self.logger.info(f"Audio saved to: {file_path}")
                    
                    return result
                    
                except Exception as e:
                    self.logger.error(f"Failed to generate audio with {provider_name}: {e}")
                    last_error = e
                    continue
            
            # 所有提供商都失败了
            raise Exception(f"All audio providers failed. Last error: {last_error}")
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Audio generation failed after {processing_time:.2f}s: {e}")
            
            # 记录错误日志
            logger = self.config.get_logger('story_generator')
            logger.error(f"Media generation failed - Type: audio, Provider: unknown, "
                        f"Processing time: {processing_time:.2f}s")
            
            raise
    
    async def _generate_with_minimax_sync(self, request: AudioGenerationRequest) -> GeneratedAudio:
        """使用MiniMax同步TTS生成音频"""
        start_time = time.time()
        
        # 获取语音配置
        voice_config = self.voice_configs['minimax'].get(request.language, self.voice_configs['minimax']['zh'])
        voice_id = request.voice_id or voice_config['voice_id']
        
        # 获取GroupId
        group_id = os.getenv('MINIMAX_GROUP_ID')
        if not group_id:
            group_id = '1961322907531485224'  # 默认值
        
        # MiniMax同步TTS API
        api_url = f"https://api.minimaxi.com/v1/t2a_v2?GroupId={group_id}"
        
        payload = {
            "model": "speech-2.5-hd-preview",
            "text": request.text,
            "stream": False,  # 同步模式
            "language_boost": "Chinese" if request.language == 'zh' else "auto",
            "output_format": "hex",  # 返回hex编码
            "voice_setting": {
                "voice_id": voice_id,
                "speed": request.speed,
                "vol": request.volume,
                "pitch": 0,
                "emotion": "happy"
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_keys['minimax']}",
            "Content-Type": "application/json"
        }
        
        self.logger.info(f"Using MiniMax sync TTS with GroupId: {group_id}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers, timeout=60) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"MiniMax sync API error {response.status}: {error_text}")
                
                result = await response.json()
                
                if result.get('base_resp', {}).get('status_code') != 0:
                    error_msg = result.get('base_resp', {}).get('status_msg', 'Unknown error')
                    raise Exception(f"MiniMax sync failed: {error_msg}")
                
                # 获取hex编码的音频数据
                hex_audio = result.get('data', {}).get('audio')
                if not hex_audio:
                    raise Exception("No audio data in MiniMax response")
                
                # 解码hex数据为bytes
                audio_data = bytes.fromhex(hex_audio)
                
                self.logger.info(f"MiniMax sync TTS completed: {len(audio_data)} bytes")
                
                # 估算音频时长
                char_count = len(request.text)
                estimated_duration = (char_count / 5.0) / request.speed
                
                return GeneratedAudio(
                    audio_data=audio_data,
                    text=request.text,
                    language=request.language,
                    voice_id=voice_id,
                    duration_seconds=estimated_duration,
                    file_size=len(audio_data),
                    provider='minimax',
                    format='mp3',
                    generation_time=time.time() - start_time
                )

    async def _generate_with_azure(self, request: AudioGenerationRequest) -> GeneratedAudio:
        """使用Azure TTS生成音频"""
        start_time = time.time()
        
        # 获取语音配置
        voice_config = self.voice_configs['azure'].get(request.language, self.voice_configs['azure']['zh'])
        voice_id = request.voice_id or voice_config['voice_id']
        
        # 构建SSML
        ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{request.language}">
    <voice name="{voice_id}">
        <mstts:express-as style="{voice_config.get('style', 'newscast')}" role="{voice_config.get('role', 'narrator')}">
            <prosody rate="{request.speed}" volume="{request.volume}">
                {request.text}
            </prosody>
        </mstts:express-as>
    </voice>
</speak>'''
        
        # Azure TTS API
        api_url = f"https://{self._get_azure_region()}.tts.speech.microsoft.com/cognitiveservices/v1"
        
        headers = {
            'Ocp-Apim-Subscription-Key': self.api_keys['azure'],
            'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': 'audio-24khz-48kbitrate-mono-mp3',
            'User-Agent': 'story_generator'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, data=ssml.encode('utf-8'), headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Azure TTS API error {response.status}: {error_text}")
                
                audio_data = await response.read()
                
                # 估算音频时长（基于文本长度和语速）
                char_count = len(request.text)
                estimated_duration = (char_count / 5.0) / request.speed  # 大约5个字符/秒
                
                return GeneratedAudio(
                    audio_data=audio_data,
                    text=request.text,
                    language=request.language,
                    voice_id=voice_id,
                    duration_seconds=estimated_duration,
                    file_size=len(audio_data),
                    provider='azure',
                    format='mp3',
                    generation_time=time.time() - start_time
                )
    
    async def _generate_with_elevenlabs(self, request: AudioGenerationRequest) -> GeneratedAudio:
        """使用ElevenLabs生成音频"""
        start_time = time.time()
        
        # 获取语音ID
        voice_config = self.voice_configs['elevenlabs'].get(request.language, self.voice_configs['elevenlabs']['en'])
        voice_id = request.voice_id or voice_config['voice_id']
        
        # ElevenLabs API
        api_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        payload = {
            "text": request.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
        
        headers = {
            "xi-api-key": self.api_keys['elevenlabs'],
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"ElevenLabs API error {response.status}: {error_text}")
                
                audio_data = await response.read()
                
                # 估算音频时长
                char_count = len(request.text)
                estimated_duration = (char_count / 5.0) / request.speed
                
                return GeneratedAudio(
                    audio_data=audio_data,
                    text=request.text,
                    language=request.language,
                    voice_id=voice_id,
                    duration_seconds=estimated_duration,
                    file_size=len(audio_data),
                    provider='elevenlabs',
                    format='mp3',
                    generation_time=time.time() - start_time
                )
    
    async def _generate_with_openai(self, request: AudioGenerationRequest) -> GeneratedAudio:
        """使用OpenAI TTS生成音频"""
        start_time = time.time()
        
        # OpenAI TTS API
        api_url = f"{self.config.get_llm_config('script_generation').api_base}/audio/speech"
        
        voice_id = request.voice_id or 'alloy'
        
        payload = {
            "model": "tts-1",
            "input": request.text,
            "voice": voice_id,
            "response_format": "mp3",
            "speed": request.speed
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_keys['openai']}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI TTS API error {response.status}: {error_text}")
                
                audio_data = await response.read()
                
                # 估算音频时长
                char_count = len(request.text)
                estimated_duration = (char_count / 5.0) / request.speed
                
                return GeneratedAudio(
                    audio_data=audio_data,
                    text=request.text,
                    language=request.language,
                    voice_id=voice_id,
                    duration_seconds=estimated_duration,
                    file_size=len(audio_data),
                    provider='openai',
                    format='mp3',
                    generation_time=time.time() - start_time
                )
    
    def _get_azure_region(self) -> str:
        """获取Azure区域"""
        # 可以从配置中读取，默认使用eastus
        return self.config.get('media.audio.azure_region', 'eastus')
    
    
    def generate_audio_sync(self, request: AudioGenerationRequest, 
                           provider: Optional[str] = None) -> GeneratedAudio:
        """
        同步生成音频（对异步方法的包装）
        
        Args:
            request: 音频生成请求
            provider: 指定提供商（可选）
        
        Returns:
            GeneratedAudio: 生成的音频
        """
        return asyncio.run(self.generate_audio_async(request, provider))
    
    async def batch_generate_audio(self, requests: List[AudioGenerationRequest], 
                                 max_concurrent: int = 3) -> List[GeneratedAudio]:
        """
        批量生成音频
        
        Args:
            requests: 音频生成请求列表
            max_concurrent: 最大并发数
        
        Returns:
            List[GeneratedAudio]: 生成的音频列表
        """
        self.logger.info(f"Starting batch audio generation: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(request: AudioGenerationRequest) -> GeneratedAudio:
            async with semaphore:
                return await self.generate_audio_async(request)
        
        # 执行并发生成
        tasks = [generate_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch audio generation failed for request {i}: {result}")
                failed_count += 1
            else:
                successful_results.append(result)
        
        self.logger.info(f"Batch audio generation completed: {len(successful_results)} successful, {failed_count} failed")
        
        return successful_results
    
    def save_audio(self, audio: GeneratedAudio, output_dir: Optional[str] = None, 
                   filename: Optional[str] = None) -> str:
        """
        保存生成的音频到文件
        
        Args:
            audio: 生成的音频
            output_dir: 输出目录（可选）
            filename: 文件名（可选）
        
        Returns:
            str: 保存的文件路径
        """
        try:
            # 生成文件名
            if not filename:
                filename = self.file_manager.generate_filename(
                    content=audio.text,
                    prefix=f"audio_{audio.provider}",
                    extension=audio.format
                )
            
            # 确定输出路径
            if output_dir:
                filepath = Path(output_dir) / filename
            else:
                filepath = self.file_manager.get_output_path('audio', filename)
            
            # 确保目录存在
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存音频文件
            with open(filepath, 'wb') as f:
                f.write(audio.audio_data)
            
            self.logger.info(f"Saved audio to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to save audio: {e}")
            raise
    
    def split_text_for_tts(self, text: str, max_length: int = 500) -> List[str]:
        """
        将长文本分割为适合TTS的短段
        
        Args:
            text: 原始文本
            max_length: 最大段落长度
        
        Returns:
            List[str]: 分割后的文本段落
        """
        if len(text) <= max_length:
            return [text]
        
        segments = []
        current_segment = ""
        
        # 按句子分割
        sentences = text.replace('。', '。\n').replace('！', '！\n').replace('？', '？\n').split('\n')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(current_segment) + len(sentence) <= max_length:
                current_segment += sentence
            else:
                if current_segment:
                    segments.append(current_segment)
                current_segment = sentence
        
        if current_segment:
            segments.append(current_segment)
        
        return segments
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """获取音频生成统计信息"""
        cache_stats = self.cache.get_cache_stats()
        
        return {
            'providers': {
                'primary': self.primary_provider,
                'fallback': self.fallback_providers,
                'available_keys': [k for k, v in self.api_keys.items() if v]
            },
            'cache_stats': cache_stats.get('disk_cache', {}).get('audio', {}),
            'config': {
                'voice_speed': self.audio_config.get('voice_speed', 1.2),
                'voice_volume': self.audio_config.get('voice_volume', 1.0),
                'default_voice_id': self.default_voice_id
            }
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"AudioGenerator(primary={self.primary_provider}, fallback={self.fallback_providers})"