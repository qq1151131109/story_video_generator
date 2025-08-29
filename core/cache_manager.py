"""
缓存管理系统 - 避免重复API调用，节省成本
"""
import json
import hashlib
import time
from pathlib import Path
from typing import Any, Optional, Dict
import pickle
import logging
import threading
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    created_at: float
    access_count: int = 0
    last_accessed: float = 0

class CacheManager:
    """
    缓存管理系统 - 避免重复API调用，节省成本
    
    支持的缓存类型：
    - scripts: 文案生成缓存
    - scenes: 分镜分割缓存
    - images: 图像生成缓存
    - audio: 语音合成缓存
    - prompts: 提示词优化缓存
    """
    
    def __init__(self, cache_dir: str = "output/cache", 
                 ttl_hours: int = 24, max_size_mb: int = 1024):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.ttl_seconds = ttl_hours * 3600
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.logger = logging.getLogger(__name__)
        
        # 线程锁，确保缓存操作线程安全
        self._lock = threading.RLock()
        
        # 缓存分类目录
        self.cache_types = {
            'scripts': self.cache_dir / 'scripts',
            'scenes': self.cache_dir / 'scenes', 
            'images': self.cache_dir / 'images',
            'audio': self.cache_dir / 'audio',
            'prompts': self.cache_dir / 'prompts',
            'characters': self.cache_dir / 'characters',
            'themes': self.cache_dir / 'themes'
        }
        
        # 创建缓存目录
        for cache_type_dir in self.cache_types.values():
            cache_type_dir.mkdir(exist_ok=True)
        
        # 内存缓存（热缓存）
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._memory_cache_size = 0
        self._max_memory_cache_size = 100 * 1024 * 1024  # 100MB
        
        # 启动时清理过期缓存
        self._cleanup_expired_cache()
    
    def get_cache_key(self, data: Any) -> str:
        """生成缓存键"""
        if isinstance(data, str):
            content = data
        elif isinstance(data, dict):
            content = json.dumps(data, sort_keys=True, ensure_ascii=False)
        elif isinstance(data, (list, tuple)):
            content = json.dumps(data, ensure_ascii=False)
        else:
            content = str(data)
        
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]  # 使用前16位
    
    def _get_cache_path(self, cache_type: str, cache_key: str) -> Path:
        """获取缓存文件路径"""
        if cache_type not in self.cache_types:
            raise ValueError(f"Unknown cache type: {cache_type}")
        
        return self.cache_types[cache_type] / f"{cache_key}.cache"
    
    def _get_memory_cache_key(self, cache_type: str, cache_key: str) -> str:
        """获取内存缓存键"""
        return f"{cache_type}:{cache_key}"
    
    def get(self, cache_type: str, cache_key: str) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            cache_type: 缓存类型
            cache_key: 缓存键
        """
        with self._lock:
            try:
                # 先检查内存缓存
                memory_key = self._get_memory_cache_key(cache_type, cache_key)
                if memory_key in self._memory_cache:
                    entry = self._memory_cache[memory_key]
                    
                    # 检查TTL
                    if time.time() - entry.created_at <= self.ttl_seconds:
                        entry.access_count += 1
                        entry.last_accessed = time.time()
                        self.logger.debug(f"Memory cache hit: {cache_type}/{cache_key}")
                        return entry.data
                    else:
                        # 过期，从内存中删除
                        del self._memory_cache[memory_key]
                
                # 检查磁盘缓存
                cache_path = self._get_cache_path(cache_type, cache_key)
                
                if not cache_path.exists():
                    return None
                
                # 检查TTL
                if time.time() - cache_path.stat().st_mtime > self.ttl_seconds:
                    cache_path.unlink()
                    return None
                
                # 读取缓存
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                
                # 加载到内存缓存
                self._add_to_memory_cache(memory_key, cached_data)
                
                self.logger.debug(f"Disk cache hit: {cache_type}/{cache_key}")
                return cached_data
                
            except Exception as e:
                self.logger.warning(f"Cache read error for {cache_type}/{cache_key}: {e}")
                return None
    
    def set(self, cache_type: str, cache_key: str, data: Any) -> bool:
        """
        设置缓存
        
        Args:
            cache_type: 缓存类型
            cache_key: 缓存键
            data: 缓存数据
        """
        with self._lock:
            try:
                # 检查缓存大小限制
                self._cleanup_if_needed()
                
                # 写入磁盘缓存
                cache_path = self._get_cache_path(cache_type, cache_key)
                with open(cache_path, 'wb') as f:
                    pickle.dump(data, f)
                
                # 添加到内存缓存
                memory_key = self._get_memory_cache_key(cache_type, cache_key)
                self._add_to_memory_cache(memory_key, data)
                
                self.logger.debug(f"Cache set: {cache_type}/{cache_key}")
                return True
                
            except Exception as e:
                self.logger.error(f"Cache write error for {cache_type}/{cache_key}: {e}")
                return False
    
    def _add_to_memory_cache(self, memory_key: str, data: Any):
        """添加到内存缓存"""
        try:
            data_size = len(pickle.dumps(data))
            
            # 如果数据太大，不添加到内存缓存
            if data_size > self._max_memory_cache_size * 0.1:  # 超过10%的内存缓存大小
                return
            
            # 清理内存缓存空间
            while (self._memory_cache_size + data_size > self._max_memory_cache_size 
                   and self._memory_cache):
                self._evict_lru_memory_cache()
            
            # 添加到内存缓存
            entry = CacheEntry(
                data=data,
                created_at=time.time(),
                access_count=1,
                last_accessed=time.time()
            )
            
            self._memory_cache[memory_key] = entry
            self._memory_cache_size += data_size
            
        except Exception as e:
            self.logger.warning(f"Failed to add to memory cache: {e}")
    
    def _evict_lru_memory_cache(self):
        """清除最少使用的内存缓存项"""
        if not self._memory_cache:
            return
        
        # 找到最少使用的项
        lru_key = min(self._memory_cache.keys(), 
                     key=lambda k: (self._memory_cache[k].access_count, 
                                   self._memory_cache[k].last_accessed))
        
        # 删除项并更新大小
        try:
            entry = self._memory_cache[lru_key]
            data_size = len(pickle.dumps(entry.data))
            del self._memory_cache[lru_key]
            self._memory_cache_size -= data_size
            self.logger.debug(f"Evicted from memory cache: {lru_key}")
        except Exception as e:
            self.logger.warning(f"Failed to evict from memory cache: {e}")
    
    def _cleanup_if_needed(self):
        """清理过期和超大缓存"""
        current_time = time.time()
        total_size = 0
        cache_files = []
        
        # 收集所有缓存文件信息
        for cache_type_dir in self.cache_types.values():
            for cache_file in cache_type_dir.glob("*.cache"):
                try:
                    stat = cache_file.stat()
                    cache_files.append({
                        'path': cache_file,
                        'mtime': stat.st_mtime,
                        'size': stat.st_size
                    })
                    total_size += stat.st_size
                except Exception as e:
                    self.logger.warning(f"Failed to stat cache file {cache_file}: {e}")
        
        # 删除过期文件
        removed_count = 0
        for cache_file in cache_files[:]:
            if current_time - cache_file['mtime'] > self.ttl_seconds:
                try:
                    cache_file['path'].unlink()
                    cache_files.remove(cache_file)
                    total_size -= cache_file['size']
                    removed_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete expired cache file: {e}")
        
        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} expired cache files")
        
        # 如果还是超出大小限制，删除最旧的文件
        if total_size > self.max_size_bytes:
            cache_files.sort(key=lambda x: x['mtime'])
            target_size = int(self.max_size_bytes * 0.8)  # 清理到80%
            
            removed_size = 0
            while total_size - removed_size > target_size and cache_files:
                oldest_file = cache_files.pop(0)
                try:
                    oldest_file['path'].unlink()
                    removed_size += oldest_file['size']
                except Exception as e:
                    self.logger.warning(f"Failed to delete old cache file: {e}")
            
            if removed_size > 0:
                self.logger.info(f"Cleaned up {removed_size / 1024 / 1024:.1f}MB old cache files")
    
    def _cleanup_expired_cache(self):
        """启动时清理过期缓存"""
        try:
            current_time = time.time()
            removed_count = 0
            
            for cache_type_dir in self.cache_types.values():
                if not cache_type_dir.exists():
                    continue
                    
                for cache_file in cache_type_dir.glob("*.cache"):
                    try:
                        if current_time - cache_file.stat().st_mtime > self.ttl_seconds:
                            cache_file.unlink()
                            removed_count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to clean expired cache file {cache_file}: {e}")
            
            if removed_count > 0:
                self.logger.info(f"Startup: cleaned up {removed_count} expired cache files")
        
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired cache on startup: {e}")
    
    def clear_cache(self, cache_type: Optional[str] = None):
        """
        清空缓存
        
        Args:
            cache_type: 指定要清空的缓存类型，None表示清空所有
        """
        with self._lock:
            try:
                if cache_type:
                    # 清空指定类型的缓存
                    cache_dir = self.cache_types.get(cache_type)
                    if cache_dir and cache_dir.exists():
                        for cache_file in cache_dir.glob("*.cache"):
                            cache_file.unlink()
                        self.logger.info(f"Cleared cache type: {cache_type}")
                    
                    # 清空内存缓存中对应的项
                    keys_to_remove = [k for k in self._memory_cache.keys() if k.startswith(f"{cache_type}:")]
                    for key in keys_to_remove:
                        del self._memory_cache[key]
                    
                else:
                    # 清空所有缓存
                    for cache_dir in self.cache_types.values():
                        if cache_dir.exists():
                            for cache_file in cache_dir.glob("*.cache"):
                                cache_file.unlink()
                    
                    # 清空内存缓存
                    self._memory_cache.clear()
                    self._memory_cache_size = 0
                    
                    self.logger.info("Cleared all cache")
            
            except Exception as e:
                self.logger.error(f"Failed to clear cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            stats = {
                'memory_cache': {
                    'entries': len(self._memory_cache),
                    'size_mb': self._memory_cache_size / 1024 / 1024,
                    'max_size_mb': self._max_memory_cache_size / 1024 / 1024
                },
                'disk_cache': {},
                'total_size_mb': 0
            }
            
            total_size = 0
            for cache_type, cache_dir in self.cache_types.items():
                if not cache_dir.exists():
                    stats['disk_cache'][cache_type] = {'entries': 0, 'size_mb': 0}
                    continue
                
                entries = 0
                type_size = 0
                for cache_file in cache_dir.glob("*.cache"):
                    try:
                        entries += 1
                        type_size += cache_file.stat().st_size
                    except:
                        pass
                
                stats['disk_cache'][cache_type] = {
                    'entries': entries,
                    'size_mb': type_size / 1024 / 1024
                }
                total_size += type_size
            
            stats['total_size_mb'] = total_size / 1024 / 1024
            stats['max_size_mb'] = self.max_size_bytes / 1024 / 1024
            
            return stats
    
    def __str__(self) -> str:
        """字符串表示"""
        stats = self.get_cache_stats()
        return f"CacheManager(memory: {stats['memory_cache']['entries']} entries, " \
               f"disk: {stats['total_size_mb']:.1f}MB)"