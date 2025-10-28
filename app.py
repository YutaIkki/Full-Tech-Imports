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

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

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
            'quantidade': 1
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
    return render_template('carrinho.html', carrinho=carrinho, total=total, usuario=session.get("usuario_nome"))

@app.route('/remover_do_carrinho/<produto_id>', methods=['POST'])
def remover_do_carrinho(produto_id):
    carrinho = session.get('carrinho', {})
    if produto_id in carrinho:
        del carrinho[produto_id]
        session['carrinho'] = carrinho
    return redirect(url_for('carrinho'))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = generate_password_hash(request.form["senha"])

        db = get_db()
        try:
            db.execute("INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)", 
                       (nome, email, senha))
            db.commit()
            flash("✅ Cadastro realizado com sucesso! Faça login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("❌ Email já cadastrado.", "error")
        finally:
            db.close()
    return render_template("register.html")

from db import verificar_login

from db import verificar_login

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        user = verificar_login(email, senha)

        if user:
            session['usuario_id'] = user['id']
            session['usuario_nome'] = user['nome']
            session['perfil'] = user['perfil']

            if user['perfil'] == 'Admin':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('perfil'))
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

    total_produtos = len(produtos)
    produtos_baixo_estoque = sum(1 for p in produtos if p["estoque"] <= 5)
    renda_mensal = sum(p["preco"] * p["estoque"] for p in produtos)

    db.close()

    return render_template(
        "admin.html",
        usuario=session.get("usuario_nome"),
        produtos=produtos,
        total_produtos=total_produtos,
        produtos_baixo_estoque=produtos_baixo_estoque,
        renda_mensal=renda_mensal
    )

if __name__ == '__main__':
    app.run(debug=True)
