"""
场景分割器 - 将文案分割为多个场景分镜
对应原工作流Node_1165778配置
"""
import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass

from core.config_manager import ConfigManager, ModelConfig
from utils.file_manager import FileManager
from utils.enhanced_llm_manager import EnhancedLLMManager

@dataclass
class Scene:
    """单个场景"""
    sequence: int              # 场景序号
    content: str              # 场景内容文本
    image_prompt: str         # 图像提示词 (文生图用)
    video_prompt: str         # 视频提示词 (图生视频用)
    duration_seconds: float   # 时长（秒）
    animation_type: str       # 动画类型
    subtitle_text: str        # 字幕文本
    
@dataclass
class SceneSplitRequest:
    """场景分割请求"""
    script_content: str       # 原始文案内容
    language: str            # 语言代码
    use_coze_rules: bool = True  # 使用原Coze工作流分割规则
    target_scene_count: int = 8  # 目标场景数量（仅在use_coze_rules=False时使用）
    scene_duration: float = 3.0  # 每个场景时长（秒）

@dataclass
class SceneSplitResult:
    """场景分割结果"""
    scenes: List[Scene]       # 场景列表
    total_duration: float     # 总时长
    language: str            # 语言
    original_script: str     # 原始文案
    split_time: float        # 分割耗时
    model_used: str          # 使用的模型

class SceneSplitter:
    """
    场景分割器
    
    基于原Coze工作流Node_1165778配置：
    - 模型: DeepSeek-V3
    - Temperature: 0.8
    - Max tokens: 8192
    - 将文案分割为8个场景，每个场景3秒
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.content')
        
        # 支持的语言 - 必须在加载提示词模板之前设置
        self.supported_languages = self.config.get_supported_languages()
        
        # 获取LLM配置
        self.llm_config = self.config.get_llm_config('scene_splitting')
        
        # 图像提示词生成器（延迟初始化避免循环导入）
        self._image_prompt_generator = None
        
        # 使用统一的增强LLM管理器
        self.llm_manager = EnhancedLLMManager(config_manager)
        self.logger.info("✅ 使用增强LLM管理器 (统一架构)")
        
        # 加载提示词模板
        self._load_prompt_templates()
    
    
    def _get_image_prompt_generator(self):
        """延迟初始化图像提示词生成器"""
        if self._image_prompt_generator is None:
            from .image_prompt_generator import ImagePromptGenerator
            self._image_prompt_generator = ImagePromptGenerator(
                self.config, self.file_manager
            )
            self.logger.info("Initialized image prompt generator")
        return self._image_prompt_generator
    
    async def _generate_image_prompts_for_scenes(self, scenes: List[Scene], request: SceneSplitRequest) -> List[Scene]:
        """
        使用专门的图像提示词生成器为场景生成高质量图像提示词
        
        Args:
            scenes: 原始场景列表
            request: 场景分割请求
        
        Returns:
            List[Scene]: 更新后的场景列表
        """
        try:
            # 获取图像提示词生成器
            image_prompt_generator = self._get_image_prompt_generator()
            
            # 创建图像提示词生成请求
            from .image_prompt_generator import ImagePromptRequest
            prompt_request = ImagePromptRequest(
                scenes=scenes,
                language=request.language,
                style="ancient_horror"
            )
            
            # 使用LLM生成图像提示词
            self.logger.info(f"Generating image prompts for {len(scenes)} scenes using LLM...")
            prompt_result = await image_prompt_generator.generate_image_prompts_async(prompt_request)
            
            self.logger.info(f"Successfully generated {len(prompt_result.scenes)} image prompts in {prompt_result.generation_time:.2f}s")
            
            return prompt_result.scenes
            
        except Exception as e:
            self.logger.error(f"Failed to generate image prompts using LLM: {e}")
            # 不再使用fallback机制，直接抛出异常以暴露问题
            raise Exception(f"LLM image prompt generation failed: {e}. No fallback methods provided.")
    
    def _load_prompt_templates(self):
        """加载提示词模板"""
        self.prompt_templates = {}
        prompts_dir = Path("config/prompts")
        
        for lang in self.supported_languages:
            lang_dir = prompts_dir / lang
            if lang_dir.exists():
                # 加载场景分割提示词
                scene_prompt_file = lang_dir / "scene_splitting.txt"
                if scene_prompt_file.exists():
                    try:
                        content = self.file_manager.load_text(scene_prompt_file)
                        if content:
                            self.prompt_templates[lang] = content
                            self.logger.debug(f"Loaded scene splitting prompt for language: {lang}")
                    except Exception as e:
                        self.logger.error(f"Failed to load scene splitting prompt for {lang}: {e}")
        
        if not self.prompt_templates:
            self.logger.warning("No scene splitting prompts loaded, using default templates")
            self._create_default_prompts()
    
    def _create_default_prompts(self):
        """创建默认提示词模板"""
        self.prompt_templates = {
            'zh': """# 角色
你是一个专业的视频分镜师，负责将历史故事文案分割为适合视频制作的多个场景。

## 技能
### 技能1：场景分割
1. 将输入的历史故事文案分割为8个独立场景
2. 每个场景应该包含完整的故事片段，时长约3秒
3. 为每个场景生成详细的英文图像描述提示词，必须包含具体的人物、服装、环境、动作等细节
4. 确保场景之间的连贯性和逻辑性
5. 生成适合的字幕文本

## 输出格式
请严格按照以下JSON格式输出，**注意image_prompt必须用英文生成**：

