"""
主角图像生成器 - 双重图像系统的核心组件
基于原Coze工作流的主角图像生成和抠图处理
"""
import asyncio
import time
import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from .image_generator import ImageGenerator, ImageGenerationRequest, GeneratedImage
from .cutout_processor import CutoutProcessor, CutoutRequest, CutoutResult

@dataclass
class CharacterImageRequest:
    """主角图像生成请求"""
    story_content: str          # 故事内容
    language: str              # 语言代码
    style: str = "ancient"     # 图像风格
    
@dataclass
class CharacterImageResult:
    """主角图像生成结果"""
    success: bool                      # 是否成功
    original_image: Optional[GeneratedImage]  # 原始主角图像
    cutout_result: Optional[CutoutResult]     # 抠图结果
    character_description: str         # 主角描述
    generation_time: float            # 总生成时间
    error_message: str = ""           # 错误信息

class CharacterImageGenerator:
    """
    主角图像生成器
    
    实现原Coze工作流的主角图像生成机制：
    1. 分析故事内容，提取主角特征
    2. 生成主角图像（背景留白，人物居中）
    3. 智能抠图处理，生成透明背景PNG
    4. 返回可复用的主角图像资源
    """
    
    def __init__(self, config_manager: ConfigManager, file_manager: FileManager):
        """初始化主角图像生成器"""
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.media')
        
        # 初始化依赖组件
        self.image_generator = ImageGenerator(config_manager, file_manager)
        self.cutout_processor = CutoutProcessor(config_manager, file_manager)
        
        # 支持的语言
        self.supported_languages = config_manager.get_supported_languages()
        
        # 主角特征提取模板
        self._load_character_templates()
        
        self.logger.info("CharacterImageGenerator initialized with image generation and cutout processing")
    
    def _load_character_templates(self):
        """加载主角特征提取模板"""
        self.character_templates = {
            'zh': {
                'historical_figures': {
                    '秦始皇': 'Emperor Qin Shi Huang wearing black dragon robe with golden embroidery',
                    '嬴政': 'Emperor Qin Shi Huang wearing imperial black robes with dragon patterns',
                    '朱元璋': 'Emperor Zhu Yuanzhang in Ming dynasty imperial robes',
                    '汉武帝': 'Emperor Wu of Han in ancient Chinese imperial clothing',
                    '唐太宗': 'Emperor Taizong in Tang dynasty royal attire',
                    '康熙': 'Emperor Kangxi in Qing dynasty imperial robes',
                    '乾隆': 'Emperor Qianlong in elaborate Qing imperial dress',
                    '武则天': 'Empress Wu Zetian in ornate Tang dynasty empress robes',
                    '李世民': 'Emperor Li Shimin in Tang imperial military armor',
                    '刘邦': 'Emperor Liu Bang in early Han dynasty robes',
                    '项羽': 'Xiang Yu in ancient Chinese military armor with cape'
                },
                'default_style': 'ancient Chinese emperor wearing traditional imperial robes',
                'clothing_keywords': ['龙袍', '铠甲', '官服', '战甲', '皇袍'],
                'period_keywords': ['秦朝', '汉朝', '唐朝', '宋朝', '明朝', '清朝', '春秋', '战国']
            },
            'en': {
                'historical_figures': {
                    'Emperor': 'Ancient Chinese emperor in traditional imperial robes',
                    'General': 'Ancient Chinese general in military armor',
                    'Scholar': 'Ancient Chinese scholar in traditional robes',
                    'Warrior': 'Ancient Chinese warrior in battle armor'
                },
                'default_style': 'ancient Chinese historical figure in traditional clothing',
                'clothing_keywords': ['robe', 'armor', 'imperial', 'military', 'traditional'],
                'period_keywords': ['ancient', 'dynasty', 'imperial', 'traditional', 'historical']
            }
        }
    
    async def generate_character_image_async(self, request: CharacterImageRequest) -> CharacterImageResult:
        """
        异步生成主角图像
        
        Args:
            request: 主角图像生成请求
        
        Returns:
            CharacterImageResult: 生成结果
        """
        start_time = time.time()
        
        try:
            # 暂时禁用主角图像缓存，因为需要每次生成新的抠图
            # 主角图像通常不会频繁重复使用，而抠图结果需要实时处理
            # cache_key = self.cache.get_cache_key({
            #     'story_content': request.story_content,
            #     'language': request.language,
            #     'style': request.style
            # })
            # 
            # cached_result = self.cache.get('character_images', cache_key)
            # if cached_result:
            #     self.logger.info(f"Cache hit for character image")
            #     cached_result['generation_time'] = time.time() - start_time
            #     return CharacterImageResult(**cached_result)
            
            # 步骤1: 分析主角特征
            character_description = self._analyze_character(request.story_content, request.language)
            self.logger.info(f"Character analysis completed: {character_description[:100]}...")
            
            # 步骤2: 生成主角图像提示词
            character_prompt = self._generate_character_prompt(character_description, request.style)
            self.logger.info(f"Character prompt generated: {character_prompt[:100]}...")
            
            # 步骤3: 生成原始主角图像
            image_request = ImageGenerationRequest(
                prompt=character_prompt,
                style="portrait",  # 使用肖像风格
                width=512,  # 适合抠图的尺寸
                height=512
            )
            
            original_image = await self.image_generator.generate_image_async(image_request)
            # 图像生成器在失败时会抛出异常，成功时返回GeneratedImage对象
            
            self.logger.info(f"Original character image generated: {original_image.file_path}")
            
            # 步骤4: 抠图处理（使用已测试成功的配置）
            # 注意：抠图API需要网络可访问的URL，不能使用本地文件路径
            # 如果原始图像有remote_url，使用remote_url；否则跳过抠图
            cutout_result = None
            if original_image.remote_url:
                self.logger.info(f"Using remote URL for cutout: {original_image.remote_url}")
                cutout_request = CutoutRequest(
                    image_url=original_image.remote_url  # 使用远程URL
                )
                
                cutout_result = await self.cutout_processor.process_cutout_async(cutout_request)
                if not cutout_result.success:
                    self.logger.warning(f"Cutout processing failed: {cutout_result.error_message}")
                    # 抠图失败不算致命错误，仍然可以使用原图
                else:
                    self.logger.info(f"Cutout processing completed: {cutout_result.local_file_path}")
            else:
                self.logger.info(f"Skipping cutout processing: no remote URL available (provider: {original_image.provider})")
            
            # 创建结果对象
            result = CharacterImageResult(
                success=True,
                original_image=original_image,
                cutout_result=cutout_result if cutout_result and cutout_result.success else None,
                character_description=character_description,
                generation_time=time.time() - start_time
            )
            
            # 暂时禁用缓存，确保每次都能执行完整的图像生成和抠图流程
            # cache_data = {
            #     'success': result.success,
            #     'original_image': None,  # 不缓存具体图像对象
            #     'cutout_result': None,   # 不缓存具体抠图对象
            #     'character_description': result.character_description
            # }
            # self.cache.set('character_images', cache_key, cache_data)
            
            self.logger.info(f"Character image generation completed: {result.generation_time:.2f}s")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Character image generation failed: {e}"
            self.logger.error(error_msg)
            
            return CharacterImageResult(
                success=False,
                original_image=None,
                cutout_result=None,
                character_description="",
                generation_time=processing_time,
                error_message=error_msg
            )
    
    def _analyze_character(self, story_content: str, language: str) -> str:
        """
        分析故事内容，提取主角特征
        
        Args:
            story_content: 故事内容
            language: 语言代码
        
        Returns:
            str: 主角特征描述
        """
        template = self.character_templates.get(language, self.character_templates['zh'])
        
        # 查找明确的历史人物
        for figure_name, description in template['historical_figures'].items():
            if figure_name in story_content:
                self.logger.debug(f"Found historical figure: {figure_name}")
                return description
        
        # 分析时代背景
        period_info = ""
        for period in template['period_keywords']:
            if period in story_content:
                period_info = period
                break
        
        # 分析服装描述
        clothing_info = ""
        for clothing in template['clothing_keywords']:
            if clothing in story_content:
                clothing_info = clothing
                break
        
        # 组合描述
        if period_info and clothing_info:
            if language == 'zh':
                return f"Ancient Chinese {period_info} period character wearing {clothing_info}, traditional historical style"
            else:
                return f"Ancient {period_info} character in {clothing_info}, historical style"
        elif period_info:
            if language == 'zh':
                return f"Ancient Chinese {period_info} period character in traditional clothing"
            else:
                return f"Ancient {period_info} historical figure in traditional attire"
        else:
            return template['default_style']
    
    def _generate_character_prompt(self, character_description: str, style: str) -> str:
        """
        生成主角图像提示词
        
        基于原Coze工作流的要求：
        - 只出现一个人物
        - 背景留白
        - 正对屏幕，人物居中
        
        Args:
            character_description: 主角特征描述
            style: 图像风格
        
        Returns:
            str: 图像生成提示词
        """
        # 基础人物描述
        base_prompt = character_description
        
        # 构图要求（按原工作流规范）
        composition_requirements = [
            "single character only",           # 只有一个人物
            "facing forward",                  # 正对屏幕
            "centered composition",            # 人物居中
            "white background",                # 白色背景
            "clean background",                # 干净背景
            "portrait style",                  # 肖像风格
            "high quality",                    # 高质量
            "detailed character design"       # 详细人物设计
        ]
        
        # 风格要求
        style_requirements = []
        if style == "ancient":
            style_requirements.extend([
                "ancient Chinese art style",
                "traditional painting style",
                "historical accuracy",
                "dignified pose"
            ])
        elif style == "realistic":
            style_requirements.extend([
                "photorealistic",
                "detailed facial features",
                "realistic lighting"
            ])
        
        # 组合完整提示词
        full_prompt = f"{base_prompt}, {', '.join(composition_requirements)}"
        if style_requirements:
            full_prompt += f", {', '.join(style_requirements)}"
        
        # 添加负向提示词
        negative_elements = [
            "multiple people",
            "crowd",
            "complex background",
            "busy scene",
            "blurry",
            "low quality"
        ]
        
        full_prompt += f". Avoid: {', '.join(negative_elements)}"
        
        return full_prompt
    
    def generate_character_image_sync(self, request: CharacterImageRequest) -> CharacterImageResult:
        """
        同步生成主角图像（对异步方法的包装）
        
        Args:
            request: 主角图像生成请求
        
        Returns:
            CharacterImageResult: 生成结果
        """
        return asyncio.run(self.generate_character_image_async(request))
    
    async def batch_generate_character_images(self, requests: List[CharacterImageRequest], 
                                            max_concurrent: int = 1) -> List[CharacterImageResult]:
        """
        批量生成主角图像
        
        注意：主角图像通常每个故事只需要一张，批量生成用于多个故事的场景
        
        Args:
            requests: 生成请求列表
            max_concurrent: 最大并发数（建议设为1，避免API限流）
        
        Returns:
            List[CharacterImageResult]: 生成结果列表
        """
        self.logger.info(f"Starting batch character image generation: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(request: CharacterImageRequest) -> CharacterImageResult:
            async with semaphore:
                return await self.generate_character_image_async(request)
        
        # 执行并发生成
        tasks = [generate_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch character image generation failed for request {i}: {result}")
                failed_count += 1
                # 创建失败结果
                failed_result = CharacterImageResult(
                    success=False,
                    original_image=None,
                    cutout_result=None,
                    character_description="",
                    generation_time=0.0,
                    error_message=str(result)
                )
                successful_results.append(failed_result)
            else:
                successful_results.append(result)
        
        self.logger.info(f"Batch character image generation completed: {len(successful_results) - failed_count} successful, {failed_count} failed")
        
        return successful_results
    
    def get_character_generation_stats(self) -> Dict[str, Any]:
        """获取主角图像生成统计信息"""
        cache_stats = self.cache.get_cache_stats()
        image_stats = self.image_generator.get_generation_stats()
        cutout_stats = self.cutout_processor.get_cutout_stats()
        
        return {
            'supported_languages': self.supported_languages,
            'cache_stats': cache_stats.get('disk_cache', {}).get('character_images', {}),
            'image_generation_stats': image_stats,
            'cutout_processing_stats': cutout_stats,
            'available_templates': list(self.character_templates.keys())
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"CharacterImageGenerator(languages={self.supported_languages})"