from db import criar_tabelas, criar_admin

def inicializar_dados():
    criar_tabelas()
    criar_admin()
    print("✅ Banco inicializado (somente tabelas e admin).")

if __name__ == "__main__":
    inicializar_dados()
