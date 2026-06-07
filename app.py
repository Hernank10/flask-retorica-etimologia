from flask import Flask, render_template, request, jsonify
import json
import random
import os

app = Flask(__name__)

def cargar_datos_retorica():
    ruta = os.path.join('data', 'retorica.json')
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def cargar_datos_etimologia():
    ruta = os.path.join('data', 'etimologia.json')
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

retorica_data = cargar_datos_retorica()
etimologia_data = cargar_datos_etimologia()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/retorica')
def retorica():
    return render_template('retorica.html', figuras=retorica_data)

@app.route('/etimologia')
def etimologia():
    return render_template('etimologia.html', raices=etimologia_data)

@app.route('/examen', methods=['GET', 'POST'])
def examen():
    if request.method == 'POST':
        tema = request.form.get('tema', 'retorica')
        num_preguntas = int(request.form.get('num_preguntas', 10))
        return render_template('examen.html', tema=tema, num_preguntas=num_preguntas)
    return render_template('examen_form.html')

@app.route('/api/generar_preguntas', methods=['POST'])
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
            pregunta_texto = f"¿Qué figura retórica se define como '{item['teoria'][:80]}...'?"
        else:
            respuesta = item['element']
            otros = [r for r in etimologia_data if r['element'] != respuesta]
            distractores = [r['element'] for r in random.sample(otros, min(3, len(otros)))]
            pregunta_texto = f"¿Qué raíz grecolatina significa '{item['meaning']}'?"
        
        opciones = [respuesta] + distractores
        random.shuffle(opciones)
        preguntas.append({
            'pregunta': pregunta_texto,
            'respuesta_correcta': respuesta,
            'opciones': opciones
        })
    return jsonify(preguntas)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