```json
{
  "scenes": [
    {
      "sequence": 1,
      "content": "场景1的故事内容",
      "image_prompt": "Ancient China, Emperor Zhu Yuanzhang wearing tattered cloth robes, gaunt and weary face, begging in desolate fields, background of post-war ruins, dim tones, historical realistic style, ancient horror atmosphere, white background, traditional clothing, high definition, high contrast, low saturation colors",
      "duration_seconds": 3.0,
      "animation_type": "轻微放大",
      "subtitle_text": "场景1的字幕文本"
    }
  ]
}
```

## 重要提醒 - 图像提示词英文化要求
- **image_prompt字段必须用英文生成**，这样AI绘图效果更好
- **每个场景的图像提示词必须不同且具体**，避免生成相同图像
- 英文提示词必须根据场景内容生成具体描述，包含：
  * Specific character appearance and actions (具体人物外貌和动作)
  * Detailed clothing and decorations (详细服装和装饰) 
  * Clear environment and background (明确环境和背景)
  * Historical period characteristics (历史时代特征)
  * Different camera angles and perspectives (不同的镜头角度和视角)
  * Unique scene elements for each scene (每个场景的独特元素)
- 统一添加样式要求：ancient horror style, white background, dim colors, twilight atmosphere, traditional clothing, rough lines, character close-up, high definition, high contrast, low saturation colors, shallow depth of field
- 示例正确格式："Ancient China Warring States period, Emperor Qin Shi Huang wearing black dragon robe, stern and majestic expression, standing in Xianyang Palace hall, ornate palace architecture background, dim lighting, solemn atmosphere, ancient horror style, high definition"
- 绝对不能使用："历史场景1"、"场景描述"、"图像提示"等中文占位符
- **确保每个场景的描述都包含不同的细节、角度或元素，避免重复**

## 限制
1. 必须输出恰好8个场景
2. 每个场景时长固定为3秒
3. 图像描述要详细且符合历史背景，用英文表达包含具体细节
4. 字幕文本保持中文，简洁明了

现在请分割以下历史故事文案：

{{script_content}}""",

            'en': """# Role
You are a professional video storyboard artist responsible for splitting historical story scripts into multiple scenes suitable for video production.

## Skills
### Skill 1: Scene Splitting
1. Split the input historical story script into 8 independent scenes
2. Each scene should contain a complete story segment, lasting about 3 seconds
3. Generate detailed English image description prompts for each scene, including specific details about characters, clothing, environment, and actions
4. Ensure coherence and logic between scenes
5. Generate suitable subtitle text

## Output Format
Please output strictly in the following JSON format with **English image prompts**:

```json
{
  "scenes": [
    {
      "sequence": 1,
      "content": "Story content for scene 1",
      "image_prompt": "Ancient China, Emperor Zhu Yuanzhang wearing tattered cloth robes, gaunt and weary face, begging in desolate fields, background of post-war ruins, dim tones, historical realistic style, ancient horror atmosphere, white background, traditional clothing, high definition, high contrast, low saturation colors", 
      "duration_seconds": 3.0,
      "animation_type": "slight zoom",
      "subtitle_text": "Subtitle text for scene 1"
    }
  ]
}
```

## Important Notes - English Image Prompt Requirements
- **image_prompt must be in English** for optimal AI image generation results
- English prompts must include specific scene-based descriptions with:
  * Specific character appearance and actions
  * Detailed clothing and decorations
  * Clear environment and background
  * Historical period characteristics
  * Artistic style elements
- Always include style requirements: ancient horror style, white background, dim colors, twilight atmosphere, traditional clothing, rough lines, character close-up, high definition, high contrast, low saturation colors, shallow depth of field
- Example format: "Ancient China Warring States period, Emperor Qin Shi Huang wearing black dragon robe, stern and majestic expression, standing in Xianyang Palace hall, ornate palace architecture background, dim lighting, solemn atmosphere, ancient horror style, high definition"
- Never use generic placeholders like "Historical Scene 1", "Scene Description"

## Constraints
1. Must output exactly 8 scenes
2. Each scene duration is fixed at 3 seconds
3. Image descriptions must be detailed, historically accurate, and in English
4. Subtitle text should be concise and clear

Now please split the following historical story script:

{{script_content}}""",

            'es': """# Rol
Eres un artista profesional de storyboard de video responsable de dividir guiones de historias históricas en múltiples escenas adecuadas para la producción de video.

## Habilidades
### Habilidad 1: División de Escenas
1. Dividir el guión de historia histórica de entrada en 8 escenas independientes
2. Cada escena debe contener un segmento completo de la historia, que dure unos 3 segundos
3. Generar indicaciones detalladas en inglés para descripción de imagen para cada escena
4. Asegurar coherencia y lógica entre escenas
5. Generar texto de subtítulos adecuado

## Formato de Salida
Por favor, genera estrictamente en el siguiente formato JSON con **indicaciones de imagen en inglés**:

```json
{
  "scenes": [
    {
      "sequence": 1,
      "content": "Contenido de la historia para la escena 1",
      "image_prompt": "Ancient China, Emperor Zhu Yuanzhang wearing tattered cloth robes, gaunt and weary face, begging in desolate fields, background of post-war ruins, dim tones, historical realistic style, ancient horror atmosphere, white background, traditional clothing, high definition, high contrast, low saturation colors",
      "duration_seconds": 3.0,
      "animation_type": "zoom ligero", 
      "subtitle_text": "Texto de subtítulo para la escena 1"
    }
  ]
}
```

## Notas Importantes - Requisitos de Indicaciones de Imagen en Inglés
- **image_prompt debe estar en inglés** para obtener mejores resultados de generación de imágenes AI
- Las indicaciones en inglés deben incluir descripciones específicas basadas en la escena con:
  * Apariencia específica del personaje y acciones
  * Ropa detallada y decoraciones
  * Entorno claro y fondo
  * Características del período histórico
  * Elementos de estilo artístico
