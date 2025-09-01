"""
文件管理工具 - 处理输出文件、临时文件管理
"""
import os
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime
import hashlib

class FileManager:
    """
    文件管理器 - 统一处理项目中的文件操作
    
    功能：
    - 管理输出目录结构
    - 临时文件清理
    - 文件命名规范
    - 批量文件操作
    """
    
    def __init__(self, output_dir: str = "output", temp_dir: str = "output/temp"):
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self.logger = logging.getLogger(__name__)
        
        # 创建必要的目录结构
        self._create_directory_structure()
    
    def _create_directory_structure(self):
        """创建项目目录结构"""
        directories = [
            self.output_dir,
            self.temp_dir,
            self.output_dir / "scripts",      # 文案输出
            self.output_dir / "scenes",       # 分镜输出
            self.output_dir / "images",       # 图片输出
            self.output_dir / "audio",        # 音频输出
            self.output_dir / "videos",       # 视频输出
            self.output_dir / "subtitles",    # 字幕输出
            self.output_dir / "manifests",    # 媒体清单输出
            self.output_dir / "cache",        # 缓存目录
            self.output_dir / "logs",         # 日志目录
            self.temp_dir / "images",         # 临时图片
            self.temp_dir / "audio",          # 临时音频
            self.temp_dir / "processing"      # 处理中文件
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                self.logger.debug(f"Created directory: {directory}")
            except Exception as e:
                self.logger.error(f"Failed to create directory {directory}: {e}")
    
    def generate_filename(self, content: str, prefix: str = "", suffix: str = "", 
                         extension: str = "", max_length: int = 50) -> str:
        """
        生成标准化的文件名
        
        Args:
            content: 内容用于生成唯一标识
            prefix: 文件名前缀
            suffix: 文件名后缀  
            extension: 文件扩展名
            max_length: 文件名最大长度
        """
        # 生成内容的哈希值作为唯一标识
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
        
        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 组合文件名
        parts = []
        if prefix:
            parts.append(prefix)
        parts.append(timestamp)
        parts.append(content_hash)
        if suffix:
            parts.append(suffix)
        
        filename = "_".join(parts)
        
        # 限制长度
        if len(filename) > max_length:
            filename = filename[:max_length]
        
        # 添加扩展名
        if extension and not extension.startswith('.'):
            extension = '.' + extension
        
        return filename + extension
    
    def save_json(self, data: Dict[Any, Any], filepath: Union[str, Path], 
                  create_dirs: bool = True) -> bool:
        """
        保存JSON数据
        
        Args:
            data: 要保存的数据
            filepath: 文件路径
            create_dirs: 是否创建目录
        """
        try:
            filepath = Path(filepath)
            
            if create_dirs:
                filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"Saved JSON to: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save JSON to {filepath}: {e}")
            return False
    
    def load_json(self, filepath: Union[str, Path]) -> Optional[Dict[Any, Any]]:
        """
        加载JSON数据
        
        Args:
            filepath: 文件路径
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                self.logger.warning(f"File not found: {filepath}")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.logger.debug(f"Loaded JSON from: {filepath}")
            return data
            
        except Exception as e:
            self.logger.error(f"Failed to load JSON from {filepath}: {e}")
            return None
    
    def save_text(self, content: str, filepath: Union[str, Path], 
                  encoding: str = 'utf-8', create_dirs: bool = True) -> bool:
        """
        保存文本内容
        
        Args:
            content: 文本内容
            filepath: 文件路径
            encoding: 编码格式
            create_dirs: 是否创建目录
        """
        try:
            filepath = Path(filepath)
            
            if create_dirs:
                filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding=encoding) as f:
                f.write(content)
            
            self.logger.debug(f"Saved text to: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save text to {filepath}: {e}")
            return False
    
    def load_text(self, filepath: Union[str, Path], 
                  encoding: str = 'utf-8') -> Optional[str]:
        """
        加载文本内容
        
        Args:
            filepath: 文件路径
            encoding: 编码格式
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                self.logger.warning(f"File not found: {filepath}")
                return None
            
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            
            self.logger.debug(f"Loaded text from: {filepath}")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to load text from {filepath}: {e}")
            return None
    
    def get_output_path(self, category: str, filename: str) -> Path:
        """
        获取标准输出路径
        
        Args:
            category: 文件类别 (scripts, scenes, images, audio, videos, subtitles)
            filename: 文件名
        """
        category_dirs = {
            'scripts': self.output_dir / "scripts",
            'scenes': self.output_dir / "scenes", 
            'images': self.output_dir / "images",
            'audio': self.output_dir / "audio",
            'videos': self.output_dir / "videos",
            'subtitles': self.output_dir / "subtitles",
            'manifests': self.output_dir / "manifests",
            'logs': self.output_dir / "logs",
            'temp': self.output_dir / "temp",
            'debug': self.output_dir / "debug"
        }
        
        if category not in category_dirs:
            raise ValueError(f"Unknown category: {category}")
        
        return category_dirs[category] / filename
    
    def get_temp_path(self, category: str, filename: str) -> Path:
        """
        获取临时文件路径
        
        Args:
            category: 文件类别 (images, audio, processing)
            filename: 文件名
        """
        category_dirs = {
            'images': self.temp_dir / "images",
            'audio': self.temp_dir / "audio",
            'processing': self.temp_dir / "processing"
        }
        
        if category not in category_dirs:
            raise ValueError(f"Unknown temp category: {category}")
        
        return category_dirs[category] / filename
    
    def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """
        清理临时文件
        
        Args:
            max_age_hours: 文件最大保留时间（小时）
        
        Returns:
            清理的文件数量
        """
        cleaned_count = 0
        current_time = datetime.now().timestamp()
        max_age_seconds = max_age_hours * 3600
        
        try:
            for temp_file in self.temp_dir.rglob("*"):
                if temp_file.is_file():
                    file_age = current_time - temp_file.stat().st_mtime
                    
                    if file_age > max_age_seconds:
                        try:
                            temp_file.unlink()
                            cleaned_count += 1
                            self.logger.debug(f"Cleaned temp file: {temp_file}")
                        except Exception as e:
                            self.logger.warning(f"Failed to clean temp file {temp_file}: {e}")
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned {cleaned_count} temp files")
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup temp files: {e}")
        
        return cleaned_count
    
    def get_file_info(self, filepath: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        获取文件信息
        
        Args:
            filepath: 文件路径
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                return None
            
            stat = filepath.stat()
            
            return {
                'path': str(filepath),
                'name': filepath.name,
                'size_bytes': stat.st_size,
                'size_mb': stat.st_size / 1024 / 1024,
                'created_at': datetime.fromtimestamp(stat.st_ctime),
                'modified_at': datetime.fromtimestamp(stat.st_mtime),
                'is_file': filepath.is_file(),
                'is_dir': filepath.is_dir(),
                'extension': filepath.suffix
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get file info for {filepath}: {e}")
            return None
    
    def list_files(self, directory: Union[str, Path], 
                   pattern: str = "*", recursive: bool = False) -> List[Path]:
        """
        列出目录中的文件
        
        Args:
            directory: 目录路径
            pattern: 文件匹配模式
            recursive: 是否递归搜索
        """
        try:
            directory = Path(directory)
            
            if not directory.exists() or not directory.is_dir():
                return []
            
            if recursive:
                files = list(directory.rglob(pattern))
            else:
                files = list(directory.glob(pattern))
            
            # 只返回文件，不包括目录
            return [f for f in files if f.is_file()]
            
        except Exception as e:
            self.logger.error(f"Failed to list files in {directory}: {e}")
            return []
    
    def copy_file(self, src: Union[str, Path], dst: Union[str, Path], 
                  create_dirs: bool = True) -> bool:
        """
        复制文件
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
            create_dirs: 是否创建目标目录
        """
        try:
            src = Path(src)
            dst = Path(dst)
            
            if not src.exists():
                self.logger.error(f"Source file not found: {src}")
                return False
            
            if create_dirs:
                dst.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(src, dst)
            self.logger.debug(f"Copied file: {src} -> {dst}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to copy file {src} -> {dst}: {e}")
            return False
    
    def move_file(self, src: Union[str, Path], dst: Union[str, Path], 
                  create_dirs: bool = True) -> bool:
        """
        移动文件
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
            create_dirs: 是否创建目标目录
        """
        try:
            src = Path(src)
            dst = Path(dst)
            
            if not src.exists():
                self.logger.error(f"Source file not found: {src}")
                return False
            
            if create_dirs:
                dst.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(src), str(dst))
            self.logger.debug(f"Moved file: {src} -> {dst}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to move file {src} -> {dst}: {e}")
            return False
    
    def delete_file(self, filepath: Union[str, Path]) -> bool:
        """
        删除文件
        
        Args:
            filepath: 文件路径
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                self.logger.warning(f"File not found: {filepath}")
                return True
            
            if filepath.is_file():
                filepath.unlink()
            elif filepath.is_dir():
                shutil.rmtree(filepath)
            
            self.logger.debug(f"Deleted: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete {filepath}: {e}")
            return False
    
    def get_directory_size(self, directory: Union[str, Path]) -> Dict[str, Any]:
        """
        获取目录大小信息
        
        Args:
            directory: 目录路径
        """
        try:
            directory = Path(directory)
            
            if not directory.exists() or not directory.is_dir():
                return {'total_size_bytes': 0, 'total_size_mb': 0, 'file_count': 0}
            
            total_size = 0
            file_count = 0
            
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                        file_count += 1
                    except:
                        pass
            
            return {
                'total_size_bytes': total_size,
                'total_size_mb': total_size / 1024 / 1024,
                'file_count': file_count
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get directory size for {directory}: {e}")
            return {'total_size_bytes': 0, 'total_size_mb': 0, 'file_count': 0}
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"FileManager(output={self.output_dir}, temp={self.temp_dir})"