"""
ConfigManager单元测试
测试配置管理的核心功能
"""
import pytest
import json
from unittest.mock import patch, mock_open
from pathlib import Path

from core.config_manager import ConfigManager


class TestConfigManager:
    """ConfigManager测试类"""
    
    @pytest.fixture
    def sample_config(self):
        """示例配置数据"""
        return {
            "general": {
                "output_dir": "output",
                "log_level": "INFO",
                "max_concurrent_tasks": 3
            },
            "llm": {
                "default": {
                    "model": "openai/gpt-4",
                    "api_key": "${OPENROUTER_API_KEY}"
                }
            }
        }
    
    @pytest.mark.unit
    def test_config_loading(self, sample_config):
        """测试配置加载"""
        config_json = json.dumps(sample_config)
        
        with patch('builtins.open', mock_open(read_data=config_json)), \
             patch.object(Path, 'exists', return_value=True):
            
            config_manager = ConfigManager()
            
            assert config_manager.get('general.output_dir') == "output"
            assert config_manager.get('general.log_level') == "INFO" 
            assert config_manager.get('general.max_concurrent_tasks') == 3
    
    @pytest.mark.unit
    def test_nested_config_access(self, sample_config):
        """测试嵌套配置访问"""
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = sample_config
            
            config_manager = ConfigManager()
            
            # 测试嵌套访问
            assert config_manager.get('llm.default.model') == "openai/gpt-4"
            assert config_manager.get('llm.default.api_key') == "${OPENROUTER_API_KEY}"
    
    @pytest.mark.unit
    def test_default_values(self):
        """测试默认值功能"""
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = {"general": {"output_dir": "output"}}
            
            config_manager = ConfigManager()
            
            # 测试存在的配置
            assert config_manager.get('general.output_dir') == "output"
            
            # 测试不存在的配置，使用默认值
            assert config_manager.get('nonexistent.key', 'default') == 'default'
            assert config_manager.get('general.nonexistent', 100) == 100
    
    @pytest.mark.unit
    def test_environment_variable_expansion(self, sample_config):
        """测试环境变量展开"""
        with patch.object(ConfigManager, '_load_main_config') as mock_load, \
             patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-api-key'}):
            
            mock_load.return_value = sample_config
            config_manager = ConfigManager()
            
            # 测试环境变量展开
            expanded_key = config_manager._expand_env_vars("${OPENROUTER_API_KEY}")
            assert expanded_key == "test-api-key"
            
            # 测试获取展开后的值
            llm_config = config_manager.get_llm_config('default')
            assert llm_config['api_key'] == "test-api-key"
    
    @pytest.mark.unit
    def test_llm_config_retrieval(self, sample_config):
        """测试LLM配置获取"""
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = sample_config
            config_manager = ConfigManager()
            
            llm_config = config_manager.get_llm_config('default')
            
            assert llm_config is not None
            assert llm_config['model'] == "openai/gpt-4"
            assert '${' not in llm_config['api_key']  # 应该被展开
    
    @pytest.mark.unit  
    def test_supported_languages(self, sample_config):
        """测试支持的语言"""
        sample_config['general']['supported_languages'] = ['zh', 'en', 'es']
        
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = sample_config
            config_manager = ConfigManager()
            
            languages = config_manager.get_supported_languages()
            
            assert isinstance(languages, list)
            assert 'zh' in languages
            assert 'en' in languages
            assert 'es' in languages
    
    @pytest.mark.unit
    def test_config_validation(self, sample_config):
        """测试配置验证"""
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = sample_config
            config_manager = ConfigManager()
            
            # 测试配置验证
            errors = config_manager.validate_config()
            
            # 应该有错误，因为API密钥是环境变量
            assert isinstance(errors, list)
            # 在测试环境中可能有缺失的API密钥错误
    
    @pytest.mark.unit
    def test_invalid_json_handling(self):
        """测试无效JSON处理"""
        invalid_json = "{ invalid json }"
        
        with patch('builtins.open', mock_open(read_data=invalid_json)), \
             patch.object(Path, 'exists', return_value=True):
            
            with pytest.raises(Exception):  # 应该抛出异常
                ConfigManager()
    
    @pytest.mark.unit
    def test_missing_config_file(self):
        """测试配置文件不存在的情况"""
        with patch.object(Path, 'exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                ConfigManager()
    
    @pytest.mark.unit
    def test_config_inheritance(self, sample_config):
        """测试配置继承"""
        # 添加特定任务的配置
        sample_config['llm']['script_generation'] = {
            "temperature": 0.8,
            "max_tokens": 1000
        }
        
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = sample_config
            config_manager = ConfigManager()
            
            # 获取特定任务配置应该继承默认配置
            script_config = config_manager.get_llm_config('script_generation')
            
            assert script_config is not None
            assert script_config.get('temperature') == 0.8
            assert script_config.get('max_tokens') == 1000
            # 应该继承默认配置
            assert 'model' in script_config or 'api_key' in script_config
    
    @pytest.mark.unit
    def test_cache_behavior(self, sample_config):
        """测试配置缓存行为"""
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = sample_config
            
            config_manager = ConfigManager()
            
            # 多次访问同一配置
            config1 = config_manager.get('general.output_dir')
            config2 = config_manager.get('general.output_dir')
            
            assert config1 == config2
            
            # 验证_load_main_config只被调用一次（缓存生效）
            assert mock_load.call_count == 1


class TestConfigManagerEdgeCases:
    """ConfigManager边缘情况测试"""
    
    @pytest.mark.unit
    def test_empty_config_key(self):
        """测试空配置键"""
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = {"general": {"output_dir": "output"}}
            config_manager = ConfigManager()
            
            # 空键应该返回整个配置
            full_config = config_manager.get('')
            assert 'general' in full_config
    
    @pytest.mark.unit
    def test_none_default_value(self):
        """测试None作为默认值"""
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = {"general": {"output_dir": "output"}}
            config_manager = ConfigManager()
            
            result = config_manager.get('nonexistent.key', None)
            assert result is None
    
    @pytest.mark.unit
    def test_complex_nested_access(self):
        """测试复杂嵌套访问"""
        complex_config = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep_value"
                    }
                }
            }
        }
        
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = complex_config
            config_manager = ConfigManager()
            
            assert config_manager.get('level1.level2.level3.value') == "deep_value"
            assert config_manager.get('level1.level2.level3') == {"value": "deep_value"}


# 性能测试
class TestConfigManagerPerformance:
    """ConfigManager性能测试"""
    
    @pytest.mark.unit
    @pytest.mark.performance
    def test_config_access_performance(self, performance_tracker):
        """测试配置访问性能"""
        large_config = {"general": {f"key_{i}": f"value_{i}" for i in range(1000)}}
        
        with patch.object(ConfigManager, '_load_main_config') as mock_load:
            mock_load.return_value = large_config
            config_manager = ConfigManager()
            
            performance_tracker.start('config_access')
            
            # 访问多个配置
            for i in range(100):
                config_manager.get(f'general.key_{i % 100}')
            
            duration = performance_tracker.end('config_access')
            
            # 配置访问应该很快
            assert duration < 0.1, f"Config access too slow: {duration:.3f}s"