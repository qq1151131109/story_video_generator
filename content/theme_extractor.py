"""
主题标题提取器 - 基于原Coze工作流Node 1199098
从故事文案中提取2个字的核心标题
"""
import asyncio
import time
import logging
import json
from typing import Dict, Optional, Any
from dataclasses import dataclass

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from utils.llm_client_manager import LLMClientManager

@dataclass
class ThemeExtractRequest:
    """主题提取请求"""
    content: str           # 故事文案内容
    language: str = "zh"   # 语言代码

@dataclass
class ThemeExtractResult:
    """主题提取结果"""
    success: bool                 # 是否成功
    title: str                    # 提取的2字标题
    processing_time: float        # 处理时间
    error_message: str = ""       # 错误信息

class ThemeExtractor:
    """
    主题标题提取器
    
    基于原Coze工作流的主题提取逻辑：
    - 从历史故事中提取最核心的主题
    - 生成一个2个字的标题
    - 要求朗朗上口，有视觉冲击力
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 cache_manager: CacheManager, file_manager: FileManager):
        self.config = config_manager
        self.cache = cache_manager  # May be None
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.content')
        
        # 获取LLM配置
        self.llm_config = config_manager.get_llm_config('theme_extraction')
        if not self.llm_config:
            # 使用脚本生成的配置作为后备
            self.llm_config = config_manager.get_llm_config('script_generation')
            
        # 初始化多提供商LLM客户端管理器
        self.llm_manager = LLMClientManager(config_manager)
        
        self.logger.info("ThemeExtractor initialized")
    
    async def extract_theme_async(self, request: ThemeExtractRequest) -> ThemeExtractResult:
        """
        异步提取主题标题
        
        Args:
            request: 主题提取请求
        
        Returns:
            ThemeExtractResult: 提取结果
        """
        start_time = time.time()
        
        try:
            # 检查缓存
            cache_key = self.cache.get_cache_key({
                'content': request.content[:200],  # 使用前200字作为缓存键
                'language': request.language,
                'type': 'theme_extraction'
            }) if self.cache else None
            
            cached_result = self.cache.get('scripts', cache_key) if self.cache and cache_key else None
            if cached_result:
                self.logger.info("Cache hit for theme extraction")
                cached_result['processing_time'] = time.time() - start_time
                return ThemeExtractResult(**cached_result)
            
            # 构建提示词
            system_prompt = self._build_system_prompt(request.language)
            user_prompt = self._build_user_prompt(request.content, request.language)
            
            # 调用LLM - 使用openai.AsyncOpenAI
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            self.logger.info(f"Extracting theme from content: {len(request.content)} characters")
            
            # 使用多提供商fallback机制调用LLM
            # 将system和user消息合并为单个prompt
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            content = await self.llm_manager.call_llm_with_fallback(
                prompt=combined_prompt,
                task_type='theme_extraction',
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens
            )
            
            # 解析结果
            title = self._parse_response(content)
            
            # 验证结果
            if not self._validate_title(title):
                raise ValueError(f"Generated title '{title}' does not meet requirements")
            
            # 创建结果对象
            result = ThemeExtractResult(
                success=True,
                title=title,
                processing_time=time.time() - start_time
            )
            
            # 缓存结果
            cache_data = {
                'success': result.success,
                'title': result.title
            }
            if self.cache and cache_key:
                self.cache.set('scripts', cache_key, cache_data)
            
            self.logger.info(f"Theme extracted: '{title}' in {result.processing_time:.2f}s")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Theme extraction failed: {e}"
            self.logger.error(error_msg)
            
            return ThemeExtractResult(
                success=False,
                title="",
                processing_time=processing_time,
                error_message=error_msg
            )
    
    def _build_system_prompt(self, language: str) -> str:
        """构建系统提示词"""
        if language == "zh":
            return """你是一个专业的标题提取专家。你的任务是从历史故事中提取最核心的主题，生成一个2个字的标题。

要求：
1. 必须是2个汉字
2. 概括故事核心主题
3. 朗朗上口，有视觉冲击力
4. 适合作为视频标题显示
5. 例如：赤壁、长城、变法、征战、统一、焚书

直接输出2个字，不要其他解释。"""
        else:
            return """You are a professional title extraction expert. Extract the core theme from historical stories and generate a 2-character title.

Requirements:
1. Must be exactly 2 Chinese characters
2. Summarize the core theme of the story
3. Catchy and visually impactful
4. Suitable for video title display
5. Examples: 赤壁, 长城, 变法, 征战, 统一, 焚书

Output only the 2 characters, no other explanation."""
    
    def _build_user_prompt(self, content: str, language: str) -> str:
        """构建用户提示词"""
        if language == "zh":
            return f"""请从以下历史故事中提取2个字的核心标题：

{content}

标题："""
        else:
            return f"""Please extract a 2-character core title from the following historical story:

{content}

Title:"""
    
    def _parse_response(self, response: str) -> str:
        """解析LLM响应"""
        title = response.strip()
        
        # 移除可能的标点符号和多余文本
        import re
        # 提取中文字符
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', title)
        
        if len(chinese_chars) >= 2:
            return ''.join(chinese_chars[:2])
        elif len(chinese_chars) == 1:
            # 如果只有一个字符，尝试从原始响应中找更多
            return chinese_chars[0] + '史'  # 添加默认后缀
        else:
            # 如果没有中文字符，使用默认标题
            return "历史"
    
    def _validate_title(self, title: str) -> bool:
        """验证标题是否符合要求"""
        if not title:
            return False
        
        # 检查是否为2个中文字符
        import re
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', title)
        
        return len(chinese_chars) == 2
    
    def extract_theme_sync(self, request: ThemeExtractRequest) -> ThemeExtractResult:
        """
        同步提取主题标题（对异步方法的包装）
        
        Args:
            request: 主题提取请求
        
        Returns:
            ThemeExtractResult: 提取结果
        """
        return asyncio.run(self.extract_theme_async(request))
    
    def get_extraction_stats(self) -> Dict[str, Any]:
        """获取提取统计信息"""
        cache_stats = self.cache.get_cache_stats() if self.cache else {}
        
        return {
            'cache_stats': cache_stats.get('disk_cache', {}).get('scripts', {}),
            'llm_config': {
                'model': self.llm_config.get('model', 'unknown'),
                'max_tokens': self.llm_config.get('max_tokens', 0),
                'temperature': self.llm_config.get('temperature', 0)
            }
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ThemeExtractor(model={self.llm_config.get('model', 'unknown')})"