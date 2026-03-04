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

        # Budget allocations (approx 1 token = 4 chars)
        # We want to keep injected context under ~16,000 chars (4000 tokens)
        MAX_INJECTED_CHARS = 16000
        budget_remaining = MAX_INJECTED_CHARS

        # 1. Base Identity
        if role_type == "engineer":
            prompt_parts.append(
                "You are an expert AI software engineer pair-programming with the user.\n"
                "You prioritize clean, modular code, comprehensive error handling, and security.\n"
                "Always verify paths before reading/writing files, and follow the project's established conventions."  # noqa: E501
            )

        # 2. Configured Universal Rules (from ~/.gptcgt/config.toml)
        ConfigManager.get_instance()

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
            if ws.safe_exists(progress_path) and budget_remaining > 0:
                progress_content = ws.safe_read(progress_path)
                if progress_content:
                    alloc = min(len(progress_content), 4000)
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
                    prompt_parts.append(progress_content[:alloc])  # Truncate to budget
                    prompt_parts.append("------------------------------")
                    budget_remaining -= alloc

            phase_tracker = PhaseTracker(ws)
            phase_tracker.ensure_loaded()
            phase_path = ws.get_project_root() / ".gptcgt" / "phase.md"
            if ws.safe_exists(phase_path) and budget_remaining > 0:
                phase_content = ws.safe_read(phase_path)
                if phase_content:
                    alloc = min(len(phase_content), 3000, budget_remaining)
                    prompt_parts.append("\n# Project Status (phase.md)")
                    prompt_parts.append(phase_content[:alloc])
                    budget_remaining -= alloc
        except Exception:
            pass  # Workspace not initialized yet

        # 4.5. Project Context (Repo Map)
        try:
            ws = Workspace.get_instance()
            project_path = ws.get_project_root() / ".gptcgt" / "project.md"
            if ws.safe_exists(project_path) and budget_remaining > 0:
                project_content = ws.safe_read(project_path)
                if project_content:
                    alloc = min(len(project_content), 3000, budget_remaining)
                    prompt_parts.append("\n# Project Context Map")
                    prompt_parts.append(project_content[:alloc])
                    budget_remaining -= alloc
        except Exception:
            pass

        # 4.7. Agent Blackboard (shared inter-agent state)
        try:
            from src.core.blackboard import AgentBlackboard
            bb = AgentBlackboard.get_instance()
            bb_context = bb.to_context_string()
            if bb_context and budget_remaining > 0:
                alloc = min(len(bb_context), 4000, budget_remaining)
                prompt_parts.append(f"\n{bb_context[:alloc]}")
                budget_remaining -= alloc
        except Exception:
            pass

        # 5. Temporal Awareness
        now = datetime.now()
        prompt_parts.append(f"\n# Temporal Context\nCurrent Time: {now.isoformat()}")

        # 6. Vector Memory (Self-Reflective Compaction Memory)
        try:
            ws = Workspace.get_instance()
            memory_path = ws.get_project_root() / ".gptcgt" / "memory.json"
            if ws.safe_exists(memory_path):
                import json
                try:
                    memory_data = json.loads(ws.safe_read(memory_path))
                except Exception:
                    memory_data = []

                if memory_data:
                    # Let's see if we have a task brief to search against
                    search_query = custom_instructions or "general programming task"
                    try:
                        from src.core.blackboard import AgentBlackboard
                        bb = AgentBlackboard.get_instance()
                        tb = bb.read("task_brief")
                        if tb and hasattr(tb, "user_request"):
                            search_query = tb.user_request
                    except Exception as e:
                        from src.core.logger import get_logger
                        get_logger("core.system_prompt").warning(f"Failed to read task brief for memory: {e}")

                    # Calculate query embedding via synchronous litellm
                    import os  # noqa: F401

                    import litellm

                    from src.agents.factory import PROVIDER_KEY_MAP
                    from src.auth.keychain import KeyChainManager

                    emb_query = None
                    provider = "openai"  # default
                    k_name = PROVIDER_KEY_MAP.get(provider)
                    api_key = KeyChainManager.get_key(k_name) if k_name else None
                    
                    if not api_key:
                        provider = "google"
                        k_name = PROVIDER_KEY_MAP.get(provider)
                        api_key = KeyChainManager.get_key(k_name) if k_name else None

                    if api_key:
                        emb_model = "text-embedding-3-small" if provider == "openai" else "gemini/text-embedding-004"
                        try:
                            if provider == "openai":
                                os.environ["OPENAI_API_KEY"] = api_key
                            elif provider == "google":
                                os.environ["GEMINI_API_KEY"] = api_key
                            
                            emb_res = litellm.embedding(
                                model=emb_model,
                                input=[search_query],
                            )
                            emb_query = emb_res.data[0]['embedding']
                        except Exception:
                            pass

                    # Retrieve top 3 lessons
                    top_lessons = []
                    if emb_query:
                        def _cosine_sim(v1, v2):
                            dot = sum(a * b for a, b in zip(v1, v2))
                            mag1 = sum(a * a for a in v1) ** 0.5
                            mag2 = sum(b * b for b in v2) ** 0.5
                            return dot / (mag1 * mag2) if mag1 and mag2 else 0.0

                        scored_lessons = []
                        for m in memory_data:
                            if m.get('type') == 'telemetry':
                                continue
                            lesson_emb = m.get('embedding')
                            if not lesson_emb:
                                continue
                            score = _cosine_sim(emb_query, lesson_emb)
                            scored_lessons.append((score, m))

                        scored_lessons.sort(key=lambda x: x[0], reverse=True)
                        top_lessons = [m for _, m in scored_lessons[:3]]
                        
                        if not top_lessons:
                            # Fallback: Just take the 3 most recent non-telemetry if embedding loop yielded nothing
                            top_lessons = [m for m in memory_data if m.get('type') != 'telemetry'][-3:]
                    else:
                        # Fallback: Just take the 3 most recent
                        top_lessons = [m for m in memory_data if m.get('type') != 'telemetry'][-3:]

                    if top_lessons:
                        prompt_parts.append("\n<accumulated_learnings>")
                        for l in top_lessons:  # noqa: E741
                            lesson = l.get("lesson") or l.get("action_taken") or ""
                            trigger = l.get("trigger") or l.get("failure_mode") or "unknown"
                            if lesson:
                                prompt_parts.append(f"- RULE: {lesson} (Context: {trigger})")
                        prompt_parts.append("</accumulated_learnings>")
                        prompt_parts.append(
                            "<directive>CRITICAL: You must adhere to these past learnings to avoid repeating previous mistakes in this codebase.</directive>"  # noqa: E501
                        )

                        # Transient UI memory injection indicators
                        from src.core.events import AgentStatusUpdate
                        identity = model_name if model_name else role_type
                        try:
                            import textual.app as _tapp
                            current_app = _tapp.active_app.get()
                            current_app.post_message(AgentStatusUpdate(
                                agent_id="memory",
                                model_name=identity,
                                status="thinking",
                                detail=f"Injected {len(top_lessons)} vector memories."
                            ))
                        except Exception:
                            pass
        except Exception:
            pass

        return "\n".join(prompt_parts)
