"""
多语言文案生成器 - 基于DeepSeek-V3的历史故事文案生成
对应原工作流Node_121343配置
"""
import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass

from core.config_manager import ConfigManager, ModelConfig
# 缓存已删除
from utils.file_manager import FileManager
from utils.llm_client_manager import LLMClientManager

@dataclass
class ScriptGenerationRequest:
    """文案生成请求"""
    theme: str                  # 主题
    language: str              # 语言代码 (zh, en, es)
    style: str = "horror"      # 风格：horror, documentary, dramatic
    target_length: int = 800   # 目标长度（字符数）
    include_title: bool = True # 是否包含标题

@dataclass  
class GeneratedScript:
    """生成的文案"""
    title: str                 # 标题
    content: str               # 正文内容
    language: str              # 语言
    theme: str                 # 主题
    word_count: int            # 字数统计
    generation_time: float     # 生成耗时
    model_used: str            # 使用的模型

class ScriptGenerator:
    """
    多语言文案生成器
    
    基于原Coze工作流Node_121343配置：
    - 模型: DeepSeek-V3
    - Temperature: 0.8  
    - Max tokens: 1024
    - 支持多语言：中文、英语、西班牙语
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
        self.llm_config = self.config.get_llm_config('script_generation')
        
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
                # 加载文案生成提示词
                script_prompt_file = lang_dir / "script_generation.txt"
                if script_prompt_file.exists():
                    try:
                        content = self.file_manager.load_text(script_prompt_file)
                        if content:
                            self.prompt_templates[lang] = content
                            self.logger.debug(f"Loaded script prompt for language: {lang}")
                    except Exception as e:
                        self.logger.error(f"Failed to load script prompt for {lang}: {e}")
        
        if not self.prompt_templates:
            self.logger.warning("No script generation prompts loaded, using default templates")
            self._create_default_prompts()
    
    def _create_default_prompts(self):
        """创建默认提示词模板"""
        self.prompt_templates = {
            'zh': """# 角色
你是一个专业的历史故事文案写手，专门创作引人入胜的历史故事。

## 技能
### 技能1：历史故事文案创作
1. 根据给定主题，创作一个引人入胜的历史故事文案
2. 文案风格要求：悬疑、恐怖、引人深思
3. 语言要生动形象，营造紧张氛围
4. 内容要有历史依据，但可以适当艺术化处理
5. 结构清晰：开场吸引注意 → 故事主体 → 结尾升华

## 限制
1. 文案长度控制在800字符左右
2. 语言风格要符合中文表达习惯
3. 内容要积极向上，不涉及敏感话题

现在请根据以下主题创作历史故事文案：

{{theme}}""",
            
            'en': """# Role
You are a professional historical storyteller who creates captivating historical narratives.

## Skills
### Skill 1: Historical Story Writing
1. Create an engaging historical story based on the given theme
2. Style requirements: mysterious, thrilling, thought-provoking
3. Use vivid language to create a tense atmosphere
4. Content should be historically grounded but can be artistically enhanced
5. Clear structure: engaging opening → main story → meaningful conclusion

## Constraints
1. Keep the script around 800 characters
2. Use natural English expression
3. Content should be positive and avoid sensitive topics

Please create a historical story based on the following theme:

{{theme}}""",
            
            'es': """# Rol
Eres un escritor profesional de historias históricas que crea narrativas históricas cautivadoras.

## Habilidades
### Habilidad 1: Escritura de Historias Históricas
1. Crear una historia histórica atractiva basada en el tema dado
2. Requisitos de estilo: misterioso, emocionante, que provoque reflexión
3. Usar un lenguaje vívido para crear una atmósfera tensa
4. El contenido debe estar basado históricamente pero puede ser mejorado artísticamente
5. Estructura clara: apertura atractiva → historia principal → conclusión significativa

## Restricciones
1. Mantener el guión alrededor de 800 caracteres
2. Usar expresión natural en español
3. El contenido debe ser positivo y evitar temas sensibles

Por favor, crea una historia histórica basada en el siguiente tema:

