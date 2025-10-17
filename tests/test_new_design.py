"""
Test new TranslationAgent (simplified) and Pipeline with separator method
"""
import sys
from pathlib import Path
from unittest.mock import Mock
import re

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docsagent.agents.translation_agent import TranslationAgent
from docsagent.agents.config_pipeline import ConfigGenerationPipeline


def test_translation_agent_simple():
    """Test simplified TranslationAgent - pure translation"""
    print("=" * 60)
    print("Test 1: Simplified TranslationAgent")
    print("=" * 60)
    
    # Mock LLM
    mock_model = Mock()
    mock_model.invoke.return_value = Mock(content="## 查询超时\n\n这是描述。")
    
    agent = TranslationAgent(chat_model=mock_model)
    
    # Test simple translation
    en_text = "## Query Timeout\n\nThis is a description."
    zh_text = agent.translate(en_text, 'zh')
    
    print(f"Input: {en_text}")
    print(f"Output: {zh_text}")
    
    assert "查询超时" in zh_text
    assert mock_model.invoke.called
    print("✅ Simple translation test passed\n")


def test_translation_with_markers():
    """Test translation with marker preservation"""
    print("=" * 60)
    print("Test 2: Translation with Marker Preservation")
    print("=" * 60)
    
    mock_model = Mock()
    mock_model.invoke.return_value = Mock(
        content="配置 1\n\n<!-- CONFIG_SEP_0 -->\n\n配置 2"
    )
    
    agent = TranslationAgent(chat_model=mock_model)
    
    text = "Config 1\n\n<!-- CONFIG_SEP_0 -->\n\nConfig 2"
    translated = agent.translate(text, 'zh', preserve_markers=True)
    
    print(f"Input: {text}")
    print(f"Output: {translated}")
    
    # Check marker preserved
    assert "<!-- CONFIG_SEP_0 -->" in translated
    print("✅ Marker preservation test passed\n")


def test_pipeline_separator_methods():
    """Test Pipeline's separator combine/split methods"""
    print("=" * 60)
    print("Test 3: Pipeline Separator Methods")
    print("=" * 60)
    
    pipeline = ConfigGenerationPipeline()
    
    # Test combine
    docs = [
        "## Config 1\n\nDescription 1",
        "## Config 2\n\nDescription 2",
        "## Config 3\n\nDescription 3"
    ]
    
    combined, pattern = pipeline._combine_docs_with_separators(docs)
    print(f"\nCombined text ({len(combined)} chars):")
    print(combined[:200] + "...")
    print(f"\nSeparator pattern: {pattern}")
    
    # Verify separators exist
    assert "<!-- CONFIG_SEP_0 -->" in combined
    assert "<!-- CONFIG_SEP_1 -->" in combined
    assert "<!-- CONFIG_SEP_2 -->" not in combined  # Should only have 0 and 1 (between 3 docs)
    print("✅ Combine test passed")
    
    # Test split
    split_docs = pipeline._split_by_separators(combined, pattern, len(docs))
    
    print(f"\nSplit result: {len(split_docs)} documents")
    for i, doc in enumerate(split_docs):
        print(f"  Doc {i}: {doc[:50]}...")
    
    assert len(split_docs) == len(docs), f"Expected {len(docs)}, got {len(split_docs)}"
    print("✅ Split test passed\n")


def test_pipeline_batch_translation():
    """Test Pipeline batch translation with separators"""
    print("=" * 60)
    print("Test 4: Pipeline Batch Translation")
    print("=" * 60)
    
    # Mock translation agent
    mock_translation_agent = Mock()
    
    def mock_translate(text, target_lang, preserve_markers=False):
        """Mock translation that preserves separators"""
        if preserve_markers and "<!-- CONFIG_SEP_" in text:
            # Simulate translation while preserving markers
            translated = text.replace("Config", "配置")
            translated = translated.replace("Description", "描述")
            return translated
        else:
            return text.replace("Config", "配置")
    
    mock_translation_agent.translate.side_effect = mock_translate
    
    # Create pipeline with mock
    pipeline = ConfigGenerationPipeline()
    pipeline.translation_agent = mock_translation_agent
    
    # Test batch translation
    en_docs = [
        "## Config 1\n\nDescription for config 1",
        "## Config 2\n\nDescription for config 2",
        "## Config 3\n\nDescription for config 3"
    ]
    
    zh_docs = pipeline.translate_docs_batch(en_docs, 'zh', use_separator=True)
    
    print(f"\nTranslated {len(zh_docs)} documents:")
    for i, doc in enumerate(zh_docs):
        print(f"\n  Doc {i}:")
        print(f"    {doc[:60]}...")
    
    # Verify
    assert len(zh_docs) == len(en_docs), f"Expected {len(en_docs)}, got {len(zh_docs)}"
    assert all("配置" in doc for doc in zh_docs), "All docs should be translated"
    assert all("描述" in doc for doc in zh_docs), "All docs should be translated"
    
    print("\n✅ Batch translation test passed\n")


def test_separator_pattern_matching():
    """Test separator regex pattern"""
    print("=" * 60)
    print("Test 5: Separator Pattern Matching")
    print("=" * 60)
    
    # Test pattern
    text = """Config 1

<!-- CONFIG_SEP_0 -->

Config 2

<!-- CONFIG_SEP_1 -->

Config 3"""
    
    pattern = r"<!-- CONFIG_SEP_\d+ -->"
    parts = re.split(r'\s*' + pattern + r'\s*', text)
    cleaned = [p.strip() for p in parts if p.strip()]
    
    print(f"\nOriginal text has {text.count('CONFIG_SEP')} separators")
    print(f"Split into {len(cleaned)} parts:")
    for i, part in enumerate(cleaned):
        print(f"  Part {i}: {part[:30]}...")
    
    assert len(cleaned) == 3, f"Expected 3 parts, got {len(cleaned)}"
    print("\n✅ Pattern matching test passed\n")


if __name__ == "__main__":
    test_translation_agent_simple()
    test_translation_with_markers()
    test_pipeline_separator_methods()
    test_pipeline_batch_translation()
    test_separator_pattern_matching()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
