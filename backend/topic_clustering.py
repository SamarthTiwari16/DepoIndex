import json
from typing import List, Dict, Optional
from dataclasses import dataclass
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('topic_clustering.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TopicCluster:
    name: str
    topics: List[str]
    legal_theme: str
    key_issues: List[str]
    confidence: float
    representative_excerpt: str

class GeminiTopicClusterer:
    """
    Uses Gemini to cluster topics semantically with legal context awareness
    """
    
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            'gemini-1.5-pro',
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json"
            },
            safety_settings={
                'HARASSMENT': 'block_none',
                'HATE_SPEECH': 'block_none',
                'SEXUALLY_EXPLICIT': 'block_none',
                'DANGEROUS_CONTENT': 'block_none'
            }
        )
        self.rate_limit_delay = 1.5  # seconds between calls

    def _enforce_rate_limit(self):
        """Ensure we don't exceed API rate limits"""
        elapsed = time.time() - self.rate_limit_last_call
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.rate_limit_last_call = time.time()

    def cluster_topics(self, topics: List[Dict], max_clusters: int = 5) -> List[TopicCluster]:
        """
        Cluster topics using Gemini's understanding of legal concepts
        """
        if not topics:
            return []

        # Prepare the input for Gemini
        topics_str = "\n".join(
            f"- {t['title']} (Page {t.get('page', '?')}, Line {t.get('line', '?')}): {t.get('context', '')[:100]}..."
            for t in topics
        )

        prompt = f"""
        As a legal AI expert, analyze these deposition topics and group them into {max_clusters} 
        semantically meaningful clusters based on:

        1. Legal issues addressed
        2. Factual patterns
        3. Testimony type
        4. Relevance to case theories

        For each cluster provide:
        - A concise name (3-5 words)
        - List of member topics
        - The primary legal theme
        - 3-5 key issues covered
        - Confidence score (0-1)
        - A representative excerpt

        Topics:
        {topics_str}

        Return JSON format:
        {{
            "clusters": [
                {{
                    "name": "string",
                    "topics": ["list"],
                    "legal_theme": "string",
                    "key_issues": ["list"],
                    "confidence": float,
                    "representative_excerpt": "string"
                }}
            ]
        }}
        """

        try:
            self._enforce_rate_limit()
            response = self.model.generate_content(prompt)
            
            # Parse the response
            if response.candidates and response.candidates[0].content.parts:
                result = json.loads(response.text)
                return [
                    TopicCluster(
                        name=c["name"],
                        topics=c["topics"],
                        legal_theme=c["legal_theme"],
                        key_issues=c["key_issues"],
                        confidence=c.get("confidence", 0.7),
                        representative_excerpt=c["representative_excerpt"]
                    )
                    for c in result.get("clusters", [])
                ]
        except Exception as e:
            logger.error(f"Clustering failed: {str(e)}")
        
        return []

    def hierarchical_cluster(self, topics: List[Dict], levels: int = 2) -> Dict:
        """
        Create a hierarchical cluster structure using recursive Gemini analysis
        """
        if not topics or levels <= 0:
            return {}

        top_level = self.cluster_topics(topics, max_clusters=3)
        
        hierarchy = {}
        for cluster in top_level:
            self._enforce_rate_limit()
            hierarchy[cluster.name] = {
                "details": cluster,
                "subclusters": self.hierarchical_cluster(
                    [t for t in topics if t['title'] in cluster.topics],
                    levels - 1
                )
            }
        
        return hierarchy

def save_clusters(clusters: List[TopicCluster], output_path: str) -> None:
    """Save clusters with proper formatting"""
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    "clusters": [
                        {
                            "name": c.name,
                            "legal_theme": c.legal_theme,
                            "key_issues": c.key_issues,
                            "confidence": c.confidence,
                            "representative_excerpt": c.representative_excerpt,
                            "member_topics": c.topics
                        }
                        for c in clusters
                    ]
                },
                f,
                indent=2
            )
        logger.info(f"Saved clusters to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save clusters: {str(e)}")

if __name__ == "__main__":
    # Example usage
    from generate_topics import TopicGenerator  # Reuse your topic generator
    
    # Initialize with your API key
    clusterer = GeminiTopicClusterer("YOUR_API_KEY")
    
    # Generate sample topics (or load from file)
    generator = TopicGenerator("YOUR_API_KEY")
    with open("output/topics.json") as f:
        topics = json.load(f)["topics"]
    
    # Cluster the topics
    clusters = clusterer.cluster_topics(topics)
    
    # Save results
    save_clusters(clusters, "output/clusters.json")
    
    # Optional: Generate hierarchical structure
    hierarchy = clusterer.hierarchical_cluster(topics)
    with open("output/hierarchy.json", "w") as f:
        json.dump(hierarchy, f, indent=2)