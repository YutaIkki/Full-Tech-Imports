from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import json
from datetime import datetime
from flask import jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'chave-secreta-qualquer'

@app.template_filter('brl')
def brl(valor):
    """
    Formata valores numéricos para o padrão brasileiro: 1234.5 → 1.234,50
    """
    try:
        valor = float(valor)
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return valor

DATABASE = 'fulltech_estoque.db'
UPLOAD_FOLDER = "static/img/produtos"
PERFIL_UPLOAD_FOLDER = "static/img/perfis"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PERFIL_UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PERFIL_UPLOAD_FOLDER"] = PERFIL_UPLOAD_FOLDER

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

def row_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}

def rows_to_dict(rows):
    return [row_to_dict(row) for row in rows]

from db import verificar_login, criar_tabelas, criar_admin, salvar_endereco_usuario, obter_enderecos_usuario, definir_endereco_principal, remover_endereco, atualizar_schema_pedidos
criar_tabelas()
criar_admin()
atualizar_schema_pedidos() 

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

    # Lógica simplificada de cálculo de frete
    if cep.startswith('0'):
        frete = 19.90
    elif cep.startswith('1') or cep.startswith('2'):
        frete = 24.90
    else:
        frete = 29.90

    session['frete'] = frete
    session['cep'] = cep  
    session.modified = True 
    
    return {"frete": frete}

@app.route('/atualizar_quantidade', methods=['POST'])
def atualizar_quantidade():
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
        
        imagem = produto['imagem']  
        
        if "imagem" in request.files and request.files["imagem"].filename != "":
            arquivo = request.files["imagem"]
            if arquivo and allowed_file(arquivo.filename):
                nome_arquivo = secure_filename(arquivo.filename)
                caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome_arquivo)
                arquivo.save(caminho)
                imagem = f"img/produtos/{nome_arquivo}"

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
            if arquivo and allowed_file(arquivo.filename):
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
        flash("Você precisa estar logado para acessar o perfil.", "error")
        return redirect(url_for("login"))

    db = get_db()
    usuario = db.execute("SELECT * FROM usuarios WHERE id = ?", (session["usuario_id"],)).fetchone()
    
    if not usuario:
        flash("Usuário não encontrado.", "error")
        db.close()
        return redirect(url_for("login"))
    
    try:
        pedidos = db.execute("""
            SELECT * FROM pedidos 
            WHERE usuario_id = ? 
            ORDER BY id DESC
        """, (session["usuario_id"],)).fetchall()
    except sqlite3.OperationalError:
        pedidos = []
    try:
        enderecos = db.execute("""
            SELECT * FROM enderecos_usuarios 
            WHERE usuario_id = ? 
            ORDER BY principal DESC, id DESC
        """, (session["usuario_id"],)).fetchall()
        enderecos = [dict(endereco) for endereco in enderecos]
    except sqlite3.OperationalError:
        # Se a tabela não existir ainda, cria endereços vazios
        enderecos = []
        
    db.close()
    
    usuario_dict = dict(usuario)
    if not usuario_dict.get('foto_perfil'):
        usuario_dict['foto_perfil'] = 'default.png'
    
    return render_template("perfil.html", usuario=usuario_dict, pedidos=pedidos, enderecos=enderecos)

@app.route("/salvar_endereco", methods=["POST"])
def salvar_endereco():
    if "usuario_id" not in session:
        return jsonify({"success": False, "message": "Usuário não logado"}), 401
    
    data = request.get_json()
    
    endereco_data = {
        'cep': data.get('cep', '').strip(),
        'logradouro': data.get('logradouro', '').strip(),
        'numero': data.get('numero', '').strip(),
        'complemento': data.get('complemento', '').strip(),
        'bairro': data.get('bairro', '').strip(),
        'cidade': data.get('cidade', '').strip(),
        'estado': data.get('estado', '').strip()
    }
    
    # Validar campos obrigatórios
    campos_obrigatorios = ['cep', 'logradouro', 'numero', 'bairro', 'cidade', 'estado']
    for campo in campos_obrigatorios:
        if not endereco_data[campo]:
            return jsonify({"success": False, "message": f"Campo {campo} é obrigatório"}), 400
    
    principal = data.get('principal', False)
    
    # Usar a função do db.py
    resultado = salvar_endereco_usuario(session["usuario_id"], endereco_data, principal)
    
    if resultado:
        return jsonify({"success": True, "message": "Endereço salvo com sucesso"})
    else:
        return jsonify({"success": False, "message": "Este endereço já está cadastrado"}), 400

