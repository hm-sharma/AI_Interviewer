import subprocess
import sys
import time
import os
import signal

def run_services():
    print("=" * 60)
    print("AI-Based Adaptive Interviewer System Booster")
    print("=" * 60)
    
    # Check dependencies
    missing_deps = []
    for dep, name in [
        ("uvicorn", "uvicorn"),
        ("streamlit", "streamlit"),
        ("fastapi", "fastapi"),
        ("sqlalchemy", "sqlalchemy"),
        ("fitz", "pymupdf"),
        ("faiss", "faiss-cpu")
    ]:
        try:
            __import__(dep)
        except ImportError:
            missing_deps.append(name)
            
    if missing_deps:
        print(f"[ERROR] Missing required packages: {', '.join(missing_deps)}")
        print(f"Please install dependencies for this Python version ({sys.executable}) by running:")
        print(f"  \"{sys.executable}\" -m pip install -r backend/requirements.txt -r frontend/requirements.txt")
        return
        
    # Check current directory
    print(f"Current Directory: {os.getcwd()}")
    
    # Command to launch backend
    backend_cmd = [
        sys.executable, "-m", "uvicorn", "backend.app.main:app",
        "--host", "127.0.0.1", "--port", "8000"
    ]
    
    # Command to launch frontend
    frontend_cmd = [
        sys.executable, "-m", "streamlit", "run", "frontend/app.py",
        "--server.port", "8501", "--server.address", "127.0.0.1"
    ]
    
    processes = []
    try:
        # Start backend
        print("\n[1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...")
        backend_proc = subprocess.Popen(
            backend_cmd
        )
        processes.append(backend_proc)
        
        # Give backend a moment to start
        print("Waiting for backend to initialize database and setup API routes...")
        time.sleep(3)
        
        # Check if backend started successfully
        if backend_proc.poll() is not None:
            print("[ERROR] Backend failed to start. Please check the logs printed above.")
            return
            
        print("[OK] Backend service is running.")
        
        # Start frontend
        print("\n[2/2] Starting Streamlit Frontend on http://127.0.0.1:8501 ...")
        frontend_proc = subprocess.Popen(
            frontend_cmd
        )
        processes.append(frontend_proc)
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Both services are running successfully!")
        print("  - Backend URL: http://127.0.0.1:8000")
        print("  - Frontend URL: http://127.0.0.1:8501")
        print("Press Ctrl+C to terminate both services.")
        print("=" * 60 + "\n")
        
        # Monitor processes and forward logs
        while True:
            # We check if any process has exited
            for proc in processes:
                if proc.poll() is not None:
                    print(f"\n[WARNING] One of the processes exited prematurely (code {proc.poll()}). Shutting down...")
                    raise KeyboardInterrupt
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nShutting down services, cleaning up processes...")
        for proc in processes:
            try:
                # On Windows, taskkill is more robust if standard terminate doesn't work
                if os.name == 'nt':
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    proc.terminate()
                    proc.wait(timeout=2)
            except Exception:
                pass
        print("Services successfully terminated. Goodbye!")

if __name__ == "__main__":
    run_services()
