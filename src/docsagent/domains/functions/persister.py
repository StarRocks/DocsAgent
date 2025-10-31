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

"""FEConfigPersister: Save multi-language docs and metadata"""

import json
from pathlib import Path
from typing import List
from collections import defaultdict
from string import Template
from loguru import logger

from docsagent.core import DocPersister
from docsagent.domains.models import FunctionItem
from docsagent import config


class FunctionsPersister(DocPersister):
    """Save configuration documentation to files (implements DocPersister protocol)"""
    
    def __init__(self):
        self.meta_path = Path(config.META_DIR) / "functions"
        logger.debug(f"FunctionsPersister initialized: meta={self.meta_path}")

    def _save_documents(self, funcs: List[FunctionItem], output_dir: str, target_langs: List[str]) -> None:
        """Generate and save markdown docs for each language"""
        for item in funcs:
            if item.catalog is None:
                logger.info(f"Skipping function {item.name} due to missing catalog")
                continue
            
            lost_lang = []
            for lang in target_langs:
                logger.debug(f"Generating {lang} docs...")
                
                if item.documents.get(lang, "").strip() == "":
                    lost_lang.append(lang)
                    continue

                output_path = Path(output_dir) / lang / "functions" / item.catalog / f"{item.name}.md"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(item.documents.get(lang, ""))
            logger.info(f"Skipping function {item.name} for lost languages: {lost_lang}")
        
        logger.debug(f"Saved docs for {len(target_langs)} languages")

    def _save_meta(self, items: List[FunctionItem]) -> None:
        """Save metadata as JSON file"""
        if not self.meta_path.exists():
            self.meta_path.mkdir(parents=True, exist_ok=True)

        for item in items:
            meta_file = self.meta_path / f"{item.name}.meta"

            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(item.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved metadata → {meta_file}")