- Incluir siempre requisitos de estilo: ancient horror style, white background, dim colors, twilight atmosphere, traditional clothing, rough lines, character close-up, high definition, high contrast, low saturation colors, shallow depth of field
- Formato de ejemplo: "Ancient China Warring States period, Emperor Qin Shi Huang wearing black dragon robe, stern and majestic expression, standing in Xianyang Palace hall, ornate palace architecture background, dim lighting, solemn atmosphere, ancient horror style, high definition"
- Nunca usar marcadores genéricos como "Historical Scene 1", "Scene Description"

## Restricciones
1. Debe generar exactamente 8 escenas
2. La duración de cada escena es fija en 3 segundos
3. Las descripciones de imagen deben ser detalladas, históricamente precisas, y en inglés
4. El texto del subtítulo debe ser conciso y claro

Ahora por favor divide el siguiente guión de historia histórica:

{{script_content}}"""
        }
    
    async def split_scenes_async(self, request: SceneSplitRequest) -> SceneSplitResult:
        """
        异步分割场景
        
        Args:
            request: 场景分割请求
        
        Returns:
            SceneSplitResult: 分割结果
        """
        start_time = time.time()
        
        try:
            # 缓存已禁用 - 每次都生成新内容
            
            # 验证请求
            if request.language not in self.supported_languages:
                raise ValueError(f"Unsupported language: {request.language}")
            
            # 强制使用LLM分割 - 不再使用coze_rules fallback
            if request.language not in self.prompt_templates:
                raise ValueError(f"No prompt template for language: {request.language}")
            
            # 构建提示词
            prompt_template = self.prompt_templates[request.language]
            prompt = prompt_template.replace('{{script_content}}', request.script_content)
            
            # 调用LLM API
            self.logger.info(f"Splitting scenes for {request.language} script...")
            
            response = await self._call_llm_api(prompt)
            
            if not response:
                raise ValueError("Empty response from LLM")
            
            # 检查响应类型 - 处理增强LLM管理器直接返回Scene列表的情况
            if isinstance(response, list):
                # 增强LLM管理器成功返回了Scene列表
                scenes = response
                self.logger.info(f"✅ 直接获得结构化场景列表: {len(scenes)} scenes")
            else:
                # 传统字符串响应，需要解析
                self.logger.debug(f"LLM Response length: {len(response)}")
                scenes = self._parse_scenes_response(response, request)
            
            # 记录实际生成的场景数量 - 不设置任何限制，完全基于内容自然分割
            self.logger.info(f"Generated {len(scenes)} scenes based on content structure")
            
            # 只做基本的数据完整性检查
            if len(scenes) == 0:
                raise ValueError("No scenes were generated from the script")
            
            # 提供信息性提示，但不限制场景数量
            if len(scenes) == 1:
                self.logger.info("Single scene generated - this is fine for short content")
            elif len(scenes) > 20:
                self.logger.info(f"Large number of scenes ({len(scenes)}) - this suggests rich, detailed content")
            
            # 使用专门的图像提示词生成器生成高质量提示词
            scenes = await self._generate_image_prompts_for_scenes(scenes, request)
            
            # 计算总时长
            total_duration = sum(scene.duration_seconds for scene in scenes)
            
            # 创建结果对象
            result = SceneSplitResult(
                scenes=scenes,
                total_duration=total_duration,
                language=request.language,
                original_script=request.script_content,
                split_time=time.time() - start_time,
                model_used=self.llm_config.name
            )
            
            # 缓存结果
            cache_data = {
                'scenes': [self._scene_to_dict(scene) for scene in scenes],
                'total_duration': result.total_duration,
                'language': result.language,
                'original_script': result.original_script,
                'model_used': result.model_used
            }
            
            # 缓存已禁用
            
            # 记录日志
            logger = self.config.get_logger('story_generator')
            logger.info(f"Content generation - Type: scene_splitting, Language: {request.language}, "
                       f"Input: {len(request.script_content)} chars, Output: {len(json.dumps(cache_data, ensure_ascii=False))} chars, "
                       f"Time: {result.split_time:.2f}s")
            
            self.logger.info(f"Split scenes successfully: {len(scenes)} scenes, {total_duration:.1f}s total duration")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Scene splitting failed: {e}")
            
            # 记录错误日志
            logger = self.config.get_logger('story_generator')
            logger.error(f"Content generation failed - Type: scene_splitting, Language: {request.language}, "
                        f"Input: {len(request.script_content)} chars, Time: {processing_time:.2f}s")
            
            raise
    
    def _split_prompt(self, prompt: str) -> tuple[str, str]:
        """将单个prompt分离为system_prompt和user_prompt"""
        
        # 尝试从prompt中找到合适的分割点
        lines = prompt.split('\n')
        
        # 查找指示用户输入开始的标志
        user_start_markers = ['故事内容:', '请分割以下故事:', '脚本内容:', '故事:', '内容:']
        
        system_lines = []
        user_lines = []
        found_user_start = False
        
        for line in lines:
            line_clean = line.strip()
            if not found_user_start:
                # 检查是否找到用户内容开始标志
                for marker in user_start_markers:
                    if marker in line_clean:
                        found_user_start = True
                        user_lines.append(line)
                        break
                if not found_user_start:
                    system_lines.append(line)
            else:
                user_lines.append(line)
        
        # 如果没有找到明确的分割点，采用简单的策略
        if not user_lines:
            # 将前80%作为系统提示词，后20%作为用户输入
            split_point = int(len(lines) * 0.8)
            system_lines = lines[:split_point]
            user_lines = lines[split_point:]
        
        system_prompt = '\n'.join(system_lines).strip()
        user_prompt = '\n'.join(user_lines).strip()
        
        # 确保至少有基本的系统提示词
        if not system_prompt:
            system_prompt = "你是专业的故事场景分割专家。将输入的故事分割为多个场景，每个场景3秒钟。"
        
        # 确保至少有用户输入
        if not user_prompt:
            user_prompt = prompt
        
        return system_prompt, user_prompt
    
    async def _call_llm_api(self, prompt: str) -> str:
        """
        调用LLM API - 优先使用增强LLM管理器 (OpenAI Structured Output + 多层降级)
        
        Args:
            prompt: 提示词
        
        Returns:
            str or List[Scene]: LLM响应 或 结构化Scene列表
        """
        try:
            # 优先尝试增强LLM管理器 (OpenAI Structured Output + 多层降级)
            # 使用统一的增强LLM管理器
            try:
                self.logger.info("🚀 使用增强LLM管理器 (OpenAI GPT-4.1 + Structured Output)")
                
                # 从prompt中分离系统提示词和用户提示词
                system_prompt, user_prompt = self._split_prompt(prompt)
                
                structured_output = await self.llm_manager.generate_structured_output(
                    task_type='scene_splitting',
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_retries=2
                )
                
                if hasattr(structured_output, 'scenes') and structured_output.scenes:
                    # 转换为原有的Scene对象格式
                    scenes = []
                    for scene_data in structured_output.scenes:
                        scene = Scene(
                            sequence=scene_data.sequence,
                            content=scene_data.content,
                            image_prompt="",  # 后续生成
                            video_prompt="", # 后续生成  
                            duration_seconds=scene_data.duration,
                            animation_type="center_zoom_in",
                            subtitle_text=scene_data.content
                        )
                        scenes.append(scene)
                    
                    self.logger.info(f"✅ 增强LLM管理器成功: {len(scenes)} scenes (OpenAI GPT-4.1)")
                    return scenes
                        
            except Exception as e:
                self.logger.warning(f"⚠️ 增强LLM管理器失败: {e}")
                # 继续尝试传统方法
            
            # 降级：尝试传统结构化输出
            try:
                self.logger.info("🔄 降级到传统结构化输出...")
                # 从prompt中分离系统提示词和用户提示词
                system_prompt, user_prompt = self._split_prompt(prompt)
                
                structured_output = await self.llm_manager.generate_structured_output(
                    task_type='scene_splitting',
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_retries=2
                )
                
                if hasattr(structured_output, 'scenes') and structured_output.scenes:
                    # 转换为原有的Scene对象格式
                    scenes = []
                    for scene_data in structured_output.scenes:
                        scene = Scene(
                            sequence=scene_data.sequence,
                            content=scene_data.content,
                            image_prompt="",  # 后续生成
                            video_prompt="", # 后续生成
                            duration_seconds=getattr(scene_data, 'duration', 3.0),
                            animation_type="center_zoom_in",
                            subtitle_text=scene_data.content
                        )
                        scenes.append(scene)
                    
                    self.logger.info(f"✅ 传统结构化输出成功: {len(scenes)} scenes")
                    return scenes
                else:
                    # 降级到文本解析
                    content = str(structured_output)
                    
            except Exception as e:
                self.logger.warning(f"🔄 传统结构化输出失败，降级到文本解析: {e}")
                
                # 最终降级：传统文本生成
                content = await self.llm_manager.call_llm_with_fallback(
                    prompt=prompt,
                    task_type='scene_splitting',
                    temperature=self.llm_config.temperature,
                    max_tokens=self.llm_config.max_tokens
                )
            
            if not content:
                raise ValueError("Empty response from all LLM providers")
            
            return content.strip()
            
        except Exception as e:
            self.logger.error(f"LLM API call failed: {e}")
            raise
    
    def _parse_scenes_response(self, response: str, request: SceneSplitRequest) -> List[Scene]:
        """
        解析场景分割响应
        
        Args:
            response: LLM响应
            request: 原始请求
        
        Returns:
            List[Scene]: 解析的场景列表
        """
        try:
            # 尝试提取JSON部分
            json_content = self._extract_json_from_response(response)
            
            if not json_content:
                self.logger.error(f"Failed to extract JSON from response. Response length: {len(response)}")
                self.logger.error(f"Response preview (first 1000 chars): {response[:1000]}")
                raise ValueError("No valid JSON found in response")
            
            self.logger.debug(f"Extracted JSON content: {json_content[:200]}...")
            
            try:
                data = json.loads(json_content)
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {e}")
                self.logger.error(f"Invalid JSON content: {json_content}")
                raise ValueError(f"Invalid JSON format: {e}")
            
            if 'scenes' not in data:
                raise ValueError("Missing 'scenes' key in response")
            
            scenes = []
            
            for i, scene_data in enumerate(data['scenes']):
                scene = Scene(
                    sequence=scene_data.get('sequence', i + 1),
                    content=scene_data.get('content', ''),
                    image_prompt=scene_data.get('image_prompt', ''),
                    video_prompt=scene_data.get('video_prompt', ''),  # 新增视频提示词字段
                    duration_seconds=scene_data.get('duration_seconds', request.scene_duration),
                    animation_type=scene_data.get('animation_type', '轻微放大'),
                    subtitle_text=scene_data.get('subtitle_text', scene_data.get('content', ''))
                )
                
                # 验证场景内容
                if not scene.content:
                    raise ValueError(f"Empty content for scene {i + 1}")
                
                scenes.append(scene)
            
            if not scenes:
                raise ValueError("No scenes parsed from response")
            
            return scenes
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            self.logger.error(f"Raw LLM response that caused JSON error: {response[:1000]}...")
            raise ValueError(f"LLM returned invalid JSON format: {e}")
        except Exception as e:
            self.logger.error(f"Scene parsing error: {e}")
            self.logger.error(f"Raw LLM response: {response[:1000]}...")
            raise
    
    def _extract_json_from_response(self, response: str) -> Optional[str]:
        """从响应中提取JSON内容"""
        import re
        
        self.logger.debug(f"Extracting JSON from response (length: {len(response)})")
        
        # 方法1: 查找```json...```格式
        json_match = re.search(r'```json\s*\n?(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
        if json_match:
            content = json_match.group(1).strip()
            self.logger.debug("Found JSON in ```json``` block")
            return content
        
        # 方法2: 查找```...```格式（可能没有标明json）
        code_match = re.search(r'```\s*\n?(.*?)\n?```', response, re.DOTALL)
        if code_match:
            content = code_match.group(1).strip()
            if content.startswith('{') and content.endswith('}'):
                self.logger.debug("Found JSON in ``` block")
                return content
        
        # 方法3: 查找包含"scenes"的JSON对象（更宽松的匹配）
        json_obj_match = re.search(r'(\{.*?"scenes".*?\[.*?\].*?\})', response, re.DOTALL)
        if json_obj_match:
            content = json_obj_match.group(1)
            self.logger.debug("Found JSON with scenes key")
            return content
        
        # 方法4: 寻找完整的JSON大括号匹配
        start_pos = response.find('{')
        if start_pos != -1:
            bracket_count = 0
            for i, char in enumerate(response[start_pos:], start_pos):
                if char == '{':
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        candidate = response[start_pos:i+1]
                        # 验证这确实包含scenes
                        if '"scenes"' in candidate:
                            self.logger.debug("Found JSON through bracket matching")
                            return candidate
        
        # 方法5: 尝试多个JSON对象的情况
        json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        for obj in json_objects:
            if '"scenes"' in obj:
                self.logger.debug("Found JSON in multiple objects search")
                return obj
        
        # 记录响应内容的前500字符用于调试
        self.logger.warning(f"No JSON found in response. Response preview: {response[:500]}")
        return None
    
    # FALLBACK LOGIC REMOVED - 不再使用退化逻辑掩盖问题
    # def _fallback_scene_parsing(self, response: str, request: SceneSplitRequest) -> List[Scene]:
        """
        退化的场景解析（当JSON解析失败时）
        
        Args:
