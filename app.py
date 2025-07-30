import streamlit as st
import os
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import tempfile
from typing import Dict, Any
import logging
from concurrent.futures import ThreadPoolExecutor
from backend.gemini_processor import GeminiProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('depoindex.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.update({
        'results': None,
        'timestamp': None,
        'toc_text': None,
        'export_success': False,
        'current_file': None,
        'processing_stage': None,
        'progress': 0
    })

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_available = bool(GEMINI_API_KEY)
use_gemini = gemini_available  # Set directly since we removed the checkbox
num_topics = 5  # Default value since we removed the slider

# Configure Streamlit page - completely remove sidebar
st.set_page_config(
    page_title="DepoIndex - Legal Transcript Analyzer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS to completely remove sidebar and adjust layout
st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    .stApp {
        margin-left: 0;
    }
    .stProgress > div > div > div > div {
        background-color: #4a8cff;
    }
    .stMarkdown h3 {
        color: #2c3e50;
    }
    .stButton>button {
        width: 100%;
    }
    .stDownloadButton>button {
        width: 100%;
    }
    div[data-testid="stVerticalBlock"] > div:has(> .element-container > .stMarkdown > h3) {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# App Header
st.title("DepoIndex")
st.markdown("### AI-Powered Deposition Transcript Analysis")

# File Upload Section
st.header("📂 Upload Transcript")
upload_method = st.radio(
    "Select input method:",
    ["File Upload", "Paste Text"],
    horizontal=True
)

input_text = ""
current_file = None

if upload_method == "File Upload":
    uploaded_file = st.file_uploader(
        "Choose a transcript file",
        type=["txt", "pdf", "docx"],
        label_visibility="collapsed"
    )
    
    if uploaded_file:
        file_ext = uploaded_file.name.split(".")[-1].lower()
        try:
            if file_ext == "txt":
                input_text = uploaded_file.read().decode("utf-8")
                current_file = uploaded_file.name
            elif file_ext == "pdf":
                from PyPDF2 import PdfReader
                reader = PdfReader(uploaded_file)
                input_text = "\n".join(page.extract_text() or "" for page in reader.pages)
                current_file = uploaded_file.name
            elif file_ext == "docx":
                from docx import Document
                doc = Document(uploaded_file)
                input_text = "\n".join(p.text for p in doc.paragraphs)
                current_file = uploaded_file.name
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            logger.error(f"File processing error: {str(e)}")
            st.stop()
else:
    manual_text = st.text_area(
        "Paste transcript text here",
        height=300,
        placeholder="Paste deposition transcript here...",
        label_visibility="collapsed"
    )
    if manual_text:
        input_text = manual_text.strip()
        current_file = "pasted_text.txt"

# Validate input
if input_text:
    word_count = len(input_text.split())
    line_count = len(input_text.splitlines())
    
    with st.expander("Transcript Preview", expanded=False):
        st.text(f"First 500 characters:\n{input_text[:500]}...")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Word Count", word_count)
    with col2:
        st.metric("Line Count", line_count)
    
    if word_count < 100:
        st.warning("Transcript seems very short. Minimum 100 words recommended.")

# Processing functions
def _convert_results(results) -> Dict[str, Any]:
    """Standardize results format"""
    if isinstance(results, str):
        return {
            "topics": [],
            "summary": results,
            "metadata": {
                "error": True,
                "message": "Analysis failed"
            }
        }
    elif isinstance(results, list):
        return {
            "topics": results,
            "summary": f"Generated {len(results)} topics",
            "metadata": {
                "generated_at": datetime.now().isoformat()
            }
        }
    elif isinstance(results, dict):
        return results
    else:
        return {
            "topics": [],
            "summary": "Invalid results format",
            "metadata": {
                "error": True
            }
        }

def update_progress(stage: str, progress: int):
    """Update processing progress"""
    st.session_state.processing_stage = stage
    st.session_state.progress = progress
    logger.info(f"Progress: {stage} ({progress}%)")

def analyze_transcript(transcript_text: str, use_ai: bool, num_topics: int = 5) -> Dict[str, Any]:
    """Main analysis pipeline"""
    try:
        update_progress("Initializing", 10)
        processor = GeminiProcessor(api_key=GEMINI_API_KEY if use_ai else None)
        
        # Check if processor initialized properly
        if use_ai and not processor.model:
            raise RuntimeError("Failed to initialize Gemini processor")
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Generate topics
            future_topics = executor.submit(
                processor.analyze_transcript,
                transcript_text,
                num_topics
            )
            update_progress("Extracting topics", 30)
            
            # Get results
            topics = future_topics.result()
            
            # Handle empty results
            if not topics:
                raise RuntimeError("No topics could be generated")
                
            results = _convert_results(topics)
            update_progress("Processing results", 60)
            
            # Generate TOC if available
            toc_text = ""
            if use_ai and topics:
                future_toc = executor.submit(
                    processor.generate_enhanced_toc,
                    [t.__dict__ for t in topics] if hasattr(topics[0], '__dict__') else topics
                )
                update_progress("Generating TOC", 80)
                toc_text = future_toc.result() or ""
            
            update_progress("Finalizing", 95)
            
            return {
                "results": results,
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "toc_text": toc_text,
                "export_success": bool(topics)
            }
            
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise

# Start analysis
if input_text and st.button("🚀 Start Analysis", type="primary"):
    # Clear previous results
    st.session_state.update({
        'results': None,
        'timestamp': None,
        'toc_text': None,
        'export_success': False,
        'current_file': current_file,
        'processing_stage': "Starting",
        'progress': 0
    })
    
    status_area = st.empty()
    progress_bar = st.progress(0)
    result_container = st.empty()
    
    try:
        # Run analysis
        analysis_result = analyze_transcript(
            input_text, 
            use_gemini, 
            num_topics
        )
        
        # Update session state
        st.session_state.update(analysis_result)
        
        # Display completion
        status_area.markdown("✅ **Analysis Complete!**")
        progress_bar.progress(100)
        st.balloons()
        
    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        if 'progress_bar' in locals():
            progress_bar.empty()
        logger.error(f"Analysis error: {str(e)}")

# Display Results
if st.session_state.results:
    results = st.session_state.results
    
    st.header("📊 Analysis Results")
    
    # Summary metrics
    col1, col2 = st.columns(2)
    with col1:
        topics_count = len(results.get("topics", []))
        st.metric("Total Topics", topics_count)
    with col2:
        # Fixed: Use attribute access instead of .get()
        key_issues = sum(1 for t in results.get("topics", []) if t.is_key_issue)
        st.metric("Key Issues", key_issues)
    
    # Topic list - convert to dicts for dataframe
    st.subheader("Topic List")
    if results.get("topics"):
        # Convert TopicModel objects to dictionaries
        topics_data = [t.__dict__ for t in results["topics"]]
        
        st.dataframe(
            topics_data,
            column_config={
                "title": "Topic",
                "page": "Page",
                "line": "Line",
                "is_key_issue": st.column_config.CheckboxColumn("Key Issue"),
                "confidence": st.column_config.ProgressColumn(
                    "Confidence",
                    format="%.0f%%",
                    min_value=0,
                    max_value=1
                ),
                "legal_significance": "Legal Significance",
                "related_topics": "Related Topics"
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Add expandable details for each topic
        with st.expander("View Topic Details"):
            for topic in results["topics"]:
                st.markdown(f"### {topic.title}")
                cols = st.columns(3)
                with cols[0]:
                    st.metric("Page", topic.page)
                with cols[1]:
                    st.metric("Line", topic.line)
                with cols[2]:
                    st.metric("Confidence", f"{topic.confidence:.0%}")
                
                st.markdown("#### Context Excerpt")
                st.text(topic.context[:500] + ("..." if len(topic.context) > 500 else ""))
                
                if topic.related_topics:
                    st.markdown("#### Related Topics")
                    st.write(", ".join(topic.related_topics))
                
                if topic.legal_significance:
                    st.markdown("#### Legal Significance")
                    st.write(topic.legal_significance)
                
                st.divider()
    else:
        st.info("No topics found in the analysis.")
    
    # TOC section
    if st.session_state.toc_text:
        st.subheader("📑 Table of Contents")
        with st.expander("View Full TOC"):
            st.markdown(st.session_state.toc_text)
    
    # Download section
    st.header("📥 Download Results")
    
    # JSON download
    if st.session_state.results:
        # Convert TopicModel objects to dicts for JSON serialization
        downloadable_results = {
            "metadata": results.get("metadata", {}),
            "topics": [t.__dict__ for t in results.get("topics", [])],
            "summary": results.get("summary", "")
        }
        
        st.download_button(
            "Download Analysis (JSON)",
            json.dumps(downloadable_results, indent=2),
            f"deposition_analysis_{st.session_state.timestamp}.json",
            help="Complete analysis results in JSON format"
        )

# Footer
st.markdown("---")
st.markdown("""
**DepoIndex** v1.2 | *For attorney use only*  
[Report Issues](https://github.com/yourrepo/depoindex/issues) | [Documentation](https://github.com/yourrepo/depoindex)
""")