@app.route("/remover_endereco_checkout", methods=["POST"])
def remover_endereco_checkout():
    """Remove endereço diretamente da página de checkout"""
    if "usuario_id" not in session:
        return jsonify({"success": False, "message": "Usuário não logado"}), 401
    
    data = request.get_json()
    endereco_id = data.get('endereco_id')
    
    if not endereco_id:
        return jsonify({"success": False, "message": "ID do endereço é obrigatório"}), 400
    
    db = get_db()
    try:
        # Verificar se o endereço pertence ao usuário
        endereco = db.execute("""
            SELECT id, principal FROM enderecos_usuarios 
            WHERE id = ? AND usuario_id = ?
        """, (endereco_id, session["usuario_id"])).fetchone()
        
        if not endereco:
            return jsonify({"success": False, "message": "Endereço não encontrado"}), 404
        
        # Não permitir remover o endereço principal se for o único
        if endereco['principal'] == 1:
            total_enderecos = db.execute("""
                SELECT COUNT(*) as total FROM enderecos_usuarios 
                WHERE usuario_id = ?
            """, (session["usuario_id"],)).fetchone()['total']
            
            if total_enderecos == 1:
                return jsonify({
                    "success": False, 
                    "message": "Não é possível remover seu único endereço. Adicione outro endereço primeiro."
                }), 400
        
        # Remover o endereço
        db.execute("DELETE FROM enderecos_usuarios WHERE id = ? AND usuario_id = ?", 
                  (endereco_id, session["usuario_id"]))
        
        # Se era o principal, definir um novo endereço como principal
        novo_principal_id = None
        if endereco['principal'] == 1:
            novo_principal = db.execute("""
                SELECT id FROM enderecos_usuarios 
                WHERE usuario_id = ? 
                ORDER BY id DESC
                LIMIT 1
            """, (session["usuario_id"],)).fetchone()
            
            if novo_principal:
                db.execute("UPDATE enderecos_usuarios SET principal = 1 WHERE id = ?", 
                          (novo_principal['id'],))
                novo_principal_id = novo_principal['id']
        
        db.commit()
        
        # Buscar endereços atualizados
        enderecos_atualizados = db.execute("""
            SELECT * FROM enderecos_usuarios 
            WHERE usuario_id = ? 
            ORDER BY principal DESC, id DESC
        """, (session["usuario_id"],)).fetchall()
        
        enderecos_list = []
        for endereco in enderecos_atualizados:
            enderecos_list.append({
                'id': endereco['id'],
                'cep': endereco['cep'],
                'logradouro': endereco['logradouro'],
                'numero': endereco['numero'],
                'complemento': endereco['complemento'],
                'bairro': endereco['bairro'],
                'cidade': endereco['cidade'],
                'estado': endereco['estado'],
                'principal': endereco['principal']
            })
        
        return jsonify({
            "success": True, 
            "message": "Endereço removido com sucesso",
            "enderecos": enderecos_list,
            "novo_principal_id": novo_principal_id
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": f"Erro ao remover endereço: {str(e)}"}), 500
    finally:
        db.close()

@app.route("/endereco/<int:endereco_id>", methods=["GET"])
def obter_endereco(endereco_id):
    if "usuario_id" not in session:
        return {"success": False, "message": "Usuário não logado"}, 401
    
    db = get_db()
    try:
        endereco = db.execute("""
            SELECT * FROM enderecos_usuarios 
            WHERE id = ? AND usuario_id = ?
        """, (endereco_id, session["usuario_id"])).fetchone()
        
        if not endereco:
            return {"success": False, "message": "Endereço não encontrado"}, 404
            
        return {"success": True, "endereco": dict(endereco)}
        
    except Exception as e:
        return {"success": False, "message": f"Erro ao buscar endereço: {str(e)}"}, 500
    finally:
        db.close()

@app.route("/endereco/<int:endereco_id>", methods=["PUT"])
def atualizar_endereco(endereco_id):
    if "usuario_id" not in session:
        return {"success": False, "message": "Usuário não logado"}, 401
    
    data = request.get_json()
    
    endereco_data = {
        'cep': data.get('cep'),
        'logradouro': data.get('logradouro'),
        'numero': data.get('numero'),
        'complemento': data.get('complemento', ''),
        'bairro': data.get('bairro'),
        'cidade': data.get('cidade'),
        'estado': data.get('estado')
    }
    
    # Validar campos obrigatórios
    campos_obrigatorios = ['cep', 'logradouro', 'numero', 'bairro', 'cidade', 'estado']
    for campo in campos_obrigatorios:
        if not endereco_data[campo]:
            return {"success": False, "message": f"Campo {campo} é obrigatório"}, 400
    
    principal = data.get('principal', False)
    
    db = get_db()
    try:
        # Verificar se o endereço pertence ao usuário
        endereco_existente = db.execute("""
            SELECT id FROM enderecos_usuarios 
            WHERE id = ? AND usuario_id = ?
        """, (endereco_id, session["usuario_id"])).fetchone()
        
        if not endereco_existente:
            return {"success": False, "message": "Endereço não encontrado"}, 404
        
        # Se este endereço for principal, remove o principal de outros endereços
        if principal:
            db.execute("UPDATE enderecos_usuarios SET principal = 0 WHERE usuario_id = ?", (session["usuario_id"],))
        
        # Atualizar endereço
        db.execute('''
            UPDATE enderecos_usuarios 
            SET cep = ?, logradouro = ?, numero = ?, complemento = ?, 
                bairro = ?, cidade = ?, estado = ?, principal = ?
            WHERE id = ? AND usuario_id = ?
        ''', (endereco_data['cep'], endereco_data['logradouro'], 
              endereco_data['numero'], endereco_data['complemento'], 
              endereco_data['bairro'], endereco_data['cidade'], 
              endereco_data['estado'], 1 if principal else 0,
              endereco_id, session["usuario_id"]))
        
        db.commit()
        return {"success": True, "message": "Endereço atualizado com sucesso"}
        
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Erro ao atualizar endereço: {str(e)}"}, 500
    finally:
        db.close()

@app.route("/endereco/<int:endereco_id>", methods=["DELETE"])
def excluir_endereco(endereco_id):
    if "usuario_id" not in session:
        return {"success": False, "message": "Usuário não logado"}, 401
    
    db = get_db()
    try:
        # Verificar se o endereço pertence ao usuário
        endereco_existente = db.execute("""
            SELECT id, principal FROM enderecos_usuarios 
            WHERE id = ? AND usuario_id = ?
        """, (endereco_id, session["usuario_id"])).fetchone()
        
        if not endereco_existente:
            return {"success": False, "message": "Endereço não encontrado"}, 404
        
        # Excluir endereço
        db.execute("DELETE FROM enderecos_usuarios WHERE id = ? AND usuario_id = ?", 
                  (endereco_id, session["usuario_id"]))
        
        db.commit()
        return {"success": True, "message": "Endereço excluído com sucesso"}
        
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Erro ao excluir endereço: {str(e)}"}, 500
    finally:
        db.close()

@app.route("/definir_endereco_principal", methods=["POST"])
def definir_endereco_principal():
    if "usuario_id" not in session:
        return {"success": False, "message": "Usuário não logado"}, 401
    
    data = request.get_json()
    endereco_id = data.get('endereco_id')
    
    if not endereco_id:
        return {"success": False, "message": "ID do endereço é obrigatório"}, 400
    
    db = get_db()
    try:
        # Verificar se o endereço pertence ao usuário
        endereco_existente = db.execute("""
            SELECT id FROM enderecos_usuarios 
            WHERE id = ? AND usuario_id = ?
        """, (endereco_id, session["usuario_id"])).fetchone()
        
        if not endereco_existente:
            return {"success": False, "message": "Endereço não encontrado"}, 404
        
        db.execute("UPDATE enderecos_usuarios SET principal = 0 WHERE usuario_id = ?", (session["usuario_id"],))
        
        db.execute("UPDATE enderecos_usuarios SET principal = 1 WHERE id = ? AND usuario_id = ?", 
                  (endereco_id, session["usuario_id"]))
        
        db.commit()
        return {"success": True, "message": "Endereço definido como principal"}
        
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Erro ao definir endereço principal: {str(e)}"}, 500
    finally:
        db.close()

@app.route("/upload_foto", methods=["POST"])
def upload_foto():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
        
    if 'foto' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('perfil'))
        
    file = request.files['foto']
    
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('perfil'))
        
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"user_{session['usuario_id']}.{ext}")
        
        file.save(os.path.join(app.config["PERFIL_UPLOAD_FOLDER"], filename))
        
        db = get_db()
        db.execute("UPDATE usuarios SET foto_perfil = ? WHERE id = ?", (filename, session["usuario_id"]))
        db.commit()
        db.close()
        
        flash('Foto de perfil atualizada com sucesso!', 'success')
    else:
        flash('Tipo de arquivo não permitido. Use apenas imagens.', 'error')
        
    return redirect(url_for('perfil'))

