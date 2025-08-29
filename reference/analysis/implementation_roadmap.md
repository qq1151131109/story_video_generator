# 历史故事批量生产系统 - 详细实施路线图

## 🎯 项目目标

基于Coze工作流"沉浸式历史故事"，开发一个完整的Python本地实现，支持批量生产高质量历史故事视频，并扩展支持多语言（中文、英文、西班牙语等）。

## 📋 实施计划概览

### 总体时间安排：10-12天
- **阶段一**：核心框架搭建（2天）
- **阶段二**：内容生成模块（3天）  
- **阶段三**：媒体生成模块（3天）
- **阶段四**：视频合成模块（2天）
- **阶段五**：多语言支持（1天）
- **阶段六**：测试优化（1天）

---

## 🏗️ 阶段一：核心框架搭建（第1-2天）

### Day 1: 项目结构和配置系统

#### 1.1 创建项目结构
```bash
story_generator/
├── config/                    # 配置文件
│   ├── settings.json          # 主配置
│   ├── themes/               # 主题库
│   │   ├── zh.json          # 中文主题
│   │   ├── en.json          # 英文主题  
│   │   └── es.json          # 西班牙语主题
│   ├── prompts/              # 提示词模板
│   │   ├── zh/              # 中文提示词
│   │   ├── en/              # 英文提示词
│   │   └── es/              # 西班牙语提示词
│   └── api_config.json       # API配置
├── core/                     # 核心引擎
├── content/                  # 内容生成
├── media/                    # 媒体生成
├── video/                    # 视频合成
├── utils/                    # 工具库
├── output/                   # 输出目录
├── tests/                    # 测试文件
├── requirements.txt
├── main.py
└── README.md
```

#### 1.2 配置管理系统 (`core/config_manager.py`)
```python
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

@dataclass
class ModelConfig:
    """LLM模型配置"""
    name: str
    temperature: float
    max_tokens: int
    api_base: str
    api_key: str

@dataclass  
class MediaConfig:
    """媒体生成配置"""
    image_resolution: str = "1024x768"
    image_quality: str = "high"
    voice_speed: float = 1.2
    voice_volume: float = 1.0
    
@dataclass
class VideoConfig:
    """视频合成配置"""
    resolution: str = "1920x1080"
    fps: int = 30
    format: str = "mp4"

class ConfigManager:
    """配置管理器 - 完全基于原Coze工作流参数"""
    
    def __init__(self, config_path: str = "config/settings.json"):
        self.config_path = Path(config_path)
        self.config_dir = self.config_path.parent
        self.logger = logging.getLogger(__name__)
        
        # 加载主配置
        self._load_main_config()
        
        # 加载多语言配置
        self._load_language_configs()
        
        # 加载API配置
        self._load_api_configs()
    
    def _load_main_config(self):
        """加载主配置文件"""
        if not self.config_path.exists():
            self._create_default_config()
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
    
    def _create_default_config(self):
        """创建默认配置文件（基于原Coze工作流）"""
        default_config = {
            "general": {
                "output_dir": "output",
                "temp_dir": "output/temp", 
                "log_level": "INFO",
                "max_concurrent_tasks": 3,  # 对应原工作流批处理并发数
                "supported_languages": ["zh", "en", "es"],
                "default_language": "zh"
            },
            "llm": {
                # 对应Node_121343配置
                "script_generation": {
                    "model": "deepseek-v3",
                    "temperature": 0.8,
                    "max_tokens": 1024
                },
                # 对应Node_1199098配置  
                "theme_extraction": {
                    "model": "deepseek-v3",
                    "temperature": 1.0,
                    "max_tokens": 512
                },
                # 对应Node_1165778配置
                "scene_splitting": {
                    "model": "deepseek-v3", 
                    "temperature": 0.8,
                    "max_tokens": 8192
                },
                # 对应Node_186126配置
                "image_prompts": {
                    "model": "deepseek-v3-0324",
                    "temperature": 1.0,
                    "max_tokens": 16384
                },
                # 对应Node_1301843配置
                "character_analysis": {
                    "model": "deepseek-v3",
                    "temperature": 0.8, 
                    "max_tokens": 8192
                }
            },
            "media": {
                "image": {
                    "resolution": "1024x768",  # 对应原工作流custom_ratio
                    "quality": "high",
                    "style": "ancient_horror",
                    "ddim_steps": 40,  # 对应原工作流采样步数
                    "model_id": 8  # 对应原工作流模型ID
                },
                "audio": {
                    "voice_id": "7468512265134932019",  # 对应原工作流悬疑解说音色
                    "voice_speed": 1.2,  # 对应原工作流语速
                    "voice_volume": 1.0,  # 对应原工作流音量
                    "background_music_volume": 0.3
                }
            },
            "video": {
                "resolution": "1440x1080",  # 对应原工作流草稿尺寸
                "fps": 30,
                "format": "mp4",
                "enable_subtitles": True,
                "enable_keyframes": True
            },
            "subtitle": {
                "max_line_length": 25,  # 对应原工作流SUB_CONFIG.MAX_LINE_LENGTH
                "split_priority": ["。","！","？","，",",","：",":","、","；",";"," "],
                "main_font_size": 7,  # 对应Node_158201配置
                "title_font_size": 40,  # 对应Node_1182713配置
                "main_color": "#FFFFFF",
                "main_border_color": "#000000", 
                "title_color": "#000000",
                "title_border_color": "#ffffff"
            },
            "animation": {
                "scene_scale_range": [1.0, 1.5],  # 对应Node_120984场景缩放
                "character_scale_sequence": [2.0, 1.2, 1.0],  # 对应Node_120984主角缩放
                "character_scale_timing": [0, 533333],  # 对应Node_120984时间点
                "easing": "linear"
            },
            "cache": {
                "enabled": True,
                "ttl_hours": 24,
                "max_size_mb": 1024
            }
        }
        
        # 创建配置目录
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入默认配置
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Created default config at {self.config_path}")
```

