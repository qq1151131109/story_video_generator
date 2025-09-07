#!/usr/bin/env python3
"""
LangChain官方RetryOutputParser实现 - 最鲁棒的LLM输出解析方案
"""

import asyncio
import logging
from typing import Type, TypeVar, Any, Dict
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.output_parsers import RetryOutputParser, OutputFixingParser
from pydantic import BaseModel, Field

# 导入我们的数据模型
from utils.structured_output_models import SceneSplitOutput, ImagePromptOutput, CharacterAnalysisOutput

T = TypeVar('T', bound=BaseModel)

class LangChainRetryParser:
    """
    使用LangChain官方RetryOutputParser的最鲁棒解析方案
    
    特点:
    - 使用原始prompt上下文重试
    - LLM自主修复错误输出
    - 支持多次重试机制
    - 完全基于LangChain官方实现
    """
    
    def __init__(self, llm, max_retries: int = 3):
        self.llm = llm
        self.max_retries = max_retries
        self.logger = logging.getLogger('langchain_retry_parser')
        
        # 预配置的解析器缓存
        self._parsers = {}
    
    def get_retry_parser(self, pydantic_model: Type[T]) -> RetryOutputParser:
        """获取带重试功能的解析器"""
        model_name = pydantic_model.__name__
        
        if model_name not in self._parsers:
            # 创建基础Pydantic解析器
            base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
            
            # 创建重试解析器
            retry_parser = RetryOutputParser.from_llm(
                parser=base_parser,
                llm=self.llm,
                max_retries=self.max_retries
            )
            
            self._parsers[model_name] = retry_parser
            self.logger.info(f"Created RetryOutputParser for {model_name}")
        
        return self._parsers[model_name]
    
    def get_fixing_parser(self, pydantic_model: Type[T]) -> OutputFixingParser:
        """获取带修复功能的解析器"""
        model_name = pydantic_model.__name__
        cache_key = f"{model_name}_fixing"
        
        if cache_key not in self._parsers:
            # 创建基础Pydantic解析器
            base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
            
            # 创建修复解析器
            fixing_parser = OutputFixingParser.from_llm(
                parser=base_parser,
                llm=self.llm
            )
            
            self._parsers[cache_key] = fixing_parser
            self.logger.info(f"Created OutputFixingParser for {model_name}")
        
        return self._parsers[cache_key]
    
    async def parse_with_retry(self, 
                              pydantic_model: Type[T], 
                              output_text: str, 
                              original_prompt: str) -> T:
        """
        使用RetryOutputParser解析输出
        
        Args:
            pydantic_model: 目标Pydantic模型
            output_text: LLM输出文本  
            original_prompt: 原始prompt（用于重试时提供上下文）
            
        Returns:
            解析后的结构化对象
        """
        try:
            retry_parser = self.get_retry_parser(pydantic_model)
            
            # 创建PromptValue用于重试上下文
            from langchain_core.prompt_values import StringPromptValue
            prompt_value = StringPromptValue(text=original_prompt)
            
            # 使用RetryOutputParser解析（带原始prompt上下文）
            result = retry_parser.parse_with_prompt(output_text, prompt_value)
            
            self.logger.info(f"✅ RetryOutputParser成功解析 {pydantic_model.__name__}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ RetryOutputParser解析失败: {e}")
            raise
    
    async def parse_with_fixing(self, 
                               pydantic_model: Type[T], 
                               output_text: str) -> T:
        """
        使用OutputFixingParser解析输出
        
        Args:
            pydantic_model: 目标Pydantic模型
            output_text: LLM输出文本
            
        Returns:
            解析后的结构化对象
        """
        try:
            fixing_parser = self.get_fixing_parser(pydantic_model)
            
            # 使用OutputFixingParser解析（自动修复格式错误）
            result = fixing_parser.parse(output_text)
            
            self.logger.info(f"✅ OutputFixingParser成功解析 {pydantic_model.__name__}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ OutputFixingParser解析失败: {e}")
            raise
    
    async def parse_with_both_strategies(self,
                                        pydantic_model: Type[T],
                                        output_text: str,
                                        original_prompt: str = "") -> T:
        """
        综合使用两种策略: 先尝试OutputFixingParser，失败后使用RetryOutputParser
        
        Args:
            pydantic_model: 目标Pydantic模型
            output_text: LLM输出文本
            original_prompt: 原始prompt（RetryOutputParser需要）
            
        Returns:
            解析后的结构化对象
        """
        # 策略1: 尝试OutputFixingParser（更快，不需要额外LLM调用如果格式问题简单）
        try:
            self.logger.info("🔧 尝试OutputFixingParser...")
            result = await self.parse_with_fixing(pydantic_model, output_text)
            return result
        except Exception as fixing_error:
            self.logger.warning(f"OutputFixingParser失败: {fixing_error}")
        
        # 策略2: 降级到RetryOutputParser（更强大，使用原始prompt重新生成）
        if original_prompt:
            try:
                self.logger.info("🔄 降级到RetryOutputParser...")
                result = await self.parse_with_retry(pydantic_model, output_text, original_prompt)
                return result
            except Exception as retry_error:
                self.logger.error(f"RetryOutputParser也失败: {retry_error}")
        
        # 两种策略都失败
        raise Exception("Both OutputFixingParser and RetryOutputParser failed")