@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
        
    nome = request.form.get('nome_completo')
    email = request.form.get('email')
    
    if not nome or not email:
        flash('Todos os campos são obrigatórios.', 'error')
        return redirect(url_for('perfil'))
        
    db = get_db()
    try:
        usuario_existente = db.execute("SELECT id FROM usuarios WHERE email = ? AND id != ?", 
                                     (email, session["usuario_id"])).fetchone()
        if usuario_existente:
            flash('Este e-mail já está em uso por outro usuário.', 'error')
        else:
            db.execute("UPDATE usuarios SET nome = ?, email = ? WHERE id = ?", 
                      (nome, email, session["usuario_id"]))
            db.commit()
            session['usuario_nome'] = nome
            flash('Perfil atualizado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar perfil: {str(e)}', 'error')
    finally:
        db.close()
        
    return redirect(url_for('perfil'))


@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    if session.get('perfil') != 'Admin':
        flash("Acesso restrito a administradores.", "error")
        return redirect(url_for('index'))

    db = get_db()

    produtos_rows = db.execute("""
        SELECT p.id, p.nome, p.preco, p.estoque, p.imagem, c.nome AS categoria
        FROM produtos p
        LEFT JOIN categorias c ON c.id = p.categoria_id
    """).fetchall()

    fornecedores_rows = db.execute("""
        SELECT * FROM fornecedores
        ORDER BY nome
    """).fetchall()

    # Buscar as 10 movimentações mais recentes (incluindo vendas)
    movimentacoes_rows = db.execute("""
        SELECT m.data, p.nome AS produto, m.tipo, m.quantidade, u.nome AS usuario
        FROM movimentacoes m
        JOIN produtos p ON p.id = m.produto_id
        JOIN usuarios u ON u.id = m.usuario_id
        ORDER BY m.id DESC
        LIMIT 10
    """).fetchall()

    produtos = rows_to_dict(produtos_rows)
    fornecedores = rows_to_dict(fornecedores_rows)
    movimentacoes = rows_to_dict(movimentacoes_rows)

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

