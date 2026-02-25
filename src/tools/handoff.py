import json
from enum import Enum


class HandoffAction(str, Enum):
    DELEGATE = "delegate"
    CONSULT = "consult"


class DelegateToAgentTool:
    """
    A specialized system tool that allows an Agent to suspend its current generation
    and dynamically spin up a DIFFERENT Agent Model to answer a question or write code,
    before the original Agent continues.
    """

    name = "DelegateToAgent"
    description = (
        "Use this tool when you need to hand off a specific sub-task or question to "
        "another specialized AI agent. For instance, if you are the Orchestrator and "
        "need deep React styling help, delegate it to a Coder model.\n"
        "action: 'consult' if you want the answer returned to you to continue working, "
        "or 'delegate' if you want the other agent to finish the task directly."
    )
    parameters = {
        "type": "object",
        "properties": {
            "target_agent_id": {
                "type": "string",
                "description": "The explicit LiteLLM model string to spin up (e.g. 'openai/o3-mini', 'anthropic/claude-3-5-sonnet-20241022').",
            },
            "instruction": {
                "type": "string",
                "description": "The exact prompt/context you want the other agent to execute.",
            },
            "action": {
                "type": "string",
                "enum": ["delegate", "consult"],
                "description": "Whether to 'consult' (wait for the answer and resume) or 'delegate' (hand it off and exit).",
            },
            "attached_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Absolute paths of files to pass into the new agent's context window.",
            },
        },
        "required": ["target_agent_id", "instruction", "action"],
    }
    is_safe = True

    def _execute(self, **kwargs) -> str:
        # This tool is intercepted by the ChatPipeline/Orchestrator natively.
        # We return a specific JSON payload so the pipeline knows to suspend the thread
        # and trigger the Handoff.

        target = kwargs.get("target_agent_id", "openai/gpt-4o-mini")
        instruction = kwargs.get("instruction", "")
        action = kwargs.get("action", "consult")
        files = kwargs.get("attached_files", [])

        payload = {
            "__handoff_signal__": True,
            "target_agent_id": target,
            "instruction": instruction,
            "action": action,
            "files": files,
        }

        return json.dumps(payload)
