from dotenv import load_dotenv
from google import genai
from typing import Optional, List, Mapping, Any

class GeminiAI:
    def __init__(self):        
        load_dotenv()
        # The client gets the API key from the environment variable `GEMINI_API_KEY`.
        self.client = genai.Client()

    def generate_content(self, contents: str) -> str:
        response = self.client.models.generate_content(
            model="gemini-2.5-flash-lite", contents=contents
        )
        return response.text
    
    def run(self, prompt: str) -> str:
        """For compatibility with LangChain-style usage"""
        return self.generate_content(prompt)