"""
TranslationAgent: Pure translation functionality without document structure handling
"""
from typing import Literal
from loguru import logger

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from docsagent.agents.llm import get_default_chat_model


class TranslationAgent:
    """
    Pure translation agent - only handles text translation
    
    Responsibilities:
    - Translate text from English to target language
    - Handle terminology consistency
    - Provide fallback on errors
    
    NOT responsible for:
    - Document structure (splitting/merging)
    - Batch processing logic
    - File I/O
    """
    
    def __init__(self, chat_model: BaseChatModel = None, source_lang: str = 'en'):
        """
        Initialize the translation agent
        
        Args:
            chat_model: LangChain chat model (default: from config)
        """
        self.chat_model = chat_model or get_default_chat_model()
        self.source_lang = source_lang
        logger.info("TranslationAgent initialized")
    
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
        logger.info(f"Translating text to {target_lang} ({len(text)} chars)")
        
        try:
            system_prompt = self._build_system_prompt(target_lang)
            user_prompt = self._build_user_prompt(text, target_lang, preserve_markers)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.chat_model.invoke(messages)
            translated = response.content.strip()
            
            logger.debug(f"Translation completed: {len(text)} → {len(translated)} chars")
            return translated
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            # Return original text with error note
            return f"{text}\n\n*[Translation failed: {str(e)}]*"
    
    def _build_system_prompt(self, target_lang: str) -> str:
        """Build system prompt for translation"""
        lang_names = {
            'zh': 'Simplified Chinese (简体中文)',
            'ja': 'Japanese (日本語)',
            'en': 'English (English)'
        }
        
        lang_name = lang_names.get(target_lang, target_lang)
        src_name = lang_names.get(self.source_lang, self.source_lang)
        
        return f"""You are a professional technical translator specializing in database documentation.

        Your task is to translate StarRocks configuration documentation from {src_name} to {lang_name}.
        Requirements:
        - Maintain the exact Markdown formatting (headers, lists, code blocks, etc.)
        - Keep configuration names unchanged (e.g., query_timeout)
        - Keep technical terms in English when appropriate
        - Preserve code examples and SQL statements
        - Ensure natural and fluent translation
        - Keep numbers, units, and default values unchanged

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
