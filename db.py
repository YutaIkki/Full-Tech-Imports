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

    # Tabela de categorias
    db.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
    ''')

    # Tabela de produtos
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

    # Tabela de usuários
    db.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            perfil TEXT DEFAULT 'Cliente',
            foto_perfil TEXT DEFAULT 'default.png'
        )
    ''')

    # Tabela de pedidos - ATUALIZADA COM TODAS AS COLUNAS NECESSÁRIAS
    db.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            data TEXT DEFAULT CURRENT_TIMESTAMP,
            total REAL NOT NULL,
            status TEXT DEFAULT 'Em processamento',
            forma_pagamento TEXT,
            itens_json TEXT,
            endereco_entrega TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')

    # Tabela de vendas
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

    # Tabela de fornecedores
    db.execute('''
        CREATE TABLE IF NOT EXISTS fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cnpj TEXT NOT NULL UNIQUE,
            contato TEXT,
            produtos TEXT
        )
    ''')

    # Tabela de movimentações
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

    # Tabela para endereços dos usuários
    db.execute('''
        CREATE TABLE IF NOT EXISTS enderecos_usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            cep TEXT NOT NULL,
            logradouro TEXT NOT NULL,
            numero TEXT NOT NULL,
            complemento TEXT,
            bairro TEXT NOT NULL,
            cidade TEXT NOT NULL,
            estado TEXT NOT NULL,
            principal BOOLEAN DEFAULT 0,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')

    db.commit()
    db.close()
    print("✅ Todas as tabelas criadas/verificadas com sucesso.")

def atualizar_schema_pedidos():
    """
    Atualiza o schema da tabela pedidos para adicionar colunas faltantes
    """
    db = get_db()
    
    # Lista de colunas que devem existir na tabela pedidos
    colunas_necessarias = [
        ('forma_pagamento', 'TEXT'),
        ('itens_json', 'TEXT'),
        ('endereco_entrega', 'TEXT')
    ]
    
    try:
        # Verificar quais colunas já existem
        colunas_existentes = db.execute("PRAGMA table_info(pedidos)").fetchall()
        nomes_colunas_existentes = [col[1] for col in colunas_existentes]
        
        # Adicionar colunas faltantes
        for coluna, tipo in colunas_necessarias:
            if coluna not in nomes_colunas_existentes:
                db.execute(f"ALTER TABLE pedidos ADD COLUMN {coluna} {tipo}")
                print(f"✅ Coluna '{coluna}' adicionada à tabela pedidos")
        
        db.commit()
        print("✅ Schema da tabela pedidos atualizado com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao atualizar schema: {e}")
        db.rollback()
    finally:
        db.close()

def atualizar_tabela_usuarios():
    """
    Atualiza a tabela usuarios para adicionar coluna de foto de perfil se não existir
    """
    db = get_db()
    try:
        # Verificar se a coluna foto_perfil existe
        db.execute("SELECT foto_perfil FROM usuarios LIMIT 1")
        print("✅ Coluna 'foto_perfil' já existe na tabela usuarios")
    except sqlite3.OperationalError:
        try:
            db.execute("ALTER TABLE usuarios ADD COLUMN foto_perfil TEXT DEFAULT 'default.png'")
            db.commit()
            print("✅ Coluna 'foto_perfil' adicionada à tabela usuarios")
        except Exception as e:
            print(f"❌ Erro ao adicionar coluna foto_perfil: {e}")
    finally:
        db.close()

def criar_admin():
    """
    Cria o usuário administrador padrão se não existir
    """
    db = get_db()
    email_admin = "admin@fulltech.com"
    senha_admin = "Admin123"

    usuario = db.execute("SELECT * FROM usuarios WHERE email = ?", (email_admin,)).fetchone()
    if usuario:
        print("⚠️ Usuário administrador já existe.")
    else:
        try:
            senha_hash = generate_password_hash(senha_admin)
            db.execute(
                "INSERT INTO usuarios (nome, email, senha, perfil) VALUES (?, ?, ?, ?)",
                ("Administrador", email_admin, senha_hash, "Admin")
            )
            db.commit()
            print("✅ Usuário administrador criado com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao criar usuário administrador: {e}")
    db.close()

def verificar_login(email, senha_inserida):
    """
    Verifica as credenciais de login do usuário
    """
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

def salvar_endereco_usuario(usuario_id, endereco_data, principal=True):
    """
    Salva ou atualiza um endereço para o usuário
    """
    db = get_db()
    
    try:
        # Se este endereço for principal, remove o principal de outros endereços
        if principal:
            db.execute("UPDATE enderecos_usuarios SET principal = 0 WHERE usuario_id = ?", (usuario_id,))
        
        # Verifica se já existe um endereço com os mesmos dados
        endereco_existente = db.execute('''
            SELECT id FROM enderecos_usuarios 
            WHERE usuario_id = ? AND cep = ? AND logradouro = ? AND numero = ? AND bairro = ? AND cidade = ? AND estado = ?
        ''', (usuario_id, endereco_data['cep'], endereco_data['logradouro'], 
              endereco_data['numero'], endereco_data['bairro'], 
              endereco_data['cidade'], endereco_data['estado'])).fetchone()
        
        if endereco_existente:
            # Atualiza endereço existente
            db.execute('''
                UPDATE enderecos_usuarios 
                SET complemento = ?, principal = ?
                WHERE id = ?
            ''', (endereco_data.get('complemento', ''), 1 if principal else 0, endereco_existente['id']))
        else:
            # Insere novo endereço
            db.execute('''
                INSERT INTO enderecos_usuarios 
                (usuario_id, cep, logradouro, numero, complemento, bairro, cidade, estado, principal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (usuario_id, endereco_data['cep'], endereco_data['logradouro'], 
                  endereco_data['numero'], endereco_data.get('complemento', ''), 
                  endereco_data['bairro'], endereco_data['cidade'], 
                  endereco_data['estado'], 1 if principal else 0))
        
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar endereço: {e}")
        return False
    finally:
        db.close()

def obter_enderecos_usuario(usuario_id):
    """
    Retorna todos os endereços de um usuário
    """
    db = get_db()
    try:
        enderecos = db.execute('''
            SELECT * FROM enderecos_usuarios 
            WHERE usuario_id = ? 
            ORDER BY principal DESC, id DESC
        ''', (usuario_id,)).fetchall()
        return [dict(endereco) for endereco in enderecos]
    except Exception as e:
        print(f"❌ Erro ao obter endereços: {e}")
        return []
    finally:
        db.close()

def obter_endereco_principal(usuario_id):
    """
    Retorna o endereço principal do usuário
    """
    db = get_db()
    try:
        endereco = db.execute('''
            SELECT * FROM enderecos_usuarios 
            WHERE usuario_id = ? AND principal = 1
        ''', (usuario_id,)).fetchone()
        return dict(endereco) if endereco else None
    except Exception as e:
        print(f"❌ Erro ao obter endereço principal: {e}")
        return None
    finally:
        db.close()

def definir_endereco_principal(usuario_id, endereco_id):
    """
    Define um endereço como principal
    """
    db = get_db()
    try:
        # Remove principal de todos os endereços do usuário
        db.execute("UPDATE enderecos_usuarios SET principal = 0 WHERE usuario_id = ?", (usuario_id,))
        # Define o endereço específico como principal
        db.execute("UPDATE enderecos_usuarios SET principal = 1 WHERE id = ? AND usuario_id = ?", (endereco_id, usuario_id))
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Erro ao definir endereço principal: {e}")
        return False
    finally:
        db.close()

def remover_endereco(usuario_id, endereco_id):
    """
    Remove um endereço do usuário
    """
    db = get_db()
    try:
        db.execute("DELETE FROM enderecos_usuarios WHERE id = ? AND usuario_id = ?", (endereco_id, usuario_id))
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Erro ao remover endereço: {e}")
        return False
    finally:
        db.close()

def registrar_venda(produto_id, quantidade, usuario_id=None):
    """
    Registra uma venda no sistema
    """
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

    try:
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
        print(f"🛒 Venda registrada: {produto['nome']} ({quantidade} un.)")
    except Exception as e:
        print(f"❌ Erro ao registrar venda: {e}")
        db.rollback()
    finally:
        db.close()

def registrar_entrada(produto_id, quantidade, usuario_id):
    """
    Registra uma entrada de estoque
    """
    db = get_db()
    produto = db.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    if not produto:
        print("❌ Produto não encontrado.")
        db.close()
        return

    try:
        novo_estoque = produto["estoque"] + quantidade
        db.execute("UPDATE produtos SET estoque = ? WHERE id = ?", (novo_estoque, produto_id))

        data_atual = datetime.now().strftime("%d/%m/%Y")
        db.execute('''
            INSERT INTO movimentacoes (data, produto_id, tipo, quantidade, usuario_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (data_atual, produto_id, "Entrada", quantidade, usuario_id))

        db.commit()
        print(f"📦 Entrada registrada: {produto['nome']} (+{quantidade})")
    except Exception as e:
        print(f"❌ Erro ao registrar entrada: {e}")
        db.rollback()
    finally:
        db.close()

def gerar_relatorio_vendas():
    """
    Gera um relatório de vendas
    """
    db = get_db()
    try:
        vendas = db.execute('''
            SELECT p.nome, SUM(v.quantidade) AS qtd_total, SUM(v.valor_total) AS total
            FROM vendas v
            JOIN produtos p ON v.produto_id = p.id
            GROUP BY p.id
            ORDER BY total DESC
        ''').fetchall()

        print("\n📊 Relatório de Vendas:")
        for v in vendas:
            print(f"- {v['nome']}: {v['qtd_total']} un | R$ {v['total']:.2f}")

    except Exception as e:
        print(f"❌ Erro ao gerar relatório: {e}")
    finally:
        db.close()

def inicializar_banco():
    """
    Função principal para inicializar todo o banco de dados
    """
    print("🔄 Inicializando banco de dados...")
    criar_tabelas()
    atualizar_tabela_usuarios()
    atualizar_schema_pedidos()
    criar_admin()
    print("✅ Banco de dados inicializado com sucesso!")

# Executar a inicialização quando este arquivo for executado diretamente
if __name__ == "__main__":
    inicializar_banco()