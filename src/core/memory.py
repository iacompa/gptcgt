import os
from pathlib import Path

def init_gptcgt_workspace(project_root: Path) -> None:
    """Initialize the .gptcgt directory structure for a project."""
    gptcgt_dir = project_root / ".gptcgt"
    gptcgt_dir.mkdir(exist_ok=True)
    
    (gptcgt_dir / "agents").mkdir(exist_ok=True)
    # NEW: create sessions directory
    (gptcgt_dir / "sessions").mkdir(exist_ok=True)
    
    # Touch placeholder files
    for f in ["project.md", "routing.json", "history.md", "config.toml", "repo-map.json"]:
        (gptcgt_dir / f).touch(exist_ok=True)
        
    for f in ["claude.md", "gemini.md", "gpt.md"]:
        (gptcgt_dir / "agents" / f).touch(exist_ok=True)
