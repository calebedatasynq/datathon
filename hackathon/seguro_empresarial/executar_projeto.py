"""Reproduz preparação, diagnóstico, testes, relatório e notebook."""
import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR','/tmp/hackathon-matplotlib')
comandos=[
 [sys.executable,str(root/'src/preparar_base.py'),'--origem',str(root/'dados/originais'),'--saida',str(root/'dados/preparados')],
 [sys.executable,str(root/'src/analisar.py')],
 [sys.executable,str(root/'src/treinar.py')],
 [sys.executable,str(root/'tests/test_integridade.py')],
 [sys.executable,str(root/'src/gerar_entrega.py')],
]
for comando in comandos:subprocess.run(comando,cwd=root,check=True)
