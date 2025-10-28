from db import criar_tabelas, criar_admin, get_db
import sqlite3

def inicializar_dados():
    criar_tabelas()
    criar_admin()

    db = get_db()

    categorias = [
        "Motor", "Suspensão", "Transmissão", "Freios", "Pneus",
        "Elétrica Automotiva", "Lubrificantes e Aditivos", "Sistema de Combustível"
    ]

    for c in categorias:
        try:
            db.execute("INSERT INTO categorias (nome) VALUES (?)", (c,))
        except sqlite3.IntegrityError:
            pass  # já existe

    produtos_iniciais = [
        {"nome": "Pneu 205X70 R15 - FALKEN 425038", "descricao": "Pneu resistente e durável", "preco": 689.00, "preco_pix": 620.00, "categoria": "Pneus", "estoque": 10, "estoque_minimo": 2, "imagem": "pneu1.jpg"},
        {"nome": "Filtro de Óleo Bosch", "descricao": "Filtro de alta performance", "preco": 39.90, "preco_pix": 37.90, "categoria": "Motor", "estoque": 25, "estoque_minimo": 5, "imagem": "filtro1.jpg"},
    ]

    categorias_dict = {row["nome"]: row["id"] for row in db.execute("SELECT * FROM categorias").fetchall()}

    for p in produtos_iniciais:
        cat_id = categorias_dict.get(p["categoria"])
        if cat_id:
            existente = db.execute("SELECT * FROM produtos WHERE nome = ?", (p["nome"],)).fetchone()
            if not existente:
                db.execute('''
                    INSERT INTO produtos (nome, descricao, preco, preco_pix, categoria_id, estoque, estoque_minimo, imagem)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (p["nome"], p["descricao"], p["preco"], p["preco_pix"], cat_id, p["estoque"], p["estoque_minimo"], p["imagem"]))

    db.commit()
    db.close()
    print("✅ Banco inicializado com categorias, produtos e admin.")


if __name__ == "__main__":
    inicializar_dados()
