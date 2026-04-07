import asyncio
import os
import sys

# Add the app directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import SystemMessage, HumanMessage
from app.llm import get_llm

from app.matrix_service import generate_morphological_parameters, evaluate_morphological_consistency
from app.routers.matrix_router import MorphologicalParameter

async def test_generation():
    focus_question = "How to design a futuristic surveillance system?"
    print(f"Generating parameters for: {focus_question}")
    
    try:
        response = await generate_morphological_parameters(focus_question)
        print("Generation successful!")
        for param in response.parameters:
            print(f"- {param.name}: {param.states}")
            
        print("\nEvaluating consistency...")
        eval_response = await evaluate_morphological_consistency(response.parameters)
        print("Evaluation successful!")
        print(eval_response["results_list"])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_generation())