def atualizar_tabela_pedidos():
    db = get_db()
    try:
        db.execute("ALTER TABLE pedidos ADD COLUMN forma_pagamento TEXT")
    except:
        pass

    try:
        db.execute("ALTER TABLE pedidos ADD COLUMN itens_json TEXT")
    except:
        pass

    db.commit()
    db.close()
    print("Tabela pedidos atualizada.")

@app.route("/checkout", methods=["GET"])
def checkout():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    carrinho = session.get("carrinho", {})
    frete = session.get("frete", 0)
    total = sum(i["preco"] * i["quantidade"] for i in carrinho.values())
    total_final = total + (frete or 0)

    enderecos = obter_enderecos_usuario(session["usuario_id"])

    return render_template("checkout.html",
                           total=total,
                           frete=frete,
                           total_final=total_final,
                           enderecos=enderecos)

@app.route('/limpar_frete', methods=['POST'])
def limpar_frete():
    if 'frete' in session:
        session.pop('frete')
        session.modified = True
    return '', 200

@app.route("/debug_enderecos")
def debug_enderecos():
    if "usuario_id" not in session:
        return "Usuário não logado"
    
    db = get_db()
    enderecos = db.execute("""
        SELECT * FROM enderecos_usuarios 
        WHERE usuario_id = ? 
        ORDER BY principal DESC, id DESC
    """, (session["usuario_id"],)).fetchall()
    
    resultado = []
    for endereco in enderecos:
        resultado.append(dict(endereco))
    
    db.close()
    return jsonify(resultado)

