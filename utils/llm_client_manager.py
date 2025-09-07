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

# 导入新的结构化输出解析器
from utils.robust_output_parser import EnhancedLLMClient, RobustStructuredOutputParser
from utils.structured_output_models import (
    SceneSplitOutput, ImagePromptOutput, CharacterAnalysisOutput, ScriptGenerationOutput
)

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
        
        # 初始化增强客户端
        self.enhanced_clients = {}
        self._initialize_enhanced_clients()
        
        gpt5_status = "enabled" if self.gpt5_client else "disabled"
        self.logger.info(f"LangChain LLM Manager initialized with {len(self.providers)} providers, Enhanced parsers: enabled, GPT-5 API: {gpt5_status}")
    
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
        gptsapi_api_key = os.getenv('GPTSAPI_API_KEY', '')
        gptsapi_llm = ChatOpenAI(
            api_key=gptsapi_api_key,
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
                            formatted_json = json.dumps(parsed, ensure_ascii=False, indent=2)
                            self.logger.debug(f"Successfully parsed and formatted JSON response")
                            return formatted_json
                        else:
                            # 更详细的错误信息
                            self.logger.error(f"Could not extract valid JSON from response")
                            self.logger.error(f"Response preview (first 500 chars): {repr(response_text[:500])}")
                            
                            # 尝试作为普通文本返回，让上层处理
                            if response_text.strip():
                                self.logger.info("Returning raw response text for manual processing")
                                return response_text
                            else:
                                raise Exception("Empty or invalid response from LLM")
                                
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON parsing failed: {e}")
                        self.logger.error(f"Error location: line {getattr(e, 'lineno', 'unknown')}, column {getattr(e, 'colno', 'unknown')}")
                        self.logger.error(f"Error message: {getattr(e, 'msg', 'unknown')}")
                        
                        # 尝试修复常见JSON错误
                        if cleaned_json:
                            fixed_json = self._attempt_json_repair(cleaned_json)
                            if fixed_json:
                                try:
                                    parsed = json.loads(fixed_json)
                                    self.logger.info("Successfully repaired JSON format")
                                    return json.dumps(parsed, ensure_ascii=False, indent=2)
                                except json.JSONDecodeError:
                                    self.logger.warning("JSON repair attempt failed")
                        
                        # 返回原始响应
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
        
        self.logger.debug(f"Original response preview: {repr(response_text[:200])}...")
        
        # 更强力的控制字符清理
        # 移除所有控制字符，包括换行符以外的所有控制字符
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', response_text)
        
        # 进一步清理特殊Unicode字符和不可见字符
        cleaned = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060-\u206f]', '', cleaned)
        
        self.logger.debug(f"Cleaned response preview: {repr(cleaned[:200])}...")
        
        # 方法1: 查找```json...```格式
        json_match = re.search(r'```json\s*\n?(.*?)\n?```', cleaned, re.DOTALL | re.IGNORECASE)
        if json_match:
            content = json_match.group(1).strip()
            try:
                parsed = json.loads(content)
                self.logger.debug(f"Method 1 success: Found valid JSON in ```json``` block")
                return content
            except json.JSONDecodeError as e:
                self.logger.debug(f"Method 1 failed: {e}")
                pass
        
        # 方法2: 查找```...```格式  
        code_match = re.search(r'```\s*\n?(.*?)\n?```', cleaned, re.DOTALL)
        if code_match:
            content = code_match.group(1).strip()
            if content.startswith('{') or content.startswith('['):
                try:
                    parsed = json.loads(content)
                    self.logger.debug(f"Method 2 success: Found valid JSON in ``` block")
                    return content
                except json.JSONDecodeError as e:
                    self.logger.debug(f"Method 2 failed: {e}")
                    pass
        
        # 方法3: 递归查找嵌套JSON对象
        def find_json_objects(text, start=0):
            """递归查找所有可能的JSON对象"""
            objects = []
            
            # 查找数组
            try:
                array_pattern = r'\[\s*\{.*?\}\s*(?:,\s*\{.*?\}\s*)*\]'
                for match in re.finditer(array_pattern, text[start:], re.DOTALL):
                    try:
                        parsed = json.loads(match.group())
                        objects.append(match.group())
                        self.logger.debug(f"Found valid JSON array: {len(match.group())} chars")
                    except json.JSONDecodeError:
                        continue
            except:
                pass
                
            # 查找对象
            brace_count = 0
            start_pos = -1
            
            for i, char in enumerate(text[start:], start):
                if char == '{':
                    if brace_count == 0:
                        start_pos = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_pos >= 0:
                        candidate = text[start_pos:i+1]
                        try:
                            parsed = json.loads(candidate)
                            objects.append(candidate)
                            self.logger.debug(f"Found valid JSON object: {len(candidate)} chars")
                        except json.JSONDecodeError:
                            continue
            
            return objects
        
        json_objects = find_json_objects(cleaned)
        
        # 优先返回包含常见字段的JSON
        priority_fields = ['scenes', 'characters', 'image_prompt', 'video_prompt', 'content', 'text']
        
        for obj_str in json_objects:
            try:
                parsed = json.loads(obj_str)
                if isinstance(parsed, (dict, list)):
                    # 检查是否包含优先字段
                    if isinstance(parsed, dict):
                        for field in priority_fields:
                            if field in parsed:
                                self.logger.debug(f"Method 3 success: Found JSON with '{field}' field")
                                return obj_str
                    elif isinstance(parsed, list) and len(parsed) > 0:
                        if isinstance(parsed[0], dict):
                            self.logger.debug(f"Method 3 success: Found JSON array with {len(parsed)} items")
                            return obj_str
                    
                    # 如果没有优先字段，但是有效的JSON，也返回
                    self.logger.debug(f"Method 3 fallback: Found valid JSON without priority fields")
                    return obj_str
            except json.JSONDecodeError:
                continue
        
        # 如果所有方法都失败，记录详细错误信息
        self.logger.warning(f"Failed to extract valid JSON from response. Original length: {len(response_text)}, Cleaned length: {len(cleaned)}")
        self.logger.debug(f"Cleaned response full text: {repr(cleaned)}")
        
        return None
    
    def _attempt_json_repair(self, json_str: str) -> Optional[str]:
        """尝试修复常见的JSON格式问题"""
        import re
        
        if not json_str or not json_str.strip():
            return None
        
        # 修复尝试列表
        repair_attempts = [
            # 1. 移除末尾多余的逗号
            lambda s: re.sub(r',(\s*[}\]])', r'\1', s),
            
            # 2. 修复单引号为双引号
            lambda s: re.sub(r"'([^']*)':", r'"\1":', s),
            
            # 3. 修复不带引号的键名
            lambda s: re.sub(r'(\w+):', r'"\1":', s),
            
            # 4. 移除JSON外的文本
            lambda s: self._extract_core_json(s),
            
            # 5. 修复转义字符问题
            lambda s: s.replace('\\"', '"').replace("\\'", "'"),
            
            # 6. 修复缺失的引号
            lambda s: re.sub(r':\s*([^",\[\]{}]+)([,}])', r': "\1"\2', s)
        ]
        
        current = json_str.strip()
        
        for i, repair_func in enumerate(repair_attempts):
            try:
                repaired = repair_func(current)
                if repaired and repaired != current:
                    # 测试修复后的JSON是否有效
                    import json
                    json.loads(repaired)
                    self.logger.debug(f"JSON repair method {i+1} succeeded")
                    return repaired
            except (json.JSONDecodeError, Exception) as e:
                self.logger.debug(f"JSON repair method {i+1} failed: {e}")
                continue
        
        return None
    
    def _extract_core_json(self, text: str) -> str:
        """提取文本中的核心JSON部分"""
        import re
        
        # 查找最大的完整JSON对象或数组
        patterns = [
            r'(\[[\s\S]*\])',  # 数组
            r'(\{[\s\S]*\})',  # 对象
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                # 返回最长的匹配
                return max(matches, key=len)
        
        return text
    
    def _initialize_enhanced_clients(self):
        """初始化增强客户端（用于结构化输出）"""
        for provider in self.providers:
            if provider.enabled:
                self.enhanced_clients[provider.name] = EnhancedLLMClient(provider.llm)
        
        self.logger.debug(f"Initialized {len(self.enhanced_clients)} enhanced clients")
    
    async def generate_structured_output(self,
                                       task_type: str,
                                       system_prompt: str,
                                       user_prompt: str,
                                       max_retries: int = 2) -> Optional[Any]:
        """
        生成结构化输出 - 使用增强的解析器
        
        Args:
            task_type: 任务类型 (scene_splitting, image_prompt_generation, character_analysis, script_generation)
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            max_retries: 最大重试次数
            
        Returns:
            结构化输出对象 (Pydantic模型)
        """
        
        # 支持的结构化任务类型
        supported_tasks = ['scene_splitting', 'image_prompt_generation', 'character_analysis', 'script_generation']
        
        if task_type not in supported_tasks:
            self.logger.warning(f"Task type '{task_type}' not supported for structured output, falling back to regular generation")
            # 降级到普通生成
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            return await self.generate_response(messages, task_type, expect_json=True)
        
        # 尝试增强客户端
        last_error = None
        
        for provider_name, enhanced_client in self.enhanced_clients.items():
            try:
                self.logger.info(f"🔧 Trying structured generation with {provider_name}...")
                
                structured_output = await enhanced_client.generate_structured(
                    task_type=task_type,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_retries=max_retries
                )
                
                self.logger.info(f"✅ Structured generation successful with {provider_name}")
                return structured_output
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"🌐 Structured generation with {provider_name} failed: {e}")
                continue
        
        # 所有增强客户端都失败，降级到普通生成
        self.logger.warning("🔄 All enhanced clients failed, falling back to regular JSON parsing")
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.call_llm_with_fallback(messages, task_type)
            
            # 尝试手动解析为结构化格式
            return self._manual_structure_parsing(task_type, response)
            
        except Exception as fallback_error:
            self.logger.error(f"❌ Even fallback generation failed: {fallback_error}")
            raise Exception(f"All generation methods failed. Last enhanced error: {last_error}, Fallback error: {fallback_error}")
    
    def _manual_structure_parsing(self, task_type: str, response_text: str) -> Optional[Any]:
        """手动结构化解析 - 作为最后的降级方案"""
        try:
            # 尝试解析JSON
            import json
            if isinstance(response_text, str):
                # 清理和提取JSON
                cleaned_json = self._clean_and_extract_json(response_text)
                if cleaned_json:
                    parsed_data = json.loads(cleaned_json)
                    
                    # 根据任务类型创建对应的结构化对象
                    if task_type == 'scene_splitting':
                        return SceneSplitOutput.model_validate(parsed_data)
                    elif task_type == 'image_prompt_generation':
                        return ImagePromptOutput.model_validate(parsed_data)
                    elif task_type == 'character_analysis':
                        return CharacterAnalysisOutput.model_validate(parsed_data)
                    elif task_type == 'script_generation':
                        return ScriptGenerationOutput.model_validate(parsed_data)
            
            return response_text  # 返回原始响应
            
        except Exception as e:
            self.logger.warning(f"Manual structure parsing failed: {e}")
            return response_text
    
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