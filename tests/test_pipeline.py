"""
Test DocGenerationPipeline with mock agents
"""
import sys
from pathlib import Path
from unittest.mock import Mock
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docsagent.agents.config_pipeline import ConfigGenerationPipeline


def test_pipeline_with_mocks():
    """Test the complete pipeline with mocked agents"""
    
    print("=" * 60)
    print("Testing DocGenerationPipeline")
    print("=" * 60)
    
    # Mock ConfigDocAgent
    mock_doc_agent = Mock()
    mock_doc_agent.generate.side_effect = [
        """## query_timeout

### Description
Query timeout configuration controls maximum query execution time.

### Default Value
`300` seconds
""",
        """## max_connections

### Description
Maximum number of concurrent connections allowed.

### Default Value
`1024`
"""
    ]
    
    # Mock TranslationAgent
    mock_translation_agent = Mock()
    
    def mock_translate(text, target_lang):
        if target_lang == 'zh':
            return text.replace("Query timeout", "查询超时").replace("Description", "描述")
        elif target_lang == 'ja':
            return text.replace("Query timeout", "クエリタイムアウト").replace("Description", "説明")
        return text
    
    mock_translation_agent.translate.side_effect = mock_translate
    
    # Create pipeline with mocked agents
    pipeline = ConfigGenerationPipeline(
        doc_agent=mock_doc_agent,
        translation_agent=mock_translation_agent
    )
    
    # Test individual methods
    print("\n[Test 1] Testing organize_markdown...")
    
    docs = [
        "## config1\n\nContent 1",
        "## config2\n\nContent 2"
    ]
    
    configs = [
        {"name": "config1", "type": "int"},
        {"name": "config2", "type": "string"}
    ]
    
    organized = pipeline.organize_markdown(docs, configs)
    
    print(f"  Generated {len(organized)} characters")
    assert "# StarRocks Configuration Reference" in organized
    assert "## Table of Contents" in organized
    assert "config1" in organized
    assert "config2" in organized
    print("  ✓ organize_markdown test passed")
    
    # Test TOC generation
    print("\n[Test 2] Testing TOC generation...")
    toc = pipeline._generate_toc(configs)
    print(f"  TOC:\n{toc}")
    assert "config1" in toc
    assert "config2" in toc
    assert "[config1]" in toc
    print("  ✓ TOC generation test passed")
    
    # Test save_outputs
    print("\n[Test 3] Testing save_outputs...")
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline.save_outputs(
            tmpdir,
            "English content",
            "中文内容",
            "日本語コンテンツ"
        )
        
        # Check files exist
        output_path = Path(tmpdir)
        en_file = output_path / "config_reference_en.md"
        zh_file = output_path / "config_reference_zh.md"
        ja_file = output_path / "config_reference_ja.md"
        
        assert en_file.exists(), "English file not created"
        assert zh_file.exists(), "Chinese file not created"
        assert ja_file.exists(), "Japanese file not created"
        
        # Check content
        assert en_file.read_text(encoding='utf-8') == "English content"
        assert zh_file.read_text(encoding='utf-8') == "中文内容"
        assert ja_file.read_text(encoding='utf-8') == "日本語コンテンツ"
        
        print(f"  ✓ Files saved to {tmpdir}")
        print("  ✓ save_outputs test passed")
    
    # Test generate_docs_batch
    print("\n[Test 4] Testing generate_docs_batch...")
    test_configs = [
        {"name": "test_config_1", "type": "int"},
        {"name": "test_config_2", "type": "string"}
    ]
    
    docs = pipeline.generate_docs_batch(test_configs)
    
    assert len(docs) == 2, "Should generate 2 docs"
    assert mock_doc_agent.generate.call_count == 2, "Should call agent twice"
    print(f"  ✓ Generated {len(docs)} documents")
    print("  ✓ generate_docs_batch test passed")
    
    # Test translate_docs
    print("\n[Test 5] Testing translate_docs...")
    en_text = "Query timeout Description"
    
    zh_text = pipeline.translate_docs(en_text, 'zh')
    assert "查询超时" in zh_text
    print(f"  ✓ Chinese translation: {zh_text}")
    
    ja_text = pipeline.translate_docs(en_text, 'ja')
    assert "クエリタイムアウト" in ja_text
    print(f"  ✓ Japanese translation: {ja_text}")
    
    print("  ✓ translate_docs test passed")
    
    print("\n" + "=" * 60)
    print("✅ All pipeline tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_pipeline_with_mocks()
