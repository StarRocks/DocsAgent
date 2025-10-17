"""
Test ConfigDocAgent
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docsagent.agents.config_doc_agent import ConfigDocAgent
from docsagent.models import ConfigItem


def test_config_doc_agent():
    """Test the config documentation agent"""
    
    # Sample config item
    config = ConfigItem(
        name="query_timeout",
        type="int",
        defaultValue="300",
        isMutable="true",
        comment="Query execution timeout in seconds. If a query runs longer than this value, it will be killed.",
        scope="FE",
        file_path="/test/Config.java",
        line_number=100,
        useLocations=[],
        documents=""
    )
    
    # Initialize agent
    agent = ConfigDocAgent()
    
    # Generate documentation
    print("=" * 60)
    print("Testing ConfigDocAgent")
    print("=" * 60)
    print(f"\nInput config: {config.name}")
    print("\nGenerating documentation...\n")
    
    doc = agent.generate(config)
    
    print("-" * 60)
    print("Generated Documentation:")
    print("-" * 60)
    print(doc)
    print("-" * 60)
    
    # Basic validation
    assert len(doc) > 50, "Documentation too short"
    assert config.name in doc, "Config name not in documentation"
    print("\n✅ Test passed!")


if __name__ == "__main__":
    test_config_doc_agent()
