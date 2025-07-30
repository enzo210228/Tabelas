import subprocess
import os

# Caminho completo do Python que você quer usar
python_path = r"C:\Users\enzo.pinheiro\AppData\Local\Programs\Python\Python312\python.exe"

# Caminho completo para o arquivo Streamlit
app_path = os.path.join(os.getcwd(), "atabelas.py")

# Comando para executar
cmd = [python_path, "-m", "streamlit", "run", app_path]

# Executar o Streamlit
subprocess.Popen(cmd, cwd=os.getcwd())
