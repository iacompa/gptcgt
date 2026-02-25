import ast
import json
import os
import subprocess


def get_python_files(root_dirs):
    files = []
    excludes = ['.git', '.venv', 'node_modules', '.next', '.pytest_cache', '.ruff_cache', '__pycache__', '.DS_Store']
    excluded_exts = ['.pyc', '.pyo']
    for root_dir in root_dirs:
        for root, dirs, filenames in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in excludes]
            for f in filenames:
                if f == '.DS_Store' or any(f.endswith(ext) for ext in excluded_exts):
                    continue
                files.append(os.path.join(root, f))
    return files

def calculate_complexity(node):
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.With, ast.AsyncWith, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity

def analyze_python_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            loc = len(lines)

        try:
            tree = ast.parse(content)
            comp = calculate_complexity(tree)
            funcs = len([n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))])
            classes = len([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)])
        except SyntaxError:
            comp, funcs, classes = -1, -1, -1

        return {'loc': loc, 'complexity': comp, 'functions': funcs, 'classes': classes, 'type': 'python'}
    except Exception as e:
        return {'error': str(e)}

def run_ruff(dirs):
    try:
        res = subprocess.run(['ruff', 'check', '--output-format', 'json'] + dirs, capture_output=True, text=True)
        # Ruff returns non-zero if it finds issues, which is expected
        return json.loads(res.stdout) if res.stdout else []
    except Exception as e:
        print(f"Ruff failed: {e}")
        return []

def main():
    root_ws = "/Users/michael/Documents/💻 Business/Vibe Code Files/gptcgt"
    audit_dirs = [
        f"{root_ws}/Antigravity/gptcgt build",
        f"{root_ws}/gptcgt Research"
    ]

    files = get_python_files(audit_dirs)
    print(f"Discovered {len(files)} target files.")

    ruff_issues = run_ruff([audit_dirs[0]]) # Only run ruff on the codebase
    issues_by_file = {}
    for issue in ruff_issues:
        fp = issue.get("filename")
        if fp not in issues_by_file:
            issues_by_file[fp] = 0
        issues_by_file[fp] += 1

    results = {}
    for f in files:
        if f.endswith('.py'):
            stats = analyze_python_file(f)
            stats['ruff_errors'] = issues_by_file.get(f, 0)
        else:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    stats = {'loc': len(file.readlines()), 'type': f.split('.')[-1]}
            except Exception:
                stats = {'loc': 0, 'type': 'binary/unknown'}
        results[f] = stats

    out_file = "/Users/michael/Documents/💻 Business/Vibe Code Files/gptcgt/Antigravity/gptcgt build/gptcgt/audit_manifest.json"
    with open(out_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Manifest written to {out_file}")

if __name__ == "__main__":
    main()
