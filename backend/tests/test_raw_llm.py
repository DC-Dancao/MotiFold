import asyncio
import os
import sys
import json

# Add the app directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.llm.factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

async def test_raw_llm_streaming():
    topic = "鱼香肉丝的做法"
    
    prompt = """You are an expert teacher designing a visual blackboard layout.
The user wants to explain the following topic: 鱼香肉丝的做法

Your task is to design the FINAL state of the blackboard. This is what the board will look like at the very end of the lesson.
Break the final knowledge down into discrete 'blocks' (text, math, result).
Assign them non-overlapping x, y coordinates (0-80 to prevent going off-screen). 
Space them out logically (e.g., title at top, steps flowing downwards or side-by-side).
Use slight random rotations (-3 to 3) for a natural look.

Please output the response purely as JSON matching the schema for FinalBoard.
"""
    print("Calling raw LLM with streaming=True...")
    llm = get_llm(model_name="pro", streaming=True)
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Generate the final blackboard blocks for: 鱼香肉丝的做法")
        ])
        print("Raw response content length:")
        print(len(response.content))
        print("Raw response content prefix:")
        print(repr(response.content[:100]))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_raw_llm_streaming())