#### 1.3 多语言主题库配置

**`config/themes/zh.json` (中文主题库)**
```json
{
  "theme_categories": {
    "战争历史": [
      "三国演义赤壁之战",
      "秦始皇统一六国",
      "项羽乌江自刎", 
      "汉武帝抗击匈奴",
      "岳飞抗金传说",
      "成吉思汗西征"
    ],
    "宫廷秘史": [
      "武则天登基称帝",
      "杨贵妃安史之乱",
      "慈禧太后垂帘听政", 
      "康熙平定三藩",
      "雍正继位之谜",
      "乾隆下江南"
    ],
    "民间传说": [
      "包青天审案传说",
      "济公活佛传说",
      "白蛇传说",
      "梁山伯祝英台",
      "孟姜女哭长城",
      "牛郎织女传说"
    ],
    "英雄豪杰": [
      "关羽过五关斩六将",
      "赵云长坂坡救主", 
      "花木兰替父从军",
      "岳母刺字精忠报国",
      "文天祥正气歌",
      "史可法守扬州"
    ]
  },
  "batch_config": {
    "themes_per_batch": 5,
    "concurrent_processing": 3
  }
}
```

**`config/themes/en.json` (英文主题库)**
```json
{
  "theme_categories": {
    "Ancient Warfare": [
      "The Battle of Red Cliffs in Three Kingdoms",
      "Qin Shi Huang Unifies China",
      "Xiang Yu's Last Stand at Wujiang",
      "Emperor Wu's Campaign Against Xiongnu",
      "Yue Fei's Fight Against Jin Dynasty",
      "Genghis Khan's Western Conquest"
    ],
    "Imperial Secrets": [
      "Wu Zetian Becomes Empress",
      "Yang Guifei and An Lushan Rebellion", 
      "Empress Dowager Cixi's Regency",
      "Emperor Kangxi Suppresses Three Feudatories",
      "The Mystery of Yongzheng's Succession",
      "Emperor Qianlong's Southern Tours"
    ],
    "Folk Legends": [
      "Judge Bao's Court Cases",
      "Living Buddha Ji Gong's Legends",
      "The Legend of White Snake",
      "The Butterfly Lovers Story",
      "Meng Jiangnu Weeps at Great Wall",
      "The Cowherd and Weaver Girl"
    ],
    "Heroic Tales": [
      "Guan Yu Passes Five Barriers",
      "Zhao Yun Rescues Liu Shan at Changban",
      "Mulan Joins Army for Father", 
      "Yue Fei's Mother Tattoos Loyalty",
      "Wen Tianxiang's Song of Righteousness",
      "Shi Kefa Defends Yangzhou"
    ]
  },
  "batch_config": {
    "themes_per_batch": 5,
    "concurrent_processing": 3
  }
}
```

**`config/themes/es.json` (西班牙语主题库)**
```json
{
  "theme_categories": {
    "Guerra Antigua": [
      "La Batalla de los Acantilados Rojos",
      "Qin Shi Huang Unifica China",
      "La Última Batalla de Xiang Yu en Wujiang",
      "Campaña del Emperador Wu contra Xiongnu",
      "Yue Fei Lucha contra la Dinastía Jin",
      "La Conquista Occidental de Genghis Khan"
    ],
    "Secretos Imperiales": [
      "Wu Zetian se Convierte en Emperatriz",
      "Yang Guifei y la Rebelión de An Lushan",
      "La Regencia de la Emperatriz Viuda Cixi",
      "El Emperador Kangxi Suprime los Tres Feudatorios",
      "El Misterio de la Sucesión de Yongzheng",
      "Las Giras del Sur del Emperador Qianlong"
    ],
    "Leyendas Populares": [
      "Los Casos del Juez Bao",
      "Leyendas del Buda Viviente Ji Gong",
      "La Leyenda de la Serpiente Blanca",
      "La Historia de los Amantes Mariposa",
      "Meng Jiangnu Llora en la Gran Muralla",
      "El Vaquero y la Tejedora"
    ],
    "Cuentos Heroicos": [
      "Guan Yu Pasa Cinco Barreras",
      "Zhao Yun Rescata a Liu Shan en Changban",
      "Mulan se Une al Ejército por su Padre",
      "La Madre de Yue Fei Tatúa la Lealtad",
      "Canción de la Rectitud de Wen Tianxiang",
      "Shi Kefa Defiende Yangzhou"
    ]
  },
  "batch_config": {
    "themes_per_batch": 5,
    "concurrent_processing": 3
  }
}
```

### Day 2: 缓存系统和工具库

