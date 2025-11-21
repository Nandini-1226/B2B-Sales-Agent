# 🛒 B2B Sales Agent MVP

A Retrieval-Augmented Generation (RAG) based B2B sales agent built with FastAPI, Streamlit, and Elasticsearch.

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

1. **Set Environment Variables**:
```powershell
$Env:DATABASE_URL = "postgresql://user:password@localhost:5432/sales_agent"
$Env:GEMINI_API_KEY = "your-gemini-api-key"
```

2. **Run Setup**:
```bash
python setup.py
```

3. **Start the Application**:
```bash
python run.py
```

## 🔧 Manual Setup

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Setup Database**:
   - Create PostgreSQL database
   - Tables will be created automatically

3. **Index Product Data**:
```bash
python backend/services/elasticsearch_service.py
```

4. **Start Backend**:
```bash
python -m uvicorn backend.main:app --reload
```

5. **Start Frontend**:
```bash
streamlit run frontend/chat_interface.py
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

## 🧩 Components

### Conversation Manager
- Intent classification using LLM
- Two-stage conversation flow (Discovery → Quote)
- State management and context tracking

### Hybrid Search
- Text search using Elasticsearch multi-match
- Vector search using dense vectors (mock implementation)
- Reciprocal Rank Fusion for combining results

### Product Retriever
- Async wrapper for Elasticsearch operations
- Handles different CSV schemas automatically
- Fallback mechanisms for robustness

## 🔍 Key Features

- **Smart Product Indexing**: Handles different CSV column names automatically
- **Conversation State**: Tracks customer requirements and selected products
- **Intent Recognition**: Understands when to move between discovery and quote stages
- **Responsive UI**: Modern chat interface with product displays
- **Error Handling**: Graceful fallbacks when services are unavailable

## 🚨 Troubleshooting

**Backend won't start**:
- Check DATABASE_URL is set correctly
- Ensure PostgreSQL is running
- Check GEMINI_API_KEY is valid

**Search not working**:
- Elasticsearch is optional; will use fallback
- Check if product data is indexed

**Frontend errors**:
- Ensure backend is running on port 8000
- Check browser console for errors

## 🔮 Future Enhancements

- Real vector embeddings (sentence-transformers)
- User authentication
- Product cart functionality
- Email quote generation
- Advanced analytics
- Multi-language support

## 📝 Notes

This is an MVP implementation focused on core functionality. It uses mock vectors for simplicity but can be easily extended with real embeddings for production use.