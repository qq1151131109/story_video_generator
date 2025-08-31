"""
内容生成流水线 - 整合文案生成、场景分割和角色分析
"""
import asyncio
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging
from dataclasses import dataclass

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from .script_generator import ScriptGenerator, ScriptGenerationRequest, GeneratedScript
from .scene_splitter import SceneSplitter, SceneSplitRequest, SceneSplitResult
from .character_analyzer import CharacterAnalyzer, CharacterAnalysisRequest, CharacterAnalysisResult

@dataclass
class ContentGenerationRequest:
    """内容生成流水线请求"""
    theme: str                      # 主题
    language: str                   # 语言代码
    style: str = "horror"          # 风格
    target_length: int = 800       # 文案目标长度
    target_scene_count: int = 8    # 场景数量
    scene_duration: float = 3.0    # 场景时长
    max_characters: int = 3        # 最大角色数

@dataclass
class ContentGenerationResult:
    """内容生成流水线结果"""
    script: GeneratedScript           # 生成的文案
    scenes: SceneSplitResult         # 场景分割结果
    characters: CharacterAnalysisResult  # 角色分析结果
    total_processing_time: float     # 总处理时间
    request: ContentGenerationRequest  # 原始请求

class ContentPipeline:
    """
    内容生成流水线
    
    整合三个主要组件：
    1. ScriptGenerator - 文案生成
    2. SceneSplitter - 场景分割
    3. CharacterAnalyzer - 角色分析
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 cache_manager, file_manager: FileManager):
        self.config = config_manager
        # 缓存已删除
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.content')
        
        # 初始化各个组件
        self.script_generator = ScriptGenerator(config_manager, None, file_manager)
        self.scene_splitter = SceneSplitter(config_manager, None, file_manager)
        self.character_analyzer = CharacterAnalyzer(config_manager, None, file_manager)
        
        # 支持的语言
        self.supported_languages = config_manager.get_supported_languages()
        
        self.logger.info("Content pipeline initialized with all components")
    
    async def generate_content_async(self, request: ContentGenerationRequest) -> ContentGenerationResult:
        """
        异步内容生成流水线
        
        Args:
            request: 内容生成请求
        
        Returns:
            ContentGenerationResult: 生成结果
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting content generation pipeline: {request.language}/{request.theme[:20]}...")
            
            # 步骤1：生成文案
            script_request = ScriptGenerationRequest(
                theme=request.theme,
                language=request.language,
                style=request.style,
                target_length=request.target_length
            )
            
            self.logger.info("Step 1: Generating script...")
            script_result = await self.script_generator.generate_script_async(script_request)
            
            # 步骤2和3：并行执行场景分割和角色分析
            self.logger.info("Step 2&3: Splitting scenes and analyzing characters...")
            
            # 场景分割请求 - 使用Coze工作流规则
            scene_request = SceneSplitRequest(
                script_content=script_result.content,
                language=request.language,
                use_coze_rules=False,  # 强制使用LLM生成具体图像提示词，不使用fallback
                target_scene_count=request.target_scene_count,
                scene_duration=request.scene_duration
            )
            
            # 角色分析请求
            character_request = CharacterAnalysisRequest(
                script_content=script_result.content,
                language=request.language,
                max_characters=request.max_characters
            )
            
            # 并行执行
            scene_task = self.scene_splitter.split_scenes_async(scene_request)
            character_task = self.character_analyzer.analyze_characters_async(character_request)
            
            scene_result, character_result = await asyncio.gather(scene_task, character_task)
            
            # 创建结果对象
            total_time = time.time() - start_time
            result = ContentGenerationResult(
                script=script_result,
                scenes=scene_result,
                characters=character_result,
                total_processing_time=total_time,
                request=request
            )
            
            self.logger.info(f"Content generation completed in {total_time:.2f}s")
            self.logger.info(f"Generated: {script_result.word_count} chars, {len(scene_result.scenes)} scenes, {len(character_result.characters)} characters")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Content generation pipeline failed after {processing_time:.2f}s: {e}")
            raise
    
    def generate_content_sync(self, request: ContentGenerationRequest) -> ContentGenerationResult:
        """
        同步内容生成流水线（对异步方法的包装）
        
        Args:
            request: 内容生成请求
        
        Returns:
            ContentGenerationResult: 生成结果
        """
        return asyncio.run(self.generate_content_async(request))
    
    async def batch_generate_content(self, requests: List[ContentGenerationRequest], 
                                   max_concurrent: int = 2) -> List[ContentGenerationResult]:
        """
        批量内容生成
        
        Args:
            requests: 内容生成请求列表
            max_concurrent: 最大并发数
        
        Returns:
            List[ContentGenerationResult]: 生成结果列表
        """
        self.logger.info(f"Starting batch content generation: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(request: ContentGenerationRequest) -> ContentGenerationResult:
            async with semaphore:
                return await self.generate_content_async(request)
        
        # 执行并发生成
        tasks = [generate_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch content generation failed for request {i}: {result}")
                failed_count += 1
            else:
                successful_results.append(result)
        
        self.logger.info(f"Batch content generation completed: {len(successful_results)} successful, {failed_count} failed")
        
        return successful_results
    
    def save_complete_content(self, result: ContentGenerationResult, output_dir: Optional[str] = None) -> Dict[str, str]:
        """
        保存完整的内容生成结果
        
        Args:
            result: 内容生成结果
            output_dir: 输出目录（可选）
        
        Returns:
            Dict[str, str]: 保存的文件路径
        """
        saved_files = {}
        
        try:
            # 保存文案
            script_path = self.script_generator.save_script(result.script, output_dir)
            saved_files['script'] = script_path
            
            # 保存场景
            scenes_path = self.scene_splitter.save_scenes(result.scenes, output_dir)
            saved_files['scenes'] = scenes_path
            
            # 保存角色
            characters_path = self.character_analyzer.save_characters(result.characters, output_dir)
            saved_files['characters'] = characters_path
            
            # 保存完整结果摘要
            if not output_dir:
                summary_filename = self.file_manager.generate_filename(
                    content=result.script.content,
                    prefix=f"content_summary_{result.request.language}",
                    extension="json"
                )
                summary_path = self.file_manager.get_output_path('scripts', summary_filename)
            else:
                summary_path = Path(output_dir) / f"content_summary_{result.request.language}_{int(time.time())}.json"
            
            summary_data = {
                'metadata': {
                    'theme': result.request.theme,
                    'language': result.request.language,
                    'style': result.request.style,
                    'total_processing_time': result.total_processing_time,
                    'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
                },
                'script_info': {
                    'title': result.script.title,
                    'word_count': result.script.word_count,
                    'generation_time': result.script.generation_time
                },
                'scenes_info': {
                    'scene_count': len(result.scenes.scenes),
                    'total_duration': result.scenes.total_duration,
                    'split_time': result.scenes.split_time
                },
                'characters_info': {
                    'character_count': len(result.characters.characters),
                    'main_character': result.characters.main_character.name if result.characters.main_character else None,
                    'analysis_time': result.characters.analysis_time
                },
                'file_paths': saved_files
            }
            
            success = self.file_manager.save_json(summary_data, summary_path)
            if success:
                saved_files['summary'] = str(summary_path)
                self.logger.info(f"Saved complete content to {len(saved_files)} files")
            
            return saved_files
            
        except Exception as e:
            self.logger.error(f"Failed to save complete content: {e}")
            return saved_files
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """获取流水线统计信息"""
        return {
            'supported_languages': self.supported_languages,
            'components': {
                'script_generator': self.script_generator.get_generation_stats(),
                'scene_splitter': self.scene_splitter.get_splitting_stats(),
                'character_analyzer': self.character_analyzer.get_analysis_stats()
            },
            # 缓存已删除
        }
    
    def validate_request(self, request: ContentGenerationRequest) -> List[str]:
        """
        验证内容生成请求
        
        Args:
            request: 内容生成请求
        
        Returns:
            List[str]: 验证错误列表
        """
        errors = []
        
        if not request.theme:
            errors.append("Theme is required")
        
        if request.language not in self.supported_languages:
            errors.append(f"Unsupported language: {request.language}")
        
        if request.target_length <= 0:
            errors.append("Target length must be positive")
        
        if request.target_scene_count <= 0:
            errors.append("Target scene count must be positive")
        
        if request.scene_duration <= 0:
            errors.append("Scene duration must be positive")
        
        if request.max_characters <= 0:
            errors.append("Max characters must be positive")
        
        return errors
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ContentPipeline(languages={self.supported_languages})"