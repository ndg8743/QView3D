import os
from dotenv import load_dotenv, set_key

# Load the existing .env file. 
load_dotenv("server/.env")

local = "http://localhost:8000"
# Remote server running on 192.168.1.106 port 8000
remote = "http://192.168.1.106:8000"
current = os.getenv("BASE_URL")

#Check to see if the user wants to write to the db locally or remotely. Get flag from the user.

# Set the new BASE_URL
set_key("server/.env", "BASE_URL", remote)

print(f"BASE_URL updated to {remote}")

