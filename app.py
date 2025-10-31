from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'chave-secreta-qualquer'

DATABASE = 'fulltech_estoque.db'
UPLOAD_FOLDER = "static/img/produtos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

CONTACT_UPLOAD_FOLDER = "static/uploads/contato"
os.makedirs(CONTACT_UPLOAD_FOLDER, exist_ok=True)
app.config["CONTACT_UPLOAD_FOLDER"] = CONTACT_UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


from db import verificar_login, criar_tabelas, criar_admin
criar_tabelas()
criar_admin()

@app.route('/')
def index():
    db = get_db()
    categorias = db.execute('SELECT * FROM categorias ORDER BY nome').fetchall()
    produtos = db.execute('SELECT * FROM produtos').fetchall()
    db.close()

    return render_template(
        'index.html',
        produtos=produtos,
        categorias=categorias,
        usuario=session.get("usuario_nome"),
        perfil=session.get("perfil"),
        categoria_nome=None,
        categoria_selecionada=None
    )

@app.route('/add_to_cart/<int:produto_id>', methods=['POST'])
def add_to_cart(produto_id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
        
    db = get_db()
    produto = db.execute('SELECT * FROM produtos WHERE id = ?', (produto_id,)).fetchone()
    db.close()
    if not produto:
        return "Produto não encontrado", 404

    if 'carrinho' not in session:
        session['carrinho'] = {}

    carrinho = session['carrinho']

    if str(produto_id) in carrinho:
        carrinho[str(produto_id)]['quantidade'] += 1
    else:
        carrinho[str(produto_id)] = {
            'nome': produto['nome'],
            'preco': produto['preco'],
            'quantidade': 1,
            'imagem': produto['imagem'] if 'imagem' in produto.keys() else None
        }

    session['carrinho'] = carrinho
    flash(f"✅ {produto['nome']} adicionado ao carrinho!", "success")
    return redirect(url_for('index'))


@app.route('/carrinho')
def carrinho():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    carrinho = session.get('carrinho', {})
    total = sum(item['preco'] * item['quantidade'] for item in carrinho.values())
    
    if not carrinho:
        frete = None
        if 'frete' in session:
            session.pop('frete')
            session.modified = True
    else:
        frete = session.get('frete', None)  

    total_final = total + (frete or 0)
    
    return render_template(
        'carrinho.html',
        carrinho=carrinho,
        total=total,
        frete=frete,
        total_final=total_final,
        usuario=session.get("usuario_nome")
    )

@app.route('/calcular_frete', methods=['POST'])
def calcular_frete():
    cep = request.form.get('cep', '').strip()
    carrinho = session.get('carrinho', {})

    if not carrinho:
        return {"erro": "Adicione itens ao carrinho para calcular o frete."}, 400

    if not cep:
        return {"erro": "Informe um CEP válido."}, 400

    if cep.startswith('0'):
        frete = 19.90
    elif cep.startswith('1') or cep.startswith('2'):
        frete = 24.90
    else:
        frete = 29.90

    session['frete'] = frete
    session.modified = True 
    return {"frete": frete}

@app.route('/atualizar_quantidade', methods=['POST'])
def atualizar_quantidade():
    """
    Atualiza a quantidade do produto.
    Não permite quantidade <= 0, pois a remoção é tratada pela rota /remover_do_carrinho.
    """
    produto_id = request.form.get('produto_id')
    quantidade = int(request.form.get('quantidade')) 

    if 'carrinho' in session and produto_id in session['carrinho']:
        if quantidade >= 1: 
            session['carrinho'][produto_id]['quantidade'] = quantidade
        
        session.modified = True 
    return redirect(url_for('carrinho'))

@app.route('/remover_do_carrinho/<produto_id>', methods=['POST'])
def remover_do_carrinho(produto_id):
    if 'carrinho' in session and produto_id in session['carrinho']:
        del session['carrinho'][produto_id]
        
        if not session['carrinho'] and 'frete' in session:
            session.pop('frete')
            
        session.modified = True 
    return redirect(url_for('carrinho'))


@app.route('/buscar', methods=['GET'])
def buscar_produtos():
    query = request.args.get('query', '').strip()
    
    print(f"Buscando por: {query}")
    
    return redirect(url_for('index'))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]
        confirmar_senha = request.form["confirmar_senha"]
        termos = request.form.get("termos")

        if senha != confirmar_senha:
            flash("As senhas não coincidem.", "error")
            return render_template("register.html")
        
        if not termos:
            flash("Você deve aceitar os termos de serviço.", "error")
            return render_template("register.html")

        senha_hash = generate_password_hash(senha)

        db = get_db()
        try:
            db.execute("INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)", 
                       (nome, email, senha_hash))
            db.commit()
            flash("Cadastro realizado com sucesso! Faça login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email já cadastrado.", "error")
        finally:
            db.close()
    return render_template("register.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        user = verificar_login(email, senha)

        if user and user.get("sucesso"):
            session['usuario_id'] = user['id']
            session['usuario_nome'] = user['nome']
            session['perfil'] = user['perfil']

            if user['perfil'] == 'Admin':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            error = "Usuário ou senha incorretos. Tente novamente."
            return render_template('login.html', error=error)

    return render_template('login.html')


@app.route('/categoria/<int:categoria_id>')
def categoria(categoria_id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    categoria = db.execute('SELECT * FROM categorias WHERE id = ?', (categoria_id,)).fetchone()
    if not categoria:
        db.close()
        return "Categoria não encontrada", 404
    produtos = db.execute('SELECT * FROM produtos WHERE categoria_id = ?', (categoria_id,)).fetchall()
    categorias = db.execute('SELECT * FROM categorias ORDER BY nome').fetchall()
    db.close()
    return render_template('index.html', produtos=produtos, categorias=categorias, categoria_nome=categoria['nome'], categoria_selecionada=categoria_id, usuario=session.get("usuario_nome"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("login"))


@app.route("/editar-produto/<int:produto_id>", methods=["GET", "POST"])
def editar_produto(produto_id):
    if "usuario_id" not in session or session.get("perfil") != "Admin":
        flash("Acesso restrito ao administrador.", "error")
        return redirect(url_for("index"))

    db = get_db()
    produto = db.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    categorias = db.execute("SELECT * FROM categorias ORDER BY nome").fetchall()

    if not produto:
        flash("Produto não encontrado.", "error")
        db.close()
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        nome = request.form["nome"]
        descricao = request.form["descricao"]
        preco = float(request.form["preco"])
        preco_pix = float(request.form["preco_pix"])
        categoria_id = int(request.form["categoria"])
        estoque = int(request.form["estoque"])
        estoque_minimo = int(request.form["estoque_minimo"])
        imagem = request.form.get("imagem") 

        db.execute('''
            UPDATE produtos
            SET nome=?, descricao=?, preco=?, preco_pix=?, categoria_id=?, estoque=?, estoque_minimo=?, imagem=?
            WHERE id=?
        ''', (nome, descricao, preco, preco_pix, categoria_id, estoque, estoque_minimo, imagem, produto_id))
        db.commit()
        db.close()

        flash("✅ Produto atualizado com sucesso!", "success")
        return redirect(url_for("dashboard"))

    db.close()
    return render_template("editar_produto.html", produto=produto, categorias=categorias)


@app.route("/remover-produto/<int:produto_id>", methods=["GET", "POST"])
def remover_produto(produto_id):
    if "usuario_id" not in session or session.get("perfil") != "Admin":
        flash("Acesso restrito ao administrador.", "error")
        return redirect(url_for("index"))

    db = get_db()
    db.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    db.commit()
    db.close()

    flash("🗑️ Produto removido com sucesso!", "success")
    return redirect(url_for("dashboard"))


@app.route("/adicionar-produto", methods=["GET", "POST"])
def adicionar_produto():
    if "usuario_id" not in session or session.get("perfil") != "Admin":
        flash("Acesso restrito ao administrador.", "error")
        return redirect(url_for("index"))

    db = get_db()

    if request.method == "POST":
        nome = request.form["nome"]
        descricao = request.form["descricao"]
        preco = float(request.form["preco"])
        preco_pix = float(request.form["preco_pix"])
        categoria_id = int(request.form["categoria"])
        estoque = int(request.form["estoque"])
        estoque_minimo = int(request.form["estoque_minimo"])
        
        imagem = None
        if "imagem" in request.files and request.files["imagem"].filename != "":
            arquivo = request.files["imagem"]
            nome_arquivo = secure_filename(arquivo.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome_arquivo)
            arquivo.save(caminho)
            imagem = f"img/produtos/{nome_arquivo}"

        db.execute('''
            INSERT INTO produtos (nome, descricao, preco, preco_pix, categoria_id, estoque, estoque_minimo, imagem)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nome, descricao, preco, preco_pix, categoria_id, estoque, estoque_minimo, imagem))
        db.commit()
        db.close()

        flash("✅ Produto adicionado com sucesso!", "success")
        return redirect(url_for("dashboard"))

    categorias = db.execute("SELECT * FROM categorias ORDER BY nome").fetchall()
    db.close()
    return render_template("adicionar_produto.html", categorias=categorias)


@app.route("/perfil")
def perfil():
    if "usuario_id" not in session:
        flash("Você precisa estar logado.", "error")
        return redirect(url_for("login"))
    
    return render_template("perfil.html", usuario=session.get("usuario_nome"))


@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('perfil') != 'Admin':
        flash("Acesso restrito a administradores.", "error")
        return redirect(url_for('index'))

    db = get_db()

    produtos = db.execute("""
        SELECT p.id, p.nome, p.preco, p.estoque, c.nome AS categoria
        FROM produtos p
        LEFT JOIN categorias c ON c.id = p.categoria_id
    """).fetchall()

    fornecedores = db.execute("""
        SELECT * FROM fornecedores
        ORDER BY nome
    """).fetchall()

    movimentacoes = db.execute("""
        SELECT m.data, p.nome AS produto, m.tipo, m.quantidade, u.nome AS usuario
        FROM movimentacoes m
        JOIN produtos p ON p.id = m.produto_id
        JOIN usuarios u ON u.id = m.usuario_id
        ORDER BY m.id DESC
        LIMIT 5
    """).fetchall()

    total_produtos = len(produtos)
    produtos_baixo_estoque = sum(1 for p in produtos if p["estoque"] <= 5)
    produtos_em_falta = sum(1 for p in produtos if p["estoque"] == 0)
    renda_mensal = sum(p["preco"] * p["estoque"] for p in produtos)

    db.close()

    return render_template(
        "admin.html",
        usuario=session.get("usuario_nome"),
        produtos=produtos,
        fornecedores=fornecedores,
        movimentacoes=movimentacoes,
        total_produtos=total_produtos,
        produtos_baixo_estoque=produtos_baixo_estoque,
        produtos_em_falta=produtos_em_falta,
        renda_mensal=renda_mensal
    )

@app.route('/recuperar_senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form['email']
        flash('Se o email existir, enviaremos um link de recuperação.', 'info')
        return redirect(url_for('recuperar_senha'))
    
    return render_template('recuperar_senha.html')

def registrar_movimentacao(produto_id, tipo, quantidade, usuario_id):
    from datetime import datetime
    db = get_db()
    db.execute("""
        INSERT INTO movimentacoes (data, produto_id, tipo, quantidade, usuario_id)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%d/%m/%Y"), produto_id, tipo, quantidade, usuario_id))
    db.commit()
    db.close()

@app.route("/adicionar_fornecedor", methods=["GET", "POST"])
def adicionar_fornecedor():
    if request.method == "POST":
        nome = request.form.get("nome")
        cnpj = request.form.get("cnpj")
        contato = request.form.get("contato")
        produtos = request.form.get("produtos")

        if not nome or not cnpj:
            flash("Nome e CNPJ são obrigatórios!", "erro")
            return redirect(url_for("adicionar_fornecedor"))

        db = get_db()
        db.execute("""
            INSERT INTO fornecedores (nome, cnpj, contato, produtos)
            VALUES (?, ?, ?, ?)
        """, (nome, cnpj, contato, produtos))
        db.commit()
        db.close()
        flash("Fornecedor adicionado com sucesso!", "sucesso")
        return redirect(url_for("dashboard"))

    return render_template("adicionar_fornecedor.html")

@app.route("/editar_fornecedor/<int:fornecedor_id>", methods=["GET", "POST"])
def editar_fornecedor(fornecedor_id):
    db = get_db()
    fornecedor = db.execute("SELECT * FROM fornecedores WHERE id = ?", (fornecedor_id,)).fetchone()

    if not fornecedor:
        flash("Fornecedor não encontrado!", "erro")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        nome = request.form.get("nome")
        cnpj = request.form.get("cnpj")
        contato = request.form.get("contato")
        produtos = request.form.get("produtos")

        db.execute("""
            UPDATE fornecedores
            SET nome = ?, cnpj = ?, contato = ?, produtos = ?
            WHERE id = ?
        """, (nome, cnpj, contato, produtos, fornecedor_id))
        db.commit()
        db.close()

        flash("Fornecedor atualizado com sucesso!", "sucesso")
        return redirect(url_for("dashboard"))

    db.close()
    return render_template("editar_fornecedor.html", fornecedor=fornecedor)

@app.route("/remover_fornecedor/<int:fornecedor_id>")
def remover_fornecedor(fornecedor_id):
    db = get_db()
    db.execute("DELETE FROM fornecedores WHERE id = ?", (fornecedor_id,))
    db.commit()
    db.close()
    flash("Fornecedor removido com sucesso!", "sucesso")
    return redirect(url_for("dashboard"))

@app.route("/categorias", methods=["GET", "POST"])
def gerenciar_categorias():
    if "usuario_id" not in session or session.get("perfil") != "Admin":
        flash("Acesso restrito.", "error")
        return redirect(url_for("index"))

    db = get_db()
    if request.method == "POST":
        nome = request.form["nome"]
        if nome.strip():
            db.execute("INSERT INTO categorias (nome) VALUES (?)", (nome,))
            db.commit()
            flash("Categoria adicionada com sucesso!", "success")

    categorias = db.execute("SELECT * FROM categorias ORDER BY nome").fetchall()
    db.close()
    return render_template("categorias.html", categorias=categorias)

@app.route('/contato', methods=['GET', 'POST'])
def contato():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        assunto = request.form.get('assunto')
        mensagem = request.form.get('mensagem')
        
        caminho_anexo = None

        if 'anexo' in request.files:
            file = request.files['anexo']
            
            if file.filename != '':
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['CONTACT_UPLOAD_FOLDER'], filename)
                    
                    file.save(file_path)
                    
                    caminho_anexo = url_for('static', filename=f'uploads/contato/{filename}')
                else:
                    flash('Tipo de arquivo não permitido. Use JPG, PNG, GIF, PDF ou DOC(X).', 'error')
                    return redirect(url_for('contato'))
        
        print("--- NOVO CONTATO RECEBIDO ---")
        print(f"Nome: {nome}")
        print(f"E-mail: {email}")
        print(f"Assunto: {assunto}")
        print(f"Mensagem: {mensagem}")
        if caminho_anexo:
            print(f"Anexo Salvo em: {caminho_anexo}")
        print("----------------------------")
        
        flash('Sua mensagem foi enviada com sucesso! Em breve entraremos em contato.', 'success')
        
        return redirect(url_for('contato'))
    return render_template('contato.html')


if __name__ == '__main__':
    if not os.path.exists(CONTACT_UPLOAD_FOLDER):
        os.makedirs(CONTACT_UPLOAD_FOLDER)
        
    app.run(debug=True)