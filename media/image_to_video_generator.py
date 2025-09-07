"""
图生视频生成器 - RunningHub Wan2.2图生视频API集成
基于工作流ID: 1958006911062913026
"""
import asyncio
import aiohttp
import base64
import time
import json
from typing import Dict, Optional, Any
from pathlib import Path
import logging
from dataclasses import dataclass

from core.config_manager import ConfigManager
from utils.file_manager import FileManager

@dataclass
class ImageToVideoRequest:
    """图生视频请求"""
    image_path: str                    # 输入图片路径  
    image_prompt: str                  # 图像提示词（来自ImagePromptGenerator）
    duration_seconds: float            # 视频时长
    width: int = 720                   # 视频宽度
    height: int = 1280                 # 视频高度
    negative_prompt: str = ""          # 负面提示词

@dataclass
class ImageToVideoResult:
    """图生视频结果"""
    video_data: bytes                  # 视频数据
    video_path: str                    # 保存的视频文件路径
    duration_seconds: float            # 实际视频时长
    frames: int                        # 视频帧数
    file_size: int                     # 文件大小
    generation_time: float             # 生成耗时
    task_id: str                       # RunningHub任务ID

class ImageToVideoGenerator:
    """
    图生视频生成器 - RunningHub Wan2.2集成
    
    基于工作流 1958006911062913026 实现图片转视频功能
    """
    
    def __init__(self, config_manager: ConfigManager, file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.media')
        
        # 获取图生视频配置
        self.i2v_config = config_manager.get('video.image_to_video', {})
        
        # API配置
        self.api_key = config_manager.get_api_key('runninghub')
        self.workflow_id = self.i2v_config.get('workflow_id', '1958006911062913026')
        
        # 节点ID配置（基于工作流分析）
        self.node_ids = {
            'positive_prompt': self.i2v_config.get('positive_prompt_node_id', '10'),
            'negative_prompt': self.i2v_config.get('negative_prompt_node_id', '1'),
            'wan_i2v': self.i2v_config.get('wan_i2v_node_id', '5'),
            'load_image': self.i2v_config.get('load_image_node_id', '4')
        }
        
        # 视频参数
        self.default_fps = self.i2v_config.get('fps', 16)
        self.default_negative_prompt = "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
        
        if not self.api_key:
            self.logger.warning("RunningHub API key not configured")
        
        self.logger.info(f"ImageToVideoGenerator initialized with workflow: {self.workflow_id}")
    
    def calculate_frames(self, duration_seconds: float) -> int:
        """
        根据时长计算帧数
        
        Args:
            duration_seconds: 视频时长（秒）
        
        Returns:
            int: 计算出的帧数
        """
        frames = int(duration_seconds * self.default_fps)
        # RunningHub可能有帧数限制，这里设置合理范围
        frames = max(16, min(frames, 800))  # 1秒到50秒
        self.logger.debug(f"Calculated frames: {frames} for duration {duration_seconds}s")
        return frames
    
    async def generate_video_async(self, request: ImageToVideoRequest) -> ImageToVideoResult:
        """
        异步生成图生视频
        
        Args:
            request: 图生视频请求
        
        Returns:
            ImageToVideoResult: 生成结果
        """
        start_time = time.time()
        
        if not self.api_key:
            raise Exception("RunningHub API key not configured")
        
        if not Path(request.image_path).exists():
            raise Exception(f"Input image not found: {request.image_path}")
        
        try:
            # 1. 准备图片数据
            image_data = await self._prepare_image_data(request.image_path)
            
            # 2. 计算帧数
            frames = self.calculate_frames(request.duration_seconds)
            
            # 3. 构建API请求
            api_payload = self._build_api_payload(request, frames, image_data)
            
            # 4. 发起RunningHub任务
            task_id = await self._create_task(api_payload)
            
            # 5. 等待任务完成
            result_data = await self._wait_for_completion(task_id)
            
            # 6. 下载并保存视频
            video_path = await self._download_and_save_video(result_data, request)
            
            # 7. 创建结果对象
            video_file_size = Path(video_path).stat().st_size
            
            result = ImageToVideoResult(
                video_data=b'',  # 数据已保存到文件，这里不重复存储
                video_path=video_path,
                duration_seconds=request.duration_seconds,
                frames=frames,
                file_size=video_file_size,
                generation_time=time.time() - start_time,
                task_id=task_id
            )
            
            self.logger.info(f"Image-to-video generated successfully: {video_path} ({video_file_size/1024/1024:.1f}MB, {result.generation_time:.1f}s)")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Image-to-video generation failed after {processing_time:.1f}s: {e}")
            raise
    
    async def _upload_image_to_runninghub(self, image_path: str) -> str:
        """
        上传图片到RunningHub
        
        Args:
            image_path: 本地图片路径
        
        Returns:
            str: 服务器返回的fileName
        """
        if not Path(image_path).exists():
            raise Exception(f"Image file not found: {image_path}")
        
        # 检查文件大小（10MB限制）
        file_size = Path(image_path).stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10MB
            raise Exception(f"Image file too large: {file_size/1024/1024:.1f}MB (max: 10MB)")
        
        upload_url = "https://www.runninghub.cn/task/openapi/upload"
        
        headers = {
            "Host": "www.runninghub.cn"
        }
        
        # 构建multipart/form-data
        data = aiohttp.FormData()
        data.add_field('apiKey', self.api_key)
        data.add_field('fileType', 'image')
        
        # 添加文件
        with open(image_path, 'rb') as f:
            data.add_field('file', f, filename=Path(image_path).name)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(upload_url, data=data, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Image upload failed {response.status}: {error_text}")
                    
                    result = await response.json()
                    
                    if result.get('code') != 0:
                        error_msg = result.get('msg', 'Upload failed')
                        raise Exception(f"RunningHub upload error: {error_msg}")
                    
                    file_name = result.get('data', {}).get('fileName')
                    if not file_name:
                        raise Exception("No fileName returned from upload")
                    
                    self.logger.info(f"Image uploaded successfully: {file_name}")
                    return file_name
    
    async def _prepare_image_data(self, image_path: str) -> str:
        """准备图片数据 - 上传到RunningHub并返回fileName"""
        try:
            # 上传图片到RunningHub
            file_name = await self._upload_image_to_runninghub(image_path)
            return file_name
            
        except Exception as e:
            self.logger.error(f"Failed to prepare image {image_path}: {e}")
            raise
    
    def _build_api_payload(self, request: ImageToVideoRequest, frames: int, uploaded_file_name: str) -> Dict[str, Any]:
        """
        构建RunningHub API请求负载
        
        基于工作流节点配置和API文档
        """
        # 构建节点参数修改列表
        node_list = [
            # LoadImage节点 - 上传的图片
            {
                "nodeId": self.node_ids['load_image'],
                "fieldName": "image",
                "fieldValue": uploaded_file_name
            },
            # 正向提示词节点
            {
                "nodeId": self.node_ids['positive_prompt'],
                "fieldName": "text",
                "fieldValue": request.image_prompt
            },
            # 负向提示词节点  
            {
                "nodeId": self.node_ids['negative_prompt'],
                "fieldName": "text",
                "fieldValue": request.negative_prompt or self.default_negative_prompt
            },
            # WanImageToVideo节点 - 分辨率和帧数
            {
                "nodeId": self.node_ids['wan_i2v'],
                "fieldName": "width",
                "fieldValue": request.width
            },
            {
                "nodeId": self.node_ids['wan_i2v'],
                "fieldName": "height", 
                "fieldValue": request.height
            },
            {
                "nodeId": self.node_ids['wan_i2v'],
                "fieldName": "length",
                "fieldValue": frames
            }
        ]
        
        payload = {
            "apiKey": self.api_key,
            "workflowId": self.workflow_id,
            "nodeInfoList": node_list
        }
        
        self.logger.debug(f"Built API payload with {len(node_list)} node modifications")
        return payload
    
    async def _create_task(self, payload: Dict[str, Any]) -> str:
        """创建RunningHub任务"""
        api_url = "https://www.runninghub.cn/task/openapi/create"
        
        headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"RunningHub task creation failed {response.status}: {error_text}")
                
                result = await response.json()
                
                if result.get('code') != 0:
                    error_msg = result.get('msg', 'Task creation failed')
                    raise Exception(f"RunningHub API error: {error_msg}")
                
                task_id = str(result.get('data', {}).get('taskId'))
                if not task_id:
                    raise Exception("No task ID returned from RunningHub")
                
                self.logger.info(f"RunningHub I2V task created: {task_id}")
                return task_id
    
    async def _wait_for_completion(self, task_id: str) -> Dict[str, Any]:
        """等待任务完成并返回结果"""
        status_url = "https://www.runninghub.cn/task/openapi/status"
        outputs_url = "https://www.runninghub.cn/task/openapi/outputs"
        
        headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }
        
        status_payload = {
            "taskId": task_id,
            "apiKey": self.api_key
        }
        
        async with aiohttp.ClientSession() as session:
            # 轮询任务状态（图生视频通常需要更长时间）
            for attempt in range(3600):  # 60分钟超时
                await asyncio.sleep(1)
                
                try:
                    # 检查状态
                    async with session.post(status_url, json=status_payload, headers=headers) as response:
                        if response.status != 200:
                            continue
                        
                        status_result = await response.json()
                        if status_result.get('code') != 0:
                            continue
                        
                        task_status = status_result.get('data')
                        
                        if task_status == 'SUCCESS':
                            self.logger.info(f"RunningHub I2V task {task_id} completed")
                            
                            # 获取结果
                            outputs_payload = {"taskId": task_id, "apiKey": self.api_key}
                            async with session.post(outputs_url, json=outputs_payload, headers=headers) as outputs_response:
                                if outputs_response.status == 200:
                                    outputs_result = await outputs_response.json()
                                    if outputs_result.get('code') == 0:
                                        outputs = outputs_result.get('data', [])
                                        
                                        # 查找视频文件
                                        for item in outputs:
                                            if isinstance(item, dict) and 'fileUrl' in item:
                                                # 检查是否是视频文件
                                                file_url = item['fileUrl']
                                                if any(ext in file_url.lower() for ext in ['.mp4', '.mov', '.avi']):
                                                    return {'video_url': file_url}
                                            elif isinstance(item, str) and any(ext in item.lower() for ext in ['.mp4', '.mov', '.avi']):
                                                return {'video_url': item}
                                        
                                        raise Exception(f"No video file found in outputs: {outputs}")
                            
                            raise Exception(f"Failed to get outputs for task {task_id}")
                        
                        elif task_status == 'FAILED':
                            raise Exception(f"RunningHub I2V task {task_id} failed")
                        
                        elif task_status in ['RUNNING', 'QUEUED'] and attempt % 30 == 0:
                            self.logger.debug(f"RunningHub I2V task {task_id} status: {task_status} (attempt {attempt})")
                
                except Exception as e:
                    if attempt > 120:  # 2分钟后开始记录详细错误
                        self.logger.debug(f"Status check error (attempt {attempt}): {e}")
                    continue
            
            # 超时
            self.logger.error(f"RunningHub I2V task {task_id} timeout after 60 minutes")
            raise Exception(f"RunningHub I2V task {task_id} timeout")
    
    async def _download_and_save_video(self, result_data: Dict[str, Any], request: ImageToVideoRequest) -> str:
        """下载并保存生成的视频"""
        video_url = result_data.get('video_url')
        if not video_url:
            raise Exception("No video URL in result data")
        
        try:
            # 生成文件名
            filename = self.file_manager.generate_filename(
                content=request.image_prompt,
                prefix="i2v",
                extension="mp4"
            )
            
            video_path = self.file_manager.get_output_path('videos', filename)
            
            # 下载视频
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to download video: HTTP {response.status}")
                    
                    video_data = await response.read()
                    
                    # 保存到文件
                    with open(video_path, 'wb') as f:
                        f.write(video_data)
                    
                    self.logger.info(f"Downloaded I2V video: {video_path} ({len(video_data)/1024/1024:.1f}MB)")
                    return str(video_path)
        
        except Exception as e:
            self.logger.error(f"Failed to download I2V video: {e}")
            raise
    
    def generate_video_sync(self, request: ImageToVideoRequest) -> ImageToVideoResult:
        """
        同步生成图生视频（对异步方法的包装）
        
        Args:
            request: 图生视频请求
        
        Returns:
            ImageToVideoResult: 生成结果
        """
        return asyncio.run(self.generate_video_async(request))
    
    async def generate_video_async(self, request: ImageToVideoRequest) -> ImageToVideoResult:
        """异步生成图生视频主方法"""
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting I2V generation: {Path(request.image_path).name} -> {request.duration_seconds}s video")
            
            # 验证输入
            if not Path(request.image_path).exists():
                raise Exception(f"Input image not found: {request.image_path}")
            
            # 上传图片到RunningHub
            uploaded_file_name = await self._prepare_image_data(request.image_path)
            
            # 计算帧数
            frames = self.calculate_frames(request.duration_seconds)
            
            # 构建API请求
            api_payload = self._build_api_payload(request, frames, uploaded_file_name)
            
            # 发起任务
            task_id = await self._create_task(api_payload)
            
            # 等待完成
            result_data = await self._wait_for_completion(task_id)
            
            # 下载保存视频
            video_path = await self._download_and_save_video(result_data, request)
            
            # 验证视频文件
            if not Path(video_path).exists():
                raise Exception(f"Generated video file not found: {video_path}")
            
            video_file_size = Path(video_path).stat().st_size
            
            result = ImageToVideoResult(
                video_data=b'',  # 不在内存中保留大视频数据
                video_path=video_path,
                duration_seconds=request.duration_seconds,
                frames=frames,
                file_size=video_file_size,
                generation_time=time.time() - start_time,
                task_id=task_id
            )
            
            # 记录成功日志
            logger = self.config.get_logger('story_generator')
            logger.info(f"I2V generation - Input: {Path(request.image_path).name}, "
                       f"Duration: {request.duration_seconds}s, Frames: {frames}, "
                       f"Size: {video_file_size/1024/1024:.1f}MB, Time: {result.generation_time:.1f}s")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"I2V generation failed after {processing_time:.1f}s: {e}")
            
            # 记录错误日志
            logger = self.config.get_logger('story_generator')
            logger.error(f"I2V generation failed - Input: {Path(request.image_path).name if hasattr(request, 'image_path') else 'unknown'}, "
                        f"Time: {processing_time:.1f}s, Error: {str(e)}")
            
            raise
    
    
    def get_stats(self) -> Dict[str, Any]:
        """获取图生视频生成器统计信息"""
        return {
            'provider': 'runninghub',
            'workflow_id': self.workflow_id,
            'default_fps': self.default_fps,
            'node_ids': self.node_ids,
            'api_key_configured': bool(self.api_key),
            'enabled': self.i2v_config.get('enabled', False)
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ImageToVideoGenerator(workflow={self.workflow_id}, fps={self.default_fps})"