from pydantic import BaseModel, Field, ConfigDict, AliasChoices
from typing import Optional

class File(BaseModel):
    path: str = Field(description="The path to the file to be created or modified")
    purpose: str = Field(
        description="The purpose of the file, e.g. 'main application logic', 'data processing module', etc.")


class Plan(BaseModel):
    name: str = Field(description="The name of app to be built")
    description: str = Field(
        description="A oneline description of the app to be built, e.g. 'A web application for managing personal finances'")
    techstack: str = Field(
        description="The tech stack to be used for the app, e.g. 'python', 'javascript', 'react', 'flask', etc.")
    features: list[str] = Field(
        description="A list of features that the app should have, e.g. 'user authentication', 'data visualization', etc.")
    files: list[File] = Field(description="A list of files to be created, each with a 'path' and 'purpose'")

class ImplementationTask(BaseModel):
    file_path: str = Field(description="The path to the file to be modified",validation_alias=AliasChoices("file_path", "file", "filepath"))
    task_description: str = Field(description="A detailed description of the task to be performed on the file, e.g. 'add user authentication', 'implement data processing logic', etc.",validation_alias=AliasChoices("task_description", "description"))
    model_config = ConfigDict(extra="allow", populate_by_name=True)

class TaskPlan(BaseModel):
    tasks: list[ImplementationTask] = Field(description="A list of steps to be taken to implement the task",validation_alias=AliasChoices("tasks", "implementation_steps"))
    model_config = ConfigDict(extra="allow", populate_by_name=True)     #for extra variables/elements to be allowed

class CoderState(BaseModel):
    task_plan: TaskPlan = Field(description="The plan for the task to be implemented")
    current_step_idx: int = Field(0, description="The index of the current step in the implementation steps")
    current_file_content: Optional[str] = Field(None, description="The content of the file currently being edited or created")