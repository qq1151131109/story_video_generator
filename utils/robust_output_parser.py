"""
鲁棒的LLM输出解析器 - 使用LangChain + Pydantic增强格式稳定性
"""
import json
import re
import asyncio
import logging
from typing import Type, TypeVar, Any, Dict, List, Optional, Union
from pydantic import BaseModel, ValidationError
from langchain_core.output_parsers import BaseOutputParser, JsonOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from utils.structured_output_models import (
    SceneSplitOutput, ImagePromptOutput, CharacterAnalysisOutput, ScriptGenerationOutput
)

T = TypeVar('T', bound=BaseModel)

class RobustStructuredOutputParser(BaseOutputParser[T]):
    """
    强化的结构化输出解析器
    - 使用Pydantic模型验证
    - 多重清理和修复机制
    - 自动重试和降级处理
    """
    
    def __init__(self, pydantic_model: Type[T], max_repair_attempts: int = 3):
        super().__init__()
        self._pydantic_model = pydantic_model
        self._max_repair_attempts = max_repair_attempts
        self._logger = logging.getLogger('story_generator.robust_parser')
        
    def parse(self, text: str) -> T:
        """解析LLM输出文本为结构化对象"""
        
        # 第一步：基础清理
        cleaned_text = self._deep_clean_text(text)
        
        # 第二步：尝试直接解析
        for attempt in range(self._max_repair_attempts):
            try:
                if attempt == 0:
                    candidate_json = self._extract_json_from_text(cleaned_text)
                else:
                    # 使用更激进的修复方法
                    candidate_json = self._aggressive_json_repair(cleaned_text, attempt)
                
                if candidate_json:
                    # 解析JSON
                    parsed_data = json.loads(candidate_json)
                    
                    # 检查是否是list格式，如果是则包装成正确的dict格式
                    if isinstance(parsed_data, list):
                        parsed_data = self._wrap_list_as_dict(parsed_data)
                    
                    # Pydantic验证
                    validated_obj = self._pydantic_model.model_validate(parsed_data)
                    
                    self._logger.debug(f"✅ Successfully parsed with attempt {attempt + 1}")
                    return validated_obj
                    
            except (json.JSONDecodeError, ValidationError) as e:
                self._logger.debug(f"Attempt {attempt + 1} failed: {e}")
                if attempt == self._max_repair_attempts - 1:
                    # 最后一次尝试：生成默认结构
                    return self._generate_fallback_structure(text, e)
                continue
        
        raise OutputParserException(f"Failed to parse after {self._max_repair_attempts} attempts")
    
    def _deep_clean_text(self, text: str) -> str:
        """深度清理文本"""
        if not text:
            return ""
        
        # 1. 移除所有控制字符（保留换行和制表符）
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # 2. 处理特殊Unicode字符
        cleaned = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060-\u206f]', '', cleaned)
        
        # 3. 规范化引号
        cleaned = cleaned.replace('"', '"').replace('"', '"')
        cleaned = cleaned.replace(''', "'").replace(''', "'")
        
        # 4. 修复常见的JSON转义问题
        cleaned = re.sub(r'\\+"', '"', cleaned)  # 过多的反斜杠
        cleaned = re.sub(r'\\n', '\n', cleaned)  # 转义的换行符
        
        return cleaned.strip()
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """从文本中提取JSON"""
        
        # 方法1：查找```json代码块
        json_block_pattern = r'```json\s*\n?(.*?)\n?```'
        match = re.search(json_block_pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if self._is_valid_json_structure(candidate):
                return candidate
        
        # 方法2：查找普通代码块
        code_block_pattern = r'```\s*\n?(.*?)\n?```'
        match = re.search(code_block_pattern, text, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            if self._is_valid_json_structure(candidate):
                return candidate
        
        # 方法3：智能括号匹配
        return self._extract_balanced_json(text)
    
    def _extract_balanced_json(self, text: str) -> Optional[str]:
        """使用括号匹配提取JSON"""
        
        # 寻找JSON对象
        for start_char, end_char in [('{',' }'), ('[', ']')]:
            start_idx = text.find(start_char)
            if start_idx == -1:
                continue
                
            bracket_count = 0
            in_string = False
            escape_next = False
            
            for i in range(start_idx, len(text)):
                char = text[i]
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"':
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == start_char:
                        bracket_count += 1
                    elif char == end_char:
                        bracket_count -= 1
                        if bracket_count == 0:
                            candidate = text[start_idx:i+1]
                            if self._is_valid_json_structure(candidate):
                                return candidate
                            break
        
        return None
    
    def _is_valid_json_structure(self, text: str) -> bool:
        """检查是否是有效的JSON结构"""
        try:
            json.loads(text)
            return True
        except:
            return False
    
    def _aggressive_json_repair(self, text: str, attempt: int) -> Optional[str]:
        """激进的JSON修复"""
        
        # 根据尝试次数使用不同的修复策略
        repair_strategies = [
            self._repair_trailing_commas,
            self._repair_unquoted_keys,
            self._repair_single_quotes,
            self._repair_incomplete_structures,
        ]
        
        for i in range(attempt + 1):
            if i < len(repair_strategies):
                text = repair_strategies[i](text)
        
        return self._extract_json_from_text(text)
    
    def _repair_trailing_commas(self, text: str) -> str:
        """修复末尾逗号"""
        # 移除对象和数组末尾的逗号
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        return text
    
    def _repair_unquoted_keys(self, text: str) -> str:
        """修复未加引号的键"""
        # 为没有引号的键名添加引号
        text = re.sub(r'(\w+)(\s*:)', r'"\1"\2', text)
        return text
    
    def _repair_single_quotes(self, text: str) -> str:
        """修复单引号"""
        # 将单引号替换为双引号（小心处理字符串内容）
        in_string = False
        result = []
        i = 0
        
        while i < len(text):
            char = text[i]
            
            if char == '"':
                in_string = not in_string
                result.append(char)
            elif char == "'" and not in_string:
                result.append('"')
            else:
                result.append(char)
            i += 1
        
        return ''.join(result)
    
    def _repair_incomplete_structures(self, text: str) -> str:
        """修复不完整的结构"""
        # 先处理明显不完整的字段
        text = self._complete_incomplete_fields(text)
        
        # 如果JSON不完整，尝试闭合它
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        
        if open_braces > 0:
            text += '}' * open_braces
        if open_brackets > 0:
            text += ']' * open_brackets
            
        return text
    
    def _complete_incomplete_fields(self, text: str) -> str:
        """完善不完整的字段"""
        import re
        
        # 修复缺少duration字段的情况
        text = re.sub(
            r'("content":\s*"[^"]+")(\s*[},])',
            r'\1, "duration": 3.0\2',
            text
        )
        
        # 修复缺少结尾引号的情况
        text = re.sub(r'("content":\s*"[^"]*$)', r'\1"', text)
        
        # 修复缺少结尾大括号的情况（在数组元素中）
        text = re.sub(r'("duration":\s*[\d.]+)\s*$', r'\1}', text)
        
        return text
    
    def _wrap_list_as_dict(self, data_list: list) -> dict:
        """将列表格式包装成正确的字典格式"""
        model_name = self._pydantic_model.__name__
        
        if model_name == "SceneSplitOutput" and data_list:
            # 检查是否是场景数据列表
            if all(isinstance(item, dict) and 'sequence' in item for item in data_list):
                return {"scenes": data_list}
        
        elif model_name == "ImagePromptOutput" and data_list:
            # 检查是否是图像提示词数据列表
            if all(isinstance(item, dict) and 'scene_sequence' in item for item in data_list):
                return {"scenes": data_list}
        
        elif model_name == "CharacterAnalysisOutput" and data_list:
            # 检查是否是角色数据列表
            if all(isinstance(item, dict) and 'name' in item for item in data_list):
                return {"characters": data_list}
        
        # 默认情况：尝试猜测正确的结构
        return {"scenes": data_list} if data_list else {}
    
    def _generate_fallback_structure(self, original_text: str, error: Exception) -> T:
        """生成降级结构"""
        self._logger.warning(f"Generating fallback structure due to: {error}")
        
        # 根据模型类型生成基本结构
        model_name = self._pydantic_model.__name__
        
        if model_name == "SceneSplitOutput":
            # 尝试从原始文本中提取场景
            scenes = self._extract_scenes_from_text(original_text)
            return SceneSplitOutput(scenes=scenes or [
                {"sequence": 1, "content": "Scene extraction failed, using fallback", "duration": 3.0}
            ])
        
        elif model_name == "ImagePromptOutput":
            return ImagePromptOutput(scenes=[
                {"scene_sequence": 1, "image_prompt": "Fallback image prompt", "video_prompt": "Fallback video prompt"}
            ])
        
        elif model_name == "CharacterAnalysisOutput":
            return CharacterAnalysisOutput(characters=[
                {"name": "Main Character", "description": "Character analysis failed", "image_prompt": "Fallback character prompt"}
            ])
        
        elif model_name == "ScriptGenerationOutput":
            return ScriptGenerationOutput(
                title="Generated Story",
                content=original_text[:1000] if original_text else "Story generation failed",
                theme="Unknown"
            )
        
        # 默认情况：尝试创建空结构
        try:
            return self._pydantic_model()
        except:
            raise OutputParserException(f"Cannot generate fallback for {model_name}")
    
    def _extract_scenes_from_text(self, text: str) -> Optional[List[Dict]]:
        """从文本中提取场景信息"""
        scenes = []
        
        # 查找场景标记
        scene_patterns = [
            r'Scene\s*(\d+)[:：]\s*(.+?)(?=Scene\s*\d+|$)',
            r'场景\s*(\d+)[:：]\s*(.+?)(?=场景\s*\d+|$)',
            r'(\d+)[\.\)]\s*(.+?)(?=\d+[\.\)]|$)',
        ]
        
        for pattern in scene_patterns:
            matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                seq = int(match.group(1))
                content = match.group(2).strip()[:500]  # 限制长度
                if content:
                    scenes.append({
                        "sequence": seq,
                        "content": content,
                        "duration": 3.0
                    })
        
        return scenes if scenes else None

    @property 
    def _type(self) -> str:
        return "robust_structured_output_parser"


class EnhancedLLMClient:
    """
    增强的LLM客户端 - 整合结构化输出解析器
    """
    
    def __init__(self, llm: BaseLanguageModel):
        self.llm = llm
        self._logger = logging.getLogger('story_generator.enhanced_llm')
        
        # 预定义的解析器
        self.parsers = {
            'scene_splitting': RobustStructuredOutputParser(SceneSplitOutput),
            'image_prompt_generation': RobustStructuredOutputParser(ImagePromptOutput),
            'character_analysis': RobustStructuredOutputParser(CharacterAnalysisOutput),
            'script_generation': RobustStructuredOutputParser(ScriptGenerationOutput),
        }
    
    async def generate_structured(self, 
                                  task_type: str,
                                  system_prompt: str, 
                                  user_prompt: str,
                                  max_retries: int = 2) -> BaseModel:
        """
        生成结构化输出
        """
        parser = self.parsers.get(task_type)
        if not parser:
            raise ValueError(f"Unsupported task type: {task_type}")
        
        # 增强系统提示词，强调输出格式
        enhanced_system_prompt = f"""
{system_prompt}

CRITICAL: Your response must be valid JSON only. Follow these rules:
1. Output ONLY valid JSON, no other text
2. Use double quotes for all strings
3. No trailing commas
4. No control characters or special Unicode
5. Wrap JSON in ```json ... ``` if needed

Example format:
```json
{{"key": "value"}}
```
"""
        
        for attempt in range(max_retries + 1):
            try:
                # 创建消息
                messages = [
                    SystemMessage(content=enhanced_system_prompt),
                    HumanMessage(content=user_prompt)
                ]
                
                # 调用LLM
                response = await self.llm.ainvoke(messages)
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                self._logger.debug(f"LLM raw response preview: {response_text[:200]}...")
                
                # 使用结构化解析器
                structured_output = parser.parse(response_text)
                
                self._logger.info(f"✅ Structured output generated successfully for {task_type}")
                return structured_output
                
            except Exception as e:
                self._logger.warning(f"Attempt {attempt + 1} failed for {task_type}: {e}")
                
                if attempt == max_retries:
                    self._logger.error(f"❌ All attempts failed for {task_type}")
                    raise
                
                # 等待后重试
                await asyncio.sleep(1)
        
        raise Exception(f"Failed to generate structured output for {task_type}")