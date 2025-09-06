"""
基于LangChain的LLM客户端管理器 - 支持GPT-5新API格式
保持与原LLMClientManager相同的接口，使用LangChain底层实现
支持GPT-5的responses.create()和传统的chat.completions.create()两种API格式
"""
import asyncio
import logging
import os
import httpx
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

# LangChain imports
from langchain_core.language_models import BaseLLM, BaseLanguageModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser, BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.exceptions import OutputParserException

# 导入原始ModelConfig以保持兼容性
from core.config_manager import ModelConfig

@dataclass
class LangChainProvider:
    """LangChain LLM提供商配置"""
    name: str
    llm: BaseLanguageModel
    models: Dict[str, str]
    enabled: bool = True

class GPT5NewAPIClient:
    """
    GPT-5新API格式客户端
    使用responses.create()端点而不是chat.completions.create()
    """
    
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.logger = logging.getLogger('story_generator.gpt5_api')
    
    async def create_response(self, 
                            messages: List[Dict[str, str]], 
                            model: str = "openai/gpt-5",
                            temperature: float = 0.8,
                            max_tokens: int = 1024) -> str:
        """
        使用GPT-5新API格式调用LLM
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            str: 响应内容
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://story-video-generator.local",
            "X-Title": "Story Video Generator"
        }
        
        # GPT-5新API格式的请求体
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 尝试新的responses端点
                response = await client.post(
                    f"{self.base_url}/responses",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    response_text = response.text
                    self.logger.debug(f"Raw response: {response_text[:200]}...")
                    
                    # 检查响应是否为空
                    if not response_text or response_text.strip() == "":
                        self.logger.warning("Empty response from GPT-5 new API endpoint")
                        raise Exception("Empty response from GPT-5 new API endpoint")
                    
                    try:
                        result = response.json()
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Failed to parse JSON response: {e}, response: {response_text[:100]}")
                        # 尝试传统端点
                        return await self._fallback_to_legacy_api(messages, model, temperature, max_tokens, headers)
                    
                    # 新API格式的响应结构
                    if "response" in result and "content" in result["response"]:
                        content = result["response"]["content"]
                        self.logger.info(f"✅ GPT-5 new API call successful")
                        return content
                    elif "choices" in result and len(result["choices"]) > 0:
                        # 兼容传统响应格式
                        content = result["choices"][0]["message"]["content"]
                        self.logger.info(f"✅ GPT-5 new API call successful (legacy format)")
                        return content
                    else:
                        self.logger.warning(f"Unexpected response format: {result}")
                        return str(result)
                elif response.status_code == 404:
                    # 新端点不存在，尝试传统端点
                    self.logger.info("GPT-5 new API endpoint not found, falling back to legacy format")
                    return await self._fallback_to_legacy_api(messages, model, temperature, max_tokens, headers)
                else:
                    self.logger.error(f"GPT-5 API error {response.status_code}: {response.text}")
                    raise Exception(f"GPT-5 API error: {response.status_code}")
                    
        except httpx.TimeoutException:
            self.logger.error("GPT-5 API call timeout")
            raise Exception("GPT-5 API call timeout")
        except Exception as e:
            self.logger.error(f"GPT-5 API call failed: {e}")
            raise
    
    async def _fallback_to_legacy_api(self, 
                                    messages: List[Dict[str, str]], 
                                    model: str,
                                    temperature: float,
                                    max_tokens: int,
                                    headers: Dict[str, str]) -> str:
        """
        回退到传统chat.completions端点
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    self.logger.info(f"✅ GPT-5 legacy API call successful")
                    return content
                else:
                    raise Exception(f"Unexpected legacy response format: {result}")
            else:
                self.logger.error(f"GPT-5 legacy API error {response.status_code}: {response.text}")
                raise Exception(f"GPT-5 legacy API error: {response.status_code}")

