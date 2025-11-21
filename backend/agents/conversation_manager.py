# Conversation manager with discovery and quote stages
from backend.agents.product_retriever import hybrid_search
from backend.services.postgres_service import PostgresService
from backend.ai_factory import GeminiAI
from backend.models.pydantic_model import ConversationStage, ConversationState, ConversationResponse, ProductMatch, IntentClassification
import uuid
import json
import asyncio
import logging
import re

# Initialize AI model
llm = GeminiAI()

# Prompt templates
CATEGORY_DETECTION_PROMPT = """
Detect the product category from the user's message. Available categories are:
cpu, external-hard-drive, headphones, internal-hard-drive, keyboard, memory, monitor, motherboard, mouse, sound-card, speakers, ups, video-card, webcam, case, cpu-cooler, power-supply

User Message: {message}

Return ONLY a JSON object with this format:
{{"category": "cpu", "confidence": 0.9}}

If no clear category is detected, return {{"category": "general", "confidence": 0.5}}
"""

INTENT_PROMPT = """
Analyze the user's message and classify their intent. Consider the conversation history for context.

User Message: {message}

Conversation History: {conversation_history}

Classify into one of these intents:
1. product_search - User is looking for specific products
2. requirement_clarification - User is providing more details about their needs
3. quote_request - User wants pricing or to finalize selection
4. general - General conversation

Return ONLY a JSON object with this format:
{{"intent": "product_search", "confidence": 0.9, "entities": {{"product_type": "laptop", "budget": "under 1000"}}}}
"""

DISCOVERY_PROMPT = """
You are a helpful B2B sales assistant in discovery mode. Your goal is to understand the customer's needs better.

Customer Message: {message}
Found Products: {products}
Current Requirements: {requirements}

If products were found, present them briefly and ask clarifying questions to better understand their needs.
If no products were found, ask for more specific details about what they're looking for.

Keep responses friendly, professional, and focused on gathering requirements.
Ask 1-2 specific questions to move the conversation forward.
"""

QUOTE_PROMPT = """
You are a B2B sales assistant ready to provide quotes. The customer has shown interest in products and is ready for pricing.

Selected Products: {selected_products}
Customer Requirements: {requirements}
Customer Message: {message}

Provide a clear, professional quote including:
- Product recommendations that match their needs
- Brief explanation of why these products fit
- Next steps for ordering

Be confident and helpful in closing the sale.
"""

# In-memory conversation states (in production, use Redis or database)
conversation_states = {}

def format_prompt(template: str, **kwargs) -> str:
    """Simple prompt formatting without LangChain."""
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template

async def get_conversation_state(session_id: uuid.UUID) -> ConversationState:
    """Get or create conversation state."""
    if session_id not in conversation_states:
        conversation_states[session_id] = ConversationState(
            session_id=session_id,
            stage=ConversationStage.DISCOVERY
        )
    return conversation_states[session_id]

async def classify_intent(message: str, history: str = "") -> IntentClassification:
    """Classify user intent using LLM."""
    try:
        prompt = format_prompt(INTENT_PROMPT, message=message, conversation_history=history)
        result = await asyncio.to_thread(llm.generate_content, prompt)
        
        # Parse JSON response
        intent_data = json.loads(result.strip())
        return IntentClassification(**intent_data)
    except Exception as e:
        print(f"Intent classification error: {e}")
        # Default fallback
        return IntentClassification(
            intent="product_search",
            confidence=0.5,
            entities={}
        )

async def detect_category(message: str) -> dict:
    """Detect product category from user message."""
    try:
        prompt = format_prompt(CATEGORY_DETECTION_PROMPT, message=message)
        result = await asyncio.to_thread(llm.generate_content, prompt)
        category_data = json.loads(result.strip())
        logging.info(f"Category detection: {category_data}")
        return category_data
    except Exception as e:
        logging.error(f"Category detection error: {e}")
        return {"category": "general", "confidence": 0.5}

