import ast
import os


def analyze_directory(base_path, subdirs):
    report = {
        "files_scanned": 0,
        "total_lines": 0,
        "classes": 0,
        "functions": 0,
        "classes_missing_docstrings": 0,
        "functions_missing_docstrings": 0,
        "complex_functions": [], # > 15 branches
        "bare_excepts": [],
        "todo_comments": [],
    }

    for subdir in subdirs:
        search_path = os.path.join(base_path, subdir)
        if not os.path.exists(search_path):
            continue

        for root, _, files in os.walk(search_path):
            if '.venv' in root or '.git' in root or '__pycache__' in root or 'node_modules' in root:
                continue

            for file in files:
                if not file.endswith('.py'):
                    # Basic line count for non-py
                    if not file.endswith('.md'):
                        with open(os.path.join(root, file), 'r', errors='ignore') as f:
                            lines = f.readlines()
                            report["total_lines"] += len(lines)
                            report["files_scanned"] += 1
                        continue

                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.splitlines()
                        report["total_lines"] += len(lines)
                        report["files_scanned"] += 1

                        # Find TODOs
                        for i, line in enumerate(lines):
                            if 'TODO' in line or 'FIXME' in line:
                                report["todo_comments"].append(f"{os.path.relpath(filepath, base_path)}:{i+1}")

                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                report["classes"] += 1
                                if not ast.get_docstring(node):
                                    report["classes_missing_docstrings"] += 1
                            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                                report["functions"] += 1
                                if not ast.get_docstring(node):
                                    report["functions_missing_docstrings"] += 1

                                # Basic complexity check: count if/for/while
                                complexity = sum(1 for _ in ast.walk(node) if isinstance(_, (ast.If, ast.For, ast.While, ast.Try)))
                                if complexity > 10:
                                    report["complex_functions"].append(f"{os.path.relpath(filepath, base_path)}::{node.name} (Score: {complexity})")

                            # Check for bare excepts
                            elif isinstance(node, ast.ExceptHandler):
                                if node.type is None:
                                    report["bare_excepts"].append(f"{os.path.relpath(filepath, base_path)}:{node.lineno}")
                except Exception:
                    pass

    return report

if __name__ == "__main__":
    base = "/Users/michael/Documents/💻 Business/Vibe Code Files/gptcgt/Antigravity/gptcgt build/gptcgt"
    dirs_to_check = ["api", "docs", "proxy", "reports", "scripts", "src", "tests", "web"]
    data = analyze_directory(base, dirs_to_check)

    with open("comprehensive_audit_results.txt", "w") as f:
        f.write("=== COMPREHENSIVE CODEBASE AUDIT REPORTS ===\n\n")
        f.write(f"Total Files Scanned: {data['files_scanned']}\n")
        f.write(f"Total Lines of Code: {data['total_lines']}\n")
        f.write(f"Total Classes: {data['classes']} (Missing Docstrings: {data['classes_missing_docstrings']})\n")
        f.write(f"Total Functions: {data['functions']} (Missing Docstrings: {data['functions_missing_docstrings']})\n\n")

        f.write("=== BARE EXCEPTS FOUND (SECURITY SCORING) ===\n")
        for ex in data["bare_excepts"]:
            f.write(f" - {ex}\n")

        f.write("\n=== COMPLEX FUNCTIONS (>10 Branches) ===\n")
        for fn in sorted(data["complex_functions"], key=lambda x: int(x.split("Score: ")[1][:-1]), reverse=True):
            f.write(f" - {fn}\n")

        f.write("\n=== TODO / FIXME DEBT ===\n")
        for td in data["todo_comments"]:
            f.write(f" - {td}\n")

    print(f"Audit completed. Scanned {data['files_scanned']} files.")
