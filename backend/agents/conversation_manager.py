# app/services/conversation_service.py
from agents.product_retriever import hybrid_search
from backend.services.postgres_service import PostgresService
from backend.ai_factory import GeminiAI

from langchain import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# NOTE: configure OPENAI_API_KEY or Azure equivalent in env
llm = GeminiAI()

quote_prompt = PromptTemplate(
    input_variables=["selected_products", "total"],
    template="You are a helpful sales assistant. Given these products: {selected_products} and total {total}, write a friendly, concise quotation paragraph."
)
quote_chain = LLMChain(llm=llm, prompt=quote_prompt)

async def generate_quote_text(selected_products: list, total: float) -> str:
    inp = {"selected_products": selected_products, "total": total}
    res = quote_chain.run(inp)
    return res

async def handle_user_message(session_id: int, user_id: str, content: str) -> str:
    # 1. store user message
    db = PostgresService()
    await db.add_message(session_id, "user", content)
    # 2. do a simple retrieval
    products = await hybrid_search(content, top_k=3)
    # 3. prepare a simple assistant reply using retrieved products
    if products:
        reply = f"I found {len(products)} products that might match. Example: {products[0]['name']}"
    else:
        reply = "I couldn't find matching products — can you rephrase?"
    # 4. store assistant message and return
    await db.add_message(session_id, "assistant", reply)
    return reply
