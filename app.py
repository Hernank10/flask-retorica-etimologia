from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json
import random
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui_cambiar_en_produccion'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rhetoric.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página'

# ============================================================
# DECORADOR PARA ADMIN
# ============================================================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acceso denegado. Se requieren privilegios de administrador.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# MODELOS DE BASE DE DATOS
# ============================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_points = db.Column(db.Integer, default=0)
    nivel = db.Column(db.String(20), default='Aprendiz')
    
    respuestas = db.relationship('Respuesta', backref='usuario', lazy=True)
    progreso_categorias = db.relationship('ProgresoCategoria', backref='usuario', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Respuesta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tipo_ejercicio = db.Column(db.String(50))
    item_id = db.Column(db.Integer)
    respuesta_usuario = db.Column(db.Text)
    es_correcta = db.Column(db.Boolean, default=False)
    puntuacion = db.Column(db.Integer, default=0)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

class ProgresoCategoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    categoria = db.Column(db.String(100))
    aciertos = db.Column(db.Integer, default=0)
    intentos = db.Column(db.Integer, default=0)
    
    @property
    def porcentaje(self):
        if self.intentos == 0:
            return 0
        return round((self.aciertos / self.intentos) * 100)

# ============================================================
# CARGA DE DATOS
# ============================================================

def cargar_datos_retorica():
    ruta = os.path.join('data', 'retorica.json')
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Datos de respaldo
    return [
        {"id": 1, "name": "Anáfora", "category": "Repetición", "teoria": "Repetición de palabras al inicio de frases", "ejemplo": "¡Aquí fue Troya! ¡Aquí mi espada!", "ejercicio": "Escribe una anáfora", "suggestedAnswer": "Nunca olvidaré tu luz"}
    ]

def cargar_datos_etimologia():
    ruta = os.path.join('data', 'etimologia.json')
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    return [{"id": 1, "element": "bio", "origin": "griego", "meaning": "vida", "examples": "biología", "originalScript": "βίος", "exercise": "Crea una palabra", "evalQuestion": "¿Qué significa?", "suggestedAnswer": "vida"}]

retorica_data = cargar_datos_retorica()
etimologia_data = cargar_datos_etimologia()

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def calcular_nivel(puntos):
    if puntos < 100:
        return 'Aprendiz'
    elif puntos < 300:
        return 'Conocedor'
    elif puntos < 600:
        return 'Experto'
    else:
        return 'Maestro Retórico'

def actualizar_progreso(user_id, categoria, es_correcta):
    progreso = ProgresoCategoria.query.filter_by(user_id=user_id, categoria=categoria).first()
    if not progreso:
        progreso = ProgresoCategoria(user_id=user_id, categoria=categoria, aciertos=0, intentos=0)
        db.session.add(progreso)
    
    progreso.intentos += 1
    if es_correcta:
        progreso.aciertos += 1
    db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Context processor para inyectar current_user en todos los templates
@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# ============================================================
# RUTAS PÚBLICAS
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe', 'danger')
            return redirect(url_for('registro'))
        
        if User.query.filter_by(email=email).first():
            flash('El email ya está registrado', 'danger')
            return redirect(url_for('registro'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('¡Registro exitoso! Ahora puedes iniciar sesión', 'success')
        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash(f'¡Bienvenido de vuelta, {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Credenciales incorrectas', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('index'))

# ============================================================
# RUTAS PROTEGIDAS
# ============================================================

@app.route('/dashboard')
@login_required
def dashboard():
    total_respuestas = Respuesta.query.filter_by(user_id=current_user.id).count()
    respuestas_correctas = Respuesta.query.filter_by(user_id=current_user.id, es_correcta=True).count()
    porcentaje_total = round((respuestas_correctas / total_respuestas) * 100) if total_respuestas > 0 else 0
    
    progreso_categorias = ProgresoCategoria.query.filter_by(user_id=current_user.id).all()
    ultimas_actividades = Respuesta.query.filter_by(user_id=current_user.id).order_by(Respuesta.fecha.desc()).limit(10).all()
    
    recomendaciones = []
    categorias_bajas = [p for p in progreso_categorias if p.porcentaje < 50]
    if categorias_bajas:
        recomendaciones.append(f"📚 Practica más: {', '.join([c.categoria for c in categorias_bajas[:3]])}")
    if total_respuestas < 20:
        recomendaciones.append("🎯 ¡Comienza a resolver ejercicios para ganar puntos!")
    
    current_user.nivel = calcular_nivel(current_user.total_points)
    db.session.commit()
    
    return render_template('dashboard.html', 
                         usuario=current_user,
                         total_respuestas=total_respuestas,
                         respuestas_correctas=respuestas_correctas,
                         porcentaje_total=porcentaje_total,
                         progreso_categorias=progreso_categorias,
                         ultimas_actividades=ultimas_actividades,
                         recomendaciones=recomendaciones)

@app.route('/retorica')
@login_required
def retorica():
    return render_template('retorica.html', figuras=retorica_data)

@app.route('/etimologia')
@login_required
def etimologia():
    return render_template('etimologia.html', raices=etimologia_data)

@app.route('/examen', methods=['GET', 'POST'])
@login_required
def examen():
    if request.method == 'POST':
        tema = request.form.get('tema', 'retorica')
        num_preguntas = int(request.form.get('num_preguntas', 10))
        return render_template('examen.html', tema=tema, num_preguntas=num_preguntas)
    return render_template('examen_form.html')

# ============================================================
# RUTAS DE ADMINISTRADOR
# ============================================================

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    usuarios = User.query.all()
    total_usuarios = len(usuarios)
    total_respuestas = Respuesta.query.count()
    total_puntos = db.session.query(db.func.sum(Respuesta.puntuacion)).scalar() or 0
    
    stats_usuarios = []
    for u in usuarios:
        respuestas = Respuesta.query.filter_by(user_id=u.id).count()
        correctas = Respuesta.query.filter_by(user_id=u.id, es_correcta=True).count()
        stats_usuarios.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'total_respuestas': respuestas,
            'correctas': correctas,
            'puntos': u.total_points,
            'nivel': u.nivel,
            'is_admin': u.is_admin,
            'fecha_registro': u.created_at
        })
    
    return render_template('admin.html', 
                         usuarios=stats_usuarios,
                         total_usuarios=total_usuarios,
                         total_respuestas=total_respuestas,
                         total_puntos=total_puntos)

@app.route('/admin/usuario/<int:user_id>/toggle_admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('No puedes cambiar tus propios privilegios', 'danger')
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
        flash(f'Privilegios de {user.username} actualizados', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/usuario/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('No puedes eliminarte a ti mismo', 'danger')
    else:
        Respuesta.query.filter_by(user_id=user_id).delete()
        ProgresoCategoria.query.filter_by(user_id=user_id).delete()
        db.session.delete(user)
        db.session.commit()
        flash(f'Usuario {user.username} eliminado', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/estadisticas')
@login_required
@admin_required
def admin_estadisticas():
    respuestas_por_tipo = db.session.query(
        Respuesta.tipo_ejercicio, 
        db.func.count(Respuesta.id),
        db.func.sum(db.case((Respuesta.es_correcta == True, 1), else_=0))
    ).group_by(Respuesta.tipo_ejercicio).all()
    
    progreso_global = db.session.query(
        ProgresoCategoria.categoria,
        db.func.sum(ProgresoCategoria.aciertos),
        db.func.sum(ProgresoCategoria.intentos)
    ).group_by(ProgresoCategoria.categoria).all()
    
    return jsonify({
        'respuestas_por_tipo': [{'tipo': r[0] or 'General', 'total': r[1], 'correctas': r[2]} for r in respuestas_por_tipo],
        'progreso_global': [{'categoria': p[0], 'aciertos': p[1], 'intentos': p[2]} for p in progreso_global]
    })

# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/api/generar_preguntas', methods=['POST'])
@login_required
def api_generar_preguntas():
    data = request.json
    tema = data.get('tema', 'retorica')
    num = int(data.get('num', 10))
    fuente = retorica_data if tema == 'retorica' else etimologia_data
    
    if not fuente:
        return jsonify([])
    
    items = random.sample(fuente, min(num, len(fuente)))
    preguntas = []
    for item in items:
        if tema == 'retorica':
            respuesta = item['name']
            otros = [f for f in retorica_data if f['name'] != respuesta]
            distractores = [f['name'] for f in random.sample(otros, min(3, len(otros)))]
            pregunta_texto = f"¿Qué figura retórica es? {item['teoria'][:80]}..."
            categoria = item.get('category', 'Retórica')
        else:
            respuesta = item['element']
            otros = [r for r in etimologia_data if r['element'] != respuesta]
            distractores = [r['element'] for r in random.sample(otros, min(3, len(otros)))]
            pregunta_texto = f"¿Qué raíz significa '{item['meaning']}'?"
            categoria = 'Etimología'
        
        opciones = [respuesta] + distractores[:3]
        random.shuffle(opciones)
        preguntas.append({
            'id': item['id'],
            'pregunta': pregunta_texto,
            'respuesta_correcta': respuesta,
            'opciones': opciones,
            'categoria': categoria,
            'tema': tema
        })
    return jsonify(preguntas)

@app.route('/api/guardar_respuesta', methods=['POST'])
@login_required
def api_guardar_respuesta():
    data = request.json
    tipo = data.get('tipo', 'examen')
    item_id = data.get('item_id')
    es_correcta = data.get('es_correcta', False)
    respuesta_usuario = data.get('respuesta_usuario', '')
    categoria = data.get('categoria', 'General')
    
    puntos = 10 if es_correcta else 0
    
    respuesta = Respuesta(
        user_id=current_user.id,
        tipo_ejercicio=tipo,
        item_id=item_id,
        respuesta_usuario=respuesta_usuario,
        es_correcta=es_correcta,
        puntuacion=puntos
    )
    db.session.add(respuesta)
    
    current_user.total_points += puntos
    current_user.nivel = calcular_nivel(current_user.total_points)
    actualizar_progreso(current_user.id, categoria, es_correcta)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'puntos_ganados': puntos,
        'total_puntos': current_user.total_points,
        'nivel': current_user.nivel
    })

# ============================================================
# INICIALIZAR BASE DE DATOS
# ============================================================

with app.app_context():
    db.create_all()
    
    # Crear usuario administrador por defecto
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@rhetorica.com',
            is_admin=True,
            total_points=1000
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("=" * 50)
        print("✅ Usuario administrador creado:")
        print("   Usuario: admin")
        print("   Contraseña: admin123")
        print("=" * 50)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
