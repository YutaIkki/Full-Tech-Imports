import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

DATABASE = 'fulltech_estoque.db'


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def criar_tabelas():
    db = get_db()

    db.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT,
            preco REAL NOT NULL,
            preco_pix REAL,
            categoria_id INTEGER,
            estoque INTEGER DEFAULT 0,
            estoque_minimo INTEGER DEFAULT 1,
            imagem TEXT,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            perfil TEXT DEFAULT 'Cliente'
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER,
            quantidade INTEGER,
            valor_total REAL,
            data_venda TEXT,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cnpj TEXT NOT NULL UNIQUE,
            contato TEXT,
            produtos TEXT
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            produto_id INTEGER NOT NULL,
            tipo TEXT CHECK(tipo IN ('Entrada', 'Saída')) NOT NULL,
            quantidade INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            FOREIGN KEY (produto_id) REFERENCES produtos(id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')

    db.commit()
    db.close()
    print("✅ Tabelas criadas/verificadas com sucesso.")


def criar_admin():
    db = get_db()
    email_admin = "admin@fulltech.com"
    senha_admin = "Admin123"

    usuario = db.execute("SELECT * FROM usuarios WHERE email = ?", (email_admin,)).fetchone()
    if usuario:
        print("⚠️ Usuário administrador já existe.")
    else:
        senha_hash = generate_password_hash(senha_admin)
        db.execute(
            "INSERT INTO usuarios (nome, email, senha, perfil) VALUES (?, ?, ?, ?)",
            ("Administrador", email_admin, senha_hash, "Admin")
        )
        db.commit()
        print("✅ Usuário administrador criado com sucesso!")

    db.close()


def verificar_login(email, senha_inserida):
    db = get_db()
    usuario = db.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
    db.close()

    if usuario and check_password_hash(usuario["senha"], senha_inserida):
        return {
            "id": usuario["id"],
            "nome": usuario["nome"],
            "perfil": usuario["perfil"],
            "sucesso": True
        }
    else:
        return None


def registrar_venda(produto_id, quantidade, usuario_id=None):
    db = get_db()
    produto = db.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()

    if not produto:
        print("❌ Produto não encontrado.")
        db.close()
        return

    if produto["estoque"] < quantidade:
        print("⚠️ Estoque insuficiente.")
        db.close()
        return

    valor_total = produto["preco"] * quantidade
    data_venda = datetime.now().strftime("%d/%m/%Y")

    db.execute('''
        INSERT INTO vendas (produto_id, quantidade, valor_total, data_venda)
        VALUES (?, ?, ?, ?)
    ''', (produto_id, quantidade, valor_total, data_venda))

    novo_estoque = produto["estoque"] - quantidade
    db.execute("UPDATE produtos SET estoque = ? WHERE id = ?", (novo_estoque, produto_id))


    if usuario_id:
        db.execute('''
            INSERT INTO movimentacoes (data, produto_id, tipo, quantidade, usuario_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (data_venda, produto_id, "Saída", quantidade, usuario_id))

    db.commit()
    db.close()
    print(f"🛒 Venda registrada: {produto['nome']} ({quantidade} un.)")


def registrar_entrada(produto_id, quantidade, usuario_id):
    db = get_db()
    produto = db.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    if not produto:
        print("❌ Produto não encontrado.")
        db.close()
        return

    novo_estoque = produto["estoque"] + quantidade
    db.execute("UPDATE produtos SET estoque = ? WHERE id = ?", (novo_estoque, produto_id))

    data_atual = datetime.now().strftime("%d/%m/%Y")
    db.execute('''
        INSERT INTO movimentacoes (data, produto_id, tipo, quantidade, usuario_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (data_atual, produto_id, "Entrada", quantidade, usuario_id))

    db.commit()
    db.close()
    print(f"Entrada registrada: {produto['nome']} (+{quantidade})")

def gerar_relatorio_vendas():
    db = get_db()
    vendas = db.execute('''
        SELECT p.nome, SUM(v.quantidade) AS qtd_total, SUM(v.valor_total) AS total
        FROM vendas v
        JOIN produtos p ON v.produto_id = p.id
        GROUP BY p.id
        ORDER BY total DESC
    ''').fetchall()

    print("\nRelatório de Vendas:")
    for v in vendas:
        print(f"- {v['nome']}: {v['qtd_total']} un | R$ {v['total']:.2f}")

    db.close()
