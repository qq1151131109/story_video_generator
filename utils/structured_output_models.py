"""
结构化输出模型 - 使用Pydantic确保LLM输出的格式正确性
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator, model_validator
from enum import Enum

class SceneModel(BaseModel):
    """场景模型"""
    sequence: int = Field(..., ge=1, description="场景序号，从1开始")
    content: str = Field(..., min_length=5, max_length=500, description="场景内容描述")
    duration: Optional[float] = Field(default=3.0, ge=1.0, le=10.0, description="场景时长(秒)")
    
    @validator('content')
    def clean_content(cls, v):
        # 清理控制字符
        import re
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', v)
        return cleaned.strip()

class ImagePromptModel(BaseModel):
    """图像提示词模型"""
    scene_sequence: int = Field(..., ge=1, description="对应的场景序号")
    image_prompt: str = Field(..., min_length=20, max_length=2000, description="图像生成提示词")
    video_prompt: Optional[str] = Field(default="", min_length=0, max_length=1000, description="视频生成提示词（可选）")
    
    @validator('image_prompt', 'video_prompt')
    def clean_prompts(cls, v):
        # 允许video_prompt为空
        if not v:
            return ""
        import re
        # 清理控制字符和特殊符号
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', v)
        # 移除可能的JSON转义字符问题
        cleaned = cleaned.replace('\\"', '"').replace("\\'", "'")
        return cleaned.strip()

class CharacterModel(BaseModel):
    """角色模型"""
    name: str = Field(..., min_length=1, max_length=50, description="角色名称")
    description: str = Field(..., min_length=5, max_length=1000, description="角色描述")
    image_prompt: str = Field(..., min_length=20, max_length=1000, description="角色图像提示词")
    
    @validator('name', 'description', 'image_prompt')
    def clean_fields(cls, v):
        import re
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', v)
        return cleaned.strip()

class SceneSplitOutput(BaseModel):
    """场景分割输出"""
    scenes: List[SceneModel] = Field(..., min_items=5, max_items=25, description="场景列表")
    total_duration: Optional[float] = Field(default=None, description="总时长")
    
    @model_validator(mode='after')
    def validate_scenes(self):
        if self.scenes:
            # 确保序号连续
            sequences = [scene.sequence for scene in self.scenes]
            expected = list(range(1, len(self.scenes) + 1))
            if sequences != expected:
                # 自动修复序号
                for i, scene in enumerate(self.scenes):
                    scene.sequence = i + 1
        return self

class ImagePromptOutput(BaseModel):
    """图像提示词生成输出"""
    scenes: List[ImagePromptModel] = Field(..., min_items=1, description="场景图像提示词列表")
    
    @model_validator(mode='after')
    def validate_consistency(self):
        if self.scenes:
            # 确保序号不重复
            sequences = [scene.scene_sequence for scene in self.scenes]
            if len(sequences) != len(set(sequences)):
                raise ValueError("Scene sequences must be unique")
        return self

class CharacterAnalysisOutput(BaseModel):
    """角色分析输出"""
    characters: List[CharacterModel] = Field(..., min_items=1, max_items=10, description="角色列表")
    main_character: Optional[str] = Field(default=None, description="主角名称")
    
    @validator('main_character', pre=True)
    def parse_main_character(cls, v):
        """处理LLM可能返回字典格式的main_character"""
        if isinstance(v, dict):
            # 如果是字典，提取name字段
            return v.get('name', '') if v else None
        return v
    
    @model_validator(mode='after')
    def validate_main_character(self):
        if self.main_character and self.characters:
            char_names = [char.name for char in self.characters]
            if self.main_character not in char_names:
                # 自动设置第一个角色为主角
                self.main_character = self.characters[0].name
        
        return self

class ScriptGenerationOutput(BaseModel):
    """脚本生成输出"""
    title: str = Field(..., min_length=1, max_length=100, description="故事标题")
    content: str = Field(..., min_length=100, max_length=4500, description="故事内容")  # 调整为OpenAI限制内
    theme: Optional[str] = Field(default=None, max_length=50, description="故事主题")
    
    @validator('title', 'content', 'theme')
    def clean_text_fields(cls, v):
        if not v:
            return v
        import re
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', v)
        return cleaned.strip()