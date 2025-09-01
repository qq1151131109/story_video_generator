"""
多提供商LLM客户端管理器
支持自动fallback到备用提供商
"""
import asyncio
import logging
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import openai

@dataclass
class LLMProvider:
    """LLM提供商配置"""
    name: str
    api_key: str
    base_url: str
    models: Dict[str, str]  # task_type -> model_name mapping
    enabled: bool = True

class LLMClientManager:
    """
    多提供商LLM客户端管理器
    
    支持功能：
    1. 多个API提供商自动切换
    2. 失败重试和fallback机制
    3. 基于.env文件的灵活配置
    4. 负载均衡和成本优化
    """
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger('story_generator.llm_manager')
        
        # 初始化提供商配置
        self.providers = self._load_providers()
        self.clients = {}
        
        # 初始化所有可用的客户端
        self._initialize_clients()
        
        self.logger.info(f"LLM Client Manager initialized with {len(self.providers)} providers")
    
    def _load_providers(self) -> List[LLMProvider]:
        """从配置文件加载LLM提供商配置"""
        providers = []
        
        # OpenRouter - 主力提供商
        if os.getenv('OPENROUTER_API_KEY'):
            # 🔧 从配置文件读取模型而不是硬编码
            openrouter_models = {}
            for task in ['script_generation', 'theme_extraction', 'scene_splitting', 'image_prompt_generation', 'character_analysis']:
                llm_config = self.config.get(f'llm.{task}', {})
                openrouter_models[task] = llm_config.get('model', 'openai/gpt-5')
            
            providers.append(LLMProvider(
                name='openrouter',
                api_key=os.getenv('OPENROUTER_API_KEY'),
                base_url=os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
                models=openrouter_models
            ))
        
        # GPTsAPI - 备用提供商1 (GPT-5代理)
        providers.append(LLMProvider(
            name='gptsapi',
            api_key='sk-yLda99082cd843c55e0453e3e23d384715143c3db7bmrz63',
            base_url='https://api.gptsapi.net/v1',
            models={
                'script_generation': 'gpt-5',
                'theme_extraction': 'gpt-5',
                'scene_splitting': 'gpt-5',
                'image_prompt_generation': 'gpt-5',
                'character_analysis': 'gpt-5'
            }
        ))
        
        # DeepSeek - 备用提供商2
        if os.getenv('DEEPSEEK_API_KEY'):
            providers.append(LLMProvider(
                name='deepseek',
                api_key=os.getenv('DEEPSEEK_API_KEY'),
                base_url=os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
                models={
                    'script_generation': os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
                    'theme_extraction': os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
                    'scene_splitting': os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
                    'image_prompt_generation': os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
                    'character_analysis': os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
                }
            ))
        
        # Qwen - 备用提供商3
        if os.getenv('QWEN_API_KEY'):
            providers.append(LLMProvider(
                name='qwen',
                api_key=os.getenv('QWEN_API_KEY'),
                base_url=os.getenv('QWEN_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
                models={
                    'script_generation': os.getenv('QWEN_MODEL', 'qwen-turbo'),
                    'theme_extraction': os.getenv('QWEN_MODEL', 'qwen-turbo'),
                    'scene_splitting': os.getenv('QWEN_MODEL', 'qwen-turbo'),
                    'image_prompt_generation': os.getenv('QWEN_MODEL', 'qwen-turbo'),
                    'character_analysis': os.getenv('QWEN_MODEL', 'qwen-turbo')
                }
            ))
        
        return providers
    
    def _initialize_clients(self):
        """初始化所有提供商的客户端"""
        # 从配置获取超时和重试参数
        timeout = self.config.get('general.api_timeout', 120)
        max_retries = self.config.get('general.api_max_retries', 3)
        
        for provider in self.providers:
            try:
                client = openai.AsyncOpenAI(
                    api_key=provider.api_key,
                    base_url=provider.base_url,
                    timeout=float(timeout),
                    max_retries=max_retries
                )
                self.clients[provider.name] = client
                self.logger.debug(f"Initialized client for provider: {provider.name} (timeout={timeout}s, retries={max_retries})")
            except Exception as e:
                self.logger.error(f"Failed to initialize client for {provider.name}: {e}")
    
    async def call_llm_with_fallback(self, 
                                   prompt: str, 
                                   task_type: str = 'script_generation',
                                   temperature: float = 0.8,
                                   max_tokens: int = 1024) -> Optional[str]:
        """
        使用fallback机制调用LLM
        
        Args:
            prompt: 提示词
            task_type: 任务类型
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            LLM响应内容，失败时返回None
        """
        last_error = None
        
        # 从配置获取重试延迟时间
        retry_delay = self.config.get('general.retry_delay', 2)
        
        for provider in self.providers:
            if not provider.enabled or provider.name not in self.clients:
                continue
                
            client = self.clients[provider.name]
            model = provider.models.get(task_type, provider.models.get('script_generation'))
            
            try:
                self.logger.debug(f"Trying provider {provider.name} with model {model}")
                
                # 根据提供商调整参数限制
                adjusted_max_tokens = max_tokens
                if provider.name == 'deepseek':
                    # DeepSeek限制max_tokens在[1, 8192]范围内
                    adjusted_max_tokens = min(max_tokens, 8192)
                elif provider.name == 'qwen':
                    # Qwen也有类似限制
                    adjusted_max_tokens = min(max_tokens, 8000)
                
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }],
                    temperature=temperature,
                    max_tokens=adjusted_max_tokens
                )
                
                content = response.choices[0].message.content
                if content:
                    self.logger.info(f"✅ LLM call successful with provider: {provider.name}")
                    return content
                    
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                # 根据错误类型分类处理
                if 'timeout' in error_msg or 'timed out' in error_msg:
                    self.logger.warning(f"⏰ Provider {provider.name} timeout: {e}")
                    # 超时错误，等待较长时间后尝试下一个提供商
                    await asyncio.sleep(retry_delay * 2)
                elif 'rate limit' in error_msg or 'too many requests' in error_msg:
                    self.logger.warning(f"🚫 Provider {provider.name} rate limited: {e}")
                    # 频率限制，等待更长时间
                    await asyncio.sleep(retry_delay * 3)
                elif 'connection' in error_msg or 'network' in error_msg:
                    self.logger.warning(f"🌐 Provider {provider.name} connection error: {e}")
                    # 网络错误，等待配置的延迟时间
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.warning(f"❌ Provider {provider.name} failed: {e}")
                    # 其他错误，稍作等待避免快速连续失败
                    await asyncio.sleep(retry_delay * 0.5)
                
                continue
        
        # 所有提供商都失败
        self.logger.error(f"All LLM providers failed. Last error: {last_error}")
        raise Exception(f"All LLM providers failed: {last_error}")
    
    def get_available_providers(self) -> List[str]:
        """获取可用的提供商列表"""
        return [p.name for p in self.providers if p.enabled and p.name in self.clients]
    
    def disable_provider(self, provider_name: str):
        """禁用指定提供商"""
        for provider in self.providers:
            if provider.name == provider_name:
                provider.enabled = False
                self.logger.info(f"Disabled provider: {provider_name}")
                break
    
    def enable_provider(self, provider_name: str):
        """启用指定提供商"""
        for provider in self.providers:
            if provider.name == provider_name:
                provider.enabled = True
                self.logger.info(f"Enabled provider: {provider_name}")
                break
    
    def get_provider_status(self) -> Dict[str, Any]:
        """获取所有提供商状态"""
        status = {}
        for provider in self.providers:
            status[provider.name] = {
                'enabled': provider.enabled,
                'has_client': provider.name in self.clients,
                'models': provider.models
            }
        return status