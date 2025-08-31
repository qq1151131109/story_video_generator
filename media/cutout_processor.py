"""
抠图处理器 - RunningHub API集成
实现图像背景移除，生成透明背景PNG
"""
import asyncio
import aiohttp
import time
import json
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager

@dataclass
class CutoutRequest:
    """抠图请求"""
    image_url: str              # 输入图像URL
    workflow_id: str = "1961729963818991618"  # RunningHub抠图工作流ID（使用已测试成功的版本）
    
@dataclass
class CutoutResult:
    """抠图结果"""
    success: bool               # 是否成功
    transparent_image_url: str  # 透明背景图像URL
    local_file_path: Optional[str] = None  # 本地保存路径
    task_id: str = ""          # 任务ID
    processing_time: float = 0.0  # 处理时间
    error_message: str = ""     # 错误信息

class CutoutProcessor:
    """
    抠图处理器 - 基于RunningHub ComfyUI工作流
    
    功能：
    1. 调用RunningHub抠图工作流API
    2. 轮询任务状态直到完成
    3. 下载并保存透明背景图像
    4. 提供缓存机制避免重复处理
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 cache_manager: CacheManager, file_manager: FileManager):
        self.config = config_manager
        self.cache = cache_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.media')
        
        # 获取RunningHub API配置
        self.api_key = os.getenv('RUNNINGHUB_API_KEY')
        if not self.api_key:
            self.logger.warning("RUNNINGHUB_API_KEY not found in environment variables")
        
        # API配置
        self.api_base = "https://www.runninghub.cn"
        self.create_task_url = f"{self.api_base}/task/openapi/create"
        self.query_status_url = f"{self.api_base}/task/openapi/status"
        self.query_result_url = f"{self.api_base}/task/openapi/outputs"
        
        # 请求配置
        self.max_retries = 3
        self.poll_interval = 5.0  # 查询间隔（秒）
        self.max_wait_time = 300.0  # 最大等待时间（秒）
        
        self.logger.info("CutoutProcessor initialized with RunningHub API")
    
    async def process_cutout_async(self, request: CutoutRequest) -> CutoutResult:
        """
        异步抠图处理
        
        Args:
            request: 抠图请求
        
        Returns:
            CutoutResult: 抠图结果
        """
        start_time = time.time()
        
        try:
            # 检查缓存
            cache_key = self.cache.get_cache_key({
                'image_url': request.image_url,
                'workflow_id': request.workflow_id
            })
            
            cached_result = self.cache.get('cutout', cache_key)
            if cached_result:
                self.logger.info(f"Cache hit for cutout: {request.image_url}")
                cached_result['processing_time'] = time.time() - start_time
                return CutoutResult(**cached_result)
            
            # 验证API密钥
            if not self.api_key:
                raise ValueError("RUNNINGHUB_API_KEY is required for cutout processing")
            
            # 步骤1: 创建抠图任务
            task_id = await self._create_cutout_task(request)
            self.logger.info(f"Created cutout task: {task_id}")
            
            # 步骤2: 轮询任务状态直到完成
            result_data = await self._poll_task_completion(task_id)
            
            # 步骤3: 下载并保存结果图像
            local_file_path = await self._download_result_image(result_data, request.image_url)
            
            # 创建结果对象
            result = CutoutResult(
                success=True,
                transparent_image_url=result_data['fileUrl'],
                local_file_path=local_file_path,
                task_id=task_id,
                processing_time=time.time() - start_time
            )
            
            # 缓存结果
            cache_data = {
                'success': result.success,
                'transparent_image_url': result.transparent_image_url,
                'local_file_path': result.local_file_path,
                'task_id': result.task_id
            }
            self.cache.set('cutout', cache_key, cache_data)
            
            self.logger.info(f"Cutout processing completed: {result.processing_time:.2f}s")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Cutout processing failed: {e}"
            self.logger.error(error_msg)
            
            return CutoutResult(
                success=False,
                transparent_image_url="",
                task_id="",
                processing_time=processing_time,
                error_message=error_msg
            )
    
    async def _create_cutout_task(self, request: CutoutRequest) -> str:
        """
        创建抠图任务
        
        Args:
            request: 抠图请求
        
        Returns:
            str: 任务ID
        """
        payload = {
            "apiKey": self.api_key,
            "workflowId": request.workflow_id,
            "nodeInfoList": [
                {
                    "nodeId": "3",  # 正确的抠图工作流输入节点ID
                    "fieldName": "image_url",  # 正确的输入图像字段名
                    "fieldValue": request.image_url
                }
            ],
            "addMetadata": True
        }
        
        headers = {
            "Host": "www.runninghub.cn",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            for attempt in range(self.max_retries):
                try:
                    async with session.post(
                        self.create_task_url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            if result.get('code') == 0:
                                return str(result['data']['taskId'])
                            else:
                                raise Exception(f"API error: {result.get('msg', 'Unknown error')}")
                        else:
                            raise Exception(f"HTTP error: {response.status}")
                
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        raise
                    self.logger.warning(f"Task creation attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)  # 指数退避
        
        raise Exception("Failed to create cutout task after all retries")
    
    async def _poll_task_completion(self, task_id: str) -> Dict[str, Any]:
        """
        轮询任务完成状态
        
        Args:
            task_id: 任务ID
        
        Returns:
            Dict[str, Any]: 任务结果数据
        """
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            while time.time() - start_time < self.max_wait_time:
                try:
                    # 查询任务状态（使用POST方法）
                    status_payload = {
                        "apiKey": self.api_key,
                        "taskId": task_id
                    }
                    headers = {
                        "Host": "www.runninghub.cn",
                        "Content-Type": "application/json"
                    }
                    async with session.post(self.query_status_url, json=status_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            status_result = await response.json()
                            if status_result.get('code') == 0:
                                task_status = status_result['data']  # data直接就是状态字符串
                                self.logger.debug(f"Task {task_id} status: {task_status}")
                                
                                if task_status == 'SUCCESS':
                                    # 查询任务结果（使用POST方法）
                                    result_payload = {
                                        "apiKey": self.api_key,
                                        "taskId": task_id
                                    }
                                    async with session.post(self.query_result_url, json=result_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as result_response:
                                        if result_response.status == 200:
                                            result_data = await result_response.json()
                                            if result_data.get('code') == 0 and result_data['data']:
                                                return result_data['data'][0]  # 返回第一个结果
                                            else:
                                                raise Exception(f"Failed to get task result: {result_data.get('msg')}")
                                        else:
                                            raise Exception(f"HTTP error getting result: {result_response.status}")
                                
                                elif task_status == 'FAILED':
                                    raise Exception(f"Task {task_id} failed")
                                
                                # 任务仍在进行中，继续等待
                            else:
                                raise Exception(f"Status API error: {status_result.get('msg')}")
                        else:
                            raise Exception(f"HTTP error checking status: {response.status}")
                
                except Exception as e:
                    self.logger.warning(f"Error polling task status: {e}")
                
                # 等待后再次检查
                await asyncio.sleep(self.poll_interval)
        
        raise Exception(f"Task {task_id} timed out after {self.max_wait_time}s")
    
    async def _download_result_image(self, result_data: Dict[str, Any], original_url: str) -> str:
        """
        下载结果图像到本地
        
        Args:
            result_data: 任务结果数据
            original_url: 原始图像URL（用于生成文件名）
        
        Returns:
            str: 本地文件路径
        """
        file_url = result_data['fileUrl']
        file_type = result_data.get('fileType', 'png')
        
        # 生成本地文件名
        timestamp = int(time.time())
        original_name = Path(original_url).stem if original_url else "cutout"
        local_filename = f"{original_name}_cutout_{timestamp}.{file_type}"
        local_filepath = self.file_manager.get_output_path('images', local_filename)
        
        # 下载文件
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status == 200:
                    # 确保目录存在
                    Path(local_filepath).parent.mkdir(parents=True, exist_ok=True)
                    
                    # 保存文件
                    with open(local_filepath, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    
                    self.logger.info(f"Downloaded cutout result: {local_filepath}")
                    return str(local_filepath)
                else:
                    raise Exception(f"Failed to download image: HTTP {response.status}")
    
    def process_cutout_sync(self, request: CutoutRequest) -> CutoutResult:
        """
        同步抠图处理（对异步方法的包装）
        
        Args:
            request: 抠图请求
        
        Returns:
            CutoutResult: 抠图结果
        """
        return asyncio.run(self.process_cutout_async(request))
    
    async def batch_cutout(self, requests: list[CutoutRequest], 
                          max_concurrent: int = 2) -> list[CutoutResult]:
        """
        批量抠图处理
        
        Args:
            requests: 抠图请求列表
            max_concurrent: 最大并发数
        
        Returns:
            list[CutoutResult]: 抠图结果列表
        """
        self.logger.info(f"Starting batch cutout: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(request: CutoutRequest) -> CutoutResult:
            async with semaphore:
                return await self.process_cutout_async(request)
        
        # 执行并发处理
        tasks = [process_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch cutout failed for request {i}: {result}")
                failed_count += 1
                # 创建失败结果
                failed_result = CutoutResult(
                    success=False,
                    transparent_image_url="",
                    error_message=str(result)
                )
                successful_results.append(failed_result)
            else:
                successful_results.append(result)
        
        self.logger.info(f"Batch cutout completed: {len(successful_results) - failed_count} successful, {failed_count} failed")
        
        return successful_results
    
    def get_cutout_stats(self) -> Dict[str, Any]:
        """获取抠图处理统计信息"""
        cache_stats = self.cache.get_cache_stats()
        
        return {
            'api_configured': bool(self.api_key),
            'cache_stats': cache_stats.get('disk_cache', {}).get('cutout', {}),
            'api_base': self.api_base,
            'max_wait_time': self.max_wait_time,
            'poll_interval': self.poll_interval
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"CutoutProcessor(api_configured={bool(self.api_key)}, base_url={self.api_base})"