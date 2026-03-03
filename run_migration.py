from src.core.config import ConfigManager

cm = ConfigManager()
print("Before:", getattr(cm.user, "visible_panels", {}))

# Force reset layout
cm.user.visible_panels = {"files": True, "code": True, "chat": True}
cm.user.panel_sizes = {"files": 0.2, "code": 0.6, "chat": 0.2}
cm.user.panel_positions = {"files": "left", "code": "center", "chat": "right"}
cm._save_global()

print("After:", getattr(cm.user, "visible_panels", {}))
