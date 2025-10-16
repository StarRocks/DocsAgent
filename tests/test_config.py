"""测试配置文件读取功能"""
import os
import tempfile
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docsagent import config


def test_load_config_from_file():
    """测试从文件加载配置"""
    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
        f.write('# 测试配置\n')
        f.write('STARROCKS_HOME=/tmp/starrocks\n')
        f.write('LLM_MODEL=gpt-4\n')
        f.write('LLM_API_KEY=test-key-123\n')
        f.write('\n')
        f.write('# 注释行\n')
        temp_path = f.name
    
    try:
        # 加载配置
        cfg = config.load_config_from_file(temp_path)
        
        assert cfg['STARROCKS_HOME'] == '/tmp/starrocks'
        assert cfg['LLM_MODEL'] == 'gpt-4'
        assert cfg['LLM_API_KEY'] == 'test-key-123'
        
        print("✓ 配置文件读取测试通过")
    finally:
        # 清理临时文件
        os.unlink(temp_path)


def test_config_with_quotes():
    """测试带引号的配置值"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
        f.write('KEY1="value with spaces"\n')
        f.write("KEY2='single quotes'\n")
        f.write('KEY3=no quotes\n')
        temp_path = f.name
    
    try:
        cfg = config.load_config_from_file(temp_path)
        
        assert cfg['KEY1'] == 'value with spaces'
        assert cfg['KEY2'] == 'single quotes'
        assert cfg['KEY3'] == 'no quotes'
        
        print("✓ 引号处理测试通过")
    finally:
        os.unlink(temp_path)


def test_reload_config():
    """测试重新加载配置"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
        f.write('LLM_MODEL=gpt-4-turbo\n')
        temp_path = f.name
    
    try:
        # 重新加载配置
        config.reload_config(temp_path)
        
        # 验证配置已更新(如果没有环境变量覆盖)
        if 'LLM_MODEL' not in os.environ:
            assert config.LLM_MODEL == 'gpt-4-turbo'
        
        print("✓ 配置重新加载测试通过")
    finally:
        os.unlink(temp_path)


def test_current_config():
    """显示当前配置"""
    print("\n当前配置:")
    print(f"  STARROCKS_HOME: {config.STARROCKS_HOME}")
    print(f"  LLM_MODEL: {config.LLM_MODEL}")
    print(f"  LLM_API_KEY: {'***' if config.LLM_API_KEY else '(未设置)'}")


if __name__ == '__main__':
    print("开始测试配置功能...\n")
    
    test_load_config_from_file()
    test_config_with_quotes()
    test_reload_config()
    test_current_config()
    
    print("\n所有测试通过! ✓")
