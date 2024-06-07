import os
from dotenv import load_dotenv, set_key

local = "http://localhost:8000"
remote = "https://my-remote-server.com"

# Load the existing .env file. 
load_dotenv("server/.env")

# Set the new BASE_URL
set_key("server/.env", "BASE_URL", local)

print(f"BASE_URL updated to {local}")

