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

"""TranslationAgent: Translate text to target languages"""

from typing import Literal
from loguru import logger

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from docsagent.agents.llm import get_default_chat_model


class TranslationAgent:
    """Pure translation agent - text only, no document structure handling"""
    
    # Field name translation mapping
    FIELD_MAP = {
        "Type": {"ja": "タイプ", "zh": "类型", "en": "Type"},
        "Default": {"ja": "デフォルト", "zh": "默认值", "en": "Default"},
        "Unit": {"ja": "単位", "zh": "単位", "en": "Unit"},
        "Is mutable": {"ja": "変更可能", "zh": "是否可变", "en": "Is mutable"},
        "Description": {"ja": "説明", "zh": "描述", "en": "Description"},
        "Introduced in": {"ja": "導入バージョン", "zh": "引入版本", "en": "Introduced in"},
    }
    
    def __init__(self, source_lang: str = 'en'):
        self.chat_model = get_default_chat_model()
        self.source_lang = source_lang
        logger.debug("TranslationAgent initialized")
    
    def translate(
        self, 
        text: str, 
        target_lang: Literal['zh', 'ja', 'en'],
        preserve_markers: bool = False
    ) -> str:
        """
        Translate text to target language
        
        Args:
            text: Source text to translate
            target_lang: Target language code ('zh', 'ja', or 'en')
            preserve_markers: If True, instruct LLM to preserve special markers like <!-- ... -->
        
        Returns:
            Translated text
            
        Example:
            >>> agent = TranslationAgent()
            >>> text = "## Configuration\\n\\nThis is a description."
            >>> zh_text = agent.translate(text, 'zh')
        """
        logger.debug(f"Translating text to {target_lang} ({len(text)} chars)")
        
        try:
            system_prompt = self._build_system_prompt(target_lang)
            user_prompt = self._build_user_prompt(text, target_lang, preserve_markers)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.chat_model.invoke(messages)
            translated = response.content.strip()
            
            # Post-process: ensure all field names are translated
            translated = self._post_process_field_names(translated, target_lang)
            
            logger.debug(f"Translation completed: {len(text)} → {len(translated)} chars")
            return translated
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            # Re-raise exception to prevent storing failed translation
            raise RuntimeError(f"Translation to {target_lang} failed: {str(e)}") from e
    
    def _post_process_field_names(self, text: str, target_lang: str) -> str:
        """Post-process to ensure all field names are translated"""
        result = text
        for field_en, mapping in self.FIELD_MAP.items():
            field_trans = mapping.get(target_lang, field_en)
            if field_en == field_trans:
                continue  # Skip if same language
            # Replace field names in common patterns (e.g. '- Type:')
            result = result.replace(f'- {field_en}:', f'- {field_trans}:')
            result = result.replace(f'- {field_en}：', f'- {field_trans}：')
        return result
    
    def _build_system_prompt(self, target_lang: str) -> str:
        """Build system prompt for translation"""
        lang_names = {
            'zh': 'Simplified Chinese (简体中文)',
            'ja': 'Japanese (日本語)',
            'en': 'English (English)'
        }
        
        lang_name = lang_names.get(target_lang, target_lang)
        src_name = lang_names.get(self.source_lang, self.source_lang)
        
        # Build field name translation examples
        field_examples = []
        for field_en, mapping in self.FIELD_MAP.items():
            field_trans = mapping.get(target_lang, field_en)
            if field_en != field_trans:
                field_examples.append(f"  - {field_en} → {field_trans}")
        
        field_instruction = ""
        if field_examples:
            field_instruction = f"""
        - Translate ALL field names to {lang_name}. Examples:
        {chr(10).join(field_examples)}
        """
        
        return f"""You are a professional technical translator specializing in database documentation.

        Your task is to translate StarRocks configuration documentation from {src_name} to {lang_name}.
        Requirements:
        - Maintain the exact Markdown formatting (headers, lists, code blocks, etc.)
        - Keep configuration names unchanged (e.g., query_timeout)
        - Keep technical terms in English when appropriate
        - Preserve code examples and SQL statements
        - Ensure natural and fluent translation
        - Keep numbers, units, and default values unchanged{field_instruction}

        Output only the translated content, no additional commentary."""
    
    def _build_user_prompt(
        self, 
        text: str, 
        target_lang: str,
        preserve_markers: bool
    ) -> str:
        """Build user prompt for translation"""
        prompt = f"Translate the following text to {target_lang}:\n\n"
        
        if preserve_markers:
            prompt += """
            IMPORTANT: Keep ALL special markers EXACTLY as they are. Do NOT translate or modify:
            - HTML comments like: <!-- ... -->
            - Markers like: ====...====
            - Any text inside {{ }} or similar brackets

            """
        
        prompt += f"{text}\n\n"
        prompt += "Remember to preserve Markdown formatting and keep technical terms accurate."
        
        return prompt
