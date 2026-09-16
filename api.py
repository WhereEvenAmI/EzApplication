"""
FastAPI wrapper around the LangGraph app builder.
Run from the app_builder folder:  uvicorn api:app --reload --port 8000
"""
import pathlib
import threading
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.graph import agent

app = FastAPI()

# Lets the Next.js page (localhost:3000) talk to this API (localhost:8000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = pathlib.Path.cwd() / "generated_project"

# job_id -> progress. In-memory is fine for a demo.
jobs: dict = {}


class GenerateRequest(BaseModel):
    prompt: str


def run_job(job_id: str, prompt: str) -> None:
    job = jobs[job_id]
    try:
        # .stream() yields {node_name: state_update} after each node finishes
        for chunk in agent.stream(
            {"user_prompt": prompt},
            {"recursion_limit": 100},
        ):
            for node_name, node_out in chunk.items():
                if node_name == "planner":
                    plan = node_out.get("plan")
                    if plan is not None:
                        job["plan"] = {
                            "name": plan.name,
                            "description": plan.description,
                            "techstack": plan.techstack,
                            "features": plan.features,
                        }
                    job["steps"]["planner"] = "done"
                    job["steps"]["architect"] = "running"

                elif node_name == "architect":
                    task_plan = node_out.get("task_plan")
                    if task_plan is not None:
                        job["tasks"] = [
                            {"file": t.file_path, "task": t.task_description}
                            for t in task_plan.tasks
                        ]
                        job["total_steps"] = len(task_plan.tasks)
                    job["steps"]["architect"] = "done"
                    job["steps"]["coder"] = "running"

                elif node_name == "coder":
                    coder_state = node_out.get("coder_state")
                    if coder_state is not None:
                        job["done_steps"] = coder_state.current_step_idx
                    job["files"] = list_generated_files()

        job["steps"]["coder"] = "done"
        job["files"] = list_generated_files()
        job["status"] = "done"

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


def list_generated_files() -> list:
    if not PROJECT_ROOT.exists():
        return []
    return sorted(
        str(f.relative_to(PROJECT_ROOT)).replace("\\", "/")
        for f in PROJECT_ROOT.glob("**/*")
        if f.is_file()
    )


@app.post("/generate")
def generate(req: GenerateRequest):
    """Kick off a build. Returns immediately with a job id."""
    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {
        "status": "running",
        "steps": {"planner": "running", "architect": "pending", "coder": "pending"},
        "plan": None,
        "tasks": [],
        "files": [],
        "done_steps": 0,
        "total_steps": 0,
        "error": None,
    }
    threading.Thread(target=run_job, args=(job_id, req.prompt), daemon=True).start()
    return {"job_id": job_id}


@app.get("/status/{job_id}")
def status(job_id: str):
    """The frontend polls this every 1.5s."""
    return jobs.get(job_id, {"status": "not_found"})


@app.get("/file")
def file_content(path: str):
    """Read one generated file so the UI can show the code."""
    p = (PROJECT_ROOT / path).resolve()
    if PROJECT_ROOT.resolve() not in p.parents and PROJECT_ROOT.resolve() != p.parent:
        return {"content": "", "error": "outside project root"}
    if not p.exists() or p.is_dir():
        return {"content": "", "error": "not found"}
    return {"content": p.read_text(encoding="utf-8", errors="replace")}
