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
from dataclasses import dataclass

from core.config_manager import ConfigManager, ModelConfig
from utils.file_manager import FileManager
from utils.enhanced_llm_manager import EnhancedLLMManager
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
                 file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.content')
        
        # 支持的语言
        self.supported_languages = self.config.get_supported_languages()
        
        # 获取LLM配置 - 使用专门的图像提示词生成配置
        self.llm_config = self.config.get_llm_config('image_prompt_generation')
        
        # 初始化多提供商LLM客户端管理器
        self.llm_manager = EnhancedLLMManager(config_manager)
        self.logger.info("✅ 使用增强LLM管理器 (统一架构)")
        
        # 加载提示词模板
        self._load_prompt_templates()
        
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
            # 缓存已禁用 - 每次都生成新内容
            
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
            
            # 缓存已禁用
            
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
        构建图像提示词生成提示词 - 使用模板文件
        """
        # 准备场景数据
        scenes_json = []
        for scene in request.scenes:
            scenes_json.append({
                "cap": scene.content,
                "image_prompt": "",  # 待填充，使用新的标准字段名
                "video_prompt": ""   # 待填充
            })
        
        scenes_json_str = json.dumps(scenes_json, ensure_ascii=False, indent=2)
        
        # 使用模板文件
        language = request.language
        if language in self.prompt_templates:
            system_prompt = self.prompt_templates[language]
        else:
            # 使用中文作为后备
            system_prompt = self.prompt_templates.get('zh', '')
            self.logger.warning(f"No image prompt template for language {language}, using Chinese as fallback")

        # 替换模板中的占位符
        prompt = system_prompt.replace("{{scenes}}", scenes_json_str)
        
        return prompt
    
    def _split_prompt(self, full_prompt: str) -> tuple[str, str]:
        """
        分离系统提示词和用户提示词
        
        Args:
            full_prompt: 完整提示词
            
        Returns:
            tuple: (system_prompt, user_prompt)
        """
        # 查找JSON场景数据的开始位置
        json_start = full_prompt.find('[')
        if json_start == -1:
            # 如果没有找到JSON，将整个内容作为用户提示词
            return "你是专业的图像提示词生成专家。", full_prompt
        
        system_part = full_prompt[:json_start].strip()
        user_part = full_prompt[json_start:].strip()
        
        if not system_part:
            system_part = "你是专业的图像提示词生成专家。"
            
        return system_part, user_part

    async def _call_llm_api(self, prompt: str) -> str:
        """
        调用LLM API
        
        Args:
            prompt: 提示词
        
        Returns:
            str: LLM响应
        """
        try:
            # 尝试使用结构化输出
            try:
                # 分离系统提示词和用户提示词
                system_prompt, user_prompt = self._split_prompt(prompt)
                
                structured_output = await self.llm_manager.generate_structured_output(
                    task_type='image_prompt_generation',
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_retries=2
                )
                
                if hasattr(structured_output, 'scenes') and structured_output.scenes:
                    # 直接返回结构化内容，让后续处理逻辑处理
                    content = self._convert_structured_to_json(structured_output.scenes)
                    self.logger.info(f"✅ Structured image prompt generation successful: {len(structured_output.scenes)} scenes")
                else:
                    # 降级到原有方法
                    content = str(structured_output)
                    
            except Exception as e:
                self.logger.warning(f"🔄 Structured output failed, falling back to regular parsing: {e}")
                
                # 降级到原有方法
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
    
    def _convert_structured_to_json(self, scenes_data) -> str:
        """将结构化输出转换为JSON字符串"""
        import json
        
        scenes_list = []
        for scene_data in scenes_data:
            scene_dict = {
                "cap": getattr(scene_data, 'content', ''),  # 兼容原有字段名
                "image_prompt": getattr(scene_data, 'image_prompt', ''),  # 使用新的标准字段名
                "video_prompt": getattr(scene_data, 'video_prompt', '')
            }
            scenes_list.append(scene_dict)
        
        return json.dumps(scenes_list, ensure_ascii=False, indent=2)
    
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
                
                # 获取生成的英文提示词 - 支持多种字段名(新旧兼容)
                image_prompt = prompt_data.get('image_prompt', 
                                             prompt_data.get('desc_prompt', 
                                                           prompt_data.get('desc_promopt', ''))).strip()
                
                # 获取视频提示词
                video_prompt = prompt_data.get('video_prompt', '').strip()
                
                # 验证图像提示词质量
                if not image_prompt:
                    raise ValueError(f"Empty image prompt for scene {i+1}")
                
                if len(image_prompt) < 30:
                    raise ValueError(f"Image prompt too short for scene {i+1}: {image_prompt}")
                
                # 验证视频提示词（如果存在）
                if video_prompt and len(video_prompt) < 10:
                    self.logger.warning(f"Scene {i+1} video prompt might be too short: {video_prompt}")
                
                # 检查是否包含中文字符（应该是英文）
                if any(ord(char) > 127 for char in image_prompt):
                    self.logger.warning(f"Scene {i+1} image prompt contains non-ASCII characters: {image_prompt[:50]}...")
                
                # 创建更新后的场景
                updated_scene = Scene(
                    sequence=original_scene.sequence,
                    content=original_scene.content,
                    image_prompt=image_prompt,
                    video_prompt=video_prompt if video_prompt else getattr(original_scene, 'video_prompt', ''),  # 使用新生成的video_prompt
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
            self.logger.error(f"Raw LLM response that caused JSON error: {response[:1000]}...")
            raise ValueError(f"LLM returned invalid JSON format: {e}")
        except Exception as e:
            self.logger.error(f"Image prompt parsing error: {e}")
            self.logger.error(f"Raw LLM response: {response[:1000]}...")
            raise
    
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
    
    # FALLBACK LOGIC REMOVED - 不再使用退化逻辑掩盖问题
    
    def _scene_to_dict(self, scene: Scene) -> Dict[str, Any]:
        """将Scene对象转换为字典"""
        return {
            'sequence': scene.sequence,
            'content': scene.content,
            'image_prompt': scene.image_prompt,
            'video_prompt': getattr(scene, 'video_prompt', ''),
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
        return {
            'supported_languages': self.supported_languages,
            # 缓存已删除
            'model_config': {
                'name': self.llm_config.name,
                'temperature': self.llm_config.temperature,
                'max_tokens': self.llm_config.max_tokens
            }
        }
    
    def _load_prompt_templates(self):
        """加载提示词模板"""
        self.prompt_templates = {}
        prompts_dir = Path("config/prompts")
        
        for lang in self.supported_languages:
            lang_dir = prompts_dir / lang
            template_file = lang_dir / "image_prompt_generation.txt"
            
            if template_file.exists():
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        self.prompt_templates[lang] = f.read().strip()
                    self.logger.debug(f"Loaded image prompt template for language: {lang}")
                except Exception as e:
                    self.logger.warning(f"Failed to load image prompt template for {lang}: {e}")
            else:
                self.logger.warning(f"Image prompt template not found: {template_file}")
        
        self.logger.info(f"Loaded {len(self.prompt_templates)} image prompt templates")

    def __str__(self) -> str:
        """字符串表示"""
        return f"ImagePromptGenerator(model={self.llm_config.name}, languages={self.supported_languages})"