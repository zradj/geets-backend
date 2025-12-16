# geets-backend
Backend for Geets Messenger™.

## Installation and Startup
1. Ensure you have the latest Python version installed on your machine.
2. Create the virtual environment:
```bash
python3 -m venv .venv
```
3. Activate the virtual environment:

Linux:
```bash
source .venv/bin/activate
```

Windows PowerShell:
```powershell
.\.venv\Scripts\activate
```

4. Install all of the dependencies:
```bash
pip install -r requirements.txt
```
5. (Optional) Set up environment variables in `.env`
6. Run the server:
```bash
fastapi dev app/main.py
```
