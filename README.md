# 🛒 B2B Sales Agent MVP

A Retrieval-Augmented Generation (RAG) based B2B sales agent built with FastAPI, Streamlit, and Elasticsearch.

## Future Updates

- **Downloadable**: actual Quotation PDF and Pitch Deck PPT generation, and email service
- **Multilingual Approach**: using toggle for static frontend elements and sending the language to backend for other elements
- **Production grade**: Improving scalability using fallbacks, logging, modular code, caching
- **TTS/STT**: Adding an option to the chat using Elevenlabs for TTS and STT services
- **Enhancing backend**: Making the chatbot better at reading sentiment and searching products more accurately
- **User Details**: Creating user personas and adding user authentication
- **Scalability**: Using docker containerisation, load balancer, and advanced CI/CD tools

## 🚀 Features

- **Hybrid Search**: Combines text search and vector search using Reciprocal Rank Fusion (RRF)
- **Two-Stage Conversation Flow**:
  - **Discovery Stage**: Understanding customer requirements
  - **Quote Stage**: Providing product recommendations and pricing
- **Intent Classification**: AI-powered understanding of customer intent
- **Multi-turn Dialogue**: Maintains conversation context and state
- **Product Database**: Indexes CSV product data with different schemas
- **Chat History**: Persistent conversation storage in PostgreSQL

## 🏗️ Architecture

```
Frontend (Streamlit) ↔ Backend (FastAPI) ↔ Database (PostgreSQL)
                                        ↔ Search (Elasticsearch)
                                        ↔ AI (Gemini)
```

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL
- Elasticsearch (optional, will use fallback if not available)
- Gemini API key

## 🛠️ Quick Setup

1. **Run Setup**:
```bash
python setup.py
```

2. **Start the Application**:
```bash
python run.py
```

## 💬 Usage

1. Open the Streamlit interface (usually at http://localhost:8501)
2. Start chatting with the sales agent
3. The agent will:
   - **Discovery Stage**: Ask clarifying questions about your needs
   - **Quote Stage**: Provide product recommendations and pricing

### Example Conversation:

**You**: "I need a laptop for graphic design"

**Agent**: "I found some laptops that might work for graphic design. What's your budget range? Do you need any specific features like dedicated graphics or a particular screen size?"

**You**: "Budget is around $2000, need good graphics card"

**Agent**: *[Moves to Quote Stage]* "Based on your requirements, I recommend these laptops with dedicated graphics cards within your budget..."

## 📁 Project Structure

```
backend/
├── agents/              # AI agents and conversation logic
├── models/             # Pydantic data models
├── services/           # Database and search services
├── ai_factory.py       # LLM integration
└── main.py            # FastAPI application

frontend/
└── chat_interface.py   # Streamlit chat interface

data/
├── csv/               # Product CSV files
└── json/              # Product JSON files
```


## 📝 Notes

This is an MVP implementation focused on core functionality. It uses mock vectors for simplicity but can be easily extended with real embeddings for production use.