#!/usr/bin/env python3
"""
Reset the circuit breaker by restarting the main.py process
"""
import subprocess
import time
import signal
import os

def find_and_kill_main_process():
    """Find and kill the running main.py process"""
    try:
        # Get existing process
        result = subprocess.run(['pgrep', '-f', 'python.*main.py'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"🔍 Found running processes: {pids}")
            
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"🔄 Sent SIGTERM to process {pid}")
                except Exception as e:
                    print(f"⚠️ Could not kill process {pid}: {e}")
            
            time.sleep(3)  # Wait for graceful shutdown
            
            # Force kill if still running
            for pid in pids:
                try:
                    os.kill(int(pid), 0)  # Check if still running
                    os.kill(int(pid), signal.SIGKILL)
                    print(f"🔨 Force killed process {pid}")
                except OSError:
                    pass  # Process is already dead
                    
            return True
        else:
            print("ℹ️ No running main.py process found")
            return False
            
    except Exception as e:
        print(f"❌ Error finding/killing process: {e}")
        return False

def start_backend():
    """Start the backend server"""
    try:
        print("🚀 Starting backend server...")
        os.chdir('/home/aparna/Desktop/IG_realestate/backend')
        
        # Start the process in background
        subprocess.Popen(['python3', 'main.py'], 
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        
        # Wait for startup
        print("⏳ Waiting for server to start...")
        time.sleep(10)
        
        # Test health endpoint
        import requests
        response = requests.get('http://localhost:8000/api/health', timeout=5)
        if response.status_code == 200:
            print("✅ Backend server started successfully")
            return True
        else:
            print(f"❌ Backend health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error starting backend: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Circuit Breaker Reset Tool")
    print("="*40)
    
    killed = find_and_kill_main_process()
    time.sleep(2)
    
    started = start_backend()
    
    if started:
        print("\n✅ Circuit breaker reset complete!")
        print("🎯 The backend has been restarted and should now work properly.")
    else:
        print("\n❌ Failed to restart backend")
        print("🔧 You may need to manually restart: cd backend && python3 main.py")
