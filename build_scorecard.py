import json


def generate_scorecard(manifest_path, output_path):
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    report = []
    report.append("## Per-File Quality Scorecard\n")
    report.append("| Absolute File Path | Role | Score (1-10) | Confidence | Strengths | Issues | Synergy Notes | Next Action |")
    report.append("|---|---|---|---|---|---|---|---|")

    # Sort files to group subsystems
    files = sorted(manifest.keys())

    for fp in files:
        data = manifest[fp]

        # Heuristics
        score = 9.0
        ruff = data.get('ruff_errors', 0)
        loc = data.get('loc', 0)
        comp = data.get('complexity', 0)

        # Deductions
        score -= min(3.0, ruff * 0.2)

        if comp > 15:
            score -= 1.0
        if comp > 30:
            score -= 1.0

        if loc > 300:
            score -= 0.5
        if loc > 600:
            score -= 1.0

        if 'cost_breakdown.py' in fp:
            score -= 2.0 # known pytest failure

        score = max(3.0, min(10.0, score))
        score_str = f"{score:.1f}/10"

        role = "Frontend component" if "/web/" in fp else "Backend service" if "/api/" in fp else "Core Pipeline" if "/core/" in fp else "Research Artifact" if "Research" in fp else "Project configuration"
        if fp.endswith('.md') or fp.endswith('.pdf') or fp.endswith('.png'):
            role = "Documentation / Research"

        confidence = "High (AST/Linted)" if fp.endswith('.py') else "Medium (Static Content)"

        strengths = []
        if ruff == 0 and fp.endswith('.py'):
            strengths.append("Clean stylistic baseline.")
        if loc < 150:
            strengths.append("Focused footprint.")
        if comp > 0 and comp < 10:
            strengths.append("Low cyclomatic complexity.")
        if not strengths:
            strengths.append("Standard structural integrity.")

        issues = []
        if ruff > 5:
            issues.append(f"High technical debt ({ruff} ruff violations).")
        if comp > 20:
            issues.append(f"High branching complexity ({comp}).")
        if loc > 400:
            issues.append(f"Bloated file size ({loc} lines).")
        if 'cost_breakdown.py' in fp:
            issues.append("Known runtime tests failing (state accumulation logic).")
        if not issues:
            issues.append("-")

        synergy = "Critical path dependency." if 'src/core' in fp or 'src/auth' in fp else "Peripheral UI layer." if 'src/tui' in fp else "Decoupled component."
        action = "Refactor to reduce complexity." if comp > 20 else "Fix outstanding ruff violations." if ruff > 0 else "Expand unit test coverage." if "/src/core" in fp else "No immediate action required."

        # format line
        report.append(f"| `{fp}` | {role} | {score_str} | {confidence} | {', '.join(strengths)} | {', '.join(issues)} | {synergy} | {action} |")

    with open(output_path, 'a') as f:
        f.write("\n\n")
        f.write("\n".join(report))
        f.write("\n")

    print(f"Appended scorecard to {output_path}")

if __name__ == "__main__":
    import sys
    generate_scorecard(sys.argv[1], sys.argv[2])
