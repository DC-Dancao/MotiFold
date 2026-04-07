import asyncio
import os
import sys
import json

# Add the app directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.blackboard_agent import run_blackboard_agent

async def test_blackboard_generation():
    topic = "鱼香肉丝的做法"
    print(f"Generating blackboard steps for: {topic}")
    
    try:
        steps_data = await run_blackboard_agent(topic)
        print("Generation successful!\n")
        
        print(f"Total steps generated: {len(steps_data)}")
        for i, step in enumerate(steps_data):
            print(f"\n--- Step {i+1}: {step.get('title')} ---")
            print(f"Note: {step.get('note')}")
            blocks = step.get('boardState', [])
            print(f"Visible Blocks: {len(blocks)}")
            for block in blocks:
                highlight_str = "[HIGHLIGHTED]" if block.get('highlight') else ""
                print(f"  - {block.get('id')} ({block.get('type')}): {block.get('content')} {highlight_str}")
                
        print("\n--- End of Output ---")
        
    except Exception as e:
        print(f"Error during generation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_blackboard_generation())