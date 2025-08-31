"""
图像提示词生成器 - 基于原Coze工作流Node_186126的完整逻辑
对应原工作流Node_186126配置
"""
import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging
import openai
from dataclasses import dataclass

from core.config_manager import ConfigManager, ModelConfig
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from utils.llm_client_manager import LLMClientManager
from .scene_splitter import Scene

@dataclass
class ImagePromptRequest:
    """图像提示词生成请求"""
    scenes: List[Scene]      # 场景列表（包含cap字幕文案）
    language: str           # 语言代码
    style: str = "ancient_horror"  # 视觉风格

@dataclass
class ImagePromptResult:
    """图像提示词生成结果"""
    scenes: List[Scene]      # 更新后的场景列表（包含image_prompt）
    language: str           # 语言
    generation_time: float  # 生成耗时
    model_used: str         # 使用的模型

class ImagePromptGenerator:
    """
    图像提示词生成器
    
    基于原Coze工作流Node_186126配置：
    - 模型: DeepSeek-V3-0324
    - Temperature: 1.0
    - Max tokens: 16384
    - 为每个分镜生成详细的图像绘画提示词
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 cache_manager: CacheManager, file_manager: FileManager):
        self.config = config_manager
        self.cache = cache_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.content')
        
        # 支持的语言
        self.supported_languages = self.config.get_supported_languages()
        
        # 获取LLM配置 - 使用专门的图像提示词生成配置
        self.llm_config = self.config.get_llm_config('image_prompt_generation')
        
        # 初始化多提供商LLM客户端管理器
        self.llm_manager = LLMClientManager(config_manager)
        
        self.logger.info("Image prompt generator initialized")
    
    
    async def generate_image_prompts_async(self, request: ImagePromptRequest) -> ImagePromptResult:
        """
        异步生成图像提示词
        
        Args:
            request: 图像提示词生成请求
        
        Returns:
            ImagePromptResult: 生成结果
        """
        start_time = time.time()
        
        try:
            # 检查缓存
            cache_key_data = {
                'scenes_content': [scene.content for scene in request.scenes],
                'language': request.language,
                'style': request.style
            }
            
            cache_key = self.cache.get_cache_key(cache_key_data)
            
            cached_result = self.cache.get('image_prompts', cache_key)
            if cached_result:
                self.logger.info(f"Cache hit for image prompt generation: {request.language}")
                cached_result['generation_time'] = time.time() - start_time
                # 重构Scene对象
                scenes = [Scene(**scene_data) for scene_data in cached_result['scenes']]
                cached_result['scenes'] = scenes
                return ImagePromptResult(**cached_result)
            
            # 验证请求
            if request.language not in self.supported_languages:
                raise ValueError(f"Unsupported language: {request.language}")
            
            # 构建提示词 - 基于原工作流Node_186126
            prompt = self._build_image_prompt_generation_prompt(request)
            
            # 调用LLM API
            self.logger.info(f"Generating image prompts for {len(request.scenes)} scenes...")
            
            response = await self._call_llm_api(prompt)
            
            if not response:
                raise ValueError("Empty response from LLM")
            
            # 解析响应
            updated_scenes = self._parse_image_prompt_response(response, request.scenes)
            
            # 创建结果对象
            result = ImagePromptResult(
                scenes=updated_scenes,
                language=request.language,
                generation_time=time.time() - start_time,
                model_used=self.llm_config.name
            )
            
            # 缓存结果
            cache_data = {
                'scenes': [self._scene_to_dict(scene) for scene in updated_scenes],
                'language': result.language,
                'model_used': result.model_used
            }
            
            self.cache.set('image_prompts', cache_key, cache_data)
            
            # 记录日志
            logger = self.config.get_logger('story_generator')
            logger.info(f"Content generation - Type: image_prompt_generation, Language: {request.language}, "
                       f"Scenes: {len(request.scenes)}, Time: {result.generation_time:.2f}s")
            
            self.logger.info(f"Generated image prompts successfully for {len(updated_scenes)} scenes in {result.generation_time:.2f}s")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Image prompt generation failed: {e}")
            
            # 记录错误日志
            logger = self.config.get_logger('story_generator')
            logger.error(f"Content generation failed - Type: image_prompt_generation, Language: {request.language}, "
                        f"Scenes: {len(request.scenes)}, Time: {processing_time:.2f}s")
            
            raise
    
    def _build_image_prompt_generation_prompt(self, request: ImagePromptRequest) -> str:
        """
        构建图像提示词生成提示词 - 基于原工作流Node_186126的System Prompt
        """
        # 准备场景数据
        scenes_json = []
        for scene in request.scenes:
            scenes_json.append({
                "cap": scene.content,
                "desc_promopt": ""  # 待填充
            })
        
        scenes_json_str = json.dumps(scenes_json, ensure_ascii=False, indent=2)
        
        # 基于原Coze工作流Node_186126的完整System Prompt
        system_prompt = """# 角色
