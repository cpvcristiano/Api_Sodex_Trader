"""
Inicia o dashboard de trading.

  python run_dashboard.py

Acesse: http://localhost:8080
"""
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from dashboard.server import app

if __name__ == "__main__":
    print("=" * 50)
    print("  SODEX SCALPER — DASHBOARD")
    print("  http://localhost:8080")
    print("=" * 50)
    webbrowser.open("http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
