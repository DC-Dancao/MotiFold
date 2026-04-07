import json
from typing import List, Dict, Any, TypedDict, Literal
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

from app.config import settings
from app.llm import get_llm

# ============================================================================
# Schemas for Structured Output
# ============================================================================

class Block(BaseModel):
    id: str = Field(description="Unique ID for the block, e.g., blk_1")
    type: Literal["text", "math", "result"] = Field(description="Type of the block")
    content: str = Field(description="The text, math formula, or result content")
    x: int = Field(description="X coordinate percentage from 0 to 80 to prevent overflow")
    y: int = Field(description="Y coordinate percentage from 0 to 80 to prevent overflow")
    rot: int = Field(description="Rotation angle in degrees, usually between -3 and 3 for a handwritten feel")

class FinalBoard(BaseModel):
    blocks: List[Block] = Field(description="All blocks present on the blackboard at the very end of the explanation")

class StepHighlight(BaseModel):
    block_id: str = Field(description="The ID of the block")
    highlight: bool = Field(description="True if this block should be highlighted in this step")

class Step(BaseModel):
    title: str = Field(description="Short title for the current step")
    note: str = Field(description="The teacher's spoken explanation for this step")
    visible_blocks: List[StepHighlight] = Field(description="List of blocks that are VISIBLE on the board in this step. Blocks not in this list will be hidden.")

class ReverseSteps(BaseModel):
    steps: List[Step] = Field(description="The chronological steps of the explanation, from start to finish.")

# ============================================================================
# State Definition
# ============================================================================

class BlackboardState(TypedDict):
    topic: str
    final_board: FinalBoard
    reverse_steps: ReverseSteps
    final_output: List[Dict[str, Any]]

# ============================================================================
# Nodes
# ============================================================================

async def generate_final_board(state: BlackboardState):
    """
    Step 1: Generate the final complete state of the blackboard.
    """
    topic = state["topic"]
    
    parser = PydanticOutputParser(pydantic_object=FinalBoard)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert teacher designing a visual blackboard layout.
The user wants to explain the following topic: {topic}

Your task is to design the FINAL state of the blackboard. This is what the board will look like at the very end of the lesson.
Break the final knowledge down into discrete 'blocks' (text, math, result).
Assign them non-overlapping x, y coordinates (0-80 to prevent going off-screen). 
Space them out logically (e.g., title at top, steps flowing downwards or side-by-side).
Use slight random rotations (-3 to 3) for a natural look.

{format_instructions}
"""),
        ("user", "Generate the final blackboard blocks for: {topic}")
    ])
    
    # We use the PRO model for better spatial reasoning
    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=True).bind(response_format={"type": "json_object"})
    chain = prompt | llm | parser
    
    final_board = await chain.ainvoke({
        "topic": topic,
        "format_instructions": parser.get_format_instructions()
    })
    return {"final_board": final_board}

async def generate_steps_reverse(state: BlackboardState):
    """
    Step 2: Reverse-engineer the teaching process into chronological steps.
    """
    topic = state["topic"]
    final_board = state["final_board"]
    
    parser = PydanticOutputParser(pydantic_object=ReverseSteps)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert teacher. You have already designed the final blackboard layout:
{final_blocks}

Now, you need to reverse-engineer the teaching process. Break the explanation into 3 to 6 chronological steps.
For each step, provide:
1. 'title': A short title.
2. 'note': What the teacher says (the script).
3. 'visible_blocks': Which blocks from the final layout are CURRENTLY visible. 
   - Note: Blocks usually appear sequentially. Step 1 might only have 1-2 blocks. Step N will have all blocks.
   - Set 'highlight: true' for blocks that are newly added or the main focus of the current step.

{format_instructions}
"""),
        ("user", "Generate the chronological teaching steps for the topic: {topic}")
    ])
    
    llm = get_llm(model_name=settings.OPENAI_MODEL_PRO, streaming=True).bind(response_format={"type": "json_object"})
    chain = prompt | llm | parser
    
    final_blocks_json = final_board.model_dump_json(indent=2)
    reverse_steps = await chain.ainvoke({
        "topic": topic, 
        "final_blocks": final_blocks_json,
        "format_instructions": parser.get_format_instructions()
    })
    
    return {"reverse_steps": reverse_steps}

def format_output(state: BlackboardState):
    """
    Step 3: Format the structured output into the exact JSON array expected by the frontend.
    """
    final_board = state["final_board"]
    reverse_steps = state["reverse_steps"]
    
    # Create a lookup dictionary for all blocks
    blocks_lookup = {b.id: b.model_dump() for b in final_board.blocks}
    
    formatted_steps = []
    
    for step in reverse_steps.steps:
        board_state = []
        for vb in step.visible_blocks:
            if vb.block_id in blocks_lookup:
                # Copy the block data
                block_data = dict(blocks_lookup[vb.block_id])
                # Override highlight
                block_data["highlight"] = vb.highlight
                board_state.append(block_data)
                
        formatted_steps.append({
            "title": step.title,
            "note": step.note,
            "boardState": board_state
        })
        
    return {"final_output": formatted_steps}

# ============================================================================
# Graph Compilation
# ============================================================================

def create_blackboard_agent():
    workflow = StateGraph(BlackboardState)
    
    workflow.add_node("generate_final_board", generate_final_board)
    workflow.add_node("generate_steps_reverse", generate_steps_reverse)
    workflow.add_node("format_output", format_output)
    
    workflow.add_edge(START, "generate_final_board")
    workflow.add_edge("generate_final_board", "generate_steps_reverse")
    workflow.add_edge("generate_steps_reverse", "format_output")
    workflow.add_edge("format_output", END)
    
    return workflow.compile()

async def run_blackboard_agent(topic: str) -> List[Dict[str, Any]]:
    agent = create_blackboard_agent()
    initial_state = {"topic": topic}
    
    result = await agent.ainvoke(initial_state)
    return result["final_output"]
