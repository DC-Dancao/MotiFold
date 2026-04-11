import importlib


def test_research_tasks_module_imports() -> None:
    module = importlib.import_module("app.research.tasks")

    assert module.process_research.name == "process_research"
    assert module.process_research_loop.name == "process_research_loop"
    assert module.resume_research_task.name == "resume_research_task"
