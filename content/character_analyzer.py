"""
主角分析器 - 分析故事中的主要角色
对应原工作流Node_1301843配置
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
from utils.llm_client_manager import LLMClientManager

@dataclass
class Character:
    """角色信息"""
    name: str                 # 角色名称
    description: str          # 角色描述
    role: str                # 角色定位（主角、配角等）
    appearance: str          # 外貌描述
    personality: str         # 性格特征
    historical_significance: str  # 历史意义
    image_prompt: str        # 图像生成提示词

@dataclass
class CharacterAnalysisRequest:
    """角色分析请求"""
    script_content: str      # 故事内容
    language: str           # 语言代码
    max_characters: int = 3 # 最大角色数量

@dataclass
class CharacterAnalysisResult:
    """角色分析结果"""
    characters: List[Character]  # 角色列表
    main_character: Optional[Character]  # 主角
    language: str           # 语言
    original_script: str    # 原始文案
    analysis_time: float    # 分析耗时
    model_used: str         # 使用的模型

class CharacterAnalyzer:
    """
    主角分析器
    
    基于原Coze工作流Node_1301843配置：
    - 模型: DeepSeek-V3
    - Temperature: 0.8
    - Max tokens: 8192
    - 分析历史故事中的主要角色
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 cache_manager, file_manager: FileManager):
        self.config = config_manager
        # 缓存已删除
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.content')
        
        # 支持的语言 - 必须在加载提示词模板之前设置
        self.supported_languages = self.config.get_supported_languages()
        
        # 获取LLM配置
        self.llm_config = self.config.get_llm_config('character_analysis')
        
        # 初始化多提供商LLM客户端管理器
        self.llm_manager = LLMClientManager(config_manager)
        
        # 加载提示词模板
        self._load_prompt_templates()
    
    
    def _load_prompt_templates(self):
        """加载提示词模板"""
        self.prompt_templates = {}
        prompts_dir = Path("config/prompts")
        
        for lang in self.supported_languages:
            lang_dir = prompts_dir / lang
            if lang_dir.exists():
                # 加载角色分析提示词
                char_prompt_file = lang_dir / "character_analysis.txt"
                if char_prompt_file.exists():
                    try:
                        content = self.file_manager.load_text(char_prompt_file)
                        if content:
                            self.prompt_templates[lang] = content
                            self.logger.debug(f"Loaded character analysis prompt for language: {lang}")
                    except Exception as e:
                        self.logger.error(f"Failed to load character analysis prompt for {lang}: {e}")
        
        if not self.prompt_templates:
            self.logger.warning("No character analysis prompts loaded, using default templates")
            self._create_default_prompts()
    
    def _create_default_prompts(self):
        """创建默认提示词模板"""
        self.prompt_templates = {
            'zh': """# 角色
你是一个专业的历史故事分析师，负责从历史故事中分析和提取主要角色信息。

## 技能
### 技能1：角色分析
1. 从输入的历史故事中识别主要角色
2. 分析每个角色的外貌、性格、历史意义
3. 为每个角色生成详细的图像生成提示词
4. 识别故事的主角
5. 确保角色描述符合历史背景

## 输出格式
请严格按照以下JSON格式输出：

```json
{
  "characters": [
    {
      "name": "角色名称",
      "description": "角色详细描述",
      "role": "主角/配角/反派",
      "appearance": "外貌特征描述",
      "personality": "性格特征描述",
      "historical_significance": "历史意义和背景",
      "image_prompt": "角色图像生成提示词，古代恐怖风格，白色背景，昏暗色调，暮色中，庄严肃穆，威严庄重，营造紧张氛围，古代服饰，传统服装，线条粗糙，清晰，人物特写，笔触粗糙，高清，高对比度，低饱和度颜色，浅景深"
    }
  ],
  "main_character": {
    "name": "主角名称",
    "description": "主角详细描述"
  }
}
```

## 限制
1. 最多分析3个主要角色
2. 图像提示词必须包含指定的风格要素
3. 角色描述要符合历史背景
4. 必须明确标识主角

现在请分析以下历史故事中的角色：

{{content}}""",

            'en': """# Role
You are a professional historical story analyst responsible for analyzing and extracting main character information from historical stories.

## Skills
### Skill 1: Character Analysis
1. Identify main characters from the input historical story
2. Analyze each character's appearance, personality, and historical significance
3. Generate detailed image generation prompts for each character
4. Identify the protagonist of the story
5. Ensure character descriptions match historical context

## Output Format
Please output strictly in the following JSON format:

```json
{
  "characters": [
    {
      "name": "Character name",
      "description": "Detailed character description",
      "role": "protagonist/supporting/antagonist",
      "appearance": "Physical appearance description",
      "personality": "Personality traits description", 
      "historical_significance": "Historical significance and background",
      "image_prompt": "Character image generation prompt, ancient horror style, white background, dim colors, in twilight, solemn atmosphere, majestic and dignified, creating tense atmosphere, ancient clothing, traditional garments, rough lines, clear, character close-up, rough brushstrokes, high definition, high contrast, low saturation colors, shallow depth of field"
    }
  ],
  "main_character": {
    "name": "Protagonist name",
    "description": "Detailed protagonist description"
  }
}
```

## Constraints
1. Analyze at most 3 main characters
2. Image prompts must include specified style elements
3. Character descriptions must match historical context
4. Must clearly identify the protagonist

Now please analyze the characters in the following historical story:

{{content}}""",

            'es': """# Rol
Eres un analista profesional de historias históricas responsable de analizar y extraer información de personajes principales de historias históricas.

## Habilidades
### Habilidad 1: Análisis de Personajes
1. Identificar personajes principales de la historia histórica de entrada
2. Analizar la apariencia, personalidad y significado histórico de cada personaje
3. Generar indicaciones detalladas de generación de imágenes para cada personaje
4. Identificar el protagonista de la historia
5. Asegurar que las descripciones de personajes coincidan con el contexto histórico

## Formato de Salida
Por favor, genera estrictamente en el siguiente formato JSON:

```json
{
  "characters": [
    {
      "name": "Nombre del personaje",
      "description": "Descripción detallada del personaje",
      "role": "protagonista/secundario/antagonista",
      "appearance": "Descripción de apariencia física",
      "personality": "Descripción de rasgos de personalidad",
      "historical_significance": "Significado histórico y trasfondo",
      "image_prompt": "Indicación de generación de imagen del personaje, estilo de horror antiguo, fondo blanco, colores tenues, en el crepúsculo, atmósfera solemne, majestuoso y digno, creando atmósfera tensa, ropa antigua, vestimenta tradicional, líneas rugosas, claro, primer plano del personaje, pinceladas rugosas, alta definición, alto contraste, colores de baja saturación, poca profundidad de campo"
    }
  ],
  "main_character": {
    "name": "Nombre del protagonista",
    "description": "Descripción detallada del protagonista"
  }
}
```

## Restricciones
1. Analizar como máximo 3 personajes principales
2. Las indicaciones de imagen deben incluir elementos de estilo especificados
3. Las descripciones de personajes deben coincidir con el contexto histórico
4. Debe identificar claramente el protagonista

Ahora por favor analiza los personajes en la siguiente historia histórica:

{{content}}"""
        }
    
    async def analyze_characters_async(self, request: CharacterAnalysisRequest) -> CharacterAnalysisResult:
        """
        异步分析角色
        
        Args:
            request: 角色分析请求
        
        Returns:
            CharacterAnalysisResult: 分析结果
        """
        start_time = time.time()
        
        try:
            # 缓存已禁用 - 每次都生成新内容
            
            # 验证请求
            if request.language not in self.supported_languages:
                raise ValueError(f"Unsupported language: {request.language}")
            
            if request.language not in self.prompt_templates:
                raise ValueError(f"No prompt template for language: {request.language}")
            
            # 构建提示词
            prompt_template = self.prompt_templates[request.language]
            prompt = prompt_template.replace('{{content}}', request.script_content)
            
            # 调用LLM API
            self.logger.info(f"Analyzing characters for {request.language} script...")
            
            response = await self._call_llm_api(prompt)
            
            if not response:
                raise ValueError("Empty response from LLM")
            
            # 解析响应
            characters, main_character = self._parse_characters_response(response, request)
            
            # 创建结果对象
            result = CharacterAnalysisResult(
                characters=characters,
                main_character=main_character,
                language=request.language,
                original_script=request.script_content,
                analysis_time=time.time() - start_time,
                model_used=self.llm_config.name
            )
            
            # 缓存结果
            cache_data = {
                'characters': [self._character_to_dict(char) for char in characters],
                'main_character': self._character_to_dict(main_character) if main_character else None,
                'language': result.language,
                'original_script': result.original_script,
                'model_used': result.model_used
            }
            
            # 缓存已禁用
            
            # 记录日志
            logger = self.config.get_logger('story_generator')
            logger.info(f"Content generation - Type: character_analysis, Language: {request.language}, "
                       f"Input: {len(request.script_content)} chars, Output: {len(json.dumps(cache_data, ensure_ascii=False))} chars, "
                       f"Time: {result.analysis_time:.2f}s")
            
            self.logger.info(f"Analyzed characters successfully: {len(characters)} characters in {result.analysis_time:.2f}s")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Character analysis failed: {e}")
            
            # 记录错误日志
            logger = self.config.get_logger('story_generator')
            logger.error(f"Content generation failed - Type: character_analysis, Language: {request.language}, "
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
            content = await self.llm_manager.call_llm_with_fallback(
                prompt=prompt,
                task_type='character_analysis',
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens
            )
            
            if not content:
                raise ValueError("Empty response from all LLM providers")
            
            return content.strip()
            
        except Exception as e:
            self.logger.error(f"LLM API call failed: {e}")
            raise
    
    def _parse_characters_response(self, response: str, request: CharacterAnalysisRequest) -> Tuple[List[Character], Optional[Character]]:
        """
        解析角色分析响应
        
        Args:
            response: LLM响应
            request: 原始请求
        
        Returns:
            Tuple[List[Character], Optional[Character]]: 角色列表和主角
        """
        try:
            # 尝试提取JSON部分
            json_content = self._extract_json_from_response(response)
            
            if not json_content:
                raise ValueError("No valid JSON found in response")
            
            data = json.loads(json_content)
            
            characters = []
            main_character = None
            
            # 解析角色列表
            if 'characters' in data:
                for char_data in data['characters']:
                    character = Character(
                        name=char_data.get('name', '未知角色'),
                        description=char_data.get('description', ''),
                        role=char_data.get('role', '配角'),
                        appearance=char_data.get('appearance', ''),
                        personality=char_data.get('personality', ''),
                        historical_significance=char_data.get('historical_significance', ''),
                        image_prompt=char_data.get('image_prompt', '')
                    )
                    
                    characters.append(character)
            
            # 解析主角
            if 'main_character' in data and data['main_character']:
                main_char_data = data['main_character']
                
                # 查找主角是否在角色列表中
                for char in characters:
                    if char.name == main_char_data.get('name'):
                        main_character = char
                        break
                
                # 如果没找到，创建主角对象
                if not main_character and main_char_data.get('name'):
                    main_character = Character(
                        name=main_char_data.get('name', '主角'),
                        description=main_char_data.get('description', ''),
                        role='主角',
                        appearance='',
                        personality='',
                        historical_significance='',
                        image_prompt=''
                    )
            
            # 如果没有明确的主角，选择第一个角色作为主角
            if not main_character and characters:
                main_character = characters[0]
            
            # 限制角色数量
            if len(characters) > request.max_characters:
                characters = characters[:request.max_characters]
            
            return characters, main_character
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            self.logger.error(f"Raw LLM response that caused JSON error: {response[:1000]}...")
            raise ValueError(f"LLM returned invalid JSON format: {e}")
        except Exception as e:
            self.logger.error(f"Character parsing error: {e}")
            self.logger.error(f"Raw LLM response: {response[:1000]}...")
            raise
    
    def _extract_json_from_response(self, response: str) -> Optional[str]:
        """从响应中提取JSON内容"""
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
    
    # FALLBACK LOGIC REMOVED - 不再使用退化逻辑掩盖问题
    
    def _character_to_dict(self, character: Character) -> Dict[str, Any]:
        """将Character对象转换为字典"""
        return {
            'name': character.name,
            'description': character.description,
            'role': character.role,
            'appearance': character.appearance,
            'personality': character.personality,
            'historical_significance': character.historical_significance,
            'image_prompt': character.image_prompt
        }
    
    def analyze_characters_sync(self, request: CharacterAnalysisRequest) -> CharacterAnalysisResult:
        """
        同步分析角色（对异步方法的包装）
        
        Args:
            request: 角色分析请求
        
        Returns:
            CharacterAnalysisResult: 分析结果
        """
        return asyncio.run(self.analyze_characters_async(request))
    
    async def batch_analyze_characters(self, requests: List[CharacterAnalysisRequest], 
                                     max_concurrent: int = 2) -> List[CharacterAnalysisResult]:
        """
        批量角色分析
        
        Args:
            requests: 分析请求列表
            max_concurrent: 最大并发数
        
        Returns:
            List[CharacterAnalysisResult]: 分析结果列表
        """
        self.logger.info(f"Starting batch character analysis: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_with_semaphore(request: CharacterAnalysisRequest) -> CharacterAnalysisResult:
            async with semaphore:
                return await self.analyze_characters_async(request)
        
        # 执行并发分析
        tasks = [analyze_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch character analysis failed for request {i}: {result}")
                failed_count += 1
            else:
                successful_results.append(result)
        
        self.logger.info(f"Batch character analysis completed: {len(successful_results)} successful, {failed_count} failed")
        
        return successful_results
    
    def save_characters(self, result: CharacterAnalysisResult, output_dir: Optional[str] = None) -> str:
        """
        保存角色分析结果到文件
        
        Args:
            result: 角色分析结果
            output_dir: 输出目录（可选）
        
        Returns:
            str: 保存的文件路径
        """
        if not output_dir:
            filename = self.file_manager.generate_filename(
                content=result.original_script,
                prefix=f"characters_{result.language}",
                extension="json"
            )
            filepath = self.file_manager.get_output_path('scripts', filename)  # 使用scripts目录
        else:
            filepath = Path(output_dir) / f"characters_{result.language}_{int(time.time())}.json"
        
        # 准备保存数据
        save_data = {
            'metadata': {
                'language': result.language,
                'character_count': len(result.characters),
                'model_used': result.model_used,
                'analysis_time': result.analysis_time,
                'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
            },
            'original_script': result.original_script,
            'main_character': self._character_to_dict(result.main_character) if result.main_character else None,
            'characters': [self._character_to_dict(char) for char in result.characters]
        }
        
        success = self.file_manager.save_json(save_data, filepath)
        
        if success:
            self.logger.info(f"Saved characters to: {filepath}")
            return str(filepath)
        else:
            raise Exception(f"Failed to save characters to: {filepath}")
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """获取分析统计信息"""
        # 缓存已删除
        
        return {
            'supported_languages': self.supported_languages,
            # 缓存已删除
            'model_config': {
                'name': self.llm_config.name,
                'temperature': self.llm_config.temperature,
                'max_tokens': self.llm_config.max_tokens
            }
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"CharacterAnalyzer(model={self.llm_config.name}, languages={self.supported_languages})"