@app.route("/checkout/prosseguir", methods=["POST"])
def checkout_prosseguir():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    endereco_id = request.form.get("endereco_id")
    metodo_pagamento = request.form.get("pg")

    endereco_entrega = None

    if endereco_id == "novo":
        endereco_entrega = {
            'cep': request.form.get('cep'),
            'logradouro': request.form.get('logradouro'),
            'numero': request.form.get('numero'),
            'complemento': request.form.get('complemento'),
            'bairro': request.form.get('bairro'),
            'cidade': request.form.get('cidade'),
            'estado': request.form.get('estado')
        }
    else:
        db = get_db()
        try:
            endereco = db.execute('''
                SELECT * FROM enderecos_usuarios 
                WHERE id = ? AND usuario_id = ?
            ''', (int(endereco_id), session["usuario_id"])).fetchone()
            
            if endereco:
                endereco_entrega = {
                    'cep': endereco['cep'],
                    'logradouro': endereco['logradouro'],
                    'numero': endereco['numero'],
                    'complemento': endereco['complemento'],
                    'bairro': endereco['bairro'],
                    'cidade': endereco['cidade'],
                    'estado': endereco['estado']
                }
        except Exception as e:
            print(f"❌ Erro ao buscar endereço: {e}")
        finally:
            db.close()

    if not endereco_entrega:
        flash("Endereço de entrega não encontrado. Por favor, selecione ou cadastre um endereço válido.", "error")
        return redirect(url_for("checkout"))

    # Salvar endereço na sessão
    session['endereco_entrega'] = endereco_entrega

    # Redirecionar para o método de pagamento apropriado
    if metodo_pagamento == "pix":
        return redirect(url_for("pagamento_pix"))
    elif metodo_pagamento == "boleto":
        return redirect(url_for("pagamento_boleto"))
    elif metodo_pagamento == "cartao":
        return redirect(url_for("pagamento_cartao"))
    elif metodo_pagamento == "manual":
        return redirect(url_for("concluir_pedido", metodo="Pago Manual"))
    else:
        flash("Método de pagamento inválido.", "error")
        return redirect(url_for("checkout"))
    
