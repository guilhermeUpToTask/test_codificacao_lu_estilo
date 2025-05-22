#!/bin/bash

# FastAPI Project Setup Script

# Variables
PROJECT_NAME="task_maneger_fastapi"
VENV_NAME="venv"
PYTHON_VERSION="3.12.3"

# Function to display error messages and exit
error_exit() {
    echo "$1" 1>&2
    exit 1
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    error_exit "Python3 is not installed. Please install Python3 and try again."
fi

# Create project directory
echo "Creating project directory: $PROJECT_NAME"
mkdir -p "$PROJECT_NAME" || error_exit "Failed to create project directory."
cd "$PROJECT_NAME" || error_exit "Failed to enter project directory."

# Create folder structure
echo "Creating folder structure..."
mkdir -p app/{api/v1/endpoints,core,models,schemas,services,db,utils,tests} \
         migrations static templates requirements \
         || error_exit "Failed to create folder structure."

# Create empty __init__.py files to make folders Python packages
find app -type d -exec touch {}/__init__.py \;

# Create main.py
echo "Creating app/main.py..."
cat <<EOL > app/main.py
from fastapi import FastAPI
from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOL

# Create config.py
echo "Creating app/core/config.py..."
cat <<EOL > app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "$PROJECT_NAME"
    API_V1_STR: str = "/api/v1"

    class Config:
        env_file = ".env"

settings = Settings()
EOL

# Create router.py
echo "Creating app/api/v1/router.py..."
cat <<EOL > app/api/v1/router.py
from fastapi import APIRouter

api_router = APIRouter()

# Import and include your endpoints here
# Example:
# from app.api.v1.endpoints.users import router as users_router
# api_router.include_router(users_router, prefix="/users", tags=["users"])
EOL


# Create .env file
echo "Creating .env file..."
cat <<EOL > .env
# FastAPI Configuration
PROJECT_NAME="$PROJECT_NAME"
EOL


# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv "$VENV_NAME" || error_exit "Failed to create virtual environment."

# Activate virtual environment and install dependencies
echo "Activating virtual environment and installing dependencies..."
source "$VENV_NAME/bin/activate" || error_exit "Failed to activate virtual environment."
pip install --upgrade pip || error_exit "Failed to upgrade pip."
pip install -r requirements/base.txt || error_exit "Failed to install dependencies."

# Success message
echo ""
echo "FastAPI project setup complete!"
echo "To start the application:"
echo "1. Activate the virtual environment: source $VENV_NAME/bin/activate"
echo "2. Run the app: uvicorn app.main:app --reload"
echo "3. Open your browser and go to http://localhost:8000/docs"
echo ""