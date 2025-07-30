import google.generativeai as genai
from typing import List, Dict, Optional
from dataclasses import dataclass
import json
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TopicModel:
    title: str
    page: int
    line: int
    context: str
    is_key_issue: bool = False
    confidence: float = 0.7
    related_topics: List[str] = None
    legal_significance: str = None

class GeminiProcessor:
    def __init__(self, api_key: Optional[str] = None):
        self.model = self._init_gemini(api_key) if api_key else None
        self.rate_limit_last_call = 0

    def _init_gemini(self, api_key: str) -> Optional[genai.GenerativeModel]:
        """Initialize Gemini with proper safety settings"""
        try:
            genai.configure(api_key=api_key)
            
            safety_settings = {
                'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
                'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE'
            }
            
            return genai.GenerativeModel(
                'gemini-1.5-flash',
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.95,
                    "response_mime_type": "application/json"
                },
                safety_settings=safety_settings
            )
        except Exception as e:
            logger.error(f"Gemini initialization failed: {str(e)}")
            return None

    def analyze_transcript(self, text: str, num_topics: int = 5) -> List[TopicModel]:
        """Public method to analyze transcript and generate topics"""
        return self.generate_topics(text, num_topics)

    def generate_topics(self, text: str, num_topics: int = 5) -> List[TopicModel]:
        """Generate topics from transcript text"""
        if not self.model:
            return []
            
        prompt = f"""
        Analyze this legal deposition transcript and identify {num_topics} key topics.
        For each topic provide:
        - A concise 3-5 word title
        - Page and line references
        - Whether it contains key legal issues
        - Confidence score (0-1)
        - Related legal concepts
        
        Return in this JSON format:
        {{
            "topics": [
                {{
                    "title": "string",
                    "page": int,
                    "line": int,
                    "context": "string",
                    "is_key_issue": bool,
                    "confidence": float,
                    "related_topics": ["string"]
                }}
            ]
        }}
        
        Transcript:
        {text[:10000]}  # First 10k chars for demo
        """
        
        try:
            self._enforce_rate_limit()
            response = self.model.generate_content(prompt)
            
            if response.candidates and response.candidates[0].content.parts:
                result = json.loads(response.text)
                return [
                    TopicModel(
                        title=topic.get("title", "Unspecified Topic"),
                        page=topic.get("page", 1),
                        line=topic.get("line", 1),
                        context=topic.get("context", ""),
                        is_key_issue=topic.get("is_key_issue", False),
                        confidence=topic.get("confidence", 0.7),
                        related_topics=topic.get("related_topics", [])
                    )
                    for topic in result.get("topics", [])
                ]
        except Exception as e:
            logger.error(f"Topic generation failed: {e}")
        
        return []

    def generate_enhanced_toc(self, topics: List[Dict]) -> str:
        """Generate a table of contents from topics"""
        if not self.model or not topics:
            return ""
            
        prompt = f"""
        Create a professional table of contents for a legal deposition using these topics:
        {json.dumps(topics, indent=2)}
        
        Include:
        - Logical section grouping
        - Page/line references
        - Key issue markers
        - Hierarchical structure
        
        Return in Markdown format with headings.
        """
        
        try:
            self._enforce_rate_limit()
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"TOC generation failed: {e}")
            return ""

    def _enforce_rate_limit(self):
        """Ensure we don't exceed API rate limits"""
        elapsed = time.time() - self.rate_limit_last_call
        if elapsed < 1.5:  # 1.5 seconds between calls
            time.sleep(1.5 - elapsed)
        self.rate_limit_last_call = time.time()