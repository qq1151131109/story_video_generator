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
import openai
from dataclasses import dataclass

from core.config_manager import ConfigManager, ModelConfig
from core.cache_manager import CacheManager
from utils.file_manager import FileManager

@dataclass
class Scene:
    """单个场景"""
    sequence: int              # 场景序号
    content: str              # 场景内容文本
    image_prompt: str         # 图像提示词
    duration_seconds: float   # 时长（秒）
    animation_type: str       # 动画类型
    subtitle_text: str        # 字幕文本
    
@dataclass
class SceneSplitRequest:
    """场景分割请求"""
    script_content: str       # 原始文案内容
    language: str            # 语言代码
    target_scene_count: int = 8  # 目标场景数量
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
                 cache_manager: CacheManager, file_manager: FileManager):
        self.config = config_manager
        self.cache = cache_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.content')
        
        # 支持的语言 - 必须在加载提示词模板之前设置
        self.supported_languages = self.config.get_supported_languages()
        
        # 获取LLM配置
        self.llm_config = self.config.get_llm_config('scene_splitting')
        
        # 配置OpenAI客户端
        self._setup_openai_client()
        
        # 加载提示词模板
        self._load_prompt_templates()
    
    def _setup_openai_client(self):
        """配置OpenAI客户端"""
        self.client = openai.AsyncOpenAI(
            api_key=self.llm_config.api_key,
            base_url=self.llm_config.api_base
        )
        
        self.logger.info(f"Initialized OpenAI client for scene splitting")
    
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
3. 为每个场景生成详细的图像描述提示词，必须包含具体的人物、服装、环境、动作等细节
4. 确保场景之间的连贯性和逻辑性
5. 生成适合的字幕文本

## 输出格式
请严格按照以下JSON格式输出：

```json
{
  "scenes": [
    {
      "sequence": 1,
      "content": "场景1的故事内容",
      "image_prompt": "详细的图像描述，包含人物外貌、服装、环境、动作等具体细节，如：古代中国，朱元璋身穿破旧布衣，面容憔悴，在荒芜的田野中乞讨，背景是战乱后的废墟，昏暗色调，历史写实风格",
      "duration_seconds": 3.0,
      "animation_type": "轻微放大",
      "subtitle_text": "场景1的字幕文本"
    }
  ]
}
```

## 重要提醒 - 必须遵守
- image_prompt绝对不能使用"历史场景1"、"历史场景2"这样的通用占位符
- image_prompt必须根据场景内容生成具体的图像描述，包含：
  * 具体的人物外貌和动作
  * 详细的服装和装饰
  * 明确的环境和背景
  * 历史时代特征
- 示例正确格式："古代中国战国时期，秦始皇嬴政身穿黑色龙袍，面容威严，站在咸阳宫大殿中，背景是华丽的宫殿建筑，昏暗灯光，威严肃穆的氛围"
- 示例错误格式："历史场景1"、"场景描述"、"图像提示"等

## 限制
1. 必须输出恰好8个场景
2. 每个场景时长固定为3秒
3. 图像描述要详细且符合历史背景，包含具体细节
4. 字幕文本要简洁明了

现在请分割以下历史故事文案：

{{script_content}}""",

            'en': """# Role
You are a professional video storyboard artist responsible for splitting historical story scripts into multiple scenes suitable for video production.

## Skills
### Skill 1: Scene Splitting
1. Split the input historical story script into 8 independent scenes
2. Each scene should contain a complete story segment, lasting about 3 seconds
3. Generate detailed image description prompts for each scene, including specific details about characters, clothing, environment, and actions
4. Ensure coherence and logic between scenes
5. Generate suitable subtitle text

## Output Format
Please output strictly in the following JSON format:

```json
{
  "scenes": [
    {
      "sequence": 1,
      "content": "Story content for scene 1",
      "image_prompt": "Detailed image description with specific details about characters, clothing, environment, actions, e.g.: Ancient China, Zhu Yuanzhang wearing tattered cloth robes, gaunt face, begging in barren fields, background of post-war ruins, dim tones, historical realistic style", 
      "duration_seconds": 3.0,
      "animation_type": "slight zoom",
      "subtitle_text": "Subtitle text for scene 1"
    }
  ]
}
```

## Important Notes
- image_prompt must be detailed descriptions with specific details about characters, clothing, environment, actions
- Do not use generic placeholders like "Historical Scene 1", "Scene Description"
- Each scene's image_prompt should be unique and specific

## Constraints
1. Must output exactly 8 scenes
2. Each scene duration is fixed at 3 seconds
3. Image descriptions should be detailed and historically accurate with specific details
4. Subtitle text should be concise and clear

