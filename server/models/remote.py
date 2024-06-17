import os
import socket
from dotenv import load_dotenv, set_key

# Load the existing .env file. 
load_dotenv("server/.env")

# Get the current BASE_URL for this machine, find the IP address.
local_ip = socket.gethostbyname(socket.gethostname())

# Add port 8000 to the IP address
local_ip_with_port = local_ip + ":8000"

local = "http://localhost:8000"
# Remote server running on 192.168.1.106 port 8000
remote = "http://" + local_ip_with_port
current = os.getenv("BASE_URL")

#Check to see if the user wants to write to the db locally or remotely. Get flag from the user.

# Set the new BASE_URL
set_key("server/.env", "BASE_URL", remote)

print(f"BASE_URL updated to {remote}")