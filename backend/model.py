from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

# Load once globally
model = SentenceTransformer('all-MiniLM-L6-v2')
embedding_cache = []
chunk_cache = []

def build_topic_clusters(chunks, n_clusters=5):
    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts)

    # Reduce clusters if too few samples
    n_clusters = min(n_clusters, len(texts))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(embeddings)

    for i, chunk in enumerate(chunks):
        chunk["cluster"] = int(labels[i])

    # Collect text for each cluster
    cluster_texts = {i: "" for i in range(n_clusters)}
    for i, chunk in enumerate(chunks):
        cluster_texts[labels[i]] += " " + chunk["text"]

    topic_keywords = extract_cluster_keywords(cluster_texts)

    # Assign topic name to each chunk
    for chunk in chunks:
        chunk["topic_name"] = topic_keywords[chunk["cluster"]]

    # Populate caches
    global embedding_cache, chunk_cache
    embedding_cache = model.encode([chunk["text"] for chunk in chunks])
    chunk_cache = chunks

    return chunks


def extract_cluster_keywords(cluster_texts):
    vectorizer = TfidfVectorizer(stop_words='english', max_features=50)
    topic_keywords = {}
    for cluster_id, text in cluster_texts.items():
        tfidf_matrix = vectorizer.fit_transform([text])
        scores = zip(vectorizer.get_feature_names_out(), tfidf_matrix.toarray()[0])
        sorted_words = sorted(scores, key=lambda x: x[1], reverse=True)
        keywords = [word for word, score in sorted_words[:3]]  # Top 3 keywords
        topic_keywords[cluster_id] = " / ".join(keywords).title()
    return topic_keywords


def call_gpt_topic_detector(text, page, line):
    new_embedding = model.encode([text])[0]

    if embedding_cache is None or len(embedding_cache) == 0:
        return "Unknown", page, line

    def cosine_sim(a, b):
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        if a_norm == 0 or b_norm == 0:
            return 0
        return np.dot(a, b) / (a_norm * b_norm)

    similarities = [cosine_sim(e, new_embedding) for e in embedding_cache]
    best_match_index = np.argmax(similarities)
    best_chunk = chunk_cache[best_match_index]

    topic = best_chunk.get("topic_name", "Unknown")

    return topic, page, line