#### 2.1 缓存管理系统 (`core/cache_manager.py`)
```python
import json
import hashlib
import time
from pathlib import Path
from typing import Any, Optional, Dict
import pickle
import logging

class CacheManager:
    """缓存管理系统 - 避免重复API调用，节省成本"""
    
    def __init__(self, cache_dir: str = "output/cache", 
                 ttl_hours: int = 24, max_size_mb: int = 1024):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.ttl_seconds = ttl_hours * 3600
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.logger = logging.getLogger(__name__)
        
        # 缓存分类
        self.cache_types = {
            'scripts': self.cache_dir / 'scripts',
            'scenes': self.cache_dir / 'scenes', 
            'images': self.cache_dir / 'images',
            'audio': self.cache_dir / 'audio',
            'prompts': self.cache_dir / 'prompts'
        }
        
        # 创建缓存目录
        for cache_type_dir in self.cache_types.values():
            cache_type_dir.mkdir(exist_ok=True)
    
    def _get_cache_key(self, data: Any) -> str:
        """生成缓存键"""
        if isinstance(data, str):
            content = data
        elif isinstance(data, dict):
            content = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            content = str(data)
        
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, cache_type: str, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_types[cache_type] / f"{cache_key}.cache"
    
    def get(self, cache_type: str, cache_key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            cache_path = self._get_cache_path(cache_type, cache_key)
            
            if not cache_path.exists():
                return None
            
            # 检查TTL
            if time.time() - cache_path.stat().st_mtime > self.ttl_seconds:
                cache_path.unlink()
                return None
            
            with open(cache_path, 'rb') as f:
                cached_data = pickle.load(f)
            
            self.logger.debug(f"Cache hit: {cache_type}/{cache_key}")
            return cached_data
            
        except Exception as e:
            self.logger.warning(f"Cache read error: {e}")
            return None
    
    def set(self, cache_type: str, cache_key: str, data: Any) -> bool:
        """设置缓存"""
        try:
            cache_path = self._get_cache_path(cache_type, cache_key)
            
            # 检查缓存大小限制
            self._cleanup_if_needed()
            
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            
            self.logger.debug(f"Cache set: {cache_type}/{cache_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Cache write error: {e}")
            return False
    
    def _cleanup_if_needed(self):
        """清理过期和超大缓存"""
        current_time = time.time()
        total_size = 0
        cache_files = []
        
        # 收集所有缓存文件信息
        for cache_type_dir in self.cache_types.values():
            for cache_file in cache_type_dir.glob("*.cache"):
                stat = cache_file.stat()
                cache_files.append({
                    'path': cache_file,
                    'mtime': stat.st_mtime,
                    'size': stat.st_size
                })
                total_size += stat.st_size
        
        # 删除过期文件
        for cache_file in cache_files[:]:
            if current_time - cache_file['mtime'] > self.ttl_seconds:
                cache_file['path'].unlink()
                cache_files.remove(cache_file)
                total_size -= cache_file['size']
        
        # 如果还是超出大小限制，删除最旧的文件
        if total_size > self.max_size_bytes:
            cache_files.sort(key=lambda x: x['mtime'])
            while total_size > self.max_size_bytes * 0.8 and cache_files:
                oldest_file = cache_files.pop(0)
                oldest_file['path'].unlink()
                total_size -= oldest_file['size']
```

#### 2.2 工具库 (`utils/`)

**`utils/file_manager.py`**
```python
import shutil
import tempfile
from pathlib import Path
from typing import Optional, List
import logging
from urllib.parse import urlparse
import requests
import mimetypes

class FileManager:
    """文件管理工具"""
    
    def __init__(self, base_output_dir: str = "output"):
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建子目录
        self.subdirs = {
            'videos': self.base_output_dir / 'videos',
            'images': self.base_output_dir / 'images',
            'audios': self.base_output_dir / 'audios', 
            'scripts': self.base_output_dir / 'scripts',
            'temp': self.base_output_dir / 'temp',
            'logs': self.base_output_dir / 'logs'
        }
        
        for subdir in self.subdirs.values():
            subdir.mkdir(exist_ok=True)
            
        self.logger = logging.getLogger(__name__)
    
    def download_file(self, url: str, target_dir: str = 'temp', 
                     filename: Optional[str] = None) -> Optional[Path]:
        """下载文件到本地"""
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # 确定文件名
            if not filename:
                # 尝试从URL获取文件名
                parsed_url = urlparse(url)
                filename = Path(parsed_url.path).name
                
                if not filename or '.' not in filename:
                    # 根据Content-Type确定扩展名
                    content_type = response.headers.get('content-type', '')
                    ext = mimetypes.guess_extension(content_type.split(';')[0])
                    filename = f"download_{int(time.time())}{ext or ''}"
            
            target_path = self.subdirs[target_dir] / filename
            
            # 下载文件
            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.info(f"Downloaded file: {target_path}")
            return target_path
            
        except Exception as e:
            self.logger.error(f"Failed to download {url}: {e}")
            return None
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """清理临时文件"""
        temp_dir = self.subdirs['temp']
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for temp_file in temp_dir.glob("*"):
            if temp_file.is_file():
                file_age = current_time - temp_file.stat().st_mtime
                if file_age > max_age_seconds:
                    temp_file.unlink()
                    self.logger.debug(f"Cleaned up temp file: {temp_file}")
    
    def get_batch_output_dir(self, batch_id: str) -> Path:
        """为批次创建输出目录"""
        batch_dir = self.base_output_dir / f"batch_{batch_id}"
        batch_dir.mkdir(exist_ok=True)
        
        # 创建批次子目录
        for subdir_name in ['videos', 'assets', 'metadata', 'logs']:
            (batch_dir / subdir_name).mkdir(exist_ok=True)
            
        return batch_dir
```

