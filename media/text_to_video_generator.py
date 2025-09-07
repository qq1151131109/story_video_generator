"""
一体化文生视频生成器 - 基于RunningHub新工作流
工作流ID: 1964196221642489858

将文生图+图生视频整合为单一API调用，替代现有的两步流程：
- 原流程: ImageGenerator → ImageToVideoGenerator (2次API调用)
- 新流程: TextToVideoGenerator (1次API调用)

对应工作流节点配置：
- 文本编码: nodes 1,10,38 (CLIPTextEncode)
- 图像生成: Flux模型 via UNET nodes 13,14,37
- 图生视频: Wan2.2模型 via WanImageToVideo node 5
- 视频输出: 720x1280@31fps, MP4格式
"""

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Any, List
import logging
from dataclasses import dataclass

import aiohttp
from PIL import Image

from core.config_manager import ConfigManager
from utils.file_manager import FileManager

# 🌍 模块级别的全局信号量控制 - 解决多实例并发问题
_global_semaphore = None
_global_semaphore_lock = asyncio.Lock()

async def get_global_semaphore(max_concurrent: int) -> asyncio.Semaphore:
    """获取或创建全局信号量"""
    global _global_semaphore
    
    async with _global_semaphore_lock:
        if _global_semaphore is None or _global_semaphore._value != max_concurrent:
            _global_semaphore = asyncio.Semaphore(max_concurrent)
            logging.getLogger('story_generator.text_to_video').info(
                f"🌍 Created module-level global semaphore with {max_concurrent} concurrent limit"
            )
    
    return _global_semaphore


@dataclass
class TextToVideoRequest:
    """文生视频请求"""
    image_prompt: str              # 文生图提示词 (node 38)
    video_prompt: str = ""         # 图生视频提示词 (node 10)  
    negative_prompt: str = ""      # 负向提示词 (node 1)
    width: int = 720              # 视频宽度
    height: int = 1280            # 视频高度
    fps: int = 31                 # 帧率
    duration: float = 3.0         # 持续时间(秒)
    style: str = "ancient_horror" # 风格标识
    scene_id: str = ""            # 场景ID
    seed: int = -1                # 随机种子(-1为随机)


@dataclass
class TextToVideoResult:
    """文生视频结果"""
    video_path: str               # 视频文件路径
    width: int                    # 视频宽度
    height: int                   # 视频高度
    fps: int                      # 帧率
    duration: float               # 实际时长
    file_size: int                # 文件大小
    provider: str = "runninghub"  # 提供商
    workflow_id: str = ""         # 工作流ID
    task_id: str = ""             # 任务ID
    generation_time: float = 0.0  # 生成耗时


