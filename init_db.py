from db import criar_tabelas, criar_admin, atualizar_tabela_pedidos

def inicializar_dados():
    criar_tabelas()
    atualizar_tabela_pedidos()
    criar_admin()
    print("✅ Banco inicializado (somente tabelas e admin).")

if __name__ == "__main__":
    inicializar_dados()