{{theme}}"""
        }
    
    async def generate_script_async(self, request: ScriptGenerationRequest) -> GeneratedScript:
        """
        异步生成文案
        
        Args:
            request: 文案生成请求
        
        Returns:
            GeneratedScript: 生成的文案
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
            prompt = prompt_template.replace('{{theme}}', request.theme)
            
            # 调用LLM API
            self.logger.info(f"Generating script: {request.language}/{request.theme[:20]}...")
            
            response = await self._call_llm_api(prompt)
            
            if not response:
                raise ValueError("Empty response from LLM")
            
            # 解析响应
            title, content = self._parse_response(response, request.language)
            
            # 创建结果对象
            result = GeneratedScript(
                title=title,
                content=content,
                language=request.language,
                theme=request.theme,
                word_count=len(content),
                generation_time=time.time() - start_time,
                model_used=self.llm_config.name
            )
            
            # 缓存结果
            cache_data = {
                'title': result.title,
                'content': result.content,
                'language': result.language,
                'theme': result.theme,
                'word_count': result.word_count,
                'model_used': result.model_used
            }
            
            # 缓存已禁用
            
            # 记录日志
            logger = self.config.get_logger('story_generator')
            logger.info(f"Content generation - Type: script_generation, Language: {request.language}, "
                       f"Input: {len(request.theme)} chars, Output: {len(content)} chars, "
                       f"Time: {result.generation_time:.2f}s")
            
            self.logger.info(f"Generated script successfully: {result.word_count} chars in {result.generation_time:.2f}s")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Script generation failed: {e}")
            
            # 记录错误日志
            logger = self.config.get_logger('story_generator')
            logger.error(f"Content generation failed - Type: script_generation, Language: {request.language}, "
                        f"Input: {len(request.theme)} chars, Time: {processing_time:.2f}s")
            
            raise
    
    async def _call_llm_api(self, prompt: str) -> str:
        """
        使用fallback机制调用LLM API
        
        Args:
            prompt: 提示词
        
        Returns:
            str: LLM响应
        """
        try:
            content = await self.llm_manager.call_llm_with_fallback(
                prompt=prompt,
                task_type='script_generation',
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens
            )
            
            if not content:
                raise ValueError("Empty response from all LLM providers")
            
            return content.strip()
            
        except Exception as e:
            self.logger.error(f"LLM API call failed: {e}")
            raise
    
    def _parse_response(self, response: str, language: str) -> Tuple[str, str]:
        """
        解析LLM响应，提取标题和内容
        
        Args:
            response: LLM响应
            language: 语言代码
        
        Returns:
            Tuple[str, str]: 标题和内容
        """
        lines = response.strip().split('\n')
        
        title = ""
        content_lines = []
        
        # 尝试识别标题
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # 检查是否为标题格式
            if (line.startswith('#') or 
                line.startswith('标题:') or 
                line.startswith('Title:') or 
                line.startswith('Título:')):
                title = line.lstrip('#').lstrip('标题:').lstrip('Title:').lstrip('Título:').strip()
                content_lines = lines[i+1:]
                break
            else:
                # 如果第一行看起来像标题（短且独立）
                if i == 0 and len(line) < 50 and '。' not in line and '.' not in line:
                    title = line
                    content_lines = lines[i+1:]
                    break
        
        # 如果没有识别到标题，使用第一行
        if not title and lines:
            title = lines[0][:30] + "..." if len(lines[0]) > 30 else lines[0]
            content_lines = lines
        
        # 处理内容
        content = '\n'.join(content_lines).strip()
        
        # 清理内容
        content = self._clean_content(content)
        
        return title, content
    
    def _clean_content(self, content: str) -> str:
        """清理生成的内容，移除结构标识词"""
        # 移除多余的空行
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # 结构标识词列表（需要过滤的词语）
        structure_keywords = [
            '悬念开场', '身份代入', '冲突升级', '破局细节', '主题收尾',
            '开场', '结尾', '总结', '段落', '第一部分', '第二部分',
            '**', '###', '##', '#', '创作要求', '写作技巧', '内容要求'
        ]
        
        # 移除可能的标记或格式符号
        cleaned_lines = []
        for line in lines:
            # 跳过纯标记行
            if line.startswith('---') or line.startswith('===') or line.startswith('**'):
                continue
            
            # 检查是否包含结构标识词
            contains_structure_keyword = any(keyword in line for keyword in structure_keywords)
            if contains_structure_keyword:
                self.logger.warning(f"Filtered out structure keyword in line: {line[:30]}...")
                continue
            
            # 清理行首的标记
            line = line.lstrip('- ').lstrip('* ').lstrip('> ').lstrip('1234567890. ')
            if line and len(line) > 3:  # 过滤过短的行
                cleaned_lines.append(line)
        
        cleaned_content = '\n'.join(cleaned_lines)
        
        # 最后检查：如果内容过短或仍包含结构标识，返回警告
        if len(cleaned_content) < 100:
            self.logger.warning("Generated content too short after cleaning, may need regeneration")
        
        return cleaned_content
    
    def generate_script_sync(self, request: ScriptGenerationRequest) -> GeneratedScript:
        """
        同步生成文案（对异步方法的包装）
        
        Args:
            request: 文案生成请求
        
        Returns:
            GeneratedScript: 生成的文案
        """
        return asyncio.run(self.generate_script_async(request))
    
    async def batch_generate_scripts(self, requests: List[ScriptGenerationRequest], 
                                   max_concurrent: int = 3) -> List[GeneratedScript]:
        """
        批量生成文案
        
        Args:
            requests: 文案生成请求列表
            max_concurrent: 最大并发数
        
        Returns:
            List[GeneratedScript]: 生成的文案列表
        """
        self.logger.info(f"Starting batch script generation: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(request: ScriptGenerationRequest) -> GeneratedScript:
            async with semaphore:
                return await self.generate_script_async(request)
        
        # 执行并发生成
        tasks = [generate_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
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
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """获取生成统计信息"""
        
        return {
            'supported_languages': self.supported_languages,
            'model_config': {
                'name': self.llm_config.name,
                'temperature': self.llm_config.temperature,
                'max_tokens': self.llm_config.max_tokens
            }
        }
    
    def save_script(self, script: GeneratedScript, output_dir: Optional[str] = None) -> str:
        """
        保存生成的文案到文件
        
        Args:
            script: 生成的文案
            output_dir: 输出目录（可选）
        
        Returns:
            str: 保存的文件路径
        """
        if not output_dir:
            filename = self.file_manager.generate_filename(
                content=script.content,
                prefix=f"script_{script.language}",
                extension="txt"
            )
            filepath = self.file_manager.get_output_path('scripts', filename)
        else:
            filepath = Path(output_dir) / f"script_{script.language}_{int(time.time())}.txt"
        
        # 准备保存内容
        content_to_save = f"""标题: {script.title}
语言: {script.language}  
主题: {script.theme}
字数: {script.word_count}
模型: {script.model_used}
生成时间: {script.generation_time:.2f}秒
生成于: {time.strftime('%Y-%m-%d %H:%M:%S')}

--- 文案内容 ---

{script.content}
"""
        
        success = self.file_manager.save_text(content_to_save, filepath)
        
        if success:
            self.logger.info(f"Saved script to: {filepath}")
            return str(filepath)
        else:
            raise Exception(f"Failed to save script to: {filepath}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ScriptGenerator(model={self.llm_config.name}, languages={self.supported_languages})"