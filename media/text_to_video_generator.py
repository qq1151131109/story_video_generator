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
    
    def __init__(self, config: ConfigManager, cache_manager, file_manager: FileManager):
        self.config = config
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.text_to_video')
        
        # 工作流配置 - 最新一体化文生视频工作流
        self.workflow_id = "1964265917020520450"
        
        # API配置 - 使用与图像生成器相同的API端点
        self.api_key = self.config.get_api_key('runninghub')
        self.base_url = "https://www.runninghub.cn"
        
        # 超时和重试配置
        self.connect_timeout = self.config.get('general.connect_timeout', 30)  # 连接超时
        self.request_timeout = self.config.get('general.request_timeout', 60)  # 请求超时
        self.total_timeout = self.config.get('general.api_timeout', 300)  # 总超时
        self.max_retries = self.config.get('general.api_max_retries', 5)  # 增加重试次数
        self.retry_delay = self.config.get('general.retry_delay', 10)  # 增加重试间隔
        
        if not self.api_key:
            raise ValueError("RunningHub API key not configured")
    
    def _build_workflow_payload(self, request: TextToVideoRequest) -> Dict[str, Any]:
        """
        构建工作流API载荷 - 使用RunningHub标准格式
        
        基于新工作流(1964265917020520450)的节点配置：
        - 文生图提示词节点: image_prompt
        - 图生视频提示词节点: video_prompt
        - 负向提示词节点: negative_prompt
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
    
    async def generate_video_async(self, request: TextToVideoRequest) -> TextToVideoResult:
        """
        异步生成文生视频
        
        Args:
            request: 文生视频请求
            
        Returns:
            TextToVideoResult: 生成结果
        """
        start_time = time.time()
        task_id = None
        
        try:
            # 构建API载荷
            payload = self._build_workflow_payload(request)
            
            self.logger.info(f"Starting text-to-video generation: {request.image_prompt[:50]}...")
            self.logger.debug(f"Workflow payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            # 提交工作流任务
            task_id = await self._submit_workflow_task(payload)
            self.logger.info(f"Submitted workflow task: {task_id}")
            
            # 轮询任务状态直到完成
            video_url = await self._poll_task_completion(task_id)
            self.logger.info(f"Task completed, video URL: {video_url}")
            
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
                generation_time=time.time() - start_time
            )
            
            self.logger.info(f"Text-to-video generation completed: {result.file_size/1024:.1f}KB "
                           f"in {result.generation_time:.2f}s")
            
            return result
            
        except Exception as e:
            generation_time = time.time() - start_time
            self.logger.error(f"Text-to-video generation failed after {generation_time:.2f}s: {e}")
            
            # 如果有task_id，尝试取消任务
            if task_id:
                try:
                    await self._cancel_task(task_id)
                except:
                    pass  # 取消失败不影响错误处理
            
            raise
    
    async def _submit_workflow_task(self, payload: Dict[str, Any]) -> str:
        """提交工作流任务"""
        url = f"{self.base_url}/task/openapi/create"
        headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            for attempt in range(self.max_retries):
                try:
                    async with session.post(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # RunningHub API格式检查
                            if data.get('code') != 0:
                                error_msg = data.get('msg', 'Task creation failed')
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
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            while time.time() - start_time < max_poll_time:
                try:
                    async with session.post(url, json=status_payload, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get('code') == 0:
                                task_status = data.get('data')
                                
                                if task_status == 'SUCCESS':
                                    self.logger.info(f"RunningHub task {task_id} completed successfully")
                                    
                                    # 获取任务输出
                                    return await self._get_task_outputs(task_id)
                                
                                elif task_status == 'FAILED':
                                    raise Exception(f"Task {task_id} failed")
                                
                                elif task_status in ['PENDING', 'RUNNING', 'PROCESSING']:
                                    self.logger.info(f"Task {task_id} status: {task_status}, continuing to poll...")
                                
                                else:
                                    self.logger.warning(f"Unknown task status: {task_status}")
                            else:
                                error_msg = data.get('msg', 'Status check failed')
                                self.logger.warning(f"Status check error: {error_msg}")
                        
                        else:
                            error_text = await response.text()
                            self.logger.warning(f"Status poll failed: HTTP {response.status}: {error_text}")
                
                except asyncio.TimeoutError:
                    self.logger.warning("Status poll timeout, retrying...")
                
                except Exception as e:
                    self.logger.warning(f"Status poll error: {e}")
                
                # 等待下次轮询
                await asyncio.sleep(poll_interval)
            
            raise Exception(f"Task {task_id} did not complete within {max_poll_time} seconds")
    
    async def _get_task_outputs(self, task_id: str) -> str:
        """获取任务输出结果"""
        url = f"{self.base_url}/task/openapi/outputs"
        headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }
        
        outputs_payload = {"taskId": int(task_id), "apiKey": self.api_key}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
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
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
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
            
            cap.release()
            return info
            
        except Exception as e:
            self.logger.warning(f"Could not get video info: {e}")
            return {}
    
    async def _cancel_task(self, task_id: str):
        """取消运行中的任务"""
        try:
            url = f"{self.base_url}/task/openapi/cancel"
            headers = {
                "Host": "www.runninghub.cn",
                "Content-Type": "application/json"
            }
            
            cancel_payload = {"taskId": int(task_id), "apiKey": self.api_key}
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
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
        批量生成文生视频
        
        Args:
            requests: 视频生成请求列表
            max_concurrent: 最大并发数
            
        Returns:
            List[TextToVideoResult]: 生成结果列表
        """
        self.logger.info(f"Starting batch text-to-video generation: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(request: TextToVideoRequest) -> TextToVideoResult:
            async with semaphore:
                return await self.generate_video_async(request)
        
        # 执行并发生成
        tasks = [generate_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch generation failed for request {i}: {result}")
                failed_count += 1
            else:
                successful_results.append(result)
        
        self.logger.info(f"Batch generation completed: {len(successful_results)} successful, {failed_count} failed")
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