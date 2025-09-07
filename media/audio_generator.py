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
import subprocess
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import logging
from dataclasses import dataclass
import hashlib
from io import BytesIO

from core.config_manager import ConfigManager
from utils.file_manager import FileManager

# ElevenLabs imports (需要先安装: pip install elevenlabs)
try:
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False

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
class AudioSubtitle:
    """音频字幕信息"""
    text: str                    # 字幕文本
    start_time: float           # 开始时间（秒）
    end_time: float             # 结束时间（秒）
    duration: float             # 持续时间（秒）

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
    subtitles: Optional[List[AudioSubtitle]] = None  # 字幕时间戳信息

class AudioGenerator:
    """
    音频生成器 - 支持多个提供商
    
    支持的提供商：
    1. Azure TTS - 主要提供商（对应原工作流悬疑解说音色）
    2. ElevenLabs - 备用（高质量语音）
    3. OpenAI TTS - 备用
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 file_manager: FileManager):
        self.config = config_manager
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
        
        # 提供商优先级 - 支持按语言配置
        primary_provider_config = self.audio_config.get('primary_provider', 'minimax')
        if isinstance(primary_provider_config, dict):
            # 按语言配置
            self.language_providers = primary_provider_config
            self.primary_provider = primary_provider_config.get('zh', 'minimax')  # 默认使用中文配置
        else:
            # 统一配置
            self.primary_provider = primary_provider_config
            self.language_providers = {
                'zh': self.primary_provider,
                'en': self.primary_provider,
                'es': self.primary_provider,
            }
        
        # fallback机制已移除，只使用主要提供商
        
        # 语音配置
        self._load_voice_configs()
        
        # 初始化ElevenLabs客户端
        if ELEVENLABS_AVAILABLE and self.api_keys.get('elevenlabs'):
            self.elevenlabs_client = ElevenLabs(api_key=self.api_keys['elevenlabs'])
        else:
            self.elevenlabs_client = None
        
        self.logger.info(f"Audio generator initialized with primary provider: {self.primary_provider}")
    
    def _get_actual_audio_duration_from_data(self, audio_data: bytes) -> float:
        """从音频数据获取实际时长"""
        try:
            # 写入临时文件
            temp_path = self.file_manager.get_temp_path('audio', f'duration_check_{int(time.time())}.mp3')
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            # 使用FFprobe获取时长
            result = subprocess.run([
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                temp_path
            ], capture_output=True, text=True)
            
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
            
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            else:
                return 0.0
                
        except Exception as e:
            self.logger.warning(f"Failed to get audio duration from data: {e}")
            return 0.0
    
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
                    'voice_id': 'male-qn-qingse',  # 使用中文语音，MiniMax支持
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
            # 缓存已禁用 - 每次都生成新音频
            
            # 智能选择提供商：基于语言专用策略
            if provider:
                providers_to_try = [provider]
            else:
                # 根据语言选择最佳提供商
                preferred_provider = self.language_providers.get(request.language, self.primary_provider)
                
                # 确保preferred_provider是字符串
                if isinstance(preferred_provider, dict):
                    preferred_provider = preferred_provider.get(request.language, 'elevenlabs')
                
                # 只使用首选提供商，不再使用fallback
                providers_to_try = [preferred_provider]
            
            last_error = None
            for provider_name in providers_to_try:
                if not self.api_keys.get(provider_name):
                    self.logger.warning(f"No API key for provider: {provider_name}")
                    continue
                
                try:
                    self.logger.info(f"Generating audio with {provider_name}: {request.text[:30]}...")
                    
                    # 为每个provider创建适当的请求副本
                    provider_request = AudioGenerationRequest(
                        text=request.text,
                        language=request.language,
                        voice_id="",  # 将由具体provider方法设置
                        voice_style=request.voice_style,
                        speed=request.speed,
                        volume=request.volume,
                        format=request.format
                    )
                    
                    if provider_name == 'minimax':
                        result = await self._generate_with_minimax_sync(provider_request)
                    elif provider_name == 'azure':
                        result = await self._generate_with_azure(provider_request)
                    elif provider_name == 'elevenlabs':
                        result = await self._generate_with_elevenlabs(provider_request)
                    elif provider_name == 'openai':
                        result = await self._generate_with_openai(provider_request)
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
                    
                    # 缓存已禁用
                    
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
            "subtitle_enable": True,  # 启用字幕功能
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
        
        # 重试机制配置
        max_retries = self.config.get('general.api_max_retries', 3)
        retry_delay = self.config.get('general.retry_delay', 2)
        timeout_seconds = self.config.get('general.api_timeout', 180)  # 增加到3分钟
        
        last_error = None
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.logger.info(f"🔄 MiniMax retry attempt {attempt + 1}/{max_retries} after {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                
                timeout_config = aiohttp.ClientTimeout(total=timeout_seconds)
                async with aiohttp.ClientSession(timeout=timeout_config) as session:
                    async with session.post(api_url, json=payload, headers=headers) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise Exception(f"MiniMax sync API error {response.status}: {error_text}")
                        
                        result = await response.json()
                        break  # 成功后跳出重试循环
                        
            except (asyncio.TimeoutError, aiohttp.ClientError, Exception) as e:
                last_error = e
                error_str = str(e).lower()
                
                # 检查是否应该重试
                should_retry = any(keyword in error_str for keyword in [
                    'timeout', 'connection', 'network', 'temporary', 'oss-cn', 'aliyuncs'
                ])
                
                if attempt < max_retries - 1 and should_retry:
                    self.logger.warning(f"⏰ MiniMax attempt {attempt + 1} failed: {e}")
                    continue
                else:
                    raise Exception(f"MiniMax sync failed after {max_retries} attempts: {e}")
        
        else:
            raise Exception(f"MiniMax sync failed after {max_retries} attempts: {last_error}")
        
        # 处理API响应
        self.logger.debug(f"MiniMax response keys: {list(result.keys())}")
        if 'data' in result:
            data_keys = list(result['data'].keys()) if result['data'] else []
            self.logger.debug(f"MiniMax data keys: {data_keys}")
        
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
        
        # 处理字幕数据（MiniMax返回字幕文件URL）
        subtitles = []
        subtitle_file_url = result.get('data', {}).get('subtitle_file')
        
        if subtitle_file_url:
            self.logger.info(f"Downloading subtitle file from MiniMax")
            self.logger.debug(f"Subtitle file URL: {subtitle_file_url}")
            
            # 下载字幕文件，带重试机制
            subtitle_content = None
            for sub_attempt in range(max_retries):
                try:
                    if sub_attempt > 0:
                        self.logger.info(f"🔄 Subtitle download retry {sub_attempt + 1}/{max_retries}...")
                        await asyncio.sleep(retry_delay)
                    
                    timeout_config = aiohttp.ClientTimeout(total=timeout_seconds)
                    async with aiohttp.ClientSession(timeout=timeout_config) as subtitle_session:
                        async with subtitle_session.get(subtitle_file_url) as subtitle_response:
                            if subtitle_response.status == 200:
                                subtitle_content = await subtitle_response.text()
                                self.logger.debug(f"Subtitle file content preview: {subtitle_content[:200]}...")
                                break  # 成功下载，退出重试循环
                            else:
                                raise Exception(f"Subtitle download failed with status {subtitle_response.status}")
                                
                except (asyncio.TimeoutError, aiohttp.ClientError, Exception) as e:
                    if sub_attempt < max_retries - 1:
                        self.logger.warning(f"⏰ Subtitle download attempt {sub_attempt + 1} failed: {e}")
                        continue
                    else:
                        self.logger.error(f"❌ Subtitle download failed after {max_retries} attempts: {e}")
                        subtitle_content = None
                        break
            
            # 解析字幕文件内容
            if subtitle_content:
                try:
                    import json
                    subtitle_data = json.loads(subtitle_content)
                    
                    # 根据实际格式解析字幕数据
                    if isinstance(subtitle_data, list):
                        for item in subtitle_data:
                            start_ms = None
                            end_ms = None
                            text = None
                            
                            if isinstance(item, dict):
                                # MiniMax格式: {time_begin: ms, time_end: ms, text: "..."}
                                if 'time_begin' in item and 'time_end' in item and 'text' in item:
                                    start_ms = float(item['time_begin'])
                                    end_ms = float(item['time_end'])
                                    text = item['text'].strip()
                                # 通用格式1: {start: ms, end: ms, text: "..."}
                                elif 'start' in item and 'end' in item and 'text' in item:
                                    start_ms = float(item['start'])
                                    end_ms = float(item['end'])
                                    text = item['text'].strip()
                                # 通用格式2: {begin_time: ms, end_time: ms, text: "..."}
                                elif 'begin_time' in item and 'end_time' in item and 'text' in item:
                                    start_ms = float(item['begin_time'])
                                    end_ms = float(item['end_time'])
                                    text = item['text'].strip()
                                
                                if start_ms is not None and end_ms is not None and text and end_ms > start_ms:
                                    subtitle = AudioSubtitle(
                                        text=text,
                                        start_time=start_ms / 1000.0,  # 转换为秒
                                        end_time=end_ms / 1000.0,      # 转换为秒
                                        duration=(end_ms - start_ms) / 1000.0
                                    )
                                    subtitles.append(subtitle)
                                    self.logger.debug(f"Added subtitle: {start_ms/1000.0:.2f}s-{end_ms/1000.0:.2f}s: {text[:30]}...")
                    
                    self.logger.info(f"Successfully processed {len(subtitles)} subtitle segments from MiniMax")
                    
                except Exception as parse_error:
                    self.logger.warning(f"Failed to parse MiniMax subtitle file: {parse_error}")
            else:
                self.logger.warning("Failed to download subtitle file after retries")
        else:
            self.logger.info("No subtitle file URL returned by MiniMax")
        
        # 获取实际音频时长（从extra_info或FFprobe）
        actual_duration = result.get('extra_info', {}).get('audio_length', 0) / 1000.0
        if actual_duration == 0:
            # 使用FFprobe获取实际时长
            actual_duration = self._get_actual_audio_duration_from_data(audio_data)
            if actual_duration == 0:
                # 最后备用估算
                char_count = len(request.text)
                actual_duration = (char_count / 5.0) / request.speed
        
        return GeneratedAudio(
            audio_data=audio_data,
            text=request.text,
            language=request.language,
            voice_id=voice_id,
            duration_seconds=actual_duration,
            file_size=len(audio_data),
            provider='minimax',
            format='mp3',
            generation_time=time.time() - start_time,
            subtitles=subtitles if subtitles else None
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
        """使用ElevenLabs生成音频 + Forced Alignment字幕"""
        start_time = time.time()
        
        if not self.elevenlabs_client:
            raise Exception("ElevenLabs client not available. Please install elevenlabs package.")
        
        # 获取语音ID
        voice_config = self.voice_configs['elevenlabs'].get(request.language, self.voice_configs['elevenlabs']['en'])
        voice_id = request.voice_id or voice_config['voice_id']
        
        try:
            # Step 1: 生成音频
            self.logger.info(f"Generating audio with ElevenLabs voice: {voice_id}")
            
            # 使用ElevenLabs SDK生成音频
            audio_response = self.elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                text=request.text,
                model_id="eleven_multilingual_v2"
            )
            
            # 收集音频数据
            audio_data = b""
            for chunk in audio_response:
                audio_data += chunk
            
            self.logger.info(f"ElevenLabs TTS completed: {len(audio_data)} bytes")
            
            # Step 2: 保存临时音频文件用于Forced Alignment
            temp_audio_path = self.file_manager.get_temp_path('audio', f'elevenlabs_temp_{int(time.time())}.mp3')
            with open(temp_audio_path, 'wb') as f:
                f.write(audio_data)
            
            # Step 3: 使用Forced Alignment获取精确时间戳
            subtitles = []
            try:
                self.logger.info("Running ElevenLabs Forced Alignment...")
                
                with open(temp_audio_path, 'rb') as f:
                    audio_file = BytesIO(f.read())
                
                # 调用Forced Alignment API
                transcription = self.elevenlabs_client.forced_alignment.create(
                    file=audio_file,
                    text=request.text
                )
                
                # 解析时间戳
                if hasattr(transcription, 'words') and transcription.words:
                    self.logger.info(f"Received {len(transcription.words)} word alignments")
                    
                    # 按句子分组单词
                    current_sentence = ""
                    sentence_start = 0.0
                    sentence_end = 0.0
                    
                    for word_info in transcription.words:
                        current_sentence += word_info.text + " "
                        sentence_end = word_info.end
                        
                        # 检查是否是句子结束
                        if word_info.text.strip().endswith(('.', '!', '?', '。', '！', '？')):
                            subtitle = AudioSubtitle(
                                text=current_sentence.strip(),
                                start_time=sentence_start,
                                end_time=sentence_end,
                                duration=sentence_end - sentence_start
                            )
                            subtitles.append(subtitle)
                            current_sentence = ""
                            sentence_start = sentence_end
                    
                    # 处理剩余文本
                    if current_sentence.strip():
                        subtitle = AudioSubtitle(
                            text=current_sentence.strip(),
                            start_time=sentence_start,
                            end_time=sentence_end,
                            duration=sentence_end - sentence_start
                        )
                        subtitles.append(subtitle)
                        
                else:
                    self.logger.warning("No word alignments received from ElevenLabs")
                    
            except Exception as alignment_error:
                self.logger.warning(f"Forced Alignment failed: {alignment_error}, using estimated timing")
            
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_audio_path)
                except:
                    pass
            
            # Step 4: 获取实际音频时长
            actual_duration = self._get_actual_audio_duration_from_data(audio_data)
            if actual_duration == 0:
                # 备用估算
                char_count = len(request.text)
                actual_duration = (char_count / 5.0) / request.speed
            
            return GeneratedAudio(
                audio_data=audio_data,
                text=request.text,
                language=request.language,
                voice_id=voice_id,
                duration_seconds=actual_duration,
                file_size=len(audio_data),
                provider='elevenlabs',
                format='mp3',
                generation_time=time.time() - start_time,
                subtitles=subtitles if subtitles else None
            )
            
        except Exception as e:
            self.logger.error(f"ElevenLabs generation failed: {e}")
            raise
    
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
                                 max_concurrent: int = 3, provider: Optional[str] = None) -> List[Optional[GeneratedAudio]]:
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
                return await self.generate_audio_async(request, provider)
        
        # 执行并发生成
        tasks = [generate_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常：按输入顺序返回，失败用None占位
        ordered_results: List[Optional[GeneratedAudio]] = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch audio generation failed for request {i}: {result}")
                ordered_results.append(None)
                failed_count += 1
            else:
                ordered_results.append(result)
        
        self.logger.info(f"Batch audio generation completed: {len(requests) - failed_count} successful, {failed_count} failed")
        
        return ordered_results
    
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
        # 缓存已删除
        
        return {
            'providers': {
                'primary': self.primary_provider,
                # fallback机制已移除
                'available_keys': [k for k, v in self.api_keys.items() if v]
            },
            # 缓存已删除
            'config': {
                'voice_speed': self.audio_config.get('voice_speed', 1.2),
                'voice_volume': self.audio_config.get('voice_volume', 1.0),
                'default_voice_id': self.default_voice_id
            }
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"AudioGenerator(primary={self.primary_provider})"