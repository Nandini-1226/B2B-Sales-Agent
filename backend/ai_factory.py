from dotenv import load_dotenv
import os
# set openai_api_key in your environment variables to use the client
load_dotenv()
os.environ["GEMINI_API_KEY"] = os.getenv("gemini_api_key")

from google import genai

# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client()

response = client.models.generate_content(
    model="gemini-2.5-flash-lite", contents="Explain how AI works in a few words"
)
print(response.text)