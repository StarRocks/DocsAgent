# Copyright 2021-present StarRocks, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""BEConfigPersister: Save multi-language docs and metadata"""

from pathlib import Path
from typing import List
from collections import defaultdict
from string import Template
from loguru import logger

from docsagent.core import DocPersister
from docsagent.domains.models import ConfigItem, CATALOGS_LANGS
from docsagent import config


class BEConfigPersister(DocPersister):
    """Save configuration documentation to files (implements DocPersister protocol)"""
    
    def __init__(self):
        self.docs_module_dir = config.DOCS_MODULE_DIR
        self.meta_path = Path(config.META_DIR) / "be_config.meta"
        logger.debug(f"BEConfigPersister initialized: docs={self.docs_module_dir}, meta={self.meta_path}")
    
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
                sorted_configs = sorted(catalogs[catalog], key=lambda c: c.name)
                for config in sorted_configs:
                    if lang in config.documents and config.documents[lang].strip():
                        target_docs[lang] += config.documents[lang].strip() + "\n\n"
                    else:
                        logger.warning(f"Missing {lang} doc: {config.name}")
            
            self._apply_template_and_save(target_docs, lang, output_dir)
        
        logger.debug(f"Saved docs for {len(target_langs)} languages")
    
    def _organize_by_catalog(self, configs: List[ConfigItem]) -> dict:
        """Group configs by catalog"""
        catalogs = defaultdict(list)
        for cc in configs:
            catalogs[cc.catalog].append(cc)
        
        logger.debug(f"Grouped into {len(catalogs)} catalogs")
        return catalogs
    
    def _apply_template_and_save(self, target_docs: dict, lang: str, output_dir: str) -> None:
        """Apply template ($content substitution) and save to file"""
        template_path = self.docs_module_dir / lang / "BE_configuration.md"
        
        if not template_path.exists():
            logger.warning(f"Template not found: {template_path}")
            final_content = target_docs[lang]
        else:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = Template(f.read())
            final_content = template.safe_substitute(outputs=target_docs[lang])
        
        output_path = Path(output_dir) / lang / "BE_configuration.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        logger.debug(f"Saved → {output_path}")