#             response: LLM响应
#             request: 原始请求
#         
#         Returns:
#             List[Scene]: 解析的场景列表
#         """
#         self.logger.warning("Using fallback scene parsing")
#         
#         # 简单地将文案按句号分割
#         sentences = [s.strip() for s in request.script_content.split('。') if s.strip()]
#         
#         # 如果句子数量不够，按照目标数量进行均匀分割
#         if len(sentences) < request.target_scene_count:
#             # 按字符数分割
#             content_length = len(request.script_content)
#             segment_length = content_length // request.target_scene_count
#             
#             scenes = []
#             for i in range(request.target_scene_count):
#                 start_idx = i * segment_length
#                 end_idx = (i + 1) * segment_length if i < request.target_scene_count - 1 else content_length
#                 
#                 segment = request.script_content[start_idx:end_idx].strip()
#                 
#                 scene = Scene(
#                     sequence=i + 1,
#                     content=segment,
#                     image_prompt=self._generate_fallback_image_prompt(segment, i + 1),
#                     duration_seconds=request.scene_duration,
#                     animation_type="轻微放大",
#                     subtitle_text=segment[:50] + "..." if len(segment) > 50 else segment
#                 )
#                 
#                 scenes.append(scene)
#         else:
#             # 如果句子太多，合并一些句子
#             scenes_per_sentence = len(sentences) // request.target_scene_count
#             scenes = []
#             
#             for i in range(request.target_scene_count):
#                 start_idx = i * scenes_per_sentence
#                 end_idx = (i + 1) * scenes_per_sentence if i < request.target_scene_count - 1 else len(sentences)
#                 
#                 content = '。'.join(sentences[start_idx:end_idx]) + '。'
#                 
#                 scene = Scene(
#                     sequence=i + 1,
#                     content=content,
#                     image_prompt=self._generate_fallback_image_prompt(content, i + 1),
#                     duration_seconds=request.scene_duration,
#                     animation_type="轻微放大",
#                     subtitle_text=content[:50] + "..." if len(content) > 50 else content
#                 )
#                 
#                 scenes.append(scene)
#         
#         return scenes
# 
#     def _ensure_valid_image_prompts(self, scenes: List[Scene], request: SceneSplitRequest) -> List[Scene]:
#         """校验并修正场景的图像提示词，确保英文、多样且不过度重复"""
#         def contains_non_ascii(s: str) -> bool:
#             try:
#                 s.encode('ascii')
#                 return False
#             except Exception:
#                 return True
#         
#         seen_prompts = set()
#         fixed_scenes: List[Scene] = []
#         for idx, scene in enumerate(scenes, start=1):
#             prompt = scene.image_prompt or ""
#             needs_fix = False
#             if not prompt:
#                 needs_fix = True
#             elif contains_non_ascii(prompt):
#                 needs_fix = True
#             elif len(prompt) < 30:
#                 needs_fix = True
#             elif prompt in seen_prompts:
#                 needs_fix = True
#             
#             if needs_fix:
#                 new_prompt = self._generate_fallback_image_prompt(scene.content, idx)
#                 self.logger.debug(f"Fixing image_prompt for scene {idx}: '{prompt[:40]}' -> '{new_prompt[:60]}'")
#                 prompt = new_prompt
#             
#             seen_prompts.add(prompt)
#             fixed_scenes.append(Scene(
#                 sequence=scene.sequence,
#                 content=scene.content,
#                 image_prompt=prompt,
#                 duration_seconds=scene.duration_seconds,
#                 animation_type=scene.animation_type,
#                 subtitle_text=scene.subtitle_text
#             ))
#         return fixed_scenes
#     
#     def _split_by_coze_rules(self, request: SceneSplitRequest, tts_subtitles: Optional[List] = None) -> List[Scene]:
#         """
#         按照原Coze工作流规则分割场景：第一句单独成段，后续每2句一段
#         
#         Args:
#             request: 场景分割请求
#             tts_subtitles: TTS返回的字幕时间戳信息（可选）
#         
#         Returns:
#             List[Scene]: 场景列表
#         """
#         # 按句号分割句子，保留句号
#         sentences = []
#         current_sentence = ""
#         
#         for char in request.script_content:
#             current_sentence += char
#             if char in ['。', '！', '？']:  # 中文句末标点(恢复原逻辑)
#                 if current_sentence.strip():
#                     sentences.append(current_sentence.strip())
#                 current_sentence = ""
#         
#         # 如果最后没有句末标点，添加最后一段
#         if current_sentence.strip():
#             sentences.append(current_sentence.strip())
#         
#         if not sentences:
#             # 如果没有句子，将整个文本作为一个场景
#             scenes = [Scene(
#                 sequence=1,
#                 content=request.script_content,
#                 image_prompt=self._generate_fallback_image_prompt(request.script_content, 1),
#                 duration_seconds=request.scene_duration,
#                 animation_type="轻微放大",
#                 subtitle_text=request.script_content[:50] + "..." if len(request.script_content) > 50 else request.script_content
#             )]
#             return scenes
#         
#         scenes = []
#         
#         # 第一句单独成段
#         if sentences:
#             first_sentence = sentences[0]
#             # 计算第一句的时长
#             duration = self._calculate_scene_duration(first_sentence, 0, 1, tts_subtitles) if tts_subtitles else request.scene_duration
#             
#             scene = Scene(
#                 sequence=1,
#                 content=first_sentence,
#                 image_prompt=self._generate_fallback_image_prompt(first_sentence, 1),
#                 duration_seconds=duration,
#                 animation_type="轻微放大",
#                 subtitle_text=first_sentence
#             )
#             scenes.append(scene)
#         
#         # 后续每2句一段 - 添加长度预检查
#         remaining_sentences = sentences[1:]
#         scene_num = 2
#         sentence_index = 1  # 从第二句开始计数
#         
#         for i in range(0, len(remaining_sentences), 2):
#             # 取最多2句，但要检查长度限制
#             scene_sentences = remaining_sentences[i:i+2]
#             scene_content = ''.join(scene_sentences)
#             
#             # 🔍 长度预检查: 如果场景内容过长(>30字符)，单句成段  
#             if len(scene_content) > 30 and len(scene_sentences) > 1:
#                 # 第一句单独成段
#                 first_content = scene_sentences[0]
#                 duration1 = self._calculate_scene_duration(first_content, sentence_index, 1, tts_subtitles) if tts_subtitles else request.scene_duration
#                 
#                 scene1 = Scene(
#                     sequence=scene_num,
#                     content=first_content,
#                     image_prompt=self._generate_fallback_image_prompt(first_content, scene_num),
#                     duration_seconds=duration1,
#                     animation_type="轻微放大",
#                     subtitle_text=first_content
#                 )
#                 scenes.append(scene1)
#                 scene_num += 1
#                 
#                 # 如果有第二句，也单独成段
#                 if len(scene_sentences) > 1:
#                     second_content = scene_sentences[1]
#                     duration2 = self._calculate_scene_duration(second_content, sentence_index + 1, 1, tts_subtitles) if tts_subtitles else request.scene_duration
#                     
#                     scene2 = Scene(
#                         sequence=scene_num,
#                         content=second_content,
#                         image_prompt=self._generate_fallback_image_prompt(second_content, scene_num),
#                         duration_seconds=duration2,
#                         animation_type="轻微放大",
#                         subtitle_text=second_content
#                     )
#                     scenes.append(scene2)
#                     scene_num += 1
#             else:
#                 # 长度合适，按原逻辑处理
#                 sentences_in_scene = len(scene_sentences)
#                 duration = self._calculate_scene_duration(scene_content, sentence_index, sentences_in_scene, tts_subtitles) if tts_subtitles else request.scene_duration
#                 
#                 scene = Scene(
#                     sequence=scene_num,
#                     content=scene_content,
#                     image_prompt=self._generate_fallback_image_prompt(scene_content, scene_num),
#                     duration_seconds=duration,
#                     animation_type="轻微放大",
#                     subtitle_text=scene_content
#                 )
#                 scenes.append(scene)
#                 scene_num += 1
#             
#             sentence_index += len(scene_sentences)
#         
#         self.logger.info(f"Coze rules splitting: {len(sentences)} sentences → {len(scenes)} scenes")
#         self.logger.debug(f"Scene breakdown: Scene 1 (1 sentence), Scenes 2-{len(scenes)} ({len(remaining_sentences)} sentences in groups of 2)")
#         
#         return scenes
#     
#     def _calculate_scene_duration(self, scene_content: str, sentence_start_index: int, sentences_count: int, tts_subtitles: Optional[List]) -> float:
#         """
#         基于TTS字幕信息计算场景时长
#         
#         Args:
#             scene_content: 场景内容
#             sentence_start_index: 句子起始索引
#             sentences_count: 句子数量
#             tts_subtitles: TTS字幕列表
#         
#         Returns:
#             float: 场景时长（秒）
#         """
#         if not tts_subtitles:
#             # 根据字符数量估算时长（每分钟约300字）
#             chars_per_minute = 300
#             estimated_duration = (len(scene_content) / chars_per_minute) * 60
#             return max(2.0, min(estimated_duration, 10.0))  # 限制在2-10秒之间
#         
#         try:
#             # 尝试根据TTS字幕计算精确时长
#             # 找到场景内容对应的字幕段
#             scene_start_time = None
#             scene_end_time = None
#             
#             for subtitle in tts_subtitles:
#                 subtitle_text = subtitle.get('text', '').strip()
#                 if not subtitle_text:
#                     continue
#                     
#                 # 检查是否包含场景的开始文本
#                 if scene_start_time is None and scene_content[:20] in subtitle_text:
#                     scene_start_time = subtitle.get('start', 0)
#                 
#                 # 检查是否包含场景的结束文本
#                 if scene_content[-20:] in subtitle_text:
#                     scene_end_time = subtitle.get('end', subtitle.get('start', 0))
#             
#             if scene_start_time is not None and scene_end_time is not None:
#                 duration = scene_end_time - scene_start_time
#                 if duration > 0:
#                     self.logger.debug(f"TTS-based duration for scene: {duration:.2f}s")
#                     return duration
#         
#         except Exception as e:
#             self.logger.warning(f"Failed to calculate TTS-based duration: {e}")
#         
#         # 退化方案：基于字符数量估算
#         chars_per_minute = 300
#         estimated_duration = (len(scene_content) / chars_per_minute) * 60
#         return max(2.0, min(estimated_duration, 10.0))  # 限制在2-10秒之间
# 
#     # FALLBACK LOGIC REMOVED - 不再使用退化逻辑掩盖问题  
#     # def _generate_fallback_image_prompt(self, content: str, sequence: int) -> str:
#         """
#         生成退化图像提示词（基于内容而非占位符）
#         
#         Args:
#             content: 场景内容
#             sequence: 场景序号
#         
#         Returns:
#             str: 图像提示词
#         """
#         import re
#         
#         # 提取关键词来生成图像描述
#         keywords = {
#             'characters': [],
#             'places': [],
#             'actions': [],
#             'objects': []
#         }
#         
#         # 常见历史人物名称
#         historical_figures = ['秦始皇', '嬴政', '朱元璋', '汉武帝', '唐太宗', '康熙', '乾隆', '武则天', '李世民', '刘邦', '项羽']
#         for figure in historical_figures:
#             if figure in content:
#                 keywords['characters'].append(figure)
#         
#         # 常见地点
#         places = ['咸阳', '长安', '北京', '南京', '洛阳', '汴梁', '宫殿', '皇宫', '城墙', '战场', '朝堂']
#         for place in places:
#             if place in content:
#                 keywords['places'].append(place)
#         
#         # 动作词
#         actions = ['战斗', '征战', '统一', '建立', '推翻', '称帝', '登基', '治理', '改革', '变法']
#         for action in actions:
#             if action in content:
#                 keywords['actions'].append(action)
#         
#         # 物品
#         objects = ['龙袍', '铠甲', '兵器', '城池', '军队', '旗帜', '宫殿', '建筑']
#         for obj in objects:
#             if obj in content:
#                 keywords['objects'].append(obj)
#         
#         # 创建中文到英文的人物映射
#         character_mapping = {
#             '秦始皇': 'Emperor Qin Shi Huang',
#             '嬴政': 'Emperor Qin Shi Huang',
#             '朱元璋': 'Emperor Zhu Yuanzhang',
#             '汉武帝': 'Emperor Wu of Han',
#             '唐太宗': 'Emperor Taizong of Tang',
#             '康熙': 'Emperor Kangxi',
#             '乾隆': 'Emperor Qianlong',
#             '武则天': 'Empress Wu Zetian',
#             '李世民': 'Emperor Taizong Li Shimin',
#             '刘邦': 'Emperor Liu Bang',
#             '项羽': 'Xiang Yu'
#         }
#         
#         # 创建中文到英文的地点映射
#         place_mapping = {
#             '咸阳': 'Xianyang',
#             '长安': "Chang'an",
#             '北京': 'Beijing',
#             '南京': 'Nanjing',
#             '洛阳': 'Luoyang',
#             '汴梁': 'Bianliang',
#             '宫殿': 'imperial palace',
#             '皇宫': 'royal palace',
#             '城墙': 'city walls',
#             '战场': 'battlefield',
#             '朝堂': 'imperial court'
#         }
#         
#         # 根据关键词组合生成英文描述，并引入不同镜头与视角，避免重复
#         camera_angles = [
#             'close-up portrait',
#             'wide establishing shot',
#             'low-angle dramatic shot',
#             'bird\'s-eye view',
#             'over-the-shoulder view',
#             'three-quarter view',
#             'side profile shot',
#             'back view silhouette'
#         ]
#         # 交替使用角度
#         angle = camera_angles[(sequence - 1) % len(camera_angles)]
#         if keywords['characters']:
#             character_cn = keywords['characters'][0]
#             character_en = character_mapping.get(character_cn, 'ancient Chinese emperor')
#             if keywords['places']:
#                 place_cn = keywords['places'][0]
#                 place_en = place_mapping.get(place_cn, 'ancient Chinese location')
#                 return f"Ancient China, {character_en} in {place_en}, {angle}, wearing traditional imperial robes, stern and majestic expression, historical realistic style, ancient horror atmosphere, white background, dim colors, traditional clothing, high definition, high contrast, low saturation colors"
#             else:
#                 return f"Ancient China, {character_en}, {angle}, wearing black dragon robe, stern and majestic face, ancient imperial palace background, historical realistic style, ancient horror atmosphere, white background, traditional clothing, high definition, high contrast, low saturation colors"
#         elif keywords['places']:
#             place_cn = keywords['places'][0]
#             place_en = place_mapping.get(place_cn, 'ancient Chinese architecture')
#             return f"Ancient China {place_en}, {angle}, magnificent architecture, ancient architectural style, dim lighting, rich historical atmosphere, ancient horror style, white background, traditional elements, high definition, high contrast, low saturation colors, solemn atmosphere"
#         elif keywords['actions']:
#             return f"Ancient China historical scene, {angle}, traditional costumes, ancient architectural background, historical realistic style, ancient horror atmosphere, white background, dim colors, traditional clothing, high definition, high contrast, low saturation colors, solemn atmosphere"
#         else:
#             # 最后的通用英文描述
#             return f"Ancient China historical scene, {angle}, traditional clothing, ancient architecture, dim tones, historical realistic style, ancient horror atmosphere, white background, traditional elements, high definition, high contrast, low saturation colors, solemn atmosphere"
#     
    def _scene_to_dict(self, scene: Scene) -> Dict[str, Any]:
        """将Scene对象转换为字典"""
        return {
            'sequence': scene.sequence,
            'content': scene.content,
            'image_prompt': scene.image_prompt,
            'video_prompt': scene.video_prompt,  # 添加视频提示词字段
            'duration_seconds': scene.duration_seconds,
            'animation_type': scene.animation_type,
            'subtitle_text': scene.subtitle_text
        }
    

    
    def split_scenes_sync(self, request: SceneSplitRequest) -> SceneSplitResult:
        """
        同步分割场景（对异步方法的包装）
        
        Args:
            request: 场景分割请求
        
        Returns:
            SceneSplitResult: 分割结果
        """
        return asyncio.run(self.split_scenes_async(request))
    
    async def batch_split_scenes(self, requests: List[SceneSplitRequest], 
                               max_concurrent: int = 2) -> List[SceneSplitResult]:
        """
        批量场景分割
        
        Args:
            requests: 分割请求列表
            max_concurrent: 最大并发数
        
        Returns:
            List[SceneSplitResult]: 分割结果列表
        """
        self.logger.info(f"Starting batch scene splitting: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def split_with_semaphore(request: SceneSplitRequest) -> SceneSplitResult:
            async with semaphore:
                return await self.split_scenes_async(request)
        
        # 执行并发分割
        tasks = [split_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch scene splitting failed for request {i}: {result}")
                failed_count += 1
            else:
                successful_results.append(result)
        
        self.logger.info(f"Batch scene splitting completed: {len(successful_results)} successful, {failed_count} failed")
        
        return successful_results
    
    def save_scenes(self, result: SceneSplitResult, output_dir: Optional[str] = None) -> str:
        """
        保存场景分割结果到文件
        
        Args:
            result: 场景分割结果
            output_dir: 输出目录（可选）
        
        Returns:
            str: 保存的文件路径
        """
        if not output_dir:
            filename = self.file_manager.generate_filename(
                content=result.original_script,
                prefix=f"scenes_{result.language}",
                extension="json"
            )
            filepath = self.file_manager.get_output_path('scenes', filename)
        else:
            filepath = Path(output_dir) / f"scenes_{result.language}_{int(time.time())}.json"
        
        # 准备保存数据
        save_data = {
            'metadata': {
                'language': result.language,
                'total_duration': result.total_duration,
                'scene_count': len(result.scenes),
                'model_used': result.model_used,
                'split_time': result.split_time,
                'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
            },
            'original_script': result.original_script,
            'scenes': [self._scene_to_dict(scene) for scene in result.scenes]
        }
        
        success = self.file_manager.save_json(save_data, filepath)
        
        if success:
            self.logger.info(f"Saved scenes to: {filepath}")
            return str(filepath)
        else:
            raise Exception(f"Failed to save scenes to: {filepath}")
    
    def update_scene_durations_with_tts(self, scenes: List[Scene], tts_subtitles: List) -> List[Scene]:
        """
        使用TTS字幕信息更新场景时长
        
        Args:
            scenes: 原始场景列表
            tts_subtitles: TTS字幕信息
        
        Returns:
            List[Scene]: 更新时长后的场景列表
        """
        updated_scenes = []
        
        for scene in scenes:
            # 重新计算时长
            new_duration = self._calculate_scene_duration(scene.content, scene.sequence - 1, 1, tts_subtitles)
            
            # 创建新的场景对象
            updated_scene = Scene(
                sequence=scene.sequence,
                content=scene.content,
                image_prompt=scene.image_prompt,
                duration_seconds=new_duration,
                animation_type=scene.animation_type,
                subtitle_text=scene.subtitle_text
            )
            updated_scenes.append(updated_scene)
            
            self.logger.debug(f"Scene {scene.sequence} duration updated: {scene.duration_seconds:.2f}s → {new_duration:.2f}s")
        
        total_duration = sum(scene.duration_seconds for scene in updated_scenes)
        self.logger.info(f"Updated scene durations with TTS data: total {total_duration:.2f}s")
        
        return updated_scenes

    def get_splitting_stats(self) -> Dict[str, Any]:
        """获取分割统计信息"""
        
        return {
            'supported_languages': self.supported_languages,
            'model_config': {
                'name': self.llm_config.name,
                'temperature': self.llm_config.temperature,
                'max_tokens': self.llm_config.max_tokens
            }
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"SceneSplitter(model={self.llm_config.name}, languages={self.supported_languages})"