async def handle_discovery_stage(state: ConversationState, message: str) -> ConversationResponse:
    """Handle discovery stage conversation."""
    logging.info(f"Discovery stage - User message: {message}")
    
    # Detect product category
    category_info = await detect_category(message)
    detected_category = category_info.get("category", "general")
    
    # Update state with detected category
    if "product_category" not in state.discovered_requirements:
        state.discovered_requirements["product_category"] = detected_category
        logging.info(f"Set product category to: {detected_category}")
    
    # Search for products in the specific category
    current_category = state.discovered_requirements.get("product_category", "general")
    products = await hybrid_search(message, top_k=5, category=current_category)
    
    logging.info(f"Found {len(products)} products in category '{current_category}'")
    for i, p in enumerate(products[:3]):
        logging.info(f"Product {i+1}: {p.get('name', 'Unknown')} - {list(p.keys())}")
    
    # Convert to ProductMatch objects with all available fields
    product_matches = []
    for p in products:
        # Create a comprehensive product match with all available fields
        product_data = {
            "name": p.get("name", "Unknown Product"),
            "description": p.get("description", ""),
            "price": float(p.get("price", 0)) if p.get("price") and str(p.get("price", "")).replace(".", "").replace("-", "").isdigit() else 0.0,
            "score": 1.0
        }
        
        # Add all other fields as additional attributes for frontend display
        for key, value in p.items():
            if key not in ["name", "description", "price", "description_vector"] and value:
                product_data[key] = value
        
        product_match = ProductMatch(**{k: v for k, v in product_data.items() if k in ["name", "description", "price", "score"]})
        # Add extra fields for frontend display
        for key, value in product_data.items():
            if key not in ["name", "description", "price", "score"]:
                setattr(product_match, key, value)
        
        product_matches.append(product_match)
    
    # Update requirements
    intent = await classify_intent(message)
    if intent.entities:
        state.discovered_requirements.update(intent.entities)
    
    # Generate response
    products_text = json.dumps([p.model_dump() for p in product_matches], indent=2)
    requirements_text = json.dumps(state.discovered_requirements, indent=2)
    
    prompt = format_prompt(
        DISCOVERY_PROMPT,
        message=message,
        products=products_text,
        requirements=requirements_text
    )
    response_text = await asyncio.to_thread(llm.generate_content, prompt)
    
    # Enhanced stage transition logic
    quote_keywords = ["price", "cost", "quote", "buy", "purchase", "order", "how much", "get this", "i want", "i'll take", "looks good", "perfect", "interested"]
    confirmation_keywords = ["yes", "ok", "sure", "sounds good", "that works", "perfect"]
    
    message_lower = message.lower()
    should_transition = False
    
    if any(keyword in message_lower for keyword in quote_keywords) and len(product_matches) > 0:
        should_transition = True
        logging.info("Stage transition triggered by quote keywords")
    elif any(keyword in message_lower for keyword in confirmation_keywords) and len(product_matches) > 0:
        should_transition = True
        logging.info("Stage transition triggered by confirmation keywords")
    elif len(re.findall(r'\b(this|that|it)\b', message_lower)) > 0 and len(product_matches) > 0:
        should_transition = True
        logging.info("Stage transition triggered by product reference")
    
    if should_transition:
        state.stage = ConversationStage.QUOTE
        state.selected_products = [p.model_dump() for p in product_matches]
        state.total_price = sum(p.price for p in product_matches if p.price > 0)
        logging.info(f"Transitioned to QUOTE stage with {len(product_matches)} products, total: ${state.total_price}")
    
    logging.info(f"Current stage: {state.stage}")
    
    return ConversationResponse(
        message=response_text,
        stage=state.stage,
        products=product_matches,
        next_questions=["What's your budget range?", "Any specific features you need?"]
    )

async def handle_quote_stage(state: ConversationState, message: str) -> ConversationResponse:
    """Handle quote stage conversation."""
    selected_products_text = json.dumps(state.selected_products, indent=2)
    requirements_text = json.dumps(state.discovered_requirements, indent=2)
    
    prompt = format_prompt(
        QUOTE_PROMPT,
        selected_products=selected_products_text,
        requirements=requirements_text,
        message=message
    )
    response_text = await asyncio.to_thread(llm.generate_content, prompt)
    
    # Convert selected products to ProductMatch objects
    product_matches = []
    for p in state.selected_products:
        product_matches.append(ProductMatch(**p))
    
    return ConversationResponse(
        message=response_text,
        stage=state.stage,
        products=product_matches,
        next_questions=["Ready to place an order?", "Need any modifications?"]
    )

async def handle_user_message(session_id: uuid.UUID, content: str, db_service: PostgresService) -> ConversationResponse:
    """Main conversation handler with stage management."""
    # Get conversation state
    state = await get_conversation_state(session_id)
    
    # Store user message in database
    await db_service.add_message(session_id, "user", content)
    
    # Handle based on current stage
    if state.stage == ConversationStage.DISCOVERY:
        response = await handle_discovery_stage(state, content)
    else:  # QUOTE stage
        response = await handle_quote_stage(state, content)
    
    # Store assistant response
    await db_service.add_message(session_id, "assistant", response.message)
    
    # Update conversation state
    conversation_states[session_id] = state
    
    return response
