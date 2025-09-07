"""
标准化Result类型 - 统一错误处理机制
"""
from typing import Generic, TypeVar, Optional, Any, Dict
from dataclasses import dataclass
from enum import Enum

T = TypeVar('T')

class ResultStatus(Enum):
    """结果状态枚举"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"

@dataclass
class Result(Generic[T]):
    """
    标准化结果对象
    
    用于统一项目中所有操作的返回结果格式，提供一致的错误处理机制。
    """
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    status: ResultStatus = ResultStatus.SUCCESS
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def success(cls, data: T, metadata: Optional[Dict[str, Any]] = None) -> 'Result[T]':
        """创建成功结果"""
        return cls(
            success=True,
            data=data,
            status=ResultStatus.SUCCESS,
            metadata=metadata
        )

    @classmethod
    def error(cls, error: str, metadata: Optional[Dict[str, Any]] = None) -> 'Result[T]':
        """创建错误结果"""
        return cls(
            success=False,
            error=error,
            status=ResultStatus.ERROR,
            metadata=metadata
        )

    @classmethod
    def warning(cls, data: T, warning: str, metadata: Optional[Dict[str, Any]] = None) -> 'Result[T]':
        """创建警告结果"""
        return cls(
            success=True,
            data=data,
            error=warning,
            status=ResultStatus.WARNING,
            metadata=metadata
        )

    def is_success(self) -> bool:
        """检查是否成功"""
        return self.success

    def is_error(self) -> bool:
        """检查是否错误"""
        return not self.success

    def has_warning(self) -> bool:
        """检查是否有警告"""
        return self.status == ResultStatus.WARNING

    def unwrap(self) -> T:
        """
        解包数据，如果是错误则抛出异常
        
        Raises:
            RuntimeError: 当结果为错误时
        """
        if self.is_error():
            raise RuntimeError(f"Result error: {self.error}")
        return self.data

    def unwrap_or(self, default: T) -> T:
        """解包数据，如果是错误则返回默认值"""
        if self.is_error():
            return default
        return self.data

# 常用类型别名
AudioResult = Result['GeneratedAudio']
ImageResult = Result['GeneratedImage'] 
VideoResult = Result['TextToVideoResult']
ScriptResult = Result['GeneratedScript']
ScenesResult = Result['SceneSplitResult']
CharactersResult = Result['CharacterAnalysisResult']