class EnhancedLangChainLLMClient:
    """
    增强的LLM客户端 - 集成LangChain官方的鲁棒解析方案
    """
    
    def __init__(self, llm, max_retries: int = 2):
        self.llm = llm
        self.retry_parser = LangChainRetryParser(llm, max_retries)
        self.logger = logging.getLogger('enhanced_langchain_llm')
    
    async def generate_structured_with_langchain(self,
                                               pydantic_model: Type[T],
                                               system_prompt: str,
                                               user_prompt: str) -> T:
        """
        使用LangChain官方解析器生成结构化输出
        
        Args:
            pydantic_model: 目标Pydantic模型
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            
        Returns:
            解析后的结构化对象
        """
        try:
            # 增强系统提示词，明确输出格式要求
            base_parser = PydanticOutputParser(pydantic_object=pydantic_model)
            format_instructions = base_parser.get_format_instructions()
            
            enhanced_system_prompt = f"""
{system_prompt}

{format_instructions}

CRITICAL: 
- Output ONLY valid JSON that matches the schema above
- No additional text or explanations
- Ensure all required fields are included
- Use proper JSON formatting with double quotes
"""
            
            # 生成完整的prompt用于重试上下文
            full_prompt = f"System: {enhanced_system_prompt}\nUser: {user_prompt}"
            
            # 调用LLM生成输出
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content=enhanced_system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            self.logger.debug(f"LLM原始输出: {response_text[:200]}...")
            
            # 使用综合解析策略
            result = await self.retry_parser.parse_with_both_strategies(
                pydantic_model=pydantic_model,
                output_text=response_text,
                original_prompt=full_prompt
            )
            
            self.logger.info(f"✅ LangChain官方解析器成功处理 {pydantic_model.__name__}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ LangChain官方解析器失败: {e}")
            raise


# 使用示例和测试函数
async def test_langchain_official_parsers():
    """测试LangChain官方解析器的效果"""
    print("🧪 测试LangChain官方解析器")
    print("=" * 60)
    
    # 模拟LLM（这里使用模拟数据，实际使用时需要真实的LLM）
    class MockLLM:
        async def ainvoke(self, messages):
            class MockResponse:
                content = """
                根据您的要求，我来分割场景：
                
                ```json
                {
                    "scenes": [
                        {"sequence": 1, "content": "秦始皇制定统一天下战略", "duration": 3.0},
                        {"sequence": 2, "content": "组建强大军队准备征战", "duration": 3.0},
                        {"sequence": 3, "content": "攻破韩国首都的战役", "duration": 3.0},
                        {"sequence": 4, "content": "继续征服其他五国", "duration": 3.0},
                        {"sequence": 5, "content": "统一天下建立帝制", "duration": 3.0}
                    ]
                }
                ```
                
                这样分割突出了关键历史节点。
                """
            return MockResponse()
    
    try:
        # 创建增强的LLM客户端
        mock_llm = MockLLM()
        client = EnhancedLangChainLLMClient(mock_llm)
        
        # 测试场景分割
        result = await client.generate_structured_with_langchain(
            pydantic_model=SceneSplitOutput,
            system_prompt="你是专业的故事场景分割专家",
            user_prompt="将秦始皇统一天下的故事分割为5个场景"
        )
        
        print(f"✅ 成功解析 {len(result.scenes)} 个场景:")
        for scene in result.scenes:
            print(f"   场景{scene.sequence}: {scene.content}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 运行测试
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_langchain_official_parsers())