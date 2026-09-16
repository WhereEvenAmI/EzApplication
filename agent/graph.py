import sys, os
sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()
from langchain_core.globals import set_debug, set_verbose

from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from prompts import *
from states import *
from langgraph.constants import END
from langgraph.graph import StateGraph
from agent.tools import write_file, read_file, get_current_directory, list_files
from langgraph.prebuilt import create_react_agent

set_debug(True)            #gives hints of functioning in the output window too
set_verbose(True)

#llm = ChatGroq(model="llama-3.1-8b-instant")   very small model to handle this
#llm = ChatGroq(model="llama-3.3-70b-versatile")   #generated very basic calculator without css
#llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")   #emptying credits
#llm = ChatGroq(model="deepseek-r1-distill-llama-70b")
llm = ChatGroq(model="openai/gpt-oss-120b")

def planner_agent(state: dict) -> dict:
    """Converts user prompt into a structured Plan."""
    user_prompt = state["user_prompt"]
    resp = llm.with_structured_output(Plan).invoke(
        planner_prompt(user_prompt)
    )
    if resp is None:
        raise ValueError("Planner did not return a valid response.")
    return {"plan": resp}


def architect_agent(state: dict) -> dict:
    plan: Plan = state["plan"]
    resp = llm.with_structured_output(TaskPlan, method="json_mode").invoke(architect_prompt(plan))
    if resp is None:
        raise ValueError("Architect did not return a valid response.")
    return {"task_plan": resp}

def coder_agent(state: dict) -> dict:
    coder_state: CoderState = state.get("coder_state")
    if coder_state is None:
        coder_state = CoderState(task_plan=state["task_plan"], current_step_idx=0)

    steps = coder_state.task_plan.tasks
    if coder_state.current_step_idx >= len(steps):
        return {"coder_state": coder_state, "status": "DONE"}

    current_task = steps[coder_state.current_step_idx]
    existing_content = read_file.run(current_task.file_path)

    user_prompt = (
        f"Task: {current_task.task_description}\n"
        f"File: {current_task.file_path}\n"
        f"Existing content:\n{existing_content}\n"
        "Use write_file(path, content) to save your changes."
    )
    system_prompt = coder_system_prompt()


    system_prompt = coder_system_prompt()

    coder_tools = [read_file, write_file, get_current_directory, list_files]

    react_agent = create_react_agent(llm, coder_tools)
    react_agent.invoke({"messages": [{"role": "system", "content": system_prompt},
                                     {"role": "user", "content": user_prompt}]})
    coder_state.current_step_idx += 1
    return {"coder_state": coder_state}

graph=StateGraph(dict)

graph.add_node("planner",planner_agent)
graph.add_node("architect",architect_agent)
graph.add_node("coder", coder_agent)

graph.add_edge("planner","architect")
graph.add_edge("architect", "coder")
graph.add_conditional_edges(
    "coder",
    lambda s: "END" if s.get("status") == "DONE" else "coder",
    {"END": END, "coder": "coder"}
)
graph.set_entry_point("planner")

agent=graph.compile()

user_prompt="Create a simple calculator web app"

if __name__ == "__main__":
    result = agent.invoke({"user_prompt": user_prompt},
                          {"recursion_limit": 100})
    print(result)
