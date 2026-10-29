"""Abre a demo do agente: python app.py → http://127.0.0.1:8000"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("interface.servidor:app", host="127.0.0.1", port=8000)
