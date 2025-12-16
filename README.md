# geets-backend
Backend for Gits Messenger™.

## Installation and Startup
These instructions are written specifically for Linux-based systems. Some commands may be different for Windows.

1. Ensure you have the latest Python version installed on your machine.
2. Create the virtual environment:
```
python3 -m venv .venv
```
3. Activate the virtual environment:
```
source .venv/bin/activate
```
4. Install all of the dependencies:
```
pip install -r requirements.txt
```
5. (Optional) Set up environment variables in `.env`
6. Run the server:
```
fastapi dev app/main.py
```
