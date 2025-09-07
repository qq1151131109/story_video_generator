#!/usr/bin/env python3
"""
LangChain官方方案 - 彻底解决LLM输出格式鲁棒性问题

包含2024年最新的官方解决方案:
1. with_structured_output() - OpenAI Strict Mode (100%成功率)
2. RetryOutputParser - 智能重试机制  
3. OutputFixingParser - 自动修复机制
4. 多层降级策略
"""

import asyncio
import logging
from typing import Type, TypeVar, Any, Dict, List, Optional, Literal
from enum import Enum

# LangChain核心组件
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain.output_parsers import RetryOutputParser, OutputFixingParser

# 数据模型
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.structured_output_models import (
    SceneSplitOutput, ImagePromptOutput, CharacterAnalysisOutput, ScriptGenerationOutput
)

T = TypeVar('T', bound='BaseModel')

class ParseStrategy(Enum):
    """解析策略枚举"""
    STRUCTURED_OUTPUT = "structured_output"  # OpenAI Strict Mode (最可靠)
    RETRY_PARSER = "retry_parser"            # 重试解析器
    OUTPUT_FIXING = "output_fixing"          # 输出修复解析器  
    TRADITIONAL = "traditional"              # 传统解析方法

class LangChainOfficialSolution:
    """
    LangChain官方解决方案 - 2024年最强的LLM输出格式鲁棒性方案
    
    特点:
    1. 优先使用OpenAI Structured Output (strict=True) - 100%成功率
    2. 自动降级到RetryOutputParser和OutputFixingParser  
    3. 支持多种LLM提供商
    4. 完全基于LangChain官方实现
    """
    
    def __init__(self, 
                 openai_api_key: Optional[str] = None,
                 fallback_llm = None,
                 max_retries: int = 3):
        """
        初始化LangChain官方解决方案
        
        Args:
            openai_api_key: OpenAI API密钥 (用于Structured Output)
            fallback_llm: 降级LLM (用于RetryOutputParser/OutputFixingParser)
            max_retries: 最大重试次数
        """
        self.max_retries = max_retries
        self.logger = logging.getLogger('langchain_official_solution')
        
        # OpenAI LLM (支持Structured Output)
        self.openai_llm = None
        if openai_api_key:
            self.openai_llm = ChatOpenAI(
                model="gpt-4o-2024-08-06",  # 支持Structured Output的模型
                api_key=openai_api_key,
                temperature=0  # 确保稳定性
            )
            self.logger.info("✅ OpenAI Structured Output LLM 已初始化")
        
        # 降级LLM
        self.fallback_llm = fallback_llm
        
        # 解析器缓存
        self._structured_models = {}
        self._retry_parsers = {}
        self._fixing_parsers = {}
    
    def get_structured_model(self, pydantic_model: Type[T]):
        """获取支持Structured Output的模型"""
        if not self.openai_llm:
            return None
            
        model_name = pydantic_model.__name__
        
        if model_name not in self._structured_models:
            try:
                # 使用OpenAI Structured Output (strict=True)
                structured_model = self.openai_llm.with_structured_output(
                    pydantic_model,
                    method="json_schema",  # 使用最新的JSON Schema方法
                    strict=True           # 启用严格模式 - 100%符合Schema
                )
                
                self._structured_models[model_name] = structured_model
                self.logger.info(f"✅ 创建Structured Output模型: {model_name} (strict=True)")
                
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
            base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
            retry_parser = RetryOutputParser.from_llm(
                parser=base_parser,
                llm=self.fallback_llm,
                max_retries=self.max_retries
            )
            
            self._retry_parsers[model_name] = retry_parser
            self.logger.info(f"✅ 创建RetryOutputParser: {model_name}")
        
        return self._retry_parsers[model_name]
    
    def get_fixing_parser(self, pydantic_model: Type[T]) -> Optional[OutputFixingParser]:
        """获取修复解析器"""
        if not self.fallback_llm:
            return None
            
        model_name = pydantic_model.__name__
        cache_key = f"{model_name}_fixing"
        
        if cache_key not in self._fixing_parsers:
            base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
            fixing_parser = OutputFixingParser.from_llm(
                parser=base_parser,
                llm=self.fallback_llm
            )
            
            self._fixing_parsers[cache_key] = fixing_parser
            self.logger.info(f"✅ 创建OutputFixingParser: {model_name}")
        
        return self._fixing_parsers[cache_key]
    
    async def generate_structured_output(self,
                                       pydantic_model: Type[T],
                                       system_prompt: str,
                                       user_prompt: str,
                                       strategy: ParseStrategy = ParseStrategy.STRUCTURED_OUTPUT) -> T:
        """
        生成结构化输出 - 使用指定的解析策略
        
        Args:
            pydantic_model: 目标Pydantic模型
            system_prompt: 系统提示词
            user_prompt: 用户提示词  
            strategy: 解析策略
            
        Returns:
            解析后的结构化对象
        """
        
        if strategy == ParseStrategy.STRUCTURED_OUTPUT:
            return await self._generate_with_structured_output(
                pydantic_model, system_prompt, user_prompt
            )
        elif strategy == ParseStrategy.RETRY_PARSER:
            return await self._generate_with_retry_parser(
                pydantic_model, system_prompt, user_prompt
            )
        elif strategy == ParseStrategy.OUTPUT_FIXING:
            return await self._generate_with_fixing_parser(
                pydantic_model, system_prompt, user_prompt
            )
        else:
            return await self._generate_with_traditional_parsing(
                pydantic_model, system_prompt, user_prompt
            )
    
    async def generate_with_auto_fallback(self,
                                        pydantic_model: Type[T],
                                        system_prompt: str,
                                        user_prompt: str) -> T:
        """
        自动降级策略 - 从最可靠的方法开始，逐步降级
        
        降级顺序:
        1. OpenAI Structured Output (strict=True) - 100%成功率
        2. RetryOutputParser - 智能重试
        3. OutputFixingParser - 自动修复
        4. 传统解析 - 兜底方案
        """
        
        errors = []
        
        # 策略1: OpenAI Structured Output (最可靠)
        try:
            if self.openai_llm:
                self.logger.info("🚀 尝试OpenAI Structured Output (strict=True)...")
                result = await self._generate_with_structured_output(
                    pydantic_model, system_prompt, user_prompt
                )
                self.logger.info("✅ OpenAI Structured Output 成功!")
                return result
        except Exception as e:
            error_msg = f"OpenAI Structured Output失败: {e}"
            errors.append(error_msg)
            self.logger.warning(f"⚠️ {error_msg}")
        
        # 策略2: RetryOutputParser (智能重试)  
        try:
            if self.fallback_llm:
                self.logger.info("🔄 降级到RetryOutputParser...")
                result = await self._generate_with_retry_parser(
                    pydantic_model, system_prompt, user_prompt
                )
                self.logger.info("✅ RetryOutputParser 成功!")
                return result
        except Exception as e:
            error_msg = f"RetryOutputParser失败: {e}"
            errors.append(error_msg)
            self.logger.warning(f"⚠️ {error_msg}")
        
        # 策略3: OutputFixingParser (自动修复)
        try:
            if self.fallback_llm:
                self.logger.info("🔧 降级到OutputFixingParser...")
                result = await self._generate_with_fixing_parser(
                    pydantic_model, system_prompt, user_prompt
                )
                self.logger.info("✅ OutputFixingParser 成功!")
                return result
        except Exception as e:
            error_msg = f"OutputFixingParser失败: {e}"
            errors.append(error_msg)
            self.logger.warning(f"⚠️ {error_msg}")
        
        # 策略4: 传统解析 (兜底方案)
        try:
            self.logger.info("📝 降级到传统解析方法...")
            result = await self._generate_with_traditional_parsing(
                pydantic_model, system_prompt, user_prompt
            )
            self.logger.info("✅ 传统解析方法成功!")
            return result
        except Exception as e:
            error_msg = f"传统解析方法失败: {e}"
            errors.append(error_msg)
            self.logger.error(f"❌ {error_msg}")
        
        # 所有策略都失败
        all_errors = "; ".join(errors)
        raise Exception(f"所有解析策略都失败: {all_errors}")
    
    async def _generate_with_structured_output(self, 
                                             pydantic_model: Type[T],
                                             system_prompt: str, 
                                             user_prompt: str) -> T:
        """使用OpenAI Structured Output生成 (100%成功率)"""
        structured_model = self.get_structured_model(pydantic_model)
        
        if not structured_model:
            raise Exception("OpenAI Structured Output模型未初始化")
        
        # 创建消息
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 使用Structured Output - 100%符合Schema
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
        
        # 增强提示词
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
    
    async def _generate_with_traditional_parsing(self,
                                               pydantic_model: Type[T],
                                               system_prompt: str,
                                               user_prompt: str) -> T:
        """传统解析方法 (兜底方案)"""
        # 使用我们之前实现的鲁棒解析器作为兜底
        from robust_output_parser import RobustStructuredOutputParser
        
        parser = RobustStructuredOutputParser(pydantic_model)
        
        # 增强提示词  
        base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
        format_instructions = base_parser.get_format_instructions()
        
        enhanced_system_prompt = f"""
{system_prompt}

{format_instructions}

输出要求: 必须是有效的JSON格式，严格遵循上述Schema。
"""
        
        # 使用任何可用的LLM
        llm = self.fallback_llm or self.openai_llm
        if not llm:
            raise Exception("没有可用的LLM")
        
        messages = [
            SystemMessage(content=enhanced_system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await llm.ainvoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # 使用鲁棒解析器
        result = parser.parse(response_text)
        return result


# 使用示例和测试
async def test_langchain_official_solutions():
    """测试LangChain官方解决方案"""
    print("🚀 测试LangChain官方解决方案")
    print("=" * 70)
    
    # 模拟LLM (实际使用时替换为真实的LLM)
    class MockLLM:
        async def ainvoke(self, messages):
            class MockResponse:
                content = '''
                {
                    "scenes": [
                        {"sequence": 1, "content": "秦始皇制定统一战略", "duration": 3.0},
                        {"sequence": 2, "content": "集结军队准备征战", "duration": 3.0},
                        {"sequence": 3, "content": "攻克韩国首都行动", "duration": 3.0},
                        {"sequence": 4, "content": "继续征服其他诸侯", "duration": 3.0},
                        {"sequence": 5, "content": "建立统一的帝制", "duration": 3.0}
                    ]
                }
                '''
            return MockResponse()
    
    try:
        # 创建官方解决方案实例 (这里使用模拟LLM)
        solution = LangChainOfficialSolution(
            # openai_api_key="your-openai-api-key",  # 实际使用时提供真实API密钥
            fallback_llm=MockLLM(),
            max_retries=2
        )
        
        # 测试自动降级策略
        print("🎯 测试自动降级策略...")
        result = await solution.generate_with_auto_fallback(
            pydantic_model=SceneSplitOutput,
            system_prompt="你是专业的故事场景分割专家。将输入的故事分割为多个场景，每个场景3秒钟。",
            user_prompt="请将秦始皇统一天下的故事分割为5个场景，每个场景包含不同的重要情节点。"
        )
        
        print(f"✅ 自动降级策略成功! 解析了 {len(result.scenes)} 个场景:")
        for scene in result.scenes:
            print(f"   场景{scene.sequence}: {scene.content}")
        
        # 测试特定策略
        print("\n🔧 测试OutputFixingParser策略...")
        result2 = await solution.generate_structured_output(
            pydantic_model=SceneSplitOutput,
            system_prompt="你是专业的故事场景分割专家。",
            user_prompt="分割唐太宗贞观之治的故事为5个场景。",
            strategy=ParseStrategy.OUTPUT_FIXING
        )
        
        print(f"✅ OutputFixingParser策略成功! 解析了 {len(result2.scenes)} 个场景")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def demonstrate_all_strategies():
    """演示所有解析策略的效果"""
    print("\n📊 LangChain官方解决方案 - 策略对比")
    print("=" * 70)
    
    strategies = [
        (ParseStrategy.STRUCTURED_OUTPUT, "OpenAI Structured Output (100%可靠)"),
        (ParseStrategy.RETRY_PARSER, "RetryOutputParser (智能重试)"),
        (ParseStrategy.OUTPUT_FIXING, "OutputFixingParser (自动修复)"),
        (ParseStrategy.TRADITIONAL, "传统解析 (兜底方案)")
    ]
    
    print("🎯 可用策略:")
    for strategy, description in strategies:
        print(f"   {strategy.value}: {description}")
    
    print("\n💡 推荐使用顺序 (自动降级):")
    print("   1. 🥇 OpenAI Structured Output - 100%成功率,支持strict模式")
    print("   2. 🥈 RetryOutputParser - 使用原始prompt重新生成")  
    print("   3. 🥉 OutputFixingParser - LLM自动修复格式错误")
    print("   4. 🏅 传统鲁棒解析 - 多重修复策略兜底")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 运行测试
    asyncio.run(test_langchain_official_solutions())
    
    # 演示策略对比  
    asyncio.run(demonstrate_all_strategies())