class TextToVideoGenerator:
    """
    一体化文生视频生成器
    
    使用RunningHub新工作流(1964196221642489858)实现：
    文本提示词 → 图像生成(Flux) → 视频转换(Wan2.2) → MP4输出
    
    替代原有的两步流程，提高效率并减少API调用次数。
    """
    
    def __init__(self, config: ConfigManager, file_manager: FileManager):
        self.config = config
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.text_to_video')
        
        # 工作流配置 - 一体化文生视频工作流
        self.workflow_id = "1964196221642489858"
        
        # 🌍 模块级全局并发控制 - 解决多实例问题
        self._max_concurrent = self.config.get('general.max_concurrent_tasks', 3)
        # 注意：不在这里创建信号量，而是在需要时获取全局信号量
        self.logger.info(f"🌍 TextToVideoGenerator will use module-level global semaphore with {self._max_concurrent} concurrent limit")
        
        # API配置 - 使用与图像生成器相同的API端点
        self.api_key = self.config.get_api_key('runninghub')
        self.base_url = "https://www.runninghub.cn"
        
        # 超时和重试配置
        self.connect_timeout = self.config.get('general.connect_timeout', 30)  # 连接超时
        self.request_timeout = self.config.get('general.request_timeout', 60)  # 请求超时
        self.total_timeout = self.config.get('general.api_timeout', 600)  # 总超时，改为10分钟
        self.max_retries = self.config.get('general.api_max_retries', 5)  # 增加重试次数
        self.retry_delay = self.config.get('general.retry_delay', 10)  # 增加重试间隔
        
        if not self.api_key:
            raise ValueError("RunningHub API key not configured")
        
        # 🌐 优化连接配置支持5个并发任务
        self.connector_limit = 10  # 连接池大小，支持5个并发 + buffer
        self.connector_limit_per_host = 8  # 单主机最大连接数
        self.keepalive_timeout = 30  # 保持连接时间
        
        self.logger.info(f"🚀 TextToVideoGenerator optimized for concurrent tasks")
    
    def _create_optimized_session(self, total_timeout: int = 60) -> aiohttp.ClientSession:
        """创建优化的HTTP会话，支持5个并发连接"""
        connector = aiohttp.TCPConnector(
            limit=self.connector_limit,
            limit_per_host=self.connector_limit_per_host,
            keepalive_timeout=self.keepalive_timeout,
            enable_cleanup_closed=True,
            ttl_dns_cache=300,  # DNS缓存5分钟
            use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(
            total=total_timeout,
            connect=self.connect_timeout,
            sock_read=30
        )
        return aiohttp.ClientSession(connector=connector, timeout=timeout)
    
    def _build_workflow_payload(self, request: TextToVideoRequest) -> Dict[str, Any]:
        """
        构建工作流API载荷 - 使用RunningHub标准格式
        
        基于新工作流(1964196221642489858)的节点配置：
        - 节点38: 文生图提示词 (image_prompt)
        - 节点10: 图生视频提示词 (video_prompt) 
        - 节点1: 负向提示词 (negative_prompt)
        - 节点39: 分辨率设置 (width/height)
        - 节点5: WanImageToVideo长度 (length = duration × 16fps)
        - 节点36: 随机种子 (可选)
        """
        
        # RunningHub标准格式 - 与图像生成器格式一致
        node_list = [
            {
                "nodeId": "38",  # 文生图提示词节点
                "fieldName": "text",
                "fieldValue": request.image_prompt
            },
            {
                "nodeId": "10",  # 图生视频提示词节点
                "fieldName": "text", 
                "fieldValue": request.video_prompt or request.image_prompt
            },
            {
                "nodeId": "1",   # 负向提示词节点
                "fieldName": "text",
                "fieldValue": request.negative_prompt or "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
            }
        ]
        
        # 添加分辨率设置
        node_list.extend([
            {
                "nodeId": "39",  # 分辨率节点
                "fieldName": "width",
                "fieldValue": request.width
            },
            {
                "nodeId": "39",  # 分辨率节点
                "fieldName": "height",
                "fieldValue": request.height
            }
        ])
        
        # 添加WanImageToVideo的length参数（帧数 = 时长 × 16fps）
        wan_frame_count = int(request.duration * 16)  # Wan模型默认16fps
        node_list.append({
            "nodeId": "5",  # WanImageToVideo节点
            "fieldName": "length",
            "fieldValue": wan_frame_count
        })
        
        # 如果指定了seed，添加随机种子控制
        if request.seed > 0:
            node_list.append({
                "nodeId": "36",  # RandomNoise节点
                "fieldName": "noise_seed",
                "fieldValue": request.seed
            })
        
        # RunningHub标准payload格式
        payload = {
            "apiKey": self.api_key,
            "workflowId": self.workflow_id,
            "nodeInfoList": node_list
        }
        
        return payload
    
    async def generate_video_async(self, request: TextToVideoRequest, max_task_retries: int = None) -> TextToVideoResult:
        """
        异步生成文生视频（支持任务级重试）
        
        Args:
            request: 文生视频请求
            max_task_retries: 任务级最大重试次数（None时从配置读取）
            
        Returns:
            TextToVideoResult: 生成结果
        """
        # 从配置读取重试参数
        if max_task_retries is None:
            max_task_retries = self.config.get('media.max_retries', 5)
        
        retry_delays = self.config.get('media.retry_delays', [10, 20, 30, 60, 120])
        retry_keywords = self.config.get('media.retry_keywords', ['timeout', 'connection', 'network', 'temporary', 'running', 'server', 'failed'])
        
        overall_start = time.time()
        self.logger.info(f"🔄 Text-to-video generation with max_retries={max_task_retries}")
        
        # 尝试多次生成（任务级重试）
        for attempt in range(max_task_retries + 1):
            start_time = time.time()
            task_id = None
            
            try:
                if attempt > 0:
                    self.logger.info(f"🔄 Retry attempt {attempt} for: {request.image_prompt[:50]}...")
                else:
                    self.logger.info(f"🎞️ Starting text-to-video generation: {request.image_prompt[:50]}...")
                
                # 构建API载荷
                payload = self._build_workflow_payload(request)
                self.logger.debug(f"Workflow payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
                
                # 提交工作流任务
                task_id = await self._submit_workflow_task(payload)
                self.logger.info(f"Submitted workflow task: {task_id}")
                
                # 轮询任务状态直到完成
                video_url = await self._poll_task_completion(task_id)
                self.logger.info(f"✅ Task completed, video URL: {video_url}")
                
                # 下载视频文件
                video_path = await self._download_video(video_url, request.scene_id)
                
                # 获取视频信息
                video_info = self._get_video_info(video_path)
                
                # 创建结果对象
                result = TextToVideoResult(
                    video_path=str(video_path),
                    width=video_info.get('width', request.width),
                    height=video_info.get('height', request.height),
                    fps=video_info.get('fps', request.fps),
                    duration=video_info.get('duration', request.duration),
                    file_size=Path(video_path).stat().st_size,
                    provider="runninghub",
                    workflow_id=self.workflow_id,
                    task_id=task_id or "",
                    generation_time=time.time() - overall_start
                )
                
                self.logger.info(f"🎉 Text-to-video completed: {result.file_size/1024:.1f}KB "
                               f"in {result.generation_time:.2f}s (attempt {attempt + 1})")
                
                return result
                
            except Exception as e:
                attempt_time = time.time() - start_time
                
                # 取消当前任务
                if task_id:
                    try:
                        await self._cancel_task(task_id)
                    except:
                        pass
                
                # 检查是否应该重试
                if attempt < max_task_retries:
                    error_str = str(e).lower()
                    should_retry = any(keyword in error_str for keyword in retry_keywords)
                    
                    if should_retry:
                        # 使用配置的延迟时间，如果超出范围则使用最后一个值
                        retry_delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                        self.logger.warning(f"⏰ Attempt {attempt + 1}/{max_task_retries + 1} failed after {attempt_time:.1f}s: {e}")
                        self.logger.info(f"🔄 Retrying in {retry_delay}s... (delay pattern: {retry_delays})")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        self.logger.error(f"❌ Non-retryable error on attempt {attempt + 1}: {e}")
                        self.logger.error(f"💡 Error not matching retry keywords: {retry_keywords}")
                        break
                else:
                    self.logger.error(f"❌ Final attempt {attempt + 1}/{max_task_retries + 1} failed: {e}")
                    break
        
        # 所有尝试都失败了
        total_time = time.time() - overall_start
        raise Exception(f"Text-to-video generation failed after {max_task_retries + 1} attempts in {total_time:.1f}s")
    
    async def _submit_workflow_task(self, payload: Dict[str, Any]) -> str:
        """提交工作流任务"""
        url = f"{self.base_url}/task/openapi/create"
        headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }
        
        async with self._create_optimized_session(60) as session:
            for attempt in range(self.max_retries):
                try:
                    async with session.post(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # RunningHub API格式检查
                            if data.get('code') != 0:
                                error_msg = data.get('msg', 'Task creation failed')
                                
                                # 特殊处理队列满载错误 - 不重试，直接失败
                                if 'TASK_QUEUE_MAXED' in error_msg or 'queue' in error_msg.lower():
                                    self.logger.error(f"🚫 RunningHub queue is full: {error_msg}")
                                    self.logger.error("💡 Suggestion: Reduce concurrent tasks or wait and retry later")
                                    raise Exception(f"RunningHub queue full (no retry): {error_msg}")
                                
                                raise Exception(f"RunningHub task failed: {error_msg}")
                            
                            # 获取taskId（整数类型）
                            task_id = data.get('data', {}).get('taskId')
                            if not task_id:
                                raise ValueError("No taskId in response")
                            return str(task_id)
                        else:
                            error_text = await response.text()
                            raise Exception(f"HTTP {response.status}: {error_text}")
                
                except asyncio.TimeoutError as e:
                    if attempt == self.max_retries - 1:
                        raise Exception(f"Workflow submission timeout after {self.max_retries} attempts")
                    self.logger.warning(f"Workflow submission attempt {attempt + 1} timed out, retrying...")
                    await asyncio.sleep(self.retry_delay)
                
                except Exception as e:
                    error_str = str(e)
                    
                    # 队列满载错误不重试，直接抛出
                    if 'queue full (no retry)' in error_str or 'TASK_QUEUE_MAXED' in error_str:
                        raise e
                    
                    if attempt == self.max_retries - 1:
                        raise Exception(f"Workflow submission failed: {e}")
                    self.logger.warning(f"Workflow submission attempt {attempt + 1} failed: {e}, retrying...")
                    await asyncio.sleep(self.retry_delay)
    
    async def _poll_task_completion(self, task_id: str) -> str:
        """轮询任务完成状态"""
        url = f"{self.base_url}/task/openapi/status"
        headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }
        
        poll_interval = 10  # 10秒轮询间隔
        max_poll_time = self.total_timeout
        start_time = time.time()
        
        status_payload = {"taskId": int(task_id), "apiKey": self.api_key}
        
        self.logger.info(f"⏳ Starting to poll task {task_id} (max {max_poll_time}s)")
        
        async with self._create_optimized_session(self.total_timeout) as session:
            poll_count = 0
            while time.time() - start_time < max_poll_time:
                poll_count += 1
                elapsed = time.time() - start_time
                
                try:
                    async with session.post(url, json=status_payload, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get('code') == 0:
                                task_status = data.get('data')
                                
                                if task_status == 'SUCCESS':
                                    self.logger.info(f"✅ Task {task_id} SUCCESS after {elapsed:.1f}s ({poll_count} polls)")
                                    
                                    # 获取任务输出
                                    return await self._get_task_outputs(task_id)
                                
                                elif task_status == 'FAILED':
                                    # 任务在服务端失败，记录详细错误信息
                                    self.logger.warning(f"🚫 Task {task_id} FAILED on server after {elapsed:.1f}s ({poll_count} polls)")
                                    
                                    # 尝试获取详细错误信息
                                    error_details = data.get('msg', 'No error message provided')
                                    full_response = data  # 记录完整响应
                                    self.logger.error(f"💥 Task {task_id} failure details: {error_details}")
                                    self.logger.debug(f"🔍 Full API response: {full_response}")
                                    
                                    raise Exception(f"Task {task_id} failed on RunningHub server after {elapsed:.1f}s: {error_details}")
                                
                                elif task_status in ['PENDING', 'RUNNING', 'PROCESSING']:
                                    self.logger.debug(f"🔄 Task {task_id}: {task_status} (poll #{poll_count}, {elapsed:.1f}s)")
                                
                                else:
                                    self.logger.warning(f"⚠️ Task {task_id} unknown status: {task_status}")
                            else:
                                error_msg = data.get('msg', 'Status check failed')
                                self.logger.warning(f"❌ Task {task_id} status check error: {error_msg}")
                        
                        else:
                            error_text = await response.text()
                            self.logger.warning(f"❌ Task {task_id} poll failed: HTTP {response.status}: {error_text}")
                
                except asyncio.TimeoutError:
                    self.logger.warning(f"⏰ Task {task_id} poll timeout (poll #{poll_count}), retrying...")
                
                except Exception as e:
                    # 区分服务端任务失败和网络/其他错误
                    if "failed on RunningHub server" in str(e):
                        # 服务端任务失败，应该立即终止轮询并重新提交任务
                        self.logger.error(f"💥 Task {task_id} server failure: {e}")
                        raise e  # 重新抛出，让上层重试机制处理
                    else:
                        # 网络或其他临时错误，继续轮询
                        self.logger.warning(f"❌ Task {task_id} poll error (poll #{poll_count}): {e}")
                
                # 等待下次轮询
                await asyncio.sleep(poll_interval)
            
            raise Exception(f"Task {task_id} did not complete within {max_poll_time} seconds (made {poll_count} poll attempts)")
    
    async def _get_task_outputs(self, task_id: str) -> str:
        """获取任务输出结果"""
        url = f"{self.base_url}/task/openapi/outputs"
        headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }
        
        outputs_payload = {"taskId": int(task_id), "apiKey": self.api_key}
        
        async with self._create_optimized_session(30) as session:
            async with session.post(url, json=outputs_payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('code') == 0:
                        outputs = data.get('data', [])
                        
                        # 寻找视频文件URL
                        for item in outputs:
                            if isinstance(item, dict) and 'fileUrl' in item:
                                file_url = item['fileUrl']
                                # 检查是否为视频文件
                                if file_url.endswith(('.mp4', '.avi', '.mov', '.webm')):
                                    self.logger.info(f"Found video URL: {file_url}")
                                    return file_url
                        
                        # 如果没找到视频，但有输出，取第一个
                        if outputs and len(outputs) > 0:
                            if isinstance(outputs[0], dict) and 'fileUrl' in outputs[0]:
                                self.logger.warning("No video file found, using first output")
                                return outputs[0]['fileUrl']
                        
                        raise ValueError("No video output found in task outputs")
                    else:
                        error_msg = data.get('msg', 'Failed to get outputs')
                        raise Exception(f"Get outputs failed: {error_msg}")
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to get outputs: HTTP {response.status}: {error_text}")
    
    async def _download_video(self, video_url: str, scene_id: str = "") -> Path:
        """下载生成的视频文件"""
        # 生成唯一文件名
        filename = f"text_to_video_{scene_id or uuid.uuid4().hex[:8]}_{int(time.time())}.mp4"
        output_path = self.file_manager.get_output_path('videos', filename)
        
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with self._create_optimized_session(300) as session:
            async with session.get(video_url) as response:
                if response.status == 200:
                    with open(output_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    
                    self.logger.info(f"Downloaded video: {output_path} ({output_path.stat().st_size} bytes)")
                    return output_path
                else:
                    raise Exception(f"Failed to download video: HTTP {response.status}")
    
    def _get_video_info(self, video_path: Path) -> Dict[str, Any]:
        """获取视频文件信息"""
        try:
            import cv2
            
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return {}
            
            info = {
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': int(cap.get(cv2.CAP_PROP_FPS)),
                'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            }
            info['duration'] = info['frame_count'] / info['fps'] if info['fps'] > 0 else 0
            
            # 添加文件大小信息
            try:
                info['file_size'] = video_path.stat().st_size
            except Exception as size_error:
                self.logger.warning(f"Could not get file size: {size_error}")
                info['file_size'] = 0
            
            cap.release()
            return info
            
        except Exception as e:
            self.logger.warning(f"Could not get video info: {e}")
            return {
                'width': 0,
                'height': 0, 
                'fps': 0,
                'frame_count': 0,
                'duration': 0,
                'file_size': 0
            }
    
    async def _cleanup_failed_task(self, task_id: str):
        """清理失败的任务资源"""
        try:
            self.logger.info(f"🧹 Cleaning up failed task {task_id}...")
            await self._cancel_task(task_id)
        except Exception as e:
            self.logger.warning(f"Failed to cleanup task {task_id}: {e}")
    
    async def _cancel_task(self, task_id: str):
        """取消运行中的任务"""
        try:
            url = f"{self.base_url}/task/openapi/cancel"
            headers = {
                "Host": "www.runninghub.cn",
                "Content-Type": "application/json"
            }
            
            cancel_payload = {"taskId": int(task_id), "apiKey": self.api_key}
            
            async with self._create_optimized_session(30) as session:
                async with session.post(url, json=cancel_payload, headers=headers) as response:
                    if response.status == 200:
                        self.logger.info(f"Successfully cancelled task: {task_id}")
                    else:
                        self.logger.warning(f"Failed to cancel task {task_id}: HTTP {response.status}")
        
        except Exception as e:
            self.logger.warning(f"Error cancelling task {task_id}: {e}")
    
    async def batch_generate_videos(self, requests: List[TextToVideoRequest], 
                                  max_concurrent: int = 3) -> List[TextToVideoResult]:
        """
        批量生成文生视频 - 优化版（任务提交与轮询分离）
        
        Args:
            requests: 视频生成请求列表
            max_concurrent: 最大并发数
            
        Returns:
            List[TextToVideoResult]: 生成结果列表
        """
        self.logger.info(f"🚀 Starting optimized batch text-to-video generation: {len(requests)} requests (max_concurrent={max_concurrent})")
        
        # 🌍 获取模块级全局信号量
        actual_concurrent = min(max_concurrent, self._max_concurrent)
        if max_concurrent != actual_concurrent:
            self.logger.warning(f"🎯 Concurrent limit adjusted: {max_concurrent} → {actual_concurrent} (module global limit)")
        
        # 获取全局信号量
        global_semaphore = await get_global_semaphore(actual_concurrent)
        
        # 验证并发数设置的合理性
        if actual_concurrent > 3:
            self.logger.warning(f"⚠️  High concurrent setting detected: {actual_concurrent}. RunningHub typically supports max 3 concurrent tasks.")
            self.logger.warning("💡 Consider reducing to 3 or lower if you encounter TASK_QUEUE_MAXED errors.")
        
        # 阶段1：批量提交所有任务
        self.logger.info("📝 Phase 1: Batch submitting all tasks...")
        
        async def submit_task_with_semaphore(request: TextToVideoRequest) -> tuple:
            async with global_semaphore:  # 🌍 使用模块级全局信号量
                try:
                    payload = self._build_workflow_payload(request)
                    task_id = await self._submit_workflow_task(payload)
                    self.logger.info(f"✅ Task submitted: {task_id} for {request.image_prompt[:30]}...")
                    return (request, task_id, None)
                except Exception as e:
                    self.logger.error(f"❌ Task submission failed for {request.image_prompt[:30]}: {e}")
                    return (request, None, e)
        
        # 并发提交所有任务
        submit_tasks = [submit_task_with_semaphore(req) for req in requests]
        submit_results = await asyncio.gather(*submit_tasks)
        
        # 收集成功提交的任务
        submitted_tasks = [(req, task_id) for req, task_id, error in submit_results if task_id]
        failed_submissions = [(req, error) for req, task_id, error in submit_results if not task_id]
        
        # 分析失败原因
        queue_full_errors = [error for req, error in failed_submissions if 'queue full' in str(error) or 'TASK_QUEUE_MAXED' in str(error)]
        
        self.logger.info(f"📋 Task submission completed: {len(submitted_tasks)} successful, {len(failed_submissions)} failed")
        
        if queue_full_errors:
            self.logger.error(f"🚫 {len(queue_full_errors)} tasks failed due to RunningHub queue being full")
            self.logger.error("💡 Recommendations:")
            self.logger.error("   - Reduce max_concurrent_tasks in config/settings.json")
            self.logger.error(f"   - Current setting: {max_concurrent}, try setting it to 3 or lower")
            self.logger.error("   - Wait a few minutes and retry")
        
        if not submitted_tasks:
            self.logger.error("❌ No tasks were successfully submitted")
            if queue_full_errors:
                self.logger.error("🔄 All failures were due to queue being full - try again with lower concurrency")
            return []
        
        # 阶段2：并发轮询所有任务状态
        self.logger.info(f"⏱️ Phase 2: Polling {len(submitted_tasks)} tasks concurrently...")
        
        async def poll_and_download_with_semaphore(request: TextToVideoRequest, task_id: str) -> TextToVideoResult:
            async with global_semaphore:  # 🌍 使用模块级全局信号量
                try:
                    start_time = time.time()
                    
                    # 轮询任务完成
                    video_url = await self._poll_task_completion(task_id)
                    
                    # 下载视频
                    video_path = await self._download_video(video_url, request.scene_id)
                    
                    # 获取视频信息
                    video_info = self._get_video_info(video_path)
                    
                    # 创建结果对象
                    result = TextToVideoResult(
                        video_path=str(video_path),
                        width=video_info.get('width', request.width),
                        height=video_info.get('height', request.height),
                        fps=video_info.get('fps', request.fps),
                        duration=video_info.get('duration', request.duration),
                        file_size=Path(video_path).stat().st_size,
                        provider="runninghub",
                        workflow_id=self.workflow_id,
                        task_id=task_id,
                        generation_time=time.time() - start_time
                    )
                    
                    self.logger.info(f"✅ Task {task_id} completed: {result.file_size/1024:.1f}KB in {result.generation_time:.2f}s")
                    return result
                    
                except Exception as e:
                    self.logger.error(f"❌ Task {task_id} failed: {e}")
                    # 取消失败的任务
                    try:
                        await self._cancel_task(task_id)
                    except:
                        pass
                    raise
        
        # 并发轮询和下载
        poll_tasks = [poll_and_download_with_semaphore(req, task_id) for req, task_id in submitted_tasks]
        poll_results = await asyncio.gather(*poll_tasks, return_exceptions=True)
        
        # 处理最终结果
        successful_results = []
        failed_count = len(failed_submissions)  # 包含提交失败的
        
        for i, result in enumerate(poll_results):
            if isinstance(result, Exception):
                self.logger.error(f"Task polling/download failed for task {i}: {result}")
                failed_count += 1
            else:
                successful_results.append(result)
        
        self.logger.info(f"🎉 Optimized batch generation completed: {len(successful_results)} successful, {failed_count} failed")
        return successful_results
    
    async def batch_generate_videos_v2(self, requests: List[TextToVideoRequest], 
                                      max_concurrent: int = 3) -> List[TextToVideoResult]:
        """
        批量生成文生视频 - 一体化版本（避免队列溢出）
        
        每个任务从提交到完成都在单个信号量保护下进行，避免RunningHub队列堆积
        
        Args:
            requests: 文生视频请求列表
            max_concurrent: 最大并发数（建议3或更低）
            
        Returns:
            List[TextToVideoResult]: 生成结果列表
        """
        self.logger.info(f"🚀 Starting integrated batch text-to-video generation: {len(requests)} requests (max_concurrent={max_concurrent})")
        
        # 🌍 获取模块级全局信号量
        actual_concurrent = min(max_concurrent, self._max_concurrent)
        if max_concurrent != actual_concurrent:
            self.logger.warning(f"🎯 Concurrent limit adjusted: {max_concurrent} → {actual_concurrent} (module global limit)")
        
        # 获取全局信号量
        global_semaphore = await get_global_semaphore(actual_concurrent)
        
        # 验证并发数设置的合理性
        if actual_concurrent > 3:
            self.logger.warning(f"⚠️  High concurrent setting detected: {actual_concurrent}. RunningHub queue limit appears to be 3 or lower.")
            self.logger.warning("💡 Consider reducing to 3 or lower to avoid TASK_QUEUE_MAXED errors.")
        
        # 🔄 一体化流程：每个任务从提交到完成都在信号量保护下进行，避免队列堆积
        self.logger.info("🔄 Integrated approach: Each task submit→poll→download in single semaphore session...")
        
        async def process_single_task_complete(request: TextToVideoRequest) -> TextToVideoResult:
            """一体化处理单个任务：提交→轮询→下载，全程在信号量保护下，支持重试机制"""
            async with global_semaphore:  # 🌍 全程信号量保护，避免队列堆积
                # 从配置读取重试参数
                max_task_retries = self.config.get('media.max_retries', 5)
                retry_delays = self.config.get('media.retry_delays', [10, 20, 30, 60, 120])
                overall_start = time.time()
                
                self.logger.debug(f"🔄 Task retry config: max_retries={max_task_retries}, delays={retry_delays}")
                
                # 尝试多次生成（任务级重试）
                for attempt in range(max_task_retries + 1):
                    task_id = None
                    try:
                        start_time = time.time()
                        
                        if attempt > 0:
                            self.logger.info(f"🔄 Retry attempt {attempt} for: {request.image_prompt[:30]}...")
                        
                        # Step 1: 提交任务
                        payload = self._build_workflow_payload(request)
                        task_id = await self._submit_workflow_task(payload)
                        self.logger.info(f"✅ Task submitted: {task_id} for {request.image_prompt[:30]}...")
                        
                        # Step 2: 轮询任务完成
                        video_url = await self._poll_task_completion(task_id)
                        
                        # Step 3: 下载视频
                        video_path = await self._download_video(video_url, request.scene_id)
                        
                        # Step 4: 获取视频信息
                        video_info = self._get_video_info(video_path)
                        
                        # Step 5: 创建结果对象
                        result = TextToVideoResult(
                            video_path=str(video_path),
                            width=video_info.get('width', request.width),
                            height=video_info.get('height', request.height),
                            fps=video_info.get('fps', request.fps),
                            duration=video_info.get('duration', request.duration),
                            file_size=video_info.get('file_size', 0),
                            provider="runninghub",
                            workflow_id=self.workflow_id,
                            task_id=task_id,
                            generation_time=time.time() - start_time
                        )
                        
                        self.logger.info(f"✅ Integrated task completed: {video_path.name} ({result.file_size/1024/1024:.1f}MB, {result.generation_time:.1f}s)")
                        return result  # 成功，跳出重试循环
                        
                    except Exception as e:
                        error_msg = f"Task failed for {request.image_prompt[:30]} (attempt {attempt + 1}/{max_task_retries + 1}): {e}"
                        self.logger.error(f"❌ {error_msg}")
                        
                        # 清理资源
                        if task_id:
                            try:
                                await self._cleanup_failed_task(task_id)
                            except:
                                pass
                        
                        # 如果是最后一次尝试，抛出异常；否则继续重试
                        if attempt < max_task_retries:
                            # 使用配置的延迟时间
                            retry_delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                            self.logger.warning(f"⏰ Batch task attempt {attempt + 1}/{max_task_retries + 1} failed: {e}")
                            self.logger.info(f"🔄 Retrying in {retry_delay}s... (configured delays: {retry_delays})")
                            await asyncio.sleep(retry_delay)
                        else:
                            # 所有重试都失败了
                            total_time = time.time() - overall_start
                            final_error = f"Task completely failed after {max_task_retries + 1} attempts in {total_time:.1f}s: {e}"
                            raise Exception(final_error)
        
        # 并发处理所有任务（一体化流程）
        self.logger.info(f"⚡ Processing {len(requests)} tasks with max_concurrent={actual_concurrent}...")
        process_tasks = [process_single_task_complete(req) for req in requests]
        results = await asyncio.gather(*process_tasks, return_exceptions=True)
        
        # 处理结果并收集失败任务信息
        successful_results = []
        failed_tasks = []
        failed_count = 0
        queue_full_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"❌ Task {i} failed completely: {result}")
                if 'TASK_QUEUE_MAXED' in str(result) or 'queue full' in str(result):
                    queue_full_count += 1
                failed_count += 1
                # 记录失败任务的详细信息
                failed_tasks.append({
                    'index': i,
                    'request': requests[i],
                    'error': str(result)
                })
            else:
                # 添加原始索引信息，便于上层正确映射
                result.original_scene_index = i
                successful_results.append(result)
        
        # 输出详细总结和建议
        self.logger.info(f"🎉 Integrated batch generation completed: {len(successful_results)} successful, {failed_count} failed")
        
        if failed_count > 0:
            self.logger.warning(f"⚠️ 注意：{failed_count}个任务失败，最终视频可能缺少部分场景")
            
            if queue_full_count > 0:
                self.logger.error(f"🚫 {queue_full_count} tasks failed due to RunningHub queue being full")
                self.logger.error("💡 Queue Full解决方案:")
                self.logger.error(f"   - 当前并发设置: {actual_concurrent}")
                self.logger.error("   - 建议降低到2个并发: config/settings.json -> max_concurrent_tasks: 2")
                self.logger.error("   - 等待几分钟后重试")
            
            # 分析失败原因并提供具体建议
            content_failures = [task for task in failed_tasks if 'queue' not in task['error'].lower()]
            if content_failures:
                self.logger.warning(f"📝 {len(content_failures)}个任务因内容问题失败:")
                for task in content_failures[:3]:  # 只显示前3个
                    prompt_preview = task['request'].image_prompt[:50] + "..." if len(task['request'].image_prompt) > 50 else task['request'].image_prompt
                    self.logger.warning(f"   - 场景{task['index']}: {prompt_preview}")
                
                self.logger.warning("💡 内容失败解决方案:")
                self.logger.warning("   - 某些提示词可能触发内容过滤")
                self.logger.warning("   - 建议简化复杂的政治、敏感内容描述")
                self.logger.warning("   - 可以手动重试失败的场景")
            
            # 提供补救措施建议
            success_rate = len(successful_results) / len(requests) * 100
            if success_rate < 80:
                self.logger.error(f"🚨 成功率过低 ({success_rate:.1f}%)，建议：")
                self.logger.error("   1. 检查网络连接和API密钥")
                self.logger.error("   2. 降低并发数到1-2个")
                self.logger.error("   3. 简化提示词内容")
                self.logger.error("   4. 分批处理，每次2-3个场景")
            elif success_rate < 100:
                self.logger.warning(f"📊 部分成功 ({success_rate:.1f}%)，影响：")
                self.logger.warning("   - 最终视频会缺少部分场景")
                self.logger.warning("   - 建议单独重试失败的场景")
        
        return successful_results
    
    def generate_video_sync(self, request: TextToVideoRequest) -> TextToVideoResult:
        """同步生成接口"""
        return asyncio.run(self.generate_video_async(request))
    
    def get_supported_resolutions(self) -> List[tuple]:
        """获取支持的分辨率列表"""
        return [
            (720, 1280),   # 竖屏标准
            (1280, 720),   # 横屏标准
            (512, 512),    # 方形
            (768, 768),    # 方形高清
        ]
    
    def __str__(self) -> str:
        return f"TextToVideoGenerator(workflow_id={self.workflow_id}, provider=runninghub)"