---

## 📝 阶段二：内容生成模块（第3-5天）

### Day 3: 多语言LLM文案生成器

#### 3.1 多语言提示词模板

**`config/prompts/zh/script_generation.txt`（基于Node_121343）**
```
根据主题：{{theme}}，生成一个1000字左右的沉浸式历史故事，采用以下结构：

1. 悬念开场（100字）：用疑问句开头，制造悬念
   - 以"真的吗？"或"你知道吗？"开始
   - 提出一个令人震惊的历史问题
   - 激发观众的好奇心

2. 身份代入（200字）：第二人称"你"，让观众代入历史人物
   - 使用"你是..."的句式
   - 描述具体的历史场景和环境
   - 让观众感受历史人物的处境

3. 冲突升级（300字）：描述历史事件的核心矛盾
   - 详细描述历史冲突的背景
   - 展现各方势力的对立
   - 营造紧张的氛围

4. 破局细节（300字）：揭示关键转折点的细节
   - 描述决定性的历史时刻
   - 展现人物的关键选择
   - 揭示历史的转折点

5. 主题收尾（100字）：点明历史意义
   - 总结历史事件的影响
   - 点出历史的启示意义
   - 给观众深刻的思考

要求：
- 大量使用感官描写（视觉、听觉、触觉）
- 多用短句，营造紧张节奏
- 每段不超过3句话
- 加入历史专业术语
- 情感渲染要到位
- 总字数控制在900-1100字之间

历史背景要求：
- 确保历史事实的准确性
- 适当添加戏剧化的细节描写
- 保持历史的严肃性和教育意义
```

**`config/prompts/en/script_generation.txt`**
```
Based on the theme: {{theme}}, generate an immersive historical story of about 1000 words using the following structure:

1. Suspenseful Opening (100 words): Start with a question to create suspense
   - Begin with "Really?" or "Did you know?"
   - Pose a shocking historical question
   - Spark audience curiosity

2. Identity Immersion (200 words): Use second person "you" to let audience embody historical figures
   - Use "You are..." sentence patterns
   - Describe specific historical scenes and environments
   - Let audience feel the situation of historical characters

3. Conflict Escalation (300 words): Describe the core contradictions of historical events
   - Detail the background of historical conflicts
   - Show the opposition of various forces
   - Create a tense atmosphere

4. Resolution Details (300 words): Reveal details of key turning points
   - Describe decisive historical moments
   - Show crucial choices of characters
   - Reveal historical turning points

5. Thematic Conclusion (100 words): Highlight historical significance
   - Summarize the impact of historical events
   - Point out the enlightening meaning of history
   - Give audience profound thoughts

Requirements:
- Extensive use of sensory descriptions (visual, auditory, tactile)
- Use short sentences to create tense rhythm
- No more than 3 sentences per paragraph
- Include historical professional terms
- Emotional rendering should be in place
- Total word count should be controlled between 900-1100 words

Historical Background Requirements:
- Ensure accuracy of historical facts
- Appropriately add dramatic detail descriptions
- Maintain the seriousness and educational significance of history
```

**`config/prompts/es/script_generation.txt`**
```
Basado en el tema: {{theme}}, genera una historia histórica inmersiva de aproximadamente 1000 palabras usando la siguiente estructura:

1. Apertura Suspense (100 palabras): Comienza con una pregunta para crear suspense
   - Empieza con "¿En serio?" o "¿Sabías que?"
   - Plantea una pregunta histórica impactante
   - Despierta la curiosidad de la audiencia

2. Inmersión de Identidad (200 palabras): Usa segunda persona "tú" para que la audiencia encarne figuras históricas
   - Usa patrones de oración "Tú eres..."
   - Describe escenas históricas específicas y ambientes
   - Deja que la audiencia sienta la situación de los personajes históricos

3. Escalada de Conflicto (300 palabras): Describe las contradicciones centrales de los eventos históricos
   - Detalla el trasfondo de los conflictos históricos
   - Muestra la oposición de varias fuerzas
   - Crea una atmósfera tensa

4. Detalles de Resolución (300 palabras): Revela detalles de puntos de inflexión clave
   - Describe momentos históricos decisivos
   - Muestra elecciones cruciales de personajes
   - Revela puntos de inflexión históricos

5. Conclusión Temática (100 palabras): Destaca la significancia histórica
   - Resume el impacto de eventos históricos
   - Señala el significado esclarecedor de la historia
   - Da pensamientos profundos a la audiencia

Requisitos:
- Uso extensivo de descripciones sensoriales (visual, auditiva, táctil)
- Usar oraciones cortas para crear ritmo tenso
- No más de 3 oraciones por párrafo
- Incluir términos profesionales históricos
- La representación emocional debe estar en su lugar
- El conteo total de palabras debe controlarse entre 900-1100 palabras

Requisitos de Antecedentes Históricos:
- Asegurar la precisión de los hechos históricos
- Agregar apropiadamente descripciones de detalles dramáticos
- Mantener la seriedad y significado educativo de la historia
```

