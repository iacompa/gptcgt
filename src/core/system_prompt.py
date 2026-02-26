"""
System Prompt Builder.

Assembles the system prompt injected into the LLM context.
Aggregates the user's base identity rule, workspace status, phase.md context,
and any active instructions.
"""

from __future__ import annotations

from datetime import datetime

from src.core.config import ConfigManager
from src.core.phase_tracker import PhaseTracker
from src.core.workspace import Workspace


class SystemPromptBuilder:
    """Builds comprehensive system prompts for agents."""

    @staticmethod
    def build(
        role_type: str = "engineer",  # Only 'engineer' used for now, could be 'reviewer' etc
        custom_instructions: str = "",
        model_name: str | None = None,
    ) -> str:
        """
        Constructs the final system prompt.

        Args:
            role_type: The persona the agent should adopt.
            custom_instructions: Any temporary overriding instructions.
            model_name: The specific LLM ID or Agent ID (e.g., 'gpt-4o', 'orchestrator') to load custom memory.

        """
        prompt_parts = []

        # 1. Base Identity
        if role_type == "engineer":
            prompt_parts.append(
                "You are an expert AI software engineer pair-programming with the user.\n"
                "You prioritize clean, modular code, comprehensive error handling, and security.\n"
                "Always verify paths before reading/writing files, and follow the project's established conventions."  # noqa: E501
            )

        # 2. Configured Universal Rules (from ~/.gptcgt/config.toml)
        ConfigManager()
        # Universal rules are not yet a config field; this will be added when Settings supports custom system prompts  # noqa: E501
        # For now, skip this section

        # 3. Custom Instructions (e.g., from prompt/command overrides)
        if custom_instructions:
            prompt_parts.append(f"\n# Current Directives\n{custom_instructions}")

        # 4. Workspace Context
        try:
            ws = Workspace.get_instance()
            workspace_dir = ws.get_project_root()
            prompt_parts.append(f"\n# Workspace Context\nWorking Directory: {workspace_dir}")

            # Inject the User's explicit progress.md feature
            progress_path = ws.get_project_root() / "progress.md"
            if ws.safe_exists(progress_path):
                progress_content = ws.safe_read(progress_path)
                if progress_content:
                    prompt_parts.append("\n# Active Progress Tracker (`progress.md`)")
                    prompt_parts.append(
                        "The user has defined a `progress.md` file in the project root to track development."  # noqa: E501
                    )
                    prompt_parts.append(
                        "CRITICAL: You MUST use this as your source of truth. If the user marks an item as 'redo', 'not done', or adds notes, prioritize addressing them."  # noqa: E501
                    )
                    prompt_parts.append(
                        "As you complete tasks or shift focus, use your file editing tools to update `progress.md` natively (e.g., mark items [x] or change statuses) to keep the user informed."  # noqa: E501
                    )
                    prompt_parts.append("--- CURRENT PROGRESS STATE ---")
                    prompt_parts.append(progress_content[:2000])  # Truncate to avoid token bloat
                    prompt_parts.append("------------------------------")

            phase_tracker = PhaseTracker(ws)
            phase_tracker.ensure_loaded()
            phase_path = ws.get_project_root() / ".gptcgt" / "phase.md"
            if ws.safe_exists(phase_path):
                phase_content = ws.safe_read(phase_path)
                if phase_content:
                    prompt_parts.append("\n# Project Status (phase.md)")
                    prompt_parts.append(phase_content[:2000])  # Truncate to avoid token bloat
        except Exception:
            pass  # Workspace not initialized yet

        # 4.5. Project Context (Repo Map)
        try:
            ws = Workspace.get_instance()
            project_path = ws.get_project_root() / ".gptcgt" / "project.md"
            if ws.safe_exists(project_path):
                project_content = ws.safe_read(project_path)
                if project_content:
                    prompt_parts.append("\n# Project Context Map")
                    prompt_parts.append(project_content[:2000])
        except Exception:
            pass

        # 4.7. Agent Blackboard (shared inter-agent state)
        try:
            from src.core.blackboard import AgentBlackboard
            bb = AgentBlackboard.get_instance()
            bb_context = bb.to_context_string()
            if bb_context:
                prompt_parts.append(f"\n{bb_context}")
        except Exception:
            pass

        # 5. Temporal Awareness
        now = datetime.now()
        prompt_parts.append(f"\n# Temporal Context\nCurrent Time: {now.isoformat()}")

        # 6. Self-Reflective Compaction Memory (Friction-Driven)
        # Check if the specific instantiated agent has a memory record of past failures/lessons
        # We uniquely identify the "Orchestrator" vs "Arbiter" vs "gpt-4o" via their model_name
        identity = model_name if model_name else role_type
        memory_filename = identity.lower().replace(" ", "_") + ".md"
        try:
            ws = Workspace.get_instance()
            memory_path = ws.get_project_root() / ".gptcgt" / "agents" / memory_filename
            if ws.safe_exists(memory_path):
                memory_content = ws.safe_read(memory_path)
                if memory_content:
                    prompt_parts.append("\n<accumulated_learnings>")
                    prompt_parts.append(memory_content)
                    prompt_parts.append("</accumulated_learnings>")
                    prompt_parts.append(
                        "<directive>CRITICAL: You must adhere to these past learnings to avoid repeating previous mistakes in this codebase.</directive>"  # noqa: E501
                    )

                    # Phase 19: Transient UI memory injection indicators
                    from src.core.events import AgentStatusUpdate
                    try:
                        import textual.app as _tapp
                        current_app = _tapp.active_app.get()
                        current_app.post_message(AgentStatusUpdate(
                            agent_id="memory",
                            model_name=identity,
                            status="thinking",
                            detail=f"Reading memory from {memory_filename}..."
                        ))
                    except Exception:
                        pass
        except Exception:
            pass

        return "\n".join(prompt_parts)
