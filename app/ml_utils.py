# -*- coding: utf-8 -*-
import ollama
import os
from typing import Dict

# Configure Ollama client
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
ollama.Client(host=OLLAMA_HOST)

# Map tariffs to model names
MODEL_MAP = {
    "standart": "gemma3:1b",
    "pro": "gemma3:4b",
    "premium": "gemma3:12b"
}

def generate_text(prompt: str, tariff: str) -> str:
    """
    Generate text using Ollama's Gemma models based on the selected tariff.
    
    Args:
        prompt (str): The input prompt for text generation
        tariff (str): The tariff level (standart, pro, or premium)
        
    Returns:
        str: Generated text response
    """
    system_prompt = f"""
    You are a helpful seller assistant that generates text based on the user's request.
    You should generate text on RUSSIAN that is relevant to the user's request and is appropriate for the selected tariff.
    Your task is to write ONLY a very saleable sales description in RUSSIAN for a product based on the provided specifications.
    Reply only in RUSSIAN.
    """
    try:
        model_name = MODEL_MAP.get(tariff)
        if not model_name:
            return "Error: Invalid tariff selected"
            
        response = ollama.generate(
            model=model_name,
            prompt=system_prompt + "\n" + prompt,
            stream=False,
            options={
                "num_predict": 2048
            }
        )
        
        # Убедимся, что ответ правильно закодирован
        if isinstance(response['response'], bytes):
            return response['response'].decode('utf-8')
        return str(response['response'])
        
    except Exception as e:
        return f"Error generating text: {str(e)}"