#!/usr/bin/env python3
"""
增强的LLM管理器 - 支持OpenAI Structured Output + 多层降级
"""

import asyncio
import logging
import os
from typing import Type, TypeVar, Any, Dict, List, Optional, Union
from enum import Enum

# LangChain核心组件
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain.output_parsers import RetryOutputParser, OutputFixingParser
from pydantic import BaseModel

# 导入现有组件
from core.config_manager import ConfigManager
from utils.structured_output_models import (
    SceneSplitOutput, ImagePromptOutput, CharacterAnalysisOutput, ScriptGenerationOutput
)

T = TypeVar('T', bound=BaseModel)

class ParseStrategy(Enum):
    """解析策略枚举"""
    STRUCTURED_OUTPUT = "structured_output"  # OpenAI Structured Output
    RETRY_PARSER = "retry_parser"            # 重试解析器  
    OUTPUT_FIXING = "output_fixing"          # 输出修复解析器
    CUSTOM_ROBUST = "custom_robust"          # 自定义鲁棒解析

class EnhancedLLMManager:
    """
    增强的LLM管理器
    
    特点:
    1. 优先使用OpenRouter的OpenAI GPT-4.1 + Structured Output
    2. Gemini作为fallback模型
    3. RetryOutputParser作为降级方案
    4. 多层自动降级架构
    """
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.logger = logging.getLogger('enhanced_llm_manager')
        
        # 解析器缓存
        self._structured_models = {}
        self._retry_parsers = {}
        self._fixing_parsers = {}
        
        # 初始化LLM客户端
        self._init_llm_clients()
        
        # 加载解析策略配置
        self.parsing_config = config.config.get('llm', {}).get('parsing_strategy', {})
        self.primary_strategy = self.parsing_config.get('primary', 'structured_output')
        self.fallback_strategies = self.parsing_config.get('fallback_strategies', 
                                                          ['retry_parser', 'output_fixing', 'custom_robust'])
        
        self.logger.info(f"✅ 增强LLM管理器初始化完成")
        self.logger.info(f"🎯 主要策略: {self.primary_strategy}")
        self.logger.info(f"🔄 降级策略: {self.fallback_strategies}")
    
    def _init_llm_clients(self):
        """初始化LLM客户端"""
        
        # 获取OpenRouter配置
        openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        openrouter_base_url = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
        
        if not openrouter_api_key:
            self.logger.warning("⚠️ 未找到OPENROUTER_API_KEY环境变量")
            self.primary_llm = None
            self.fallback_llm = None
            return
        
        # 主LLM: OpenAI GPT-4.1 (通过OpenRouter)
        structured_config = self.config.config.get('llm', {}).get('structured_output', {})
        
        try:
            self.primary_llm = ChatOpenAI(
                model="openai/gpt-4.1",
                api_key=openrouter_api_key,
                base_url=openrouter_base_url,
                temperature=structured_config.get('temperature', 0.1),
                max_tokens=structured_config.get('max_tokens', 16384),
                timeout=120,  # 增加超时时间
                max_retries=3,  # 增加重试次数
                request_timeout=60  # 请求超时
            )
            self.logger.info("✅ 主LLM (OpenAI GPT-4.1) 初始化成功")
        except Exception as e:
            self.logger.error(f"❌ 主LLM初始化失败: {e}")
            self.primary_llm = None
        
        # Fallback LLM: Gemini (通过OpenRouter)  
        try:
            self.fallback_llm = ChatOpenAI(
                model="google/gemini-2.5-flash",
                api_key=openrouter_api_key,
                base_url=openrouter_base_url,
                temperature=0.8,
                max_tokens=81920,
                timeout=120,  # 增加超时时间
                max_retries=3,  # 增加重试次数
                request_timeout=60  # 请求超时
            )
            self.logger.info("✅ Fallback LLM (Gemini) 初始化成功")
        except Exception as e:
            self.logger.error(f"❌ Fallback LLM初始化失败: {e}")
            self.fallback_llm = None
    
    def get_structured_model(self, pydantic_model: Type[T]):
        """获取支持Structured Output的模型"""
        if not self.primary_llm:
            return None
            
        model_name = pydantic_model.__name__
        
        if model_name not in self._structured_models:
            try:
                # 检查是否启用strict模式
                structured_config = self.config.config.get('llm', {}).get('structured_output', {})
                strict_mode = structured_config.get('strict_mode', True)
                
                # 使用OpenAI兼容的Structured Output
                # 注意：OpenRouter可能不支持strict=True，所以我们使用function_calling方法
                structured_model = self.primary_llm.with_structured_output(
                    pydantic_model,
                    method="function_calling"  # OpenRouter更兼容function calling
                )
                
                self._structured_models[model_name] = structured_model
                self.logger.info(f"✅ 创建Structured Output模型: {model_name}")
                
            except Exception as e:
                self.logger.warning(f"⚠️ 无法创建Structured Output模型 {model_name}: {e}")
                return None
        
        return self._structured_models[model_name]
    
    def get_retry_parser(self, pydantic_model: Type[T]) -> Optional[RetryOutputParser]:
        """获取重试解析器"""
        if not self.fallback_llm:
            return None
            
        model_name = pydantic_model.__name__
        
        if model_name not in self._retry_parsers:
            try:
                base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
                retry_parser = RetryOutputParser.from_llm(
                    parser=base_parser,
                    llm=self.fallback_llm,
                    max_retries=3
                )
                
                self._retry_parsers[model_name] = retry_parser
                self.logger.info(f"✅ 创建RetryOutputParser: {model_name}")
                
            except Exception as e:
                self.logger.warning(f"⚠️ 无法创建RetryOutputParser {model_name}: {e}")
                return None
        
        return self._retry_parsers[model_name]
    
    def get_fixing_parser(self, pydantic_model: Type[T]) -> Optional[OutputFixingParser]:
        """获取修复解析器"""
        if not self.fallback_llm:
            return None
            
        model_name = pydantic_model.__name__
        cache_key = f"{model_name}_fixing"
        
        if cache_key not in self._fixing_parsers:
            try:
                base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
                fixing_parser = OutputFixingParser.from_llm(
                    parser=base_parser,
                    llm=self.fallback_llm
                )
                
                self._fixing_parsers[cache_key] = fixing_parser
                self.logger.info(f"✅ 创建OutputFixingParser: {model_name}")
                
            except Exception as e:
                self.logger.warning(f"⚠️ 无法创建OutputFixingParser {model_name}: {e}")
                return None
        
        return self._fixing_parsers[cache_key]
    
    async def generate_structured_output(self,
                                       task_type: str,
                                       system_prompt: str,
                                       user_prompt: str,
                                       max_retries: int = 2) -> Any:
        """
        生成结构化输出 - 使用多层降级策略
        
        Args:
            task_type: 任务类型 ('scene_splitting', 'image_prompt_generation', etc.)
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            max_retries: 最大重试次数
            
        Returns:
            解析后的结构化对象
        """
        
        # 根据任务类型选择Pydantic模型
        pydantic_model = self._get_pydantic_model_for_task(task_type)
        if not pydantic_model:
            raise ValueError(f"未支持的任务类型: {task_type}")
        
        # 使用多层降级策略
        return await self._generate_with_auto_fallback(
            pydantic_model, system_prompt, user_prompt, max_retries
        )
    
    def _get_pydantic_model_for_task(self, task_type: str) -> Optional[Type[BaseModel]]:
        """根据任务类型获取对应的Pydantic模型"""
        model_mapping = {
            'scene_splitting': SceneSplitOutput,
            'image_prompt_generation': ImagePromptOutput,
            'character_analysis': CharacterAnalysisOutput,
            'script_generation': ScriptGenerationOutput,
        }
        return model_mapping.get(task_type)
    
    async def _generate_with_auto_fallback(self,
                                         pydantic_model: Type[T],
                                         system_prompt: str,
                                         user_prompt: str,
                                         max_retries: int = 2) -> T:
        """
        自动降级策略 - 从最可靠的方法开始逐步降级
        """
        
        errors = []
        
        # 策略1: OpenAI Structured Output (最可靠)
        if self.primary_strategy == "structured_output":
            try:
                self.logger.info("🚀 尝试OpenAI Structured Output...")
                result = await self._generate_with_structured_output(
                    pydantic_model, system_prompt, user_prompt
                )
                self.logger.info("✅ OpenAI Structured Output 成功!")
                return result
            except Exception as e:
                error_msg = f"OpenAI Structured Output失败: {e}"
                errors.append(error_msg)
                self.logger.warning(f"⚠️ {error_msg}")
        
        # 降级策略执行
        for strategy in self.fallback_strategies:
            try:
                if strategy == "retry_parser":
                    self.logger.info("🔄 降级到RetryOutputParser...")
                    result = await self._generate_with_retry_parser(
                        pydantic_model, system_prompt, user_prompt
                    )
                    self.logger.info("✅ RetryOutputParser 成功!")
                    return result
                    
                elif strategy == "output_fixing":
                    self.logger.info("🔧 降级到OutputFixingParser...")
                    result = await self._generate_with_fixing_parser(
                        pydantic_model, system_prompt, user_prompt
                    )
                    self.logger.info("✅ OutputFixingParser 成功!")
                    return result
                    
                elif strategy == "custom_robust":
                    self.logger.info("📝 降级到自定义鲁棒解析...")
                    result = await self._generate_with_custom_robust(
                        pydantic_model, system_prompt, user_prompt
                    )
                    self.logger.info("✅ 自定义鲁棒解析 成功!")
                    return result
                    
            except Exception as e:
                error_msg = f"{strategy}失败: {e}"
                errors.append(error_msg)
                self.logger.warning(f"⚠️ {error_msg}")
        
        # 所有策略都失败
        all_errors = "; ".join(errors)
        raise Exception(f"所有解析策略都失败: {all_errors}")
    
    async def _generate_with_structured_output(self, 
                                             pydantic_model: Type[T],
                                             system_prompt: str,
                                             user_prompt: str) -> T:
        """使用OpenAI Structured Output生成"""
        structured_model = self.get_structured_model(pydantic_model)
        
        if not structured_model:
            raise Exception("OpenAI Structured Output模型未初始化")
        
        # 创建消息
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 使用Structured Output
        result = await structured_model.ainvoke(messages)
        return result
    
    async def _generate_with_retry_parser(self,
                                        pydantic_model: Type[T],
                                        system_prompt: str,
                                        user_prompt: str) -> T:
        """使用RetryOutputParser生成"""
        retry_parser = self.get_retry_parser(pydantic_model)
        
        if not retry_parser:
            raise Exception("RetryOutputParser未初始化")
        
        # 增强提示词包含格式说明
        base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
        format_instructions = base_parser.get_format_instructions()
        
        enhanced_system_prompt = f"""
{system_prompt}

{format_instructions}

输出要求: 必须是有效的JSON格式，严格遵循上述Schema。
"""
        
        # 生成完整prompt用于重试上下文
        full_prompt = f"System: {enhanced_system_prompt}\nUser: {user_prompt}"
        
        # 调用LLM
        messages = [
            SystemMessage(content=enhanced_system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await self.fallback_llm.ainvoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # 使用RetryOutputParser解析
        from langchain_core.prompt_values import StringPromptValue
        prompt_value = StringPromptValue(text=full_prompt)
        
        result = retry_parser.parse_with_prompt(response_text, prompt_value)
        return result
    
    async def _generate_with_fixing_parser(self,
                                         pydantic_model: Type[T],
                                         system_prompt: str,
                                         user_prompt: str) -> T:
        """使用OutputFixingParser生成"""
        fixing_parser = self.get_fixing_parser(pydantic_model)
        
        if not fixing_parser:
            raise Exception("OutputFixingParser未初始化")
        
        # 增强提示词
        base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
        format_instructions = base_parser.get_format_instructions()
        
        enhanced_system_prompt = f"""
{system_prompt}

{format_instructions}

输出要求: 必须是有效的JSON格式，严格遵循上述Schema。
"""
        
        # 调用LLM
        messages = [
            SystemMessage(content=enhanced_system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await self.fallback_llm.ainvoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # 使用OutputFixingParser解析
        result = fixing_parser.parse(response_text)
        return result
    
    async def _generate_with_custom_robust(self,
                                         pydantic_model: Type[T],
                                         system_prompt: str,
                                         user_prompt: str) -> T:
        """使用自定义鲁棒解析器生成"""
        from utils.robust_output_parser import RobustStructuredOutputParser
        
        parser = RobustStructuredOutputParser(pydantic_model)
        
        # 使用任何可用的LLM
        llm = self.fallback_llm or self.primary_llm
        if not llm:
            raise Exception("没有可用的LLM")
        
        # 增强提示词
        base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
        format_instructions = base_parser.get_format_instructions()
        
        enhanced_system_prompt = f"""
{system_prompt}

{format_instructions}

输出要求: 必须是有效的JSON格式，严格遵循上述Schema。
"""
        
        messages = [
            SystemMessage(content=enhanced_system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await llm.ainvoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # 使用自定义鲁棒解析器
        result = parser.parse(response_text)
        return result
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取当前模型配置信息"""
        return {
            "primary_model": "openai/gpt-4.1" if self.primary_llm else None,
            "fallback_model": "google/gemini-2.5-flash" if self.fallback_llm else None,
            "primary_strategy": self.primary_strategy,
            "fallback_strategies": self.fallback_strategies,
            "structured_output_enabled": bool(self.primary_llm),
            "retry_parser_enabled": bool(self.fallback_llm)
        }

    async def call_llm_with_fallback(self,
                                   prompt: str,
                                   task_type: str,
                                   temperature: Optional[float] = None,
                                   max_tokens: Optional[int] = None,
                                   **kwargs) -> str:
        """
        向后兼容方法 - 适配旧的call_llm_with_fallback接口
        
        这个方法将prompt分解为系统和用户提示词，然后调用generate_structured_output
        """
        # 简单的提示词分割策略
        # 如果prompt包含明确的system/user分隔，尝试识别
        if "System:" in prompt and "User:" in prompt:
            parts = prompt.split("User:", 1)
            system_prompt = parts[0].replace("System:", "").strip()
            user_prompt = parts[1].strip()
        else:
            # 否则将整个prompt作为用户提示词，使用空的系统提示词
            system_prompt = ""
            user_prompt = prompt
        
        try:
            # 调用结构化输出方法
            result = await self.generate_structured_output(
                task_type=task_type,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_retries=2
            )
            
            # 如果返回的是结构化对象，尝试转换为JSON格式
            if hasattr(result, 'model_dump'):
                # Pydantic模型，转换为JSON字符串
                import json
                return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
            elif hasattr(result, 'content'):
                return result.content
            elif hasattr(result, 'text'):
                return result.text
            else:
                # 其他情况，尝试转为字符串
                return str(result)
                
        except Exception as e:
            self.logger.error(f"call_llm_with_fallback compatibility method failed: {e}")
            raise


# 测试函数
async def test_enhanced_llm_manager():
    """测试增强的LLM管理器"""
    print("🧪 测试增强的LLM管理器")
    print("=" * 60)
    
    try:
        # 初始化
        config = ConfigManager()
        llm_manager = EnhancedLLMManager(config)
        
        # 显示配置信息
        info = llm_manager.get_model_info()
        print("📊 模型配置信息:")
        for key, value in info.items():
            print(f"   {key}: {value}")
        
        # 测试场景分割
        print("\n🎬 测试场景分割...")
        result = await llm_manager.generate_structured_output(
            task_type='scene_splitting',
            system_prompt="你是专业的故事场景分割专家。将输入的故事分割为多个场景，每个场景3秒钟。",
            user_prompt="请将秦始皇统一天下的故事分割为5个场景，每个场景包含不同的重要情节点。"
        )
        
        if hasattr(result, 'scenes'):
            print(f"✅ 成功解析 {len(result.scenes)} 个场景:")
            for scene in result.scenes[:3]:  # 显示前3个
                print(f"   场景{scene.sequence}: {scene.content[:50]}...")
        else:
            print(f"⚠️ 结果格式异常: {type(result)}")
            
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_enhanced_llm_manager())