Now please split the following historical story script:

{{script_content}}""",

            'es': """# Rol
Eres un artista profesional de storyboard de video responsable de dividir guiones de historias históricas en múltiples escenas adecuadas para la producción de video.

## Habilidades
### Habilidad 1: División de Escenas
1. Dividir el guión de historia histórica de entrada en 8 escenas independientes
2. Cada escena debe contener un segmento completo de la historia, que dure unos 3 segundos
3. Generar indicaciones de descripción de imagen apropiadas para cada escena
4. Asegurar coherencia y lógica entre escenas
5. Generar texto de subtítulos adecuado

## Formato de Salida
Por favor, genera estrictamente en el siguiente formato JSON:

```json
{
  "scenes": [
    {
      "sequence": 1,
      "content": "Contenido de la historia para la escena 1",
      "image_prompt": "Descripción de imagen para la escena 1",
      "duration_seconds": 3.0,
      "animation_type": "zoom ligero", 
      "subtitle_text": "Texto de subtítulo para la escena 1"
    }
  ]
}
```

## Restricciones
1. Debe generar exactamente 8 escenas
2. La duración de cada escena es fija en 3 segundos
3. Las descripciones de imagen deben ser detalladas e históricamente precisas
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
            # 检查缓存
            cache_key = self.cache.get_cache_key({
                'script_content': request.script_content,
                'language': request.language,
                'target_scene_count': request.target_scene_count,
                'scene_duration': request.scene_duration
            })
            
            cached_result = self.cache.get('scenes', cache_key)
            if cached_result:
                self.logger.info(f"Cache hit for scene splitting: {request.language}")
                cached_result['split_time'] = time.time() - start_time
                # 重构Scene对象
                scenes = [Scene(**scene_data) for scene_data in cached_result['scenes']]
                cached_result['scenes'] = scenes
                return SceneSplitResult(**cached_result)
            
            # 验证请求
            if request.language not in self.supported_languages:
                raise ValueError(f"Unsupported language: {request.language}")
            
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
            
            # 解析响应
            scenes = self._parse_scenes_response(response, request)
            
            # 验证场景数量
            if len(scenes) != request.target_scene_count:
                self.logger.warning(f"Expected {request.target_scene_count} scenes, got {len(scenes)}")
            
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
            
            self.cache.set('scenes', cache_key, cache_data)
            
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
    
    async def _call_llm_api(self, prompt: str) -> str:
        """
        调用LLM API
        
        Args:
            prompt: 提示词
        
        Returns:
            str: LLM响应
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.llm_config.name,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from LLM")
            
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
                raise ValueError("No valid JSON found in response")
            
            data = json.loads(json_content)
            
            if 'scenes' not in data:
                raise ValueError("Missing 'scenes' key in response")
            
            scenes = []
            
            for i, scene_data in enumerate(data['scenes']):
                scene = Scene(
                    sequence=scene_data.get('sequence', i + 1),
                    content=scene_data.get('content', ''),
                    image_prompt=scene_data.get('image_prompt', ''),
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
            # 尝试退化处理
            return self._fallback_scene_parsing(response, request)
        except Exception as e:
            self.logger.error(f"Scene parsing error: {e}")
            # 尝试退化处理
            return self._fallback_scene_parsing(response, request)
    
    def _extract_json_from_response(self, response: str) -> Optional[str]:
        """从响应中提取JSON内容"""
        # 查找JSON代码块
        import re
        
        # 查找```json...```格式
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL | re.IGNORECASE)
        if json_match:
            return json_match.group(1).strip()
        
        # 查找```...```格式（可能没有标明json）
        code_match = re.search(r'```\s*\n(.*?)\n```', response, re.DOTALL)
        if code_match:
            content = code_match.group(1).strip()
            if content.startswith('{') and content.endswith('}'):
                return content
        
        # 查找直接的JSON对象
        json_obj_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_obj_match:
            return json_obj_match.group(0)
        
        return None
    
    def _fallback_scene_parsing(self, response: str, request: SceneSplitRequest) -> List[Scene]:
        """
        退化的场景解析（当JSON解析失败时）
        
        Args:
            response: LLM响应
            request: 原始请求
        
        Returns:
            List[Scene]: 解析的场景列表
        """
        self.logger.warning("Using fallback scene parsing")
        
        # 简单地将文案按句号分割
        sentences = [s.strip() for s in request.script_content.split('。') if s.strip()]
        
        # 如果句子数量不够，按照目标数量进行均匀分割
        if len(sentences) < request.target_scene_count:
            # 按字符数分割
            content_length = len(request.script_content)
            segment_length = content_length // request.target_scene_count
            
            scenes = []
            for i in range(request.target_scene_count):
                start_idx = i * segment_length
                end_idx = (i + 1) * segment_length if i < request.target_scene_count - 1 else content_length
                
                segment = request.script_content[start_idx:end_idx].strip()
                
                scene = Scene(
                    sequence=i + 1,
                    content=segment,
                    image_prompt=self._generate_fallback_image_prompt(segment, i + 1),
                    duration_seconds=request.scene_duration,
                    animation_type="轻微放大",
                    subtitle_text=segment[:50] + "..." if len(segment) > 50 else segment
                )
                
                scenes.append(scene)
        else:
            # 如果句子太多，合并一些句子
            scenes_per_sentence = len(sentences) // request.target_scene_count
            scenes = []
            
            for i in range(request.target_scene_count):
                start_idx = i * scenes_per_sentence
                end_idx = (i + 1) * scenes_per_sentence if i < request.target_scene_count - 1 else len(sentences)
                
                content = '。'.join(sentences[start_idx:end_idx]) + '。'
                
                scene = Scene(
                    sequence=i + 1,
                    content=content,
                    image_prompt=self._generate_fallback_image_prompt(content, i + 1),
                    duration_seconds=request.scene_duration,
                    animation_type="轻微放大",
                    subtitle_text=content[:50] + "..." if len(content) > 50 else content
                )
                
                scenes.append(scene)
        
        return scenes
    
    def _generate_fallback_image_prompt(self, content: str, sequence: int) -> str:
        """
        生成退化图像提示词（基于内容而非占位符）
        
        Args:
            content: 场景内容
            sequence: 场景序号
        
        Returns:
            str: 图像提示词
        """
        import re
        
        # 提取关键词来生成图像描述
        keywords = {
            'characters': [],
            'places': [],
            'actions': [],
            'objects': []
        }
        
        # 常见历史人物名称
        historical_figures = ['秦始皇', '嬴政', '朱元璋', '汉武帝', '唐太宗', '康熙', '乾隆', '武则天', '李世民', '刘邦', '项羽']
        for figure in historical_figures:
            if figure in content:
                keywords['characters'].append(figure)
        
        # 常见地点
        places = ['咸阳', '长安', '北京', '南京', '洛阳', '汴梁', '宫殿', '皇宫', '城墙', '战场', '朝堂']
        for place in places:
            if place in content:
                keywords['places'].append(place)
        
        # 动作词
        actions = ['战斗', '征战', '统一', '建立', '推翻', '称帝', '登基', '治理', '改革', '变法']
        for action in actions:
            if action in content:
                keywords['actions'].append(action)
        
        # 物品
        objects = ['龙袍', '铠甲', '兵器', '城池', '军队', '旗帜', '宫殿', '建筑']
        for obj in objects:
            if obj in content:
                keywords['objects'].append(obj)
        
        # 根据关键词组合生成描述
        if keywords['characters']:
            character = keywords['characters'][0]
            if keywords['places']:
                place = keywords['places'][0]
                return f"古代中国，{character}在{place}，身穿古代帝王服饰，威严庄重，历史写实风格，高清画质，昏暗色调，庄严肃穆的氛围"
            else:
                return f"古代中国，{character}身穿龙袍，面容威严，古代宫殿背景，历史写实风格，高清画质，威严庄重的氛围"
        elif keywords['places']:
            place = keywords['places'][0]
            return f"古代中国{place}，宏伟建筑，古代建筑风格，昏暗灯光，历史氛围浓厚，高清画质，庄严肃穆"
        elif keywords['actions']:
            action = keywords['actions'][0]
            return f"古代中国历史场景，{action}主题，古代服饰，传统建筑背景，历史写实风格，高清画质，威严肃穆的氛围"
        else:
            # 最后的通用描述
            return f"古代中国历史场景，传统服装，古代建筑，昏暗色调，历史写实风格，高清画质，庄严肃穆的氛围"
    
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
    
    def get_splitting_stats(self) -> Dict[str, Any]:
        """获取分割统计信息"""
        cache_stats = self.cache.get_cache_stats()
        
        return {
            'supported_languages': self.supported_languages,
            'cache_stats': cache_stats.get('disk_cache', {}).get('scenes', {}),
            'model_config': {
                'name': self.llm_config.name,
                'temperature': self.llm_config.temperature,
                'max_tokens': self.llm_config.max_tokens
            }
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"SceneSplitter(model={self.llm_config.name}, languages={self.supported_languages})"