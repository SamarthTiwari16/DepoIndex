import argparse
import json
import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.gemini_processor import GeminiProcessor, TopicModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('transcript_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TranscriptProcessor:
    """Enhanced transcript processing with better error handling and validation"""
    
    @staticmethod
    def load_transcript(path: str) -> str:
        """Load transcript file with comprehensive validation"""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                raise FileNotFoundError(f"Transcript file not found: {path}")
            if path_obj.stat().st_size == 0:
                raise ValueError("Transcript file is empty")
                
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    raise ValueError("Transcript contains no readable content")
                return content
                
        except UnicodeDecodeError:
            logger.error("Transcript contains invalid UTF-8 characters")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load transcript: {str(e)}")
            sys.exit(1)

    @staticmethod
    def preprocess_transcript(text: str) -> str:
        """Advanced cleaning with legal-specific patterns"""
        # Remove deponent/examiner markers and exhibit references
        patterns = [
            r"^(Q|A|MR|MS|MRS|THE WITNESS|EXAMINER)[\.:]?\s*",
            r"\[.*?\]",  # Remove annotations
            r"Page \d+",  # Page numbers
            r"EXHIBIT\s+\d+",  # Exhibit markers
            r"\s{2,}",  # Extra whitespace
        ]
        
        cleaned_lines = []
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            for pattern in patterns:
                line = re.sub(pattern, "", line, flags=re.IGNORECASE)
            line = line.strip()
            
            if len(line) > 3 and any(c.isalpha() for c in line):  # Minimum viable content
                cleaned_lines.append(line)
                
        return "\n".join(cleaned_lines)

    @staticmethod
    def chunk_text(text: str, max_chars: int = 8000) -> List[str]:
        """Context-aware chunking that preserves legal discourse structure"""
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        chunks = []
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            para_length = len(para)
            
            # Start new chunk if adding this paragraph would exceed limit
            if current_length + para_length > max_chars and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0
                
            # Special handling for question/answer blocks
            if re.match(r"^(Q:|A:|Question|Answer)", para, re.IGNORECASE):
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                    
            current_chunk.append(para)
            current_length += para_length
            
        if current_chunk:
            chunks.append("\n".join(current_chunk))
            
        return chunks

    @staticmethod
    def save_results(results: Dict[str, Any], output_path: str) -> None:
        """Atomic write with backup preservation"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temp file first
            temp_path = output_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
                
            # Replace original file
            temp_path.replace(output_path)
            logger.info(f"Successfully saved results to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save results: {str(e)}")
            sys.exit(1)

class AnalysisPipeline:
    """Optimized pipeline with parallel processing and progress tracking"""
    
    def __init__(self, processor: GeminiProcessor, max_workers: int = 4):
        self.processor = processor
        self.max_workers = max_workers
        self.rate_limit_delay = 1.5  # seconds between API calls
        
    def process_transcript(self, text: str, num_topics: int = 5) -> Dict[str, Any]:
        """Execute pipeline with progress monitoring"""
        logger.info("Starting transcript analysis pipeline")
        
        # Phase 1: Preparation
        logger.info("Preprocessing transcript...")
        clean_text = TranscriptProcessor.preprocess_transcript(text)
        chunks = TranscriptProcessor.chunk_text(clean_text)
        
        if not chunks:
            logger.error("No valid content chunks after preprocessing")
            sys.exit(1)
            
        # Phase 2: Topic Generation (parallel)
        logger.info(f"Generating topics across {len(chunks)} chunks...")
        topics = self._parallel_generate_topics(chunks, num_topics)
        
        if not topics:
            logger.error("No topics could be generated")
            sys.exit(1)
            
        # Phase 3: Topic Enhancement
        logger.info("Enhancing top topics...")
        enhanced_topics = self._enhance_topics(topics)
        
        # Phase 4: Summary Generation
        logger.info("Generating final summary...")
        summary = self.processor.generate_deposition_summary(enhanced_topics)
        
        return {
            "metadata": {
                "source": "Gemini Legal Analysis",
                "processing_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "chunks_processed": len(chunks),
                "gemini_version": "gemini-1.5-flash"
            },
            "topics": [t.dict() for t in enhanced_topics],
            "summary": summary,
            "statistics": {
                "total_topics": len(enhanced_topics),
                "average_confidence": self._calculate_avg_confidence(enhanced_topics),
                "key_issues": sum(1 for t in enhanced_topics if t.is_key_issue)
            }
        }
    
    def _parallel_generate_topics(self, chunks: List[str], num_topics: int) -> List[TopicModel]:
        """Process chunks in parallel with progress tracking"""
        topics = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._process_chunk,
                    chunk,
                    i,
                    len(chunks),
                    num_topics
                ): i for i, chunk in enumerate(chunks)
            }
            
            for future in as_completed(futures):
                try:
                    chunk_topics = future.result()
                    topics.extend(chunk_topics)
                except Exception as e:
                    logger.warning(f"Chunk processing failed: {str(e)}")
                    
        return topics
    
    def _process_chunk(self, chunk: str, chunk_idx: int, total_chunks: int, num_topics: int) -> List[TopicModel]:
        """Process individual chunk with rate limiting"""
        logger.info(f"Processing chunk {chunk_idx + 1}/{total_chunks}")
        try:
            topics = self.processor.generate_topics(chunk, num_topics)
            time.sleep(self.rate_limit_delay)
            return topics
        except Exception as e:
            logger.warning(f"Failed to process chunk {chunk_idx + 1}: {str(e)}")
            return []
    
    def _enhance_topics(self, topics: List[TopicModel], max_to_enhance: int = 15) -> List[TopicModel]:
        """Enhanced topic processing with prioritization"""
        if not topics:
            return []
            
        # Prioritize by confidence and key issues
        sorted_topics = sorted(
            topics,
            key=lambda x: (x.is_key_issue, x.confidence),
            reverse=True
        )
        
        enhanced = []
        for i, topic in enumerate(sorted_topics[:max_to_enhance], 1):
            logger.info(f"Enhancing topic {i}/{min(len(topics), max_to_enhance)}: {topic.title[:50]}...")
            try:
                enhanced_topic = self.processor.enhance_topic(topic)
                enhanced.append(enhanced_topic)
                time.sleep(self.rate_limit_delay)
            except Exception as e:
                logger.warning(f"Topic enhancement failed: {str(e)}")
                enhanced.append(topic)
                
        return enhanced + sorted_topics[max_to_enhance:]
    
    def _calculate_avg_confidence(self, topics: List[TopicModel]) -> float:
        """Weighted average calculation"""
        if not topics:
            return 0.0
            
        total = sum(t.confidence * (1.5 if t.is_key_issue else 1) for t in topics)
        weights = sum(1.5 if t.is_key_issue else 1 for t in topics)
        
        return total / weights

def validate_args(args: argparse.Namespace) -> None:
    """Comprehensive argument validation"""
    if not Path(args.input_path).exists():
        raise FileNotFoundError(f"Input file not found: {args.input_path}")
    if args.topics < 1 or args.topics > 10:
        raise ValueError("Number of topics must be between 1 and 10")
    if args.enhance < 1:
        raise ValueError("Must enhance at least 1 topic")

def main():
    parser = argparse.ArgumentParser(
        description="Advanced Legal Transcript Analysis System",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--in', 
        dest='input_path', 
        required=True,
        help="Path to input transcript file"
    )
    parser.add_argument(
        '--out', 
        dest='output_path', 
        required=True,
        help="Path to save analysis results (JSON)"
    )
    parser.add_argument(
        '--topics', 
        type=int, 
        default=5,
        help="Number of topics to generate per text chunk (1-10)"
    )
    parser.add_argument(
        '--gemini-key', 
        dest='api_key', 
        required=True,
        help="Gemini API key"
    )
    parser.add_argument(
        '--enhance', 
        type=int, 
        default=15,
        help="Number of top topics to enhance"
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help="Number of parallel processing workers"
    )
    
    try:
        args = parser.parse_args()
        validate_args(args)
        
        logger.info("Initializing analysis system...")
        start_time = time.time()
        
        processor = GeminiProcessor(args.api_key)
        pipeline = AnalysisPipeline(processor, args.workers)
        
        logger.info(f"Loading transcript: {args.input_path}")
        raw_text = TranscriptProcessor.load_transcript(args.input_path)
        
        logger.info("Processing transcript...")
        results = pipeline.process_transcript(raw_text, args.topics)
        
        processing_time = time.time() - start_time
        results['statistics']['processing_time_seconds'] = round(processing_time, 2)
        
        logger.info(f"Saving results to {args.output_path}")
        TranscriptProcessor.save_results(results, args.output_path)
        
        logger.info("\n" + "="*50)
        logger.info("Analysis Complete")
        logger.info(f"  Total Topics: {results['statistics']['total_topics']}")
        logger.info(f"  Key Issues: {results['statistics']['key_issues']}")
        logger.info(f"  Avg Confidence: {results['statistics']['average_confidence']:.2f}")
        logger.info(f"  Processing Time: {processing_time:.2f} seconds")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()