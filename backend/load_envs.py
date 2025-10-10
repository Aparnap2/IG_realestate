from dotenv import load_dotenv
import os

def load_envs():
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

load_envs()
