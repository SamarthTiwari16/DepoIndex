import re
import argparse
import json
import os
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import google.generativeai as genai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('topic_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Topic:
    title: str
    page: int
    line: int
    context: str
    is_key_issue: bool = False
    confidence: float = 0.0
    related_topics: List[str] = None
    legal_significance: str = None

class TopicGenerator:
    SPEAKER_PREFIXES = r"^(MR|MS|MRS|THE WITNESS|THE COURT|BY MR|BY MS|Q|A|ATTORNEY|COUNSEL)[\.:]?\s"
    MIN_CONTENT_LENGTH = 5
    MAX_RETRIES = 3
    RATE_LIMIT_DELAY = 1.5  # seconds

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_model = self._init_gemini(gemini_api_key) if gemini_api_key else None
        self.rate_limit_last_call = 0

    def _init_gemini(self, api_key: str) -> Optional[genai.GenerativeModel]:
        """Initialize Gemini with enhanced configuration"""
        try:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel(
                'gemini-1.5-flash',
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.95,
                    "response_mime_type": "application/json"
                },
                safety_settings={
                    'HARASSMENT': 'block_none',
                    'HATE_SPEECH': 'block_none',
                    'SEXUALLY_EXPLICIT': 'block_none',
                    'DANGEROUS_CONTENT': 'block_none'
                }
            )
        except Exception as e:
            logger.error(f"Gemini initialization failed: {e}")
            return None

    def _enforce_rate_limit(self):
        """Ensure we don't exceed API rate limits"""
        elapsed = time.time() - self.rate_limit_last_call
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.rate_limit_last_call = time.time()

    def clean_text(self, text: str) -> str:
        """Enhanced text cleaning with legal-specific patterns"""
        text = re.sub(self.SPEAKER_PREFIXES, "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[.*?\]", "", text)  # Remove annotations
        return text.strip()

    def is_content_line(self, line: str) -> bool:
        """More sophisticated content detection"""
        return (
            len(line) >= self.MIN_CONTENT_LENGTH and
            not line.startswith(('Page', 'Exhibit')) and
            not re.fullmatch(r"[0-9 ·\-—]+", line) and
            sum(c.isalpha() for c in line) > 3
        )

    def generate_gemini_topic(self, lines: List[str], page: int) -> Optional[Topic]:
        """Generate topic with retry logic and better prompt engineering"""
        if not self.gemini_model or len(lines) < 2:
            return None

        prompt = f"""
        As a legal AI assistant, analyze this deposition segment (Page {page}):

        {chr(10).join(f"- {self.clean_text(line)}" for line in lines[:5])}

        Provide analysis in this exact JSON format:
        {{
            "title": "3-7 word professional title",
            "is_key_issue": boolean,
            "confidence": 0.0-1.0,
            "legal_significance": "brief analysis",
            "related_topics": ["list", "of", "related", "concepts"]
        }}

        Focus on:
        - Substantive legal issues
        - Key testimony
        - Critical admissions
        - Relevant objections
        """
        
        for attempt in range(self.MAX_RETRIES):
            try:
                self._enforce_rate_limit()
                response = self.gemini_model.generate_content(prompt)
                
                # Handle different response formats
                raw = response.text.strip()
                if raw.startswith('```json'):
                    raw = raw[7:-3].strip()  # Remove markdown code fences
                
                data = json.loads(raw)
                return Topic(
                    title=data.get("title", "Unspecified Topic"),
                    page=page,
                    line=0,
                    context="\n".join(lines[:3]),
                    is_key_issue=data.get("is_key_issue", False),
                    confidence=data.get("confidence", 0.5),
                    legal_significance=data.get("legal_significance"),
                    related_topics=data.get("related_topics", [])
                )
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    logger.error("Max retries exceeded for segment")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff

    def process_segment(self, lines: List[str], start_idx: int, lines_per_page: int) -> Tuple[List[Topic], int]:
        """Process text segment with parallel topic generation"""
        page = (start_idx // lines_per_page) + 1
        topics = []

        # Try Gemini first if available
        topic = self.generate_gemini_topic(lines, page)
        if topic:
            topic.line = start_idx + 1
            topics.append(topic)
            return topics, len(lines)

        # Fallback to basic processing
        if lines:
            title = self.clean_text(lines[0])[:50] or "Unspecified Topic"
            topics.append(Topic(
                title=title,
                page=page,
                line=start_idx + 1,
                context=lines[0]
            ))

        return topics, len(lines)

    def detect_topics(self, transcript_text: str, lines_per_page: int = 30) -> List[Dict]:
        """Main topic detection pipeline with parallel processing"""
        lines = [line.strip() for line in transcript_text.splitlines() if line.strip()]
        topics = []
        segments = []
        current_segment = []

        # First identify all content segments
        for i, line in enumerate(lines):
            if self.is_content_line(line):
                current_segment.append(line)
            elif current_segment:
                segments.append((current_segment, i - len(current_segment)))
                current_segment = []

        if current_segment:
            segments.append((current_segment, len(lines) - len(current_segment)))

        # Process segments in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(
                    self.process_segment, 
                    seg, 
                    idx, 
                    lines_per_page
                ) 
                for seg, idx in segments
            ]
            
            for future in as_completed(futures):
                try:
                    new_topics, _ = future.result()
                    topics.extend(new_topics)
                except Exception as e:
                    logger.error(f"Segment processing failed: {e}")

        logger.info(f"Extracted {len(topics)} topics ({'with Gemini' if self.gemini_model else 'basic mode'})")
        return [asdict(t) for t in topics]

def validate_args(args: argparse.Namespace) -> None:
    """Validate input arguments"""
    if not Path(args.input_path).exists():
        raise FileNotFoundError(f"Transcript not found: {args.input_path}")
    if args.lines_per_page < 10:
        raise ValueError("Lines per page must be at least 10")

def main():
    parser = argparse.ArgumentParser(
        description="AI-powered deposition topic extraction",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--in', 
        dest='input_path', 
        required=True,
        help="Transcript file path"
    )
    parser.add_argument(
        '--out', 
        dest='output_path', 
        default="output/topics.json",
        help="Output JSON path"
    )
    parser.add_argument(
        '--lines_per_page', 
        type=int, 
        default=30,
        help="Lines per page estimate"
    )
    parser.add_argument(
        '--gemini_key', 
        help="Gemini API key for enhanced analysis"
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help="Number of parallel workers"
    )

    args = parser.parse_args()
    
    try:
        validate_args(args)
        start_time = time.time()
        
        with open(args.input_path, 'r', encoding='utf-8') as f:
            transcript = f.read().strip()

        if not transcript:
            raise ValueError("Empty transcript file")

        generator = TopicGenerator(args.gemini_key)
        topics = generator.detect_topics(transcript, args.lines_per_page)

        output_path = Path(args.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": {
                    "source": args.input_path,
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "processing_time_sec": round(time.time() - start_time, 2),
                    "gemini_enabled": generator.gemini_model is not None
                },
                "topics": topics
            }, f, indent=2)

        logger.info(f"Results saved to {output_path}")
        if args.gemini_key and not generator.gemini_model:
            logger.warning("Gemini was not initialized - used basic mode")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)

if __name__ == "__main__":
    main()