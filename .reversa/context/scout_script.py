import os

def map_project(root_dir):
    exclude = {
        "node_modules", ".git", ".reversa", "_reversa_sdd", "dist", "build", 
        "coverage", "__pycache__", ".cache", ".claude", "venv", ".venv"
    }
    
    inventory = []
    stats = {
        "languages": {},
        "frameworks": [],
        "entry_points": [],
        "database_files": [],
        "test_files": []
    }
    
    for root, dirs, files in os.walk(root_dir):
        # Filter directories in-place to skip excluded ones
        dirs[:] = [d for d in dirs if d not in exclude]
        
        rel_path = os.path.relpath(root, root_dir)
        if rel_path == ".":
            rel_path = ""
            
        for file in files:
            file_path = os.path.join(rel_path, file)
            inventory.append(file_path)
            
            ext = os.path.splitext(file)[1].lower()
            if ext:
                stats["languages"][ext] = stats["languages"].get(ext, 0) + 1
            
            # Identify specific files
            f_lower = file.lower()
            if f_lower in ["main.py", "app.py", "server.py", "index.js", "run_bot.py", "run_dashboard.py"]:
                stats["entry_points"].append(file_path)
            
            if "requirements.txt" in f_lower or "package.json" in f_lower:
                stats["frameworks"].append(file_path)
            
            if any(term in f_lower for term in ["model", "schema", "db", "database", "sql", "migration"]):
                stats["database_files"].append(file_path)
                
            if any(term in f_lower for term in ["test", "spec"]):
                stats["test_files"].append(file_path)

    return inventory, stats

if __name__ == "__main__":
    root = r"c:\Users\Cristiano\Documents\Api_Sodex_Trader"
    inv, stats = map_project(root)
    
    print("INVENTORY:")
    for f in inv:
        print(f)
    print("\nSTATS:")
    import json
    print(json.dumps(stats, indent=2))
