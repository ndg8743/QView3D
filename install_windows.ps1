# Install Chocolatey
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

# Install Python and pip
choco install python -y

# Refresh environment variables
refreshenv

# Install Node.js and npm
choco install nodejs -y

# Refresh environment variables
refreshenv

# Install nvm-windows
choco install nvm -y

# Refresh environment variables
refreshenv

# Install the required version of Node.js using nvm
nvm install latest

# Install Python dependencies. Requirements was created with pipreqs.
pip install -r requirements.txt 

# Change directory to the server.
cd server

# Initialize the database. 
flask db init 

# Generate a migration script. 
flask db migrate 

# Apply the migration. 
flask db upgrade 

# Change directory to the client.
cd ../client

# Install Node.js dependencies.
npm install

# Install npm-run-all as a dev dependency
npm install --save-dev npm-run-all