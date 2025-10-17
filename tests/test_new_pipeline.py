"""
Test new pipeline with document status grouping and smart translation
"""
import sys
from pathlib import Path
from unittest.mock import Mock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docsagent.agents.config_pipeline import ConfigGenerationPipeline
from docsagent.models import ConfigItem


def test_analyze_and_group_configs():
    """Test config grouping by document status"""
    print("=" * 60)
    print("Test: Analyze and Group Configs")
    print("=" * 60)
    
    # Create test configs with different document states
    configs = [
        # Has Chinese
        ConfigItem(
            name="config_with_zh",
            type="int",
            defaultValue="100",
            isMutable="true",
            comment="Test",
            scope="FE",
            define="/test/Config.java",
            documents={'zh': '## 配置1\n\n中文文档'}
        ),
        # Has English only
        ConfigItem(
            name="config_with_en",
            type="int",
            defaultValue="200",
            isMutable="true",
            comment="Test",
            scope="FE",
            define="/test/Config.java",
            documents={'en': '## Config2\n\nEnglish doc'}
        ),
        # Has both Chinese and English
        ConfigItem(
            name="config_with_both",
            type="int",
            defaultValue="300",
            isMutable="true",
            comment="Test",
            scope="FE",
            define="/test/Config.java",
            documents={
                'zh': '## 配置3\n\n中文文档',
                'en': '## Config3\n\nEnglish doc'
            }
        ),
        # Has neither
        ConfigItem(
            name="config_empty",
            type="int",
            defaultValue="400",
            isMutable="true",
            comment="Test",
            scope="FE",
            define="/test/Config.java",
            documents={}
        ),
    ]
    
    pipeline = ConfigGenerationPipeline()
    groups = pipeline.analyze_and_group_configs(configs)
    
    print(f"\nGrouping results:")
    print(f"  Has ZH: {len(groups['has_zh'])} configs")
    print(f"    - {[c.name for c in groups['has_zh']]}")
    print(f"  Has EN only: {len(groups['has_en_only'])} configs")
    print(f"    - {[c.name for c in groups['has_en_only']]}")
    print(f"  Has neither: {len(groups['has_neither'])} configs")
    print(f"    - {[c.name for c in groups['has_neither']]}")
    
    # Verify
    assert len(groups['has_zh']) == 2  # config_with_zh and config_with_both
    assert len(groups['has_en_only']) == 1  # config_with_en
    assert len(groups['has_neither']) == 1  # config_empty
    
    print("\n✅ Grouping test passed!")


def test_generate_docs_batch_with_skip():
    """Test that generate_docs_batch skips existing docs"""
    print("\n" + "=" * 60)
    print("Test: Generate Docs Batch (Skip Existing)")
    print("=" * 60)
    
    configs = [
        # Already has English
        ConfigItem(
            name="has_en",
            type="int",
            defaultValue="100",
            isMutable="true",
            comment="Test",
            scope="FE",
            define="/test/Config.java",
            documents={'en': 'Existing English doc'}
        ),
        # Needs English
        ConfigItem(
            name="needs_en",
            type="int",
            defaultValue="200",
            isMutable="true",
            comment="Test",
            scope="FE",
            define="/test/Config.java",
            documents={}
        ),
    ]
    
    pipeline = ConfigGenerationPipeline()
    
    # Mock doc_agent
    mock_doc = Mock()
    mock_doc.generate = Mock(return_value="## Generated\n\nGenerated doc")
    pipeline.doc_agent = mock_doc
    
    print("\nGenerating English docs...")
    pipeline.generate_docs_batch(configs, target_lang='en')
    
    print(f"\nResults:")
    print(f"  has_en document: {configs[0].documents.get('en', 'MISSING')[:30]}...")
    print(f"  needs_en document: {configs[1].documents.get('en', 'MISSING')[:30]}...")
    print(f"  LLM called: {mock_doc.generate.call_count} times")
    
    # Verify
    assert configs[0].documents['en'] == 'Existing English doc'  # Not changed
    assert '## Generated' in configs[1].documents['en']  # Generated
    assert mock_doc.generate.call_count == 1  # Only called once
    
    print("\n✅ Generate with skip test passed!")


def test_translate_and_update_docs():
    """Test translate_and_update_docs method"""
    print("\n" + "=" * 60)
    print("Test: Translate and Update Docs")
    print("=" * 60)
    
    configs = [
        ConfigItem(
            name="config1",
            type="int",
            defaultValue="100",
            isMutable="true",
            comment="Test",
            scope="FE",
            define="/test/Config.java",
            documents={'en': '## Config1\n\nEnglish doc 1'}
        ),
        ConfigItem(
            name="config2",
            type="int",
            defaultValue="200",
            isMutable="true",
            comment="Test",
            scope="FE",
            define="/test/Config.java",
            documents={'en': '## Config2\n\nEnglish doc 2'}
        ),
    ]
    
    pipeline = ConfigGenerationPipeline()
    
    # Mock translation_agent
    def mock_translate(docs, target_lang, use_separator=False):
        # Simple mock: replace "English" with target language
        return [doc.replace('English', target_lang.upper()) for doc in docs]
    
    pipeline.translate_docs_batch = Mock(side_effect=mock_translate)
    
    print("\nTranslating EN → ZH...")
    pipeline.translate_and_update_docs(configs, 'en', 'zh')
    
    print(f"\nResults:")
    print(f"  config1 ZH: {configs[0].documents.get('zh', 'MISSING')[:40]}...")
    print(f"  config2 ZH: {configs[1].documents.get('zh', 'MISSING')[:40]}...")
    
    # Verify
    assert 'ZH' in configs[0].documents['zh']
    assert 'ZH' in configs[1].documents['zh']
    assert 'en' in configs[0].documents  # English still there
    
    print("\n✅ Translate and update test passed!")


def test_document_association():
    """Test that documents stay associated with configs"""
    print("\n" + "=" * 60)
    print("Test: Document-Config Association")
    print("=" * 60)
    
    config = ConfigItem(
        name="test_config",
        type="int",
        defaultValue="100",
        isMutable="true",
        comment="Test config",
        scope="FE",
        define="/test/Config.java",
        documents={}
    )
    
    print(f"\nInitial state: {config.documents}")
    
    # Add English
    config.documents['en'] = "## Test\n\nEnglish"
    print(f"After adding EN: {list(config.documents.keys())}")
    
    # Add Chinese
    config.documents['zh'] = "## 测试\n\n中文"
    print(f"After adding ZH: {list(config.documents.keys())}")
    
    # Verify association
    assert config.documents['en'] == "## Test\n\nEnglish"
    assert config.documents['zh'] == "## 测试\n\n中文"
    assert len(config.documents) == 2
    
    # Test serialization
    config_dict = config.to_dict()
    print(f"\nSerialized keys: {list(config_dict['documents'].keys())}")
    
    # Test deserialization
    restored_config = ConfigItem.from_dict(config_dict)
    print(f"Restored keys: {list(restored_config.documents.keys())}")
    
    assert restored_config.documents['en'] == config.documents['en']
    assert restored_config.documents['zh'] == config.documents['zh']
    
    print("\n✅ Document association test passed!")


if __name__ == "__main__":
    test_analyze_and_group_configs()
    test_generate_docs_batch_with_skip()
    test_translate_and_update_docs()
    test_document_association()
    
    print("\n" + "=" * 60)
    print("✅ ALL NEW PIPELINE TESTS PASSED!")
    print("=" * 60)
