from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId
import bcrypt
import os
import uuid
from datetime import datetime

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuração da chave secreta
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# Conexão com o MongoDB
try:
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("DATABASE_NAME")]
    client.admin.command("ping")
    print("✅ MongoDB conectado com sucesso")
except Exception as e:
    print("❌ Erro ao conectar ao MongoDB:", e)
    exit(1)

# Coleções
usuarios_colecao = db["usuarios"]
eventos_colecao = db["eventos"]
pedidos_colecao = db["pedidos"]

# Função para serializar documentos do MongoDB (converter ObjectId para string)
def serializar_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc

# Rota principal
@app.route("/")
def home():
    return render_template("index.html")

# Rota para inserir eventos iniciais (seed)
@app.route("/seed-eventos", methods=["POST"])
def seed_eventos():
    try:
        if eventos_colecao.count_documents({}) > 0:
            return jsonify({"mensagem": "Eventos já cadastrados"}), 200

        eventos = [
            {
                "titulo": "Festival de Rock",
                "data": "2026-04-20",
                "local": "São Paulo",
                "imagem": "https://via.placeholder.com/300x180",
                "tipos_ingresso": [
                    {"nome": "Pista", "preco": 80, "descricao": "Acesso à pista comum"},
                    {"nome": "VIP", "preco": 150, "descricao": "Área VIP próxima ao palco"},
                    {"nome": "Backstage", "preco": 300, "descricao": "Experiência premium"}
                ]
            },
            {
                "titulo": "Show Pop Night",
                "data": "2026-05-10",
                "local": "Rio de Janeiro",
                "imagem": "https://via.placeholder.com/300x180",
                "tipos_ingresso": [
                    {"nome": "Pista", "preco": 90, "descricao": "Acesso à pista comum"},
                    {"nome": "Premium", "preco": 180, "descricao": "Área premium exclusiva"}
                ]
            },
            {
                "titulo": "Noite Eletrônica",
                "data": "2026-06-15",
                "local": "Belo Horizonte",
                "imagem": "https://via.placeholder.com/300x180",
                "tipos_ingresso": [
                    {"nome": "Pista", "preco": 70, "descricao": "Entrada padrão"},
                    {"nome": "Camarote", "preco": 220, "descricao": "Camarote com vista privilegiada"}
                ]
            }
        ]

        eventos_colecao.insert_many(eventos)
        return jsonify({"mensagem": "Eventos inseridos com sucesso"}), 201

    except Exception as e:
        return jsonify({"mensagem": f"Erro ao inserir eventos: {e}"}), 500

# Rota para cadastro de usuários
@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    try:
        dados = request.get_json()

        nome = dados.get("nome", "").strip()
        email = dados.get("email", "").strip().lower()
        senha = dados.get("senha", "")
        confirmar_senha = dados.get("confirmarSenha", "")

        if not nome or not email or not senha or not confirmar_senha:
            return jsonify({"mensagem": "Preencha todos os campos"}), 400

        if senha != confirmar_senha:
            return jsonify({"mensagem": "As senhas não coincidem"}), 400

        if len(senha) < 6:
            return jsonify({"mensagem": "A senha deve ter pelo menos 6 caracteres"}), 400

        usuario_existente = usuarios_colecao.find_one({"email": email})
        if usuario_existente:
            return jsonify({"mensagem": "Email já cadastrado"}), 400

        senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())

        usuarios_colecao.insert_one({
            "nome": nome,
            "email": email,
            "senha": senha_hash
        })

        return jsonify({"mensagem": "Usuário cadastrado com sucesso"}), 201

    except Exception as e:
        return jsonify({"mensagem": f"Erro ao cadastrar usuário: {e}"}), 500

# Rota de login
@app.route("/login", methods=["POST"])
def login():
    try:
        dados = request.get_json()
        email = dados.get("email", "").strip().lower()
        senha = dados.get("senha", "")

        if not email or not senha:
            return jsonify({"mensagem": "Informe email e senha"}), 400

        usuario = usuarios_colecao.find_one({"email": email})
        if not usuario:
            return jsonify({"mensagem": "Usuário não encontrado"}), 404

        if not bcrypt.checkpw(senha.encode("utf-8"), usuario["senha"]):
            return jsonify({"mensagem": "Senha incorreta"}), 401

        return jsonify({
            "mensagem": "Login realizado com sucesso",
            "usuario": {
                "id": str(usuario["_id"]),
                "nome": usuario["nome"],
                "email": usuario["email"]
            }
        }), 200

    except Exception as e:
        return jsonify({"mensagem": f"Erro no login: {e}"}), 500

# Rota para listar eventos
@app.route("/eventos", methods=["GET"])
def listar_eventos():
    try:
        eventos = [serializar_doc(evento) for evento in eventos_colecao.find().sort("data", 1)]
        return jsonify(eventos), 200
    except Exception as e:
        return jsonify({"mensagem": f"Erro ao buscar eventos: {e}"}), 500

# Rota para criar pedido
@app.route("/pedidos", methods=["POST"])
def criar_pedido():
    try:
        dados = request.get_json()
        email_usuario = dados.get("email_usuario", "").strip().lower()
        nome_usuario = dados.get("nome_usuario", "").strip()
        itens = dados.get("itens", [])
        total = dados.get("total", 0)

        if not email_usuario or not itens:
            return jsonify({"mensagem": "Dados do pedido inválidos"}), 400

        ingressos = []

        for item in itens:
            quantidade = int(item.get("quantidade", 0))
            for _ in range(quantidade):
                ingressos.append({
                    "codigo_ingresso": str(uuid.uuid4())[:8].upper(),
                    "evento_id": item.get("evento_id"),
                    "titulo_evento": item.get("titulo_evento"),
                    "data_evento": item.get("data_evento"),
                    "local_evento": item.get("local_evento"),
                    "tipo_ingresso": item.get("tipo_ingresso"),
                    "preco_unitario": item.get("preco_unitario"),
                    "data_compra": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

        pedido = {
            "email_usuario": email_usuario,
            "nome_usuario": nome_usuario,
            "itens": itens,
            "ingressos": ingressos,
            "total": total,
            "criado_em": datetime.now()
        }

        resultado = pedidos_colecao.insert_one(pedido)

        return jsonify({
            "mensagem": "Pedido salvo com sucesso",
            "pedido_id": str(resultado.inserted_id),
            "ingressos": ingressos
        }), 201

    except Exception as e:
        return jsonify({"mensagem": f"Erro ao criar pedido: {e}"}), 500

# Rota para listar pedidos de um usuário
@app.route("/pedidos/<email>", methods=["GET"])
def listar_pedidos(email):
    try:
        pedidos = []
        for pedido in pedidos_colecao.find({"email_usuario": email.lower()}).sort("criado_em", -1):
            pedido = serializar_doc(pedido)
            if "criado_em" in pedido:
                pedido["criado_em"] = pedido["criado_em"].strftime("%Y-%m-%d %H:%M:%S")
            pedidos.append(pedido)
        return jsonify(pedidos), 200
    except Exception as e:
        return jsonify({"mensagem": f"Erro ao buscar pedidos: {e}"}), 500

# Rota para listar ingressos de um usuário
@app.route("/ingressos/<email>", methods=["GET"])
def listar_ingressos(email):
    try:
        ingressos = []
        for pedido in pedidos_colecao.find({"email_usuario": email.lower()}):
            for ingresso in pedido.get("ingressos", []):
                ingressos.append(ingresso)
        return jsonify(ingressos), 200
    except Exception as e:
        return jsonify({"mensagem": f"Erro ao buscar ingressos: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True)