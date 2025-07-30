##  DepoIndex – AI-Powered Deposition Transcript Analyzer

**DepoIndex** is an AI-powered tool designed to analyze deposition transcripts and automatically generate a structured **Table of Contents (TOC)**. It detects key topics, clusters related segments, and highlights pivotal arguments with page and line references—offering legal professionals a smarter way to navigate lengthy legal transcripts.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/samarth1701/depoindex)](https://github.com/samarth1701/depoindex/issues)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://depoindex-samarth.streamlit.app/)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)


##  Features

- **Web Interface**: Accessible via [Streamlit App](https://depoindex-samarth.streamlit.app/)
- **Frontend:** Streamlit
- **Backend:** Python
- **AI/ML:** SentenceTransformers, Google Gemini API
- **Deployment:** Streamlit Cloud
- 
##  Quick Start

## Try the Web App
Access the live version immediately:  
 [https://depoindex-samarth.streamlit.app/](https://depoindex-samarth.streamlit.app/)

## Local Installation
bash
# Clone the repository
git clone https://github.com/samarth1701/depoindex.git
cd depoindex

# Create a Virtual Environment
bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install Dependencies
bash
pip install -r requirements.txt

# Add API Key
Create a .streamlit/secrets.toml file:
GEMINI_API_KEY = "your_gemini_api_key_here"

# Or set as environment variable:
bash
export GEMINI_API_KEY=your_gemini_api_key_here

# Run Locally
bash
streamlit run app.py

## Future Plans-
- LLM-based summarization of arguments

- Pro/Con polarity detection

- Export TOC to PDF/Word format

- Support for multilingual transcripts

## License
MIT License - See LICENSE for details.

## Contact
For support or questions:
Email: samarthtiwarij16@gmail.com

