"""Agent factory: creates a configured Strands Agent with tools and system prompt."""
import sqlite3
from strands import Agent
from strands.models.bedrock import BedrockModel
from diary.config import DiaryConfig
from diary.service.tasks import TaskService
from diary.service.activity_log import ActivityLogService
from diary.service.tags import TagService
from diary.service.summary import SummaryService
from diary.agent.tools import make_tools

SYSTEM_PROMPT = """\
You are Diary, a concise task management assistant. You help the user manage their daily tasks.

## Rules

1. Before any mutation (create, update, archive, unarchive, log entry), present exactly what you will do and wait for explicit confirmation.
2. When creating or updating a task, ask about every optional field the user hasn't mentioned: description, priority, tags, due_date, scheduled_date. Suggest values where you can infer them.
3. Before suggesting tags, call list_tags to see existing tags and suggest relevant ones.
4. Accept free-form responses — the user may clarify, correct, or add context instead of just yes/no.
5. Keep responses short. No fluff.
6. When the user shares context worth saving, proactively ask "Should I save this to the task's activity log?"
7. If you save context to a task, use add_log_entry (it records source=ai automatically).
8. You CANNOT delete or edit activity log entries. Only the TUI can do that.
9. Use scheduled_date="none" to move a task to backlog (clears the date).
10. Use due_date="none" to clear a due date.
11. Do NOT use markdown formatting (no **, no #, no ```). This is a plain terminal. Use plain text only.
12. When writing descriptions, use bullet points on separate lines. Keep each point short. Example:
  "- parameterize tests\n- add fixtures\n- reduce duplication"
"""


def create_agent(conn: sqlite3.Connection, config: DiaryConfig | None = None) -> Agent:
    """Create a Strands Agent wired to the service layer via the given DB connection."""
    if config is None:
        config = DiaryConfig()

    task_svc = TaskService(conn)
    log_svc = ActivityLogService(conn)
    tag_svc = TagService(conn)
    summary_svc = SummaryService(conn)

    tools = make_tools(task_svc, log_svc, tag_svc, summary_svc)
    tool_list = list(tools.values())

    import boto3
    boto_session = boto3.Session(
        profile_name=config.aws_profile,
        region_name=config.aws_region,
    )
    model = BedrockModel(model_id=config.ai_model, boto_session=boto_session)

    return Agent(
        model=model,
        tools=tool_list,
        system_prompt=SYSTEM_PROMPT,
    )