class LangChainLLMManager:
    """
    基于LangChain的多提供商LLM管理器
    
    优势：
    1. 使用LangChain的重试和错误处理机制
    2. 内置JSON解析和验证
    3. 更好的Prompt管理
    4. 保持与原接口100%兼容
    """
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger('story_generator.langchain_llm')
        
        # 初始化LangChain提供商
        self.providers = self._initialize_langchain_providers()
        
        # 保留GPT-5新API客户端以备将来使用
        self.gpt5_client = None
        if os.getenv('OPENROUTER_API_KEY'):
            self.gpt5_client = GPT5NewAPIClient(
                api_key=os.getenv('OPENROUTER_API_KEY'),
                base_url=os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
            )
        
        # 初始化输出解析器
        self.json_parser = JsonOutputParser()
        
        gpt5_status = "enabled" if self.gpt5_client else "disabled"
        self.logger.info(f"LangChain LLM Manager initialized with {len(self.providers)} providers, GPT-5 API: {gpt5_status}")
    
    def _initialize_langchain_providers(self) -> List[LangChainProvider]:
        """初始化LangChain提供商，优先级：OpenRouter(Gemini) > GPTsAPI(GPT-5) > DeepSeek"""
        providers = []
        
        # OpenRouter提供商（首选，使用Gemini）
        if os.getenv('OPENROUTER_API_KEY'):
            openrouter_llm = ChatOpenAI(
                api_key=os.getenv('OPENROUTER_API_KEY'),
                base_url=os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
                model="google/gemini-2.5-flash",  # 主要模型
                temperature=0.8,
                max_tokens=8192,
                timeout=30,
                max_retries=3
            )
            
            providers.append(LangChainProvider(
                name='openrouter',
                llm=openrouter_llm,
                models={task: 'google/gemini-2.5-flash' for task in ['script_generation', 'theme_extraction', 'scene_splitting', 'image_prompt_generation', 'character_analysis']}
            ))
        
        # GPTsAPI提供商（fallback GPT-5提供商）
        gptsapi_llm = ChatOpenAI(
            api_key='sk-yLda99082cd843c55e0453e3e23d384715143c3db7bmrz63',
            base_url='https://api.gptsapi.net/v1',
            model="gpt-5",  # GPTsAPI使用简化的模型名称
            temperature=0.8,
            max_tokens=8192,
            timeout=30,
            max_retries=3
        )
        
        providers.append(LangChainProvider(
            name='gptsapi',
            llm=gptsapi_llm,
            models={task: 'gpt-5' for task in ['script_generation', 'theme_extraction', 'scene_splitting', 'image_prompt_generation', 'character_analysis']}
        ))
        
        # DeepSeek提供商（备选）
        if os.getenv('DEEPSEEK_API_KEY'):
            deepseek_llm = ChatOpenAI(
                api_key=os.getenv('DEEPSEEK_API_KEY'),
                base_url=os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
                model="deepseek-chat",
                temperature=0.8,
                max_tokens=8192,
                timeout=30,
                max_retries=3
            )
            
            providers.append(LangChainProvider(
                name='deepseek',
                llm=deepseek_llm,
                models={task: 'deepseek-chat' for task in ['script_generation', 'theme_extraction', 'scene_splitting', 'image_prompt_generation', 'character_analysis']}
            ))
        
        return providers
    
    async def call_llm_async(self, 
                           messages: List[Dict[str, str]], 
                           config: ModelConfig,
                           task_type: str = "general",
                           expect_json: bool = False) -> str:
        """
        异步调用LLM - 保持与原接口兼容，支持GPT-5新API
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            config: 模型配置
            task_type: 任务类型
            expect_json: 是否期望JSON响应
            
        Returns:
            str: LLM响应内容
        """
        
        # GPT-5新API暂时不可用，直接使用LangChain提供商
        # OpenRouter的/responses端点还未实现，GPTsAPI已提供GPT-5支持
        
        # 转换消息格式为LangChain格式（用于传统提供商）
        lc_messages = []
        for msg in messages:
            if msg["role"] == "system":
                lc_messages.append(SystemMessage(content=msg["content"]))
            else:
                lc_messages.append(HumanMessage(content=msg["content"]))
        
        # 尝试LangChain提供商
        last_error = None
        for provider in self.providers:
            if not provider.enabled:
                continue
                
            try:
                self.logger.debug(f"Trying provider {provider.name} with model {config.name}")
                
                # 动态更新模型配置
                # 根据提供商选择合适的模型
                if provider.name == 'deepseek':
                    model_to_use = 'deepseek-chat'
                elif provider.name == 'gptsapi':
                    # GPTsAPI使用简化的模型名称
                    if config.name == 'openai/gpt-5':
                        model_to_use = 'gpt-5'
                    else:
                        model_to_use = config.name
                elif provider.name == 'openrouter':
                    # OpenRouter作为fallback，使用Gemini
                    model_to_use = 'google/gemini-2.5-flash'
                else:
                    model_to_use = config.name
                
                provider.llm.model_name = model_to_use if hasattr(provider.llm, 'model_name') else model_to_use
                provider.llm.temperature = config.temperature
                provider.llm.max_tokens = config.max_tokens
                
                # 调用LLM
                if expect_json:
                    # 先获取原始响应
                    result = await provider.llm.ainvoke(lc_messages)
                    response_text = result.content if hasattr(result, 'content') else str(result)
                    
                    # 手动清理和提取JSON
                    try:
                        cleaned_json = self._clean_and_extract_json(response_text)
                        if cleaned_json:
                            # 验证JSON格式
                            parsed = json.loads(cleaned_json)
                            return json.dumps(parsed, ensure_ascii=False, indent=2)
                        else:
                            self.logger.warning(f"Could not extract valid JSON from response")
                            return response_text
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"JSON parsing failed: {e}")
                        return response_text
                else:
                    # 普通文本响应
                    result = await provider.llm.ainvoke(lc_messages)
                    response_text = result.content if hasattr(result, 'content') else str(result)
                    
                    self.logger.debug(f"Raw response from {provider.name}: {repr(response_text)[:200]}...")
                    
                    # 检查响应是否为空
                    if not response_text or response_text.strip() == "":
                        self.logger.warning(f"Empty response from provider: {provider.name}")
                        raise Exception(f"Empty response from provider: {provider.name}")
                    
                    self.logger.info(f"✅ LLM call successful with provider: {provider.name}")
                    return response_text
                    
            except Exception as e:
                self.logger.warning(f"🌐 Provider {provider.name} failed: {e}")
                last_error = e
                continue
        
        # 所有提供商都失败
        error_msg = f"All LLM providers failed. Last error: {last_error}"
        self.logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    def call_llm(self, messages: List[Dict[str, str]], config: ModelConfig, **kwargs) -> str:
        """同步调用LLM - 保持与原接口兼容"""
        return asyncio.run(self.call_llm_async(messages, config, **kwargs))
    
    def create_chain_for_task(self, task_type: str, prompt_template: str = None) -> Any:
        """
        为特定任务创建LangChain Chain
        这是LangChain特有的功能，可选使用
        
        Args:
            task_type: 任务类型
            prompt_template: 提示词模板
            
        Returns:
            LangChain Chain对象
        """
        if not self.providers:
            raise RuntimeError("No providers available")
        
        # 使用第一个可用提供商
        provider = self.providers[0]
        
        if prompt_template:
            # 创建带提示词模板的Chain
            prompt = ChatPromptTemplate.from_template(prompt_template)
            chain = prompt | provider.llm
        else:
            # 简单Chain
            chain = provider.llm
        
        self.logger.info(f"Created chain for task: {task_type}")
        return chain
    
    def _clean_and_extract_json(self, response_text: str) -> Optional[str]:
        """清理响应文本并提取JSON"""
        import re
        import json
        
        # 移除控制字符
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response_text)
        
        # 方法1: 查找```json...```格式
        json_match = re.search(r'```json\s*\n?(.*?)\n?```', cleaned, re.DOTALL | re.IGNORECASE)
        if json_match:
            content = json_match.group(1).strip()
            try:
                json.loads(content)  # 验证JSON有效性
                return content
            except json.JSONDecodeError:
                pass
        
        # 方法2: 查找```...```格式  
        code_match = re.search(r'```\s*\n?(.*?)\n?```', cleaned, re.DOTALL)
        if code_match:
            content = code_match.group(1).strip()
            if content.startswith('{') and content.endswith('}'):
                try:
                    json.loads(content)  # 验证JSON有效性
                    return content
                except json.JSONDecodeError:
                    pass
        
        # 方法3: 直接查找JSON对象
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        json_matches = re.findall(json_pattern, cleaned, re.DOTALL)
        
        for match in json_matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict) and 'scenes' in parsed:
                    return match
            except json.JSONDecodeError:
                continue
        
        return None
    
    def get_provider_stats(self) -> Dict[str, Any]:
        """获取提供商统计信息"""
        return {
            'total_providers': len(self.providers),
            'enabled_providers': len([p for p in self.providers if p.enabled]),
            'provider_names': [p.name for p in self.providers if p.enabled],
            'gpt5_new_api_available': self.gpt5_client is not None
        }
    
    async def test_gpt5_new_api(self) -> Dict[str, Any]:
        """
        测试GPT-5新API的可用性
        
        Returns:
            Dict包含测试结果
        """
        if not self.gpt5_client:
            return {
                'available': False,
                'reason': 'GPT-5 client not initialized (missing API key)'
            }
        
        try:
            test_messages = [{"role": "user", "content": "Hello, this is a test message."}]
            response = await self.gpt5_client.create_response(
                messages=test_messages,
                model="openai/gpt-5",
                temperature=0.7,
                max_tokens=50
            )
            
            return {
                'available': True,
                'response_length': len(response) if response else 0,
                'api_format': 'new' if '/responses' in str(self.gpt5_client.base_url) else 'legacy'
            }
            
        except Exception as e:
            return {
                'available': False,
                'reason': str(e),
                'error_type': type(e).__name__
            }
    
    async def call_llm_with_fallback(self, 
                                   prompt: str, 
                                   task_type: str = 'script_generation',
                                   temperature: float = 0.8,
                                   max_tokens: int = 1024) -> Optional[str]:
        """
        兼容性方法 - 使用fallback机制调用LLM
        保持与原LLMClientManager接口兼容
        
        Args:
            prompt: 提示词
            task_type: 任务类型
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            LLM响应内容，失败时返回None
        """
        try:
            # 构建消息格式
            messages = [{"role": "user", "content": prompt}]
            
            # 创建配置对象
            config = ModelConfig(
                name="openai/gpt-5",  # 默认使用GPT-5
                temperature=temperature,
                max_tokens=max_tokens,
                api_base="https://openrouter.ai/api/v1",
                api_key=""  # 将由LangChain管理器处理
            )
            
            # 调用新的异步方法
            response = await self.call_llm_async(messages, config, task_type=task_type)
            return response
            
        except Exception as e:
            self.logger.error(f"call_llm_with_fallback failed: {e}")
            return None


# 兼容性别名 - 保持与现有代码的兼容性
class LLMClientManager(LangChainLLMManager):
    """兼容性别名 - 使现有代码无需修改即可使用LangChain"""
    pass