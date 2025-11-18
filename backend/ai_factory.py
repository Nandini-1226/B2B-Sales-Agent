from dotenv import load_dotenv
from google import genai

class GeminiAI():
    def __init__(self):        
        # set openai_api_key in your environment variables to use the client
        load_dotenv()

        # The client gets the API key from the environment variable `GEMINI_API_KEY`.
        self.client = genai.Client()

    def generate_content(self, contents: str) -> genai.Response:
        response = self.client.models.generate_content(
            model="gemini-2.5-flash-lite", contents=contents
        )
        return response.text