@app.route("/pedido/concluir/<metodo>")
def concluir_pedido(metodo):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    carrinho = session.get("carrinho", {})
    frete = session.get("frete", 0)
    endereco = session.get("endereco_entrega", {})

    if not carrinho:
        flash("Carrinho vazio.", "error")
        return redirect(url_for("index"))

    total = sum(item['preco'] * item['quantidade'] for item in carrinho.values())
    total_final = total + (frete or 0)

    itens_json = json.dumps(carrinho)
    endereco_json = json.dumps(endereco)

    if metodo in ["PIX", "Cartão", "Pago Manual"]:
        status = "Pago"
    else:
        status = "Aguardando Pagamento"

    db = get_db()
    try:
        cursor = db.execute("""
            INSERT INTO pedidos (usuario_id, total, status, forma_pagamento, itens_json, endereco_entrega)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session["usuario_id"],
            total_final,
            status,
            metodo,
            itens_json,
            endereco_json,
        ))
        
        data_atual = datetime.now().strftime("%d/%m/%Y")
        
        for produto_id_str, item in carrinho.items():
            produto_id = int(produto_id_str)
            quantidade = item['quantidade']
            
            db.execute('''
                INSERT INTO movimentacoes (data, produto_id, tipo, quantidade, usuario_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (data_atual, produto_id, "Saída", quantidade, session["usuario_id"]))
            
            produto = db.execute("SELECT estoque FROM produtos WHERE id = ?", (produto_id,)).fetchone()
            if produto:
                novo_estoque = produto['estoque'] - quantidade
                db.execute("UPDATE produtos SET estoque = ? WHERE id = ?", (novo_estoque, produto_id))
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        flash(f"Erro ao processar pedido: {str(e)}", "error")
        return redirect(url_for("checkout"))
    finally:
        db.close()

    # Limpar carrinho e sessões relacionadas
    session.pop("carrinho", None)
    session.pop("frete", None)
    session.pop("endereco_entrega", None)

    flash("Pedido registrado com sucesso!", "success")
    return redirect(url_for("perfil"))


@app.route("/debug_schema")
def debug_schema():
    db = get_db()
    try:
        schema = db.execute("PRAGMA table_info(pedidos)").fetchall()
        db.close()
        return jsonify([dict(col) for col in schema])
    except Exception as e:
        return f"Erro: {e}"

@app.route("/finalizar_manual")
def finalizar_manual():
    return redirect(url_for("concluir_pedido", metodo="Pago Manual"))

@app.route("/pagamento/pix")
def pagamento_pix():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    carrinho = session.get("carrinho", {})
    frete = session.get("frete", 0)
    endereco = session.get("endereco_entrega", {})

    total = sum(i["preco"] * i["quantidade"] for i in carrinho.values())
    total_final = total + (frete or 0)

    # Gerar QR Code para PIX
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=PAGAMENTO_FULLTECH_{total_final}"

    return render_template("pagamento_pix.html",
                           total_final=total_final,
                           qr_code_url=qr_code_url)

@app.route("/pagamento/boleto")
def pagamento_boleto():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    carrinho = session.get("carrinho", {})
    frete = session.get("frete", 0)
    endereco = session.get("endereco_entrega", {})

    total = sum(item["preco"] * item["quantidade"] for item in carrinho.values())
    total_final = total + (frete or 0)

    return render_template("pagamento_boleto.html", total_final=total_final)

@app.route("/pagamento/cartao", methods=["GET", "POST"])
def pagamento_cartao():
    if request.method == "POST":
        return redirect(url_for("concluir_pedido", metodo="Cartão"))
    
    return render_template("pagamento_cartao.html")

@app.route("/remover_pedido/<int:pedido_id>")
def remover_pedido(pedido_id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = get_db()

    pedido = db.execute(
        "SELECT * FROM pedidos WHERE id = ? AND usuario_id = ?",
        (pedido_id, session["usuario_id"])
    ).fetchone()

    if not pedido:
        flash("Pedido não encontrado ou não pertence a você.", "error")
        db.close()
        return redirect(url_for("perfil"))

    # Remove o pedido
    db.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
    db.commit()
    db.close()

    flash("Pedido removido do histórico com sucesso!", "success")
    return redirect(url_for("perfil"))

if __name__ == '__main__':
    if not os.path.exists(PERFIL_UPLOAD_FOLDER):
        os.makedirs(PERFIL_UPLOAD_FOLDER)
    
    default_image_path = os.path.join('static', 'img', 'perfis', 'default.png')
    if not os.path.exists(default_image_path):
        print(f"⚠️ Aviso: {default_image_path} não existe. Crie uma imagem padrão.")
        
    app.run(debug=True)