根据分镜字幕cap生成绘画提示词desc_prompt。

## 技能
### 技能 1: 生成绘画提示
1. 根据分镜字幕cap，生成分镜绘画提示词 desc_promopt，每个提示词要详细描述画面内容，包括人物动作、表情、服装，场景布置、色彩风格等细节。
  - 风格要求：古代惊悚插画风格，颜色很深，黑暗中，黄昏，氛围凝重，庄严肃穆，构建出紧张氛围，古代服饰，古装，线条粗狂，清晰、人物特写，粗狂手笔，高清，高对比度，色彩低饱和，浅景深
  - 第一个分镜画面中不要出现人物，只需要一个画面背景
  - **重要：desc_promopt必须用英文生成，确保每个场景的描述都包含不同的细节、角度或元素，避免重复**
  - 每个场景必须有独特的视觉元素：
    * 不同的镜头角度 (close-up, wide shot, low-angle, bird's eye view等)
    * 不同的人物状态和表情
    * 不同的环境细节和背景元素
    * 不同的光影效果和色彩重点
    * 不同的构图和透视

===回复示例===
[
  {
    "cap": "字幕文案",
    "desc_promopt": "Ancient China, Qin Shi Huang in Xianyang Palace, wide establishing shot, wearing black dragon robe with golden embroidery, stern and contemplative expression, ornate throne room with red pillars, dim candlelight creating dramatic shadows, ancient horror style, high contrast, low saturation colors, shallow depth of field"
  }
]
===示例结束===

## 限制:
- 只对用户提供的json内容补充desc_prompt字段，不能更改原文
- 严格检查输出的json格式正确性并进行修正，特别注意json格式不要少括号，逗号等
- **确保每个desc_promopt都用英文生成，包含具体细节，并且彼此不同**
- 必须包含镜头角度、人物细节、环境描述、光影效果等多个维度的差异

现在请为以下场景生成详细的英文图像提示词：

"""

        return system_prompt + scenes_json_str
    
    async def _call_llm_api(self, prompt: str) -> str:
        """
        调用LLM API
        
        Args:
            prompt: 提示词
        
        Returns:
            str: LLM响应
        """
        try:
            content = await self.llm_manager.call_llm_with_fallback(
                prompt=prompt,
                task_type='image_prompt_generation',
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens
            )
            
            if not content:
                raise ValueError("Empty response from all LLM providers")
            
            return content.strip()
            
        except Exception as e:
            self.logger.error(f"LLM API call failed: {e}")
            raise
    
    def _parse_image_prompt_response(self, response: str, original_scenes: List[Scene]) -> List[Scene]:
        """
        解析图像提示词响应
        
        Args:
            response: LLM响应
            original_scenes: 原始场景列表
        
        Returns:
            List[Scene]: 更新后的场景列表
        """
        try:
            # 尝试提取JSON部分
            json_content = self._extract_json_from_response(response)
            
            if not json_content:
                raise ValueError("No valid JSON found in response")
            
            data = json.loads(json_content)
            
            if not isinstance(data, list):
                raise ValueError("Response should be a list of scene objects")
            
            updated_scenes = []
            
            for i, (original_scene, prompt_data) in enumerate(zip(original_scenes, data)):
                if not isinstance(prompt_data, dict):
                    raise ValueError(f"Scene {i+1} data should be an object")
                
                # 获取生成的英文提示词
                image_prompt = prompt_data.get('desc_promopt', '').strip()
                
                # 验证提示词质量
                if not image_prompt:
                    raise ValueError(f"Empty image prompt for scene {i+1}")
                
                if len(image_prompt) < 30:
                    raise ValueError(f"Image prompt too short for scene {i+1}: {image_prompt}")
                
                # 检查是否包含中文字符（应该是英文）
                if any(ord(char) > 127 for char in image_prompt):
                    self.logger.warning(f"Scene {i+1} image prompt contains non-ASCII characters: {image_prompt[:50]}...")
                
                # 创建更新后的场景
                updated_scene = Scene(
                    sequence=original_scene.sequence,
                    content=original_scene.content,
                    image_prompt=image_prompt,
                    duration_seconds=original_scene.duration_seconds,
                    animation_type=original_scene.animation_type,
                    subtitle_text=original_scene.subtitle_text
                )
                
                updated_scenes.append(updated_scene)
            
            # 检查是否所有场景都处理了
            if len(updated_scenes) != len(original_scenes):
                self.logger.warning(f"Mismatch: {len(original_scenes)} input scenes, {len(updated_scenes)} output scenes")
            
            # 检查重复提示词
            prompts = [scene.image_prompt for scene in updated_scenes]
            unique_prompts = set(prompts)
            if len(unique_prompts) < len(prompts):
                self.logger.warning(f"Found {len(prompts) - len(unique_prompts)} duplicate image prompts")
            
            return updated_scenes
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            # 尝试退化处理
            return self._fallback_image_prompt_generation(original_scenes)
        except Exception as e:
            self.logger.error(f"Image prompt parsing error: {e}")
            # 尝试退化处理
            return self._fallback_image_prompt_generation(original_scenes)
    
    def _extract_json_from_response(self, response: str) -> Optional[str]:
        """从响应中提取JSON内容"""
        import re
        
        # 查找```json...```格式
        json_match = re.search(r'```json\s*\n?(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
        if json_match:
            return json_match.group(1).strip()
        
        # 查找```...```格式（可能没有标明json）
        code_match = re.search(r'```\s*\n?(.*?)\n?```', response, re.DOTALL)
        if code_match:
            content = code_match.group(1).strip()
            if content.startswith('[') and content.endswith(']'):
                return content
        
        # 查找直接的JSON数组
        json_array_match = re.search(r'(\[.*?\])', response, re.DOTALL)
        if json_array_match:
            return json_array_match.group(1)
        
        # 最后尝试简单的方括号匹配
        start_pos = response.find('[')
        if start_pos != -1:
            bracket_count = 0
            for i, char in enumerate(response[start_pos:], start_pos):
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        return response[start_pos:i+1]
        
        return None
    
    def _fallback_image_prompt_generation(self, original_scenes: List[Scene]) -> List[Scene]:
        """
        退化的图像提示词生成（当LLM失败时）
        
        Args:
            original_scenes: 原始场景列表
        
        Returns:
            List[Scene]: 更新后的场景列表
        """
        self.logger.warning("Using fallback image prompt generation")
        
        # 预定义的多样化提示词模板
        prompt_templates = [
            "Ancient China, close-up portrait, Emperor Qin Shi Huang wearing black dragon robe, stern expression, palace interior with ornate decorations, dramatic lighting, ancient horror style, high contrast, low saturation",
            "Ancient China, wide establishing shot, imperial palace courtyard, traditional architecture with red pillars, misty atmosphere, soldiers in formation, ancient horror style, dim colors, high definition",
            "Ancient China, low-angle dramatic shot, ancient Chinese general in armor, battlefield background, war banners flying, dusty atmosphere, ancient horror style, rough lines, shallow depth of field",
            "Ancient China, bird's eye view, ancient city walls and fortifications, surrounding landscape, twilight sky, ancient horror atmosphere, high contrast, traditional elements",
            "Ancient China, over-the-shoulder view, scholar or advisor character, ancient library or study room, scrolls and books, candlelight, ancient horror style, low saturation colors",
            "Ancient China, three-quarter view, imperial court scene, officials in traditional robes, throne room setting, ceremonial atmosphere, ancient horror style, solemn mood",
            "Ancient China, side profile shot, warrior character in battle armor, weapon in hand, ancient battlefield, smoke and dust, ancient horror style, dramatic shadows",
            "Ancient China, back view silhouette, figure against ancient architecture, sunset or dawn lighting, majestic landscape, ancient horror atmosphere, high definition"
        ]
        
        updated_scenes = []
        
        for i, scene in enumerate(original_scenes):
            # 循环使用不同的模板确保多样性
            template_index = i % len(prompt_templates)
            image_prompt = prompt_templates[template_index]
            
            updated_scene = Scene(
                sequence=scene.sequence,
                content=scene.content,
                image_prompt=image_prompt,
                duration_seconds=scene.duration_seconds,
                animation_type=scene.animation_type,
                subtitle_text=scene.subtitle_text
            )
            
            updated_scenes.append(updated_scene)
        
        return updated_scenes
    
    def _scene_to_dict(self, scene: Scene) -> Dict[str, Any]:
        """将Scene对象转换为字典"""
        return {
            'sequence': scene.sequence,
            'content': scene.content,
            'image_prompt': scene.image_prompt,
            'duration_seconds': scene.duration_seconds,
            'animation_type': scene.animation_type,
            'subtitle_text': scene.subtitle_text
        }
    
    def generate_image_prompts_sync(self, request: ImagePromptRequest) -> ImagePromptResult:
        """
        同步生成图像提示词（对异步方法的包装）
        
        Args:
            request: 图像提示词生成请求
        
        Returns:
            ImagePromptResult: 生成结果
        """
        return asyncio.run(self.generate_image_prompts_async(request))
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """获取生成统计信息"""
        cache_stats = self.cache.get_cache_stats()
        
        return {
            'supported_languages': self.supported_languages,
            'cache_stats': cache_stats.get('disk_cache', {}).get('image_prompts', {}),
            'model_config': {
                'name': self.llm_config.name,
                'temperature': self.llm_config.temperature,
                'max_tokens': self.llm_config.max_tokens
            }
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ImagePromptGenerator(model={self.llm_config.name}, languages={self.supported_languages})"