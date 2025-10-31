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

"""VariablesPersister: Save multi-language docs and metadata"""

from pathlib import Path
from typing import List
from collections import defaultdict
from string import Template
from loguru import logger

from docsagent.core import DocPersister
from docsagent.domains.models import VariableItem
from docsagent import config


class VariablesPersister(DocPersister):
    """Save configuration documentation to files (implements DocPersister protocol)"""
    
    def __init__(self):
        self.docs_module_dir = config.DOCS_MODULE_DIR
        self.meta_path = Path(config.META_DIR) / "variables.meta"
        logger.debug(f"VariablesPersister initialized: docs={self.docs_module_dir}, meta={self.meta_path}")

    def _save_documents(self, variables: List[VariableItem], output_dir: str, target_langs: List[str]) -> None:
        """Generate and save markdown docs for each language"""
        variables = sorted(variables, key=lambda v: v.show)
        
        global_variables = [v for v in variables if v.scope.lower() == "global"]
        target_docs = {lang: "" for lang in target_langs}
        
        global_str = ""
        for g in global_variables:
            # if g.invisible:
            #     global_str += f"<!-- * {g.show} -->\n"
            #     logger.debug(f"Adding invisible global variable to list: {g.show}")
            # else:
            global_str += f"* {g.show}\n"                
            logger.debug(f"Adding global variable to list: {g.show}")
                
        target_docs["global"] = global_str

        for lang in target_langs:
            logger.debug(f"Generating {lang} docs...")
            for var in variables:
                if lang in var.documents:
                    # if var.invisible:
                    #     target_docs[lang] += f"<div style='display: none'>\n{var.documents[lang]}\n</div>\n\n"
                    #     logger.debug(f"Adding invisible variable to docs: {var.show}")
                    # else:
                    target_docs[lang] += var.documents[lang] + "\n\n"
                    logger.debug(f"Adding variable to docs: {var.show}")
                        
            self._apply_template_and_save(target_docs, lang, output_dir)
        
        logger.debug(f"Saved docs for {len(target_langs)} languages")
    
    def _apply_template_and_save(self, target_docs: dict, lang: str, output_dir: str) -> None:
        """Apply template ($content substitution) and save to file"""
        template_path = self.docs_module_dir / lang / "System_variable.md"
        
        if not template_path.exists():
            logger.warning(f"Template not found: {template_path}")
            final_content = target_docs[lang]
        else:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = Template(f.read())
            final_content = template.safe_substitute(global_variables_list=target_docs["global"], variables_lists=target_docs[lang])
        
        output_path = Path(output_dir) / lang / "System_variable.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        logger.debug(f"Saved → {output_path}")