#### 3.2 LLM服务集成 (`content/script_generator.py`)
```python
import asyncio
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging
from dataclasses import dataclass

import openai
from openai import AsyncOpenAI

@dataclass
class ScriptResult:
    """文案生成结果"""
    script: str
    theme_keywords: str
    word_count: int
    language: str
    metadata: Dict[str, Any]

class ScriptGenerator:
    """多语言文案生成器 - 基于Node_121343实现"""
    
    def __init__(self, config_manager, cache_manager):
        self.config = config_manager
        self.cache = cache_manager
        self.logger = logging.getLogger(__name__)
        
        # 初始化LLM客户端
        self.llm_config = self.config.get_llm_config('script_generation')
        self.client = AsyncOpenAI(
            base_url=self.llm_config.api_base,
            api_key=self.llm_config.api_key
        )
        
        # 加载多语言提示词模板
        self.prompt_templates = self._load_prompt_templates()
    
    def _load_prompt_templates(self) -> Dict[str, str]:
        """加载多语言提示词模板"""
        templates = {}
        prompts_dir = Path("config/prompts")
        
        for lang_code in self.config.get_supported_languages():
            template_path = prompts_dir / lang_code / "script_generation.txt"
            if template_path.exists():
                with open(template_path, 'r', encoding='utf-8') as f:
                    templates[lang_code] = f.read()
            else:
                self.logger.warning(f"Prompt template not found for language: {lang_code}")
        
        return templates
    
    async def generate_script(self, theme: str, language: str = "zh", 
                            custom_params: Optional[Dict] = None) -> ScriptResult:
        """
        生成历史故事文案
        
        Args:
            theme: 故事主题
            language: 语言代码 (zh/en/es)
            custom_params: 自定义参数
            
        Returns:
            ScriptResult: 生成结果
        """
        try:
            # 检查缓存
            cache_key = self.cache.get_cache_key({
                'theme': theme,
                'language': language,
                'params': custom_params or {}
            })
            
            cached_result = self.cache.get('scripts', cache_key)
            if cached_result:
                self.logger.info(f"Using cached script for theme: {theme}")
                return cached_result
            
            # 准备提示词
            prompt_template = self.prompt_templates.get(language)
            if not prompt_template:
                raise ValueError(f"Unsupported language: {language}")
            
            # 替换模板变量
            prompt = prompt_template.replace('{{theme}}', theme)
            
            # 调用LLM
            self.logger.info(f"Generating script for theme: {theme} (language: {language})")
            
            response = await self.client.chat.completions.create(
                model=self.llm_config.name,
                messages=[
                    {"role": "system", "content": "你是一位专业的历史故事创作者，擅长创作引人入胜的沉浸式历史故事。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens
            )
            
            generated_script = response.choices[0].message.content.strip()
            
            # 生成主题关键词（调用主题提取器）
            theme_keywords = await self._extract_theme_keywords(generated_script, language)
            
            # 构建结果
            result = ScriptResult(
                script=generated_script,
                theme_keywords=theme_keywords,
                word_count=len(generated_script),
                language=language,
                metadata={
                    'original_theme': theme,
                    'generation_model': self.llm_config.name,
                    'generation_params': {
                        'temperature': self.llm_config.temperature,
                        'max_tokens': self.llm_config.max_tokens
                    },
                    'custom_params': custom_params
                }
            )
            
            # 缓存结果
            self.cache.set('scripts', cache_key, result)
            
            self.logger.info(f"Generated script: {len(generated_script)} characters, theme: {theme_keywords}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to generate script for theme '{theme}': {str(e)}")
            raise
    
    async def _extract_theme_keywords(self, script: str, language: str) -> str:
        """提取主题关键词 - 基于Node_1199098实现"""
        try:
            # 多语言提示词
            extract_prompts = {
                'zh': f"""故事原文内容：{script}

请从以上历史故事中提取最核心的主题，生成一个2个字的标题。

要求：
1. 必须是2个汉字
2. 要概括故事核心主题
3. 朗朗上口，有视觉冲击力
4. 例如：赤壁、长城、变法、征战等

直接输出2个字，不要其他解释。""",

                'en': f"""Story content: {script}

Please extract the most core theme from the above historical story and generate a 2-word title.

Requirements:
1. Must be 2 English words
2. Should summarize the core theme of the story
3. Should be catchy and visually impactful
4. Examples: Red Cliffs, Great Wall, Reform, Conquest, etc.

Output only 2 words, no other explanation.""",

                'es': f"""Contenido de la historia: {script}

Por favor extrae el tema más central de la historia histórica anterior y genera un título de 2 palabras.

Requisitos:
1. Debe ser 2 palabras en español
2. Debe resumir el tema central de la historia
3. Debe ser pegadizo y visualmente impactante
4. Ejemplos: Acantilados Rojos, Gran Muralla, Reforma, Conquista, etc.

Salida solo 2 palabras, sin otra explicación."""
            }
            
            extract_prompt = extract_prompts.get(language, extract_prompts['zh'])
            
            # 使用对应Node_1199098的配置
            theme_config = self.config.get_llm_config('theme_extraction')
            
            response = await self.client.chat.completions.create(
                model=theme_config.name,
                messages=[
                    {"role": "user", "content": extract_prompt}
                ],
                temperature=theme_config.temperature,  # 1.0
                max_tokens=theme_config.max_tokens      # 512
            )
            
            theme_keywords = response.choices[0].message.content.strip()
            
            # 验证关键词格式
            if language == 'zh' and len(theme_keywords) > 4:  # 中文超过4个字符可能不是2个字
                theme_keywords = theme_keywords[:4]
            elif language in ['en', 'es'] and len(theme_keywords.split()) > 2:
                theme_keywords = ' '.join(theme_keywords.split()[:2])
            
            return theme_keywords
            
        except Exception as e:
            self.logger.error(f"Failed to extract theme keywords: {str(e)}")
            # 返回默认值
            default_themes = {
                'zh': '历史',
                'en': 'History',
                'es': 'Historia'
            }
            return default_themes.get(language, '历史')
```

### Day 4: 多语言分镜分割系统

#### 4.1 多语言分镜提示词

**`config/prompts/zh/scene_splitting.txt`（基于Node_1165778）**
```
# 角色
你是一位专业的故事创意转化师，你能够深入理解故事文案的情节、人物、场景等元素，用生动且具体的语言为绘画创作提供清晰的指引。

## 技能
### 技能1： 生成分镜字幕
1. 当用户提供故事文案时，仔细分析文案中的关键情节、人物形象、场景特点等要素。
2. 文案分镜， 生成字幕cap：
    - 字幕文案分段： 第一句单独生成一个分镜，后续每个段落均由2句话构成，语句简洁明了，表达清晰流畅，同时具备节奏感。
    - 分割文案后特别注意前后文的关联性与一致性，必须与用户提供的原文完全一致，不得进行任何修改、删减。字幕文案必须严格按照用户给的文案拆分，不能修改提供的内容更不能删除内容

===回复示例===
[{
          "cap":"字幕文案"
}]
===示例结束===

## 限制:
- 只围绕用户提供的故事文案进行分镜绘画提示词生成和主题提炼，拒绝回答与该任务无关的话题。
- 所输出的内容必须条理清晰，分镜绘画提示词要尽可能详细描述画面，主题必须为2个字。 
- 视频文案及分镜描述必须保持一致。
- 输出内容必须严格按照给定的 JSON 格式进行组织，不得偏离框架要求。
- 只对用户提示的内容进行分镜，不能更改原文
- 严格检查 输出的json格式正确性并进行修正，特别注意json格式不要少括号，逗号等

现在请对以下故事文案进行分镜分割：

{{content}}
```

#### 4.2 分镜分割器实现 (`content/scene_splitter.py`)
```python
import asyncio
import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

@dataclass
class Scene:
    """分镜场景"""
    index: int
    caption: str
    word_count: int
    estimated_duration: float
    scene_type: str

class SceneSplitter:
    """多语言分镜分割器 - 基于Node_1165778和Node_186126实现"""
    
    def __init__(self, config_manager, cache_manager):
        self.config = config_manager
        self.cache = cache_manager
        self.logger = logging.getLogger(__name__)
        
        # 初始化LLM客户端
        self.scene_config = self.config.get_llm_config('scene_splitting')
        self.prompt_config = self.config.get_llm_config('image_prompts')
        
        self.client = AsyncOpenAI(
            base_url=self.scene_config.api_base,
            api_key=self.scene_config.api_key
        )
        
        # 加载提示词模板
        self.scene_templates = self._load_scene_templates()
        self.prompt_templates = self._load_prompt_templates()
    
    async def split_and_generate_prompts(self, script: str, language: str = "zh") -> List[Dict[str, Any]]:
        """
        分镜分割并生成图像提示词
        
        Returns:
            List[Dict]: 包含cap和desc_promopt的分镜数据
        """
        try:
            # 检查缓存
            cache_key = self.cache.get_cache_key({
                'script': script,
                'language': language
            })
            
            cached_result = self.cache.get('scenes', cache_key)
            if cached_result:
                self.logger.info("Using cached scene split result")
                return cached_result
            
            # 步骤1: 分镜分割（对应Node_1165778）
            scenes_with_caps = await self._split_scenes(script, language)
            
            # 步骤2: 生成图像提示词（对应Node_186126）
            scenes_with_prompts = await self._generate_image_prompts(scenes_with_caps, language)
            
            # 缓存结果
            self.cache.set('scenes', cache_key, scenes_with_prompts)
            
            self.logger.info(f"Generated {len(scenes_with_prompts)} scenes with prompts")
            return scenes_with_prompts
            
        except Exception as e:
            self.logger.error(f"Failed to split scenes: {str(e)}")
            # 降级到规则分割
            return await self._fallback_rule_split(script, language)
    
    async def _split_scenes(self, script: str, language: str) -> List[Dict[str, str]]:
        """AI分镜分割 - 对应Node_1165778"""
        try:
            template = self.scene_templates.get(language)
            if not template:
                raise ValueError(f"Scene template not found for language: {language}")
            
            prompt = template.replace('{{content}}', script)
            
            response = await self.client.chat.completions.create(
                model=self.scene_config.name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.scene_config.temperature,  # 0.8
                max_tokens=self.scene_config.max_tokens     # 8192
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # 解析JSON响应
            try:
                scenes_data = json.loads(response_text)
                if isinstance(scenes_data, list):
                    return scenes_data
                else:
                    raise ValueError("Response is not a list")
            except json.JSONDecodeError as e:
                self.logger.warning(f"JSON parse error: {e}, trying to fix...")
                # 尝试修复JSON格式
                fixed_json = self._fix_json_format(response_text)
                return json.loads(fixed_json)
                
        except Exception as e:
            self.logger.error(f"AI scene splitting failed: {str(e)}")
            raise
    
    async def _generate_image_prompts(self, scenes_with_caps: List[Dict[str, str]], 
                                    language: str) -> List[Dict[str, Any]]:
        """生成图像提示词 - 对应Node_186126"""
        try:
            template = self.prompt_templates.get(language)
            if not template:
                raise ValueError(f"Prompt template not found for language: {language}")
            
            # 准备输入数据
            scenes_json = json.dumps(scenes_with_caps, ensure_ascii=False, indent=2)
            prompt = template.replace('{{scenes}}', scenes_json)
            
            response = await self.client.chat.completions.create(
                model=self.prompt_config.name,  # DeepSeek-V3-0324
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.prompt_config.temperature,  # 1.0
                max_tokens=self.prompt_config.max_tokens     # 16384
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # 解析JSON响应
            try:
                scenes_with_prompts = json.loads(response_text)
                
                # 验证数据格式
                for i, scene in enumerate(scenes_with_prompts):
                    if 'cap' not in scene or 'desc_promopt' not in scene:
                        raise ValueError(f"Scene {i} missing required fields")
                    
                    # 添加额外字段
                    scene.update({
                        'index': i,
                        'word_count': len(scene['cap']),
                        'estimated_duration': self._estimate_duration(scene['cap'], language),
                        'scene_type': self._detect_scene_type(scene['cap'], language)
                    })
                
                return scenes_with_prompts
                
            except json.JSONDecodeError as e:
                self.logger.warning(f"JSON parse error: {e}, trying to fix...")
                fixed_json = self._fix_json_format(response_text)
                return json.loads(fixed_json)
                
        except Exception as e:
            self.logger.error(f"Image prompt generation failed: {str(e)}")
            
            # 降级处理：为每个分镜生成基础提示词
            fallback_scenes = []
            for i, scene in enumerate(scenes_with_caps):
                fallback_scenes.append({
                    'cap': scene['cap'],
                    'desc_promopt': self._generate_fallback_prompt(scene['cap'], language),
                    'index': i,
                    'word_count': len(scene['cap']),
                    'estimated_duration': self._estimate_duration(scene['cap'], language),
                    'scene_type': 'buildup'
                })
            
            return fallback_scenes
    
    def _estimate_duration(self, text: str, language: str) -> float:
        """估算语音时长（秒）"""
        # 基于语言的平均语速
        chars_per_second = {
            'zh': 5.0,   # 中文：5字/秒
            'en': 12.0,  # 英文：12字符/秒
            'es': 10.0   # 西班牙语：10字符/秒
        }
        
        cps = chars_per_second.get(language, 5.0)
        base_duration = len(text) / cps
        
        # 考虑语速倍数1.2
        actual_duration = base_duration / 1.2
        
        # 最小时长3秒
        return max(actual_duration, 3.0)
    
    def _detect_scene_type(self, text: str, language: str) -> str:
        """检测场景类型"""
        # 多语言关键词映射
        scene_keywords = {
            'zh': {
                "opening": ["真的", "吗", "？", "竟然", "难道"],
                "buildup": ["你是", "你在", "此刻", "这时"],
                "conflict": ["然而", "但是", "却", "不料", "突然"],
                "climax": ["终于", "最后", "关键时刻", "生死关头"],
                "resolution": ["于是", "最终", "结果", "从此"],
                "ending": ["这一刻你终于明白", "原来", "其实", "才是"]
            },
            'en': {
                "opening": ["Really", "Did you know", "?", "Actually", "Could it be"],
                "buildup": ["You are", "You were", "At this moment", "Now"],
                "conflict": ["However", "But", "Yet", "Suddenly", "Unexpectedly"],
                "climax": ["Finally", "At last", "The crucial moment", "Life and death"],
                "resolution": ["Thus", "Eventually", "As a result", "From then on"],
                "ending": ["At this moment you finally understand", "It turns out", "Actually", "was the"]
            },
            'es': {
                "opening": ["¿En serio?", "¿Sabías que?", "?", "Realmente", "¿Podría ser?"],
                "buildup": ["Tú eres", "Tú estabas", "En este momento", "Ahora"],
                "conflict": ["Sin embargo", "Pero", "Aún así", "De repente", "Inesperadamente"],
                "climax": ["Finalmente", "Por fin", "El momento crucial", "Vida y muerte"],
                "resolution": ["Así", "Eventualmente", "Como resultado", "Desde entonces"],
                "ending": ["En este momento finalmente entiendes", "Resulta que", "En realidad", "era el"]
            }
        }
        
        keywords = scene_keywords.get(language, scene_keywords['zh'])
        
        # 检查各类型关键词
        for scene_type, type_keywords in keywords.items():
            if any(kw in text for kw in type_keywords):
                return scene_type
        
        return "buildup"  # 默认类型
    
    def _generate_fallback_prompt(self, caption: str, language: str) -> str:
        """生成降级图像提示词"""
        # 多语言基础风格描述
        base_styles = {
            'zh': "古代惊悚插画风格，颜色很深，黑暗中，黄昏，氛围凝重，庄严肃穆，构建出紧张氛围，古代服饰，古装，线条粗狂，清晰，高对比度，色彩低饱和，浅景深",
            'en': "Ancient horror illustration style, very dark colors, in darkness, dusk, solemn atmosphere, majestic and solemn, creating tense atmosphere, ancient costume, traditional clothing, rough lines, clear, high contrast, low saturation colors, shallow depth of field",
            'es': "Estilo de ilustración de terror antiguo, colores muy oscuros, en la oscuridad, anochecer, atmósfera solemne, majestuoso y solemne, creando atmósfera tensa, vestimenta antigua, ropa tradicional, líneas rugosas, claro, alto contraste, colores de baja saturación, poca profundidad de campo"
        }
        
        base_style = base_styles.get(language, base_styles['zh'])
        
        # 简单的关键词提取和场景描述
        if language == 'zh':
            # 中文关键词识别
            elements = []
            if "县令" in caption:
                elements.append("身穿官服的县令")
            elif "将军" in caption:
                elements.append("身穿盔甲的将军")
            elif "士兵" in caption:
                elements.append("古代士兵")
            elif "皇帝" in caption:
                elements.append("威严的皇帝")
            
            if "朝堂" in caption or "殿" in caption:
                elements.append("古代宫殿大厅")
            elif "战场" in caption:
                elements.append("古代战场")
            elif "城墙" in caption:
                elements.append("古代城墙")
            
            if elements:
                return f"{base_style}，{', '.join(elements)}"
            else:
                return f"{base_style}，古代场景，写实风格"
        
        # 英文和西班牙语使用通用描述
        return f"{base_style}, ancient scene, realistic style"
    
    async def _fallback_rule_split(self, script: str, language: str) -> List[Dict[str, Any]]:
        """规则分割降级方案"""
        try:
            self.logger.warning("Using fallback rule-based scene splitting")
            
            # 基于标点符号分割
            sentences = self._split_by_punctuation(script, language)
            
            scenes = []
            current_cap = ""
            sentence_count = 0
            
            for i, sentence in enumerate(sentences):
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                if i == 0:
                    # 第一句单独成镜
                    scenes.append({
                        'cap': sentence,
                        'desc_promopt': self._generate_fallback_prompt(sentence, language),
                        'index': len(scenes),
                        'word_count': len(sentence),
                        'estimated_duration': self._estimate_duration(sentence, language),
                        'scene_type': 'opening'
                    })
                else:
                    # 后续2句一组
                    if sentence_count == 0:
                        current_cap = sentence
                        sentence_count = 1
                    else:
                        current_cap += " " + sentence
                        
                        scenes.append({
                            'cap': current_cap,
                            'desc_promopt': self._generate_fallback_prompt(current_cap, language),
                            'index': len(scenes),
                            'word_count': len(current_cap),
                            'estimated_duration': self._estimate_duration(current_cap, language),
                            'scene_type': self._detect_scene_type(current_cap, language)
                        })
                        
                        current_cap = ""
                        sentence_count = 0
            
            # 处理剩余的单句
            if current_cap:
                scenes.append({
                    'cap': current_cap,
                    'desc_promopt': self._generate_fallback_prompt(current_cap, language),
                    'index': len(scenes),
                    'word_count': len(current_cap),
                    'estimated_duration': self._estimate_duration(current_cap, language),
                    'scene_type': 'ending'
                })
            
            self.logger.info(f"Fallback splitting generated {len(scenes)} scenes")
            return scenes
            
        except Exception as e:
            self.logger.error(f"Fallback rule split failed: {str(e)}")
            raise
    
    def _split_by_punctuation(self, text: str, language: str) -> List[str]:
        """根据标点符号分割句子"""
        if language == 'zh':
            # 中文标点符号
            pattern = r'[。！？]+'
        elif language == 'en':
            # 英文标点符号
            pattern = r'[.!?]+'
        elif language == 'es':
            # 西班牙语标点符号
            pattern = r'[.!?¡¿]+'
        else:
            pattern = r'[.!?。！？]+'
        
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _fix_json_format(self, text: str) -> str:
        """尝试修复JSON格式"""
        # 移除可能的markdown代码块标记
        text = re.sub(r'```json\s*|\s*```', '', text)
        
        # 尝试添加缺失的方括号
        text = text.strip()
        if not text.startswith('['):
            text = '[' + text
        if not text.endswith(']'):
            text = text + ']'
        
        return text
```

### Day 5: 多语言图像提示词模板

继续创建多语言图像提示词模板...

**`config/prompts/zh/image_prompts.txt`（基于Node_186126）**
```
# 角色
根据分镜字幕cap生成绘画提示词desc_prompt。

## 技能
### 技能 1:  生成绘画提示
1. 根据分镜字幕cap，生成分镜绘画提示词 desc_promopt，每个提示词要详细描述画面内容，包括人物动作、表情、服装，场景布置、色彩风格等细节。
  - 风格要求：古代惊悚插画风格，颜色很深，黑暗中，黄昏，氛围凝重，庄严肃穆，构建出紧张氛围，古代服饰，古装，线条粗狂 ，清晰、人物特写，粗狂手笔，高清，高对比度，色彩低饱和，浅景深
  - 第一个分镜画面中不要出现人物，只需要一个画面背景

===回复示例===
[
  {
    "cap": "字幕文案",
    "desc_promopt": "分镜图像提示词"
  }
]
===示例结束===

## 限制:
- 只对用户提供的json内容补充desc_prompt字段，不能更改原文
- 严格检查输出的 json 格式正确性并进行修正，特别注意 json 格式不要少括号，逗号等

现在请为以下分镜数据生成图像提示词：

{{scenes}}
```

这个实施计划展示了前5天的详细工作安排。我已经开始真实实现每个模块，严格按照原Coze工作流的参数和逻辑来设计。接下来我将继续实施后续阶段，包括媒体生成、视频合成等模块。

需要我继续实施接下来的阶段吗？