"""FEConfigPersister: Save multi-language docs and metadata"""

from pathlib import Path
from typing import List
from collections import defaultdict
from string import Template
from loguru import logger
import json

from docsagent.domains.models import ConfigItem, CATALOGS_LANGS
from docsagent import config


class FEConfigPersister:
    """Save configuration documentation to files (implements DocPersister protocol)"""
    
    def __init__(self):
        self.docs_module_dir = config.DOCS_MODULE_DIR
        self.meta_dir = Path(config.META_DIR)
        logger.debug(f"FEConfigPersister initialized: docs={self.docs_module_dir}, meta={self.meta_dir}")
    
    def save(self, items: List[ConfigItem], output_dir: str, target_langs: List[str]) -> None:
        """Save docs and metadata for multiple languages"""
        if not items:
            logger.warning("No items to save")
            return
        
        logger.info(f"Saving {len(items)} items → {output_dir} [{', '.join(target_langs)}]")
        
        self._save_meta(items)
        self._save_documents(items, output_dir, target_langs)
        
        logger.success(f"Saved {len(items)} config items")
    
    def _save_documents(self, configs: List[ConfigItem], output_dir: str, target_langs: List[str]) -> None:
        """Generate and save markdown docs for each language"""
        catalogs = self._organize_by_catalog(configs)
        
        for lang in target_langs:
            logger.debug(f"Generating {lang} docs...")
            
            target_docs = {lang: ""}
            
            for catalog in CATALOGS_LANGS:
                if catalog not in catalogs or not catalogs[catalog]:
                    continue
                
                target_docs[lang] += f"### {CATALOGS_LANGS[catalog][lang]}\n\n"
                
                for config in catalogs[catalog]:
                    if lang in config.documents:
                        target_docs[lang] += config.documents[lang] + "\n\n"
                    else:
                        logger.warning(f"Missing {lang} doc: {config.name}")
            
            self._apply_template_and_save(target_docs, lang, output_dir)
        
        logger.info(f"Saved docs for {len(target_langs)} languages")
    
    def _organize_by_catalog(self, configs: List[ConfigItem]) -> dict:
        """Group configs by catalog"""
        catalogs = defaultdict(list)
        for cc in configs:
            catalogs[cc.catalog].append(cc)
        
        logger.debug(f"Grouped into {len(catalogs)} catalogs")
        return catalogs
    
    def _apply_template_and_save(self, target_docs: dict, lang: str, output_dir: str) -> None:
        """Apply template ($content substitution) and save to file"""
        template_path = self.docs_module_dir / lang / "FE_configuration.md"
        
        if not template_path.exists():
            logger.warning(f"Template not found: {template_path}")
            final_content = target_docs[lang]
        else:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = Template(f.read())
            final_content = template.safe_substitute(outputs=target_docs[lang])
        
        output_path = Path(output_dir) / lang / "FE_configuration.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        logger.debug(f"Saved → {output_path}")
    
    def _save_meta(self, configs: List[ConfigItem]) -> None:
        """Save metadata in JSON format"""
        meta_path = self.meta_dir / "fe_config.meta"
        logger.info(f"Saving metadata → {meta_path}")
        
        try:
            data = [c.to_dict() for c in configs]
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(configs)} config items to {meta_path}")
        except Exception as e:
            logger.error(f"Failed to save configs to {meta_path}: {e}")
        
        logger.success(f"Metadata saved")