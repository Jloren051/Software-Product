from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId
import bcrypt
import os
import uuid
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DATABASE_NAME")]

users_collection = db["users"]
events_collection = db["events"]
orders_collection = db["orders"]

def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/seed-events", methods=["POST"])
def seed_events():
    if events_collection.count_documents({}) > 0:
        return jsonify({"message": "Eventos já cadastrados"}), 200

    eventos = [
        {
            "title": "Festival de Rock",
            "date": "2026-04-20",
            "location": "São Paulo",
            "image": "https://via.placeholder.com/300x180",
            "ticketTypes": [
                {"name": "Pista", "price": 80, "description": "Acesso à pista comum"},
                {"name": "VIP", "price": 150, "description": "Área VIP próxima ao palco"},
                {"name": "Backstage", "price": 300, "description": "Experiência premium"}
            ]
        },
        {
            "title": "Show Pop Night",
            "date": "2026-05-10",
            "location": "Rio de Janeiro",
            "image": "https://via.placeholder.com/300x180",
            "ticketTypes": [
                {"name": "Pista", "price": 90, "description": "Acesso à pista comum"},
                {"name": "Premium", "price": 180, "description": "Área premium exclusiva"}
            ]
        },
        {
            "title": "Noite Eletrônica",
            "date": "2026-06-15",
            "location": "Belo Horizonte",
            "image": "https://via.placeholder.com/300x180",
            "ticketTypes": [
                {"name": "Pista", "price": 70, "description": "Entrada padrão"},
                {"name": "Camarote", "price": 220, "description": "Camarote com vista privilegiada"}
            ]
        }
    ]

    events_collection.insert_many(eventos)
    return jsonify({"message": "Eventos inseridos com sucesso"}), 201

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm_password = data.get("confirmPassword", "")

    if not name or not email or not password or not confirm_password:
        return jsonify({"message": "Preencha todos os campos"}), 400

    if password != confirm_password:
        return jsonify({"message": "As senhas não coincidem"}), 400

    if len(password) < 6:
        return jsonify({"message": "A senha deve ter pelo menos 6 caracteres"}), 400

    existing_user = users_collection.find_one({"email": email})
    if existing_user:
        return jsonify({"message": "Email já cadastrado"}), 400

    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    users_collection.insert_one({
        "name": name,
        "email": email,
        "password": hashed_password
    })

    return jsonify({"message": "Usuário cadastrado com sucesso"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"message": "Informe email e senha"}), 400

    user = users_collection.find_one({"email": email})

    if not user:
        return jsonify({"message": "Usuário não encontrado"}), 404

    if not bcrypt.checkpw(password.encode("utf-8"), user["password"]):
        return jsonify({"message": "Senha incorreta"}), 401

    return jsonify({
        "message": "Login realizado com sucesso",
        "user": {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"]
        }
    }), 200

@app.route("/events", methods=["GET"])
def get_events():
    eventos = []

    for event in events_collection.find().sort("date", 1):
        event["_id"] = str(event["_id"])
        eventos.append(event)

    return jsonify(eventos), 200

@app.route("/orders", methods=["POST"])
def create_order():
    data = request.get_json()

    user_email = data.get("user_email", "").strip().lower()
    user_name = data.get("user_name", "").strip()
    items = data.get("items", [])
    total = data.get("total", 0)

    if not user_email or not items:
        return jsonify({"message": "Dados do pedido inválidos"}), 400

    tickets = []

    for item in items:
        quantity = int(item.get("quantity", 0))

        for _ in range(quantity):
            tickets.append({
                "ticket_code": str(uuid.uuid4())[:8].upper(),
                "event_id": item.get("event_id"),
                "event_title": item.get("event_title"),
                "event_date": item.get("event_date"),
                "event_location": item.get("event_location"),
                "ticket_type": item.get("ticket_type"),
                "unit_price": item.get("unit_price"),
                "purchase_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

    order = {
        "user_email": user_email,
        "user_name": user_name,
        "items": items,
        "tickets": tickets,
        "total": total,
        "created_at": datetime.now()
    }

    result = orders_collection.insert_one(order)

    return jsonify({
        "message": "Pedido salvo com sucesso",
        "order_id": str(result.inserted_id),
        "tickets": tickets
    }), 201

@app.route("/orders/<email>", methods=["GET"])
def get_orders(email):
    pedidos = []

    for order in orders_collection.find({"user_email": email.lower()}).sort("created_at", -1):
        order["_id"] = str(order["_id"])
        if "created_at" in order:
            order["created_at"] = order["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        pedidos.append(order)

    return jsonify(pedidos), 200

@app.route("/tickets/<email>", methods=["GET"])
def get_tickets(email):
    tickets = []

    for order in orders_collection.find({"user_email": email.lower()}):
        for ticket in order.get("tickets", []):
            tickets.append(ticket)

    return jsonify(tickets), 200

if __name__ == "__main__":
    app.run(debug=True)