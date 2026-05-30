import os
import hashlib
import time
import pandas as pd
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from datetime import datetime
import smtplib
import random
from email.mime.text import MIMEText
from typing import Dict, TypedDict

app = FastAPI(title="Nexus Médico Nacional - EUS 2026")

# --- 1. SEGURIDAD Y CONFIGURACIÓN ---

# Usamos variables de entorno para evitar dejar contraseñas expuestas en producción.
EMAIL_SISTEMA = os.getenv("EMAIL_SISTEMA", "raffael.recf@gmail.com")
PASS_APLICACION = os.getenv("PASS_APLICACION", "twsjmckqpzgtqgzs")

# Llave médica por defecto (Hash SHA-256 de tu contraseña de médico)
LLAVE_MEDICA_SEGURA = os.getenv("LLAVE_MEDICA_SEGURA", "5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5")
NOMBRE_MEDICO_ACTUAL = "Ramirez" 

def generar_hash(password: str) -> str:
    """Genera un hash SHA-256 seguro."""
    return hashlib.sha256(password.encode()).hexdigest()

# --- ESTRUCTURA DE RECUPERACIÓN SEGURA ---

class EstructuraCodigo(TypedDict):
    codigo: int
    expiracion: float

# Diccionario en memoria que indexa los códigos por email
codigos_recuperacion: Dict[str, EstructuraCodigo] = {}

def guardar_codigo_recuperacion(email: str, codigo: int, minutos_validez: int = 10) -> None:
    """Registra el código de recuperación para un usuario con tiempo de expiración."""
    tiempo_expiracion = time.time() + (minutos_validez * 60)
    codigos_recuperacion[email] = {
        "codigo": codigo,
        "expiracion": tiempo_expiracion
    }

def verificar_codigo_recuperacion(email: str, codigo_ingresado: int) -> bool:
    """Valida si el código es correcto, está vigente y lo consume eliminándolo de memoria."""
    if email not in codigos_recuperacion:
        return False
    
    datos_registro = codigos_recuperacion[email]
    
    # Comprobar si el token ya caducó
    if time.time() > datos_registro["expiracion"]:
        del codigos_recuperacion[email]
        return False
        
    # Comprobar coincidencia numérica
    if datos_registro["codigo"] == codigo_ingresado:
        del codigos_recuperacion[email]  # Token de un solo uso
        return True
        
    return False

# --- CARGA DE DATOS ---

def cargar_datos():
    ruta_carpeta = os.path.dirname(os.path.abspath(__file__))
    ruta_archivo = os.path.join(ruta_carpeta, "Diabetes_Mexico_FULL.csv")
    
    try:
        df = pd.read_csv(ruta_archivo)
        df.columns = df.columns.str.strip()
        print("✅ Base de datos cargada correctamente.")
        return df.fillna(0)
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: No se pudo cargar la base de datos. Detalles: {e}")
        return None

def obtener_paciente(folio: str):
    df = cargar_datos()
    if df is None:
        return None, "Error: No se pudo cargar la base de datos local."
    
    # Filtrado estricto por CURP o folio
    paciente = df[(df['folio_i'].astype(str) == folio) | (df.get('CURP', '') == folio)]
    if paciente.empty:
        return None, "Error: Paciente no encontrado."
    
    return paciente.iloc[0], None


# --- 2. MOTOR CLÍNICO MODULARIZADO ---

def evaluar_glucosa(glucosa: float):
    if glucosa < 100:
        return {
            "color_glucosa": "#22c55e",
            "clase_badge_glucosa": "success",
            "msg_glucosa": "Nivel Normal (Bajo Riesgo)",
            "desc_glucosa": f"Nivel de glucosa en ayunas óptimo ({glucosa} mg/dL). El paciente demuestra una homeostasis glucémica adecuada y una sensibilidad a la insulina preservada.",
            "consejos_glucosa": [
                "<strong>Mantenimiento continuo:</strong> Continúa con una dieta balanceada rica en fibra y carbohidratos complejos.",
                "<strong>Prevención:</strong> Prioriza fuentes de hidratación limpias como agua natural, evitando refrescos o jugos procesados."
            ],
            "medico_glucosa": {
                "estatus": "Homeostasis Glucémica Normal",
                "metas": "Mantener HbA1c < 5.7% y glucemia basal < 100 mg/dL.",
                "farmaco": "No requiere intervención farmacológica hipoglucemiante actual.",
                "monitoreo": "Tamizaje de control anual en ayunas salvo aparición de factores de riesgo."
            }
        }
    elif glucosa < 126:
        return {
            "color_glucosa": "#f59e0b",
            "clase_badge_glucosa": "warning",
            "msg_glucosa": "Prediabetes (Riesgo Moderado)",
            "desc_glucosa": f"Glucosa basal alterada en ayunas ({glucosa} mg/dL). Existe una resistencia periférica latente a la insulina y disfunción incipiente de las células beta pancreáticas.",
            "consejos_glucosa": [
                "<strong>Control de porciones:</strong> Reduce significativamente el consumo de harinas refinadas y azúcares añadidos.",
                "<strong>Movimiento estratégico:</strong> Incorpora 30 minutos diarios de caminata a paso rápido para sensibilizar receptores."
            ],
            "medico_glucosa": {
                "estatus": "Prediabetes (Intolerancia a la Glucosa Basal)",
                "metas": "Reducir peso corporal entre un 5% y 7%. Lograr glucemia basal < 100 mg/dL.",
                "farmaco": "Evaluar uso de Metformina si coexiste con IMC > 35 kg/m² o edad < 60 años.",
                "monitoreo": "Hemoglobina Glicosilada (HbA1c) y perfil lipídico cada 6 meses."
            }
        }
    else:
        return {
            "color_glucosa": "#ef4444",
            "clase_badge_glucosa": "danger",
            "msg_glucosa": "Diabetes (Riesgo Alto)",
            "desc_glucosa": f"Hiperglucemia franca en ayunas ({glucosa} mg/dL) compatible con criterios diagnósticos de Diabetes Mellitus. El umbral renal está comprometido.",
            "consejos_glucosa": [
                "<strong>Atención Médica Urgente:</strong> Es prioritario que agendes una consulta de seguimiento para evaluación farmacológica.",
                "<strong>Monitoreo estricto:</strong> Elimina por completo carbohidratos de alto índice glucémico."
            ],
            "medico_glucosa": {
                "estatus": "Diabetes Mellitus Establecida",
                "metas": "Alcanzar HbA1c < 7.0%, glucemia preprandial de 80-130 mg/dL.",
                "farmaco": "Iniciar o ajustar monoterapia/terapia combinada (Metformina como primera línea).",
                "monitoreo": "Automonitoreo capilar diario y examen de microalbuminuria trimestral."
            }
        }

def evaluar_trigliceridos(trig: float):
    if trig < 150:
        return {
            "color_trig": "#22c55e",
            "clase_badge_trig": "success",
            "msg_trig": "Perfil Lipídico Óptimo",
            "desc_trig": f"Triglicéridos basales en rango protector ({trig} mg/dL). Bajo riesgo cinético de ateroesclerosis.",
            "consejos_trig": ["<strong>Grasas buenas:</strong> Sigue consumiendo grasas saludables como aguacate e integrales."],
            "medico_trig": "Fracción lipídica controlada. Mantener hábitos dietéticos vigentes."
        }
    elif trig < 200:
        return {
            "color_trig": "#f59e0b",
            "clase_badge_trig": "warning",
            "msg_trig": "Límite Alto de Riesgo",
            "desc_trig": f"Hipertrigliceridemia limítrofe ({trig} mg/dL). Sugiere sobrecarga metabólica por hidratos de carbono refinados.",
            "consejos_trig": ["<strong>Grasas saturadas:</strong> Modera el consumo de carnes rojas grasas, embutidos y fritos."],
            "medico_trig": "Alerta lipídica. Priorizar modificaciones terapéuticas en el estilo de vida (MTEV)."
        }
    else:
        return {
            "color_trig": "#ef4444",
            "clase_badge_trig": "danger",
            "msg_trig": "Hipertrigliceridemia Severa",
            "desc_trig": f"Concentración de triglicéridos críticamente elevada ({trig} mg/dL). Incrementa el riesgo de pancreatitis aguda.",
            "consejos_trig": [
                "<strong>Omisión de alcohol y azúcares:</strong> El alcohol y los dulces elevan drásticamente este indicador.",
                "<strong>Omega-3 y Fibra:</strong> Incrementa el consumo de pescados azules y suplementación médica."
            ],
            "medico_trig": "Riesgo Cardiovascular Alto. Considerar Fibratos de manera inmediata para suprimir riesgo de pancreatitis."
        }

def evaluar_perfil_clinico(glucosa: float, trig: float):
    res_glucosa = evaluar_glucosa(glucosa)
    res_trig = evaluar_trigliceridos(trig)
    return {**res_glucosa, **res_trig}


# --- 3. COMPONENTES VISUALES Y REUTILIZACIÓN (CSS GLOBAL) ---

def obtener_css_base():
    return """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --hospital-blue: #003366; --hospital-cyan: #00a3ad; --bg-light: #f1f5f9; --text-main: #334155; --nexus-blue: #1a56db; }
        body { font-family: 'Inter', sans-serif; background: var(--bg-light); margin: 0; color: var(--text-main); }
        .exam-gallery { display: flex; gap: 15px; justify-content: center; margin-top: 20px; flex-wrap: wrap; }
        .exam-item { position: relative; cursor: pointer; transition: transform 0.3s; }
        .exam-item:hover { transform: scale(1.1); }
        .exam-item img { width: 80px; height: 80px; border-radius: 50%; border: 3px solid var(--nexus-blue); object-fit: cover; background: white; padding: 5px; }
        .tooltip-box { visibility: hidden; width: 200px; background-color: #0f172a; color: #fff; text-align: center; border-radius: 8px; padding: 10px; position: absolute; z-index: 10; bottom: 125%; left: 50%; margin-left: -100px; opacity: 0; transition: opacity 0.3s; font-size: 0.75rem; box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
        .exam-item:hover .tooltip-box { visibility: visible; opacity: 1; }
        .hero-diabetes { width: 100%; height: 250px; object-fit: cover; border-radius: 15px; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        .header-nexus { background: #0a1f2d; padding: 30px; text-align: center; border-bottom: 4px solid var(--hospital-cyan); }
        .container { max-width: 1200px; margin: auto; padding: 40px 20px; }
        .card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); margin-bottom: 25px; border: 1px solid #e2e8f0; }
        .input-nexus { width: 100%; padding: 12px; margin-bottom: 15px; border-radius: 6px; border: 1px solid #cbd5e1; box-sizing: border-box; }
        .btn-nexus { padding: 14px; border-radius: 8px; border: none; font-weight: 700; cursor: pointer; width: 100%; text-transform: uppercase; text-align: center; text-decoration: none; display: block; }
        .btn-blue { background: #2563eb; color: white; }
        .btn-dark { background: #0f172a; color: white; }
        .btn-cyan { background: var(--hospital-cyan); color: white; }
        .advice-tag { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; margin-bottom: 5px; }
    </style>
    """


# --- 4. ENDPOINTS BASE ---

@app.get("/logo_nexus")
async def get_logo():
    if os.path.exists("LogoDePP.png"):
        return FileResponse("LogoDePP.png")
    return {"error": "Logo no encontrado"}

@app.get("/", response_class=HTMLResponse)
async def home():
    img_diabetes_hero = "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&q=80&w=800"
    examenes = [
        {"img": "https://cdn-icons-png.flaticon.com/512/2864/2864344.png", "title": "Glucosa", "info": "Mide azúcar en ayunas. Normal: <100 mg/dL."},
        {"img": "https://cdn-icons-png.flaticon.com/512/3022/3022570.png", "title": "HbA1c", "info": "Promedio de 3 meses. Meta: <5.7%."},
        {"img": "https://cdn-icons-png.flaticon.com/512/822/822143.png", "title": "Insulina", "info": "Hormona clave para procesar energía."},
        {"img": "https://cdn-icons-png.flaticon.com/512/2491/2491295.png", "title": "Lípidos", "info": "Control de colesterol y triglicéridos."}
    ]
    exam_html = "".join([f'<div class="exam-item"><img src="{ex["img"]}"><div class="tooltip-box"><b>{ex["title"]}</b><br>{ex["info"]}</div></div>' for ex in examenes])

    return f"""
    
    <html><head><title>Nexus Médico</title>{obtener_css_base()}</head>
    <body>
        <div class='header-nexus'>
            <img src='/logo_nexus' style='height:80px; margin-bottom:10px;' onerror="this.style.display='none'">
            <h1 style='color:white; margin:0;'>NEXUS MÉDICO NACIONAL</h1>
        </div>
        <div class='container'>
            <img src="{img_diabetes_hero}" class="hero-diabetes">
            <div style="text-align:center; margin-bottom:40px;">
                <h2 style="color:var(--hospital-blue);">Glosario de Inteligencia Clínica</h2>
                <div class="exam-gallery">{exam_html}</div>
            </div>
            <div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:20px;'>
                <div class='card'>
                    <h3>Registro</h3>
                    <form action='/registro/medico' method='post'>
                        <input type='text' name='nombre' placeholder='Nombre' required class='input-nexus'>
                        <input type='text' name='cedula' placeholder='Cédula' required class='input-nexus'>
                        <input type='password' name='nueva_llave' placeholder='Contraseña' required class='input-nexus'>
                        <button class='btn-nexus btn-blue'>Registrar</button>
                    </form>
                </div>
               <div class='card'>
                    <h3>Acceso Médico</h3>
                    <form action='/login/medico' method='post'>
                        <input type='password' name='llave' placeholder='Contraseña Médica' required class='input-nexus'>
                        <input type='text' name='folio' placeholder='CURP o Folio del Paciente' required class='input-nexus'>
                        <button class='btn-nexus btn-dark'>Acceder a Expediente</button>
                        <div style="margin-top:15px; text-align: center;">
                            <a href="/olvide_password" style="color: #4b5563; font-size: 0.85rem; text-decoration: none; font-weight: 600;">
                                <i class="fas fa-key"></i> ¿Olvidaste tu contraseña?
                            </a>
                        </div>
                    </form>
                </div>
                <div class='card'>
                    <h3>Paciente</h3>
                    <form action='/login/paciente' method='post'>
                        <input type='text' name='folio' placeholder='CURP' required class='input-nexus'>
                        <button class='btn-nexus btn-cyan'>Ver Resultados</button>
                    </form>
                </div>
            </div>
            <div id="aviso-banner" 
     style="background: #1e293b; color: #f1f5f9; padding: 15px; position: fixed; bottom: 0; left: 0; 
            width: 100%; z-index: 9999; display: flex; justify-content: center; align-items: center; 
            gap: 15px; border-top: 1px solid #334155; font-family: sans-serif;">
    
    <span style="font-size: 0.9rem;">NEXUS utiliza datos para fines estrictamente clínicos.</span>
    
    <a href="/aviso-privacidad" 
       style="color: #cbd5e1; text-decoration: underline; font-size: 0.9rem; font-weight: bold;">
       Ver Aviso de Privacidad
    </a>

    <button onclick="document.getElementById('aviso-banner').style.display='none'" 
            style="background: #334155; border: none; color: white; padding: 5px 12px; 
                   cursor: pointer; border-radius: 4px; font-size: 0.8rem; margin-left: 10px;">
        Entendido
    </button>
</div>
        </div>
    </body></html>
    """


# --- VISTA PARA SOLICITAR CÓDIGO DE RECUPERACIÓN ---

@app.get("/olvide_password", response_class=HTMLResponse)
async def olvide_password():
    return f"""
    <html><head><title>Recuperar Contraseña</title>{obtener_css_base()}</head>
    <body>
        <div class="container" style="max-width: 500px; margin-top: 100px;">
            <div class="card">
                <h3 style="text-align: center;"><i class="fas fa-unlock-alt" style="color: #2563eb;"></i> Recuperar Contraseña</h3>
                <p style="font-size: 0.85rem; color: #4b5563; margin-bottom: 20px; text-align: center;">
                    Ingresa tu correo registrado para recibir un código de verificación de un solo uso.
                </p>
                <form action="/enviar_codigo" method="post">
                    <input type="email" name="email" placeholder="correo@ejemplo.com" required class="input-nexus">
                    <button type="submit" class="btn-nexus btn-blue">Enviar Código</button>
                </form>
                <div style="text-align: center; margin-top: 15px;">
                    <a href="/" style="color: #64748b; text-decoration: none; font-size: 0.85rem;"><i class="fas fa-arrow-left"></i> Volver al Inicio</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


# --- 5. ENDPOINTS DE RECUPERACIÓN DE CONTRASEÑA ---

@app.post("/enviar_codigo", response_class=HTMLResponse)
async def enviar_codigo(email: str = Form(...)):
    # Generamos un código numérico único para este email
    nuevo_codigo = random.randint(100000, 999999)
    guardar_codigo_recuperacion(email, nuevo_codigo)
    
    try:
        # Crear mensaje de correo electrónico
        msg = MIMEText(f"Tu código de recuperación de un solo uso es: {nuevo_codigo}\n\nEste código vencerá automáticamente en 10 minutos.")
        msg['Subject'] = "Código de Recuperación de Credenciales - Nexus"
        msg['From'] = EMAIL_SISTEMA
        msg['To'] = email

        # Envío seguro mediante TLS en el puerto 587
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_SISTEMA, PASS_APLICACION)
            server.send_message(msg)
            
        return f"""
        <html><head><title>Verificar Código</title>{obtener_css_base()}</head>
        <body>
            <div class="container" style="max-width: 500px; margin-top: 100px;">
                <div class="card">
                    <h3><i class="fas fa-shield-alt" style="color: #10b981;"></i> Código Enviado</h3>
                    <p style="font-size:0.85rem; color:#4b5563; margin-bottom: 20px;">
                        Hemos enviado un código a <b>{email}</b>. Ingresa el código y tu nueva clave abajo.
                    </p>
                    <form action="/verificar_codigo" method="post">
                        <!-- Pasamos el correo de forma oculta para validar al destinatario correcto -->
                        <input type="hidden" name="email" value="{email}">
                        <input type="text" name="code" placeholder="Código de 6 dígitos" required class="input-nexus" style="text-align:center; font-size: 1.2rem; letter-spacing: 5px;">
                        <input type="password" name="new_pass" placeholder="Nueva Contraseña" required class="input-nexus">
                        <button type="submit" class="btn-nexus btn-blue">Actualizar Contraseña</button>
                    </form>
                </div>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html><head><title>Error</title>{obtener_css_base()}</head>
        <body>
            <div class="container" style="max-width: 500px; margin-top: 100px;">
                <div class="card" style="border-top: 5px solid #ef4444;">
                    <h3 style="color:#ef4444;"><i class="fas fa-exclamation-triangle"></i> Error de Conexión</h3>
                    <p style="font-size: 0.9rem;">No pudimos conectar con el servidor de correos para enviar el token. Detalles del error:</p>
                    <pre style="background: #f1f5f9; padding: 10px; border-radius: 6px; font-size: 0.8rem; overflow-x: auto;">{str(e)}</pre>
                    <a href="/olvide_password" class="btn-nexus btn-dark" style="margin-top: 15px;">Intentar de Nuevo</a>
                </div>
            </div>
        </body>
        </html>
        """

@app.post("/verificar_codigo", response_class=HTMLResponse)
async def verificar_codigo(email: str = Form(...), code: str = Form(...), new_pass: str = Form(...)):
    try:
        codigo_num = int(code.strip())
    except ValueError:
        return f"<html><head>{obtener_css_base()}</head><body><div class='container'><div class='card' style='border-top:5px solid #ef4444;'><h3>Error</h3><p>El formato del código no es válido.</p><a href='/olvide_password' class='btn-nexus btn-dark'>Regresar</a></div></div></body></html>"

    if verificar_codigo_recuperacion(email, codigo_num):
        global LLAVE_MEDICA_SEGURA
        LLAVE_MEDICA_SEGURA = generar_hash(new_pass)
        return f"""
        <html><head><meta http-equiv='refresh' content='4;url=/' />{obtener_css_base()}</head>
        <body>
            <div class="container" style="max-width: 500px; margin-top: 100px;">
                <div class="card" style="border-top: 5px solid #10b981; text-align: center;">
                    <h2 style="color: #10b981;"><i class="fas fa-check-circle"></i> Cambio Exitoso</h2>
                    <p>Tu contraseña ha sido actualizada correctamente.</p>
                    <p style="font-size: 0.8rem; color:#64748b;">Serás redirigido al portal médico en unos segundos...</p>
                    <a href="/" class="btn-nexus btn-blue" style="margin-top: 15px;">Ir al Inicio</a>
                </div>
            </div>
        </body>
        </html>
        """
    
    return f"""
    <html><head>{obtener_css_base()}</head>
    <body>
        <div class="container" style="max-width: 500px; margin-top: 100px;">
            <div class="card" style="border-top: 5px solid #ef4444; text-align: center;">
                <h3 style="color: #ef4444;"><i class="fas fa-times-circle"></i> Error de Validación</h3>
                <p>El código es incorrecto, ya caducó o no pertenece a tu sesión.</p>
                <a href="/olvide_password" class="btn-nexus btn-dark" style="margin-top: 15px;">Solicitar Nuevo Código</a>
            </div>
        </div>
    </body>
    </html>
    """


# --- REGISTRO MÉDICO ---

@app.post("/registro/medico", response_class=HTMLResponse)
async def registro_medico(nombre: str = Form(...), cedula: str = Form(...), nueva_llave: str = Form(...)):
    global LLAVE_MEDICA_SEGURA, NOMBRE_MEDICO_ACTUAL
    LLAVE_MEDICA_SEGURA = generar_hash(nueva_llave)
    NOMBRE_MEDICO_ACTUAL = nombre
    return f"<html><head><meta http-equiv='refresh' content='4;url=/' />{obtener_css_base()}</head><body><div class='container' style='text-align:center; padding-top:100px;'><div class='card' style='max-width:500px; margin:auto; border-top: 5px solid #10b981;'><h2 style='color:#10b981;'>¡Registro Exitoso!</h2><p>Bienvenido, <b>Dr. {nombre}</b>.</p></div></div></body></html>"


# --- ACCESO MÉDICO DIRECTO AL EXPEDIENTE DE PACIENTE ESPECÍFICO ---

@app.post("/login/medico", response_class=HTMLResponse)
async def login_medico(llave: str = Form(...), folio: str = Form(...)):
    # 1. Validar la credencial de acceso del médico de forma segura
    if generar_hash(llave) != LLAVE_MEDICA_SEGURA:
        return HTMLResponse(
            content=f"""
            <html><head>{obtener_css_base()}</head>
            <body>
                <div class="container" style="max-width: 500px; margin-top: 100px;">
                    <div class="card" style="border-top: 5px solid #ef4444; text-align: center;">
                        <h3 style="color: #ef4444;"><i class="fas fa-lock"></i> Acceso Denegado</h3>
                        <p>La contraseña médica proporcionada es incorrecta o no tiene los permisos suficientes.</p>
                        <a href="/" class="btn-nexus btn-dark" style="margin-top: 15px;">Volver a Intentar</a>
                    </div>
                </div>
            </body>
            </html>
            """, 
            status_code=403
        )
    
    # 2. Intentar buscar inmediatamente al paciente solicitado en la base de datos
    p_data, err = obtener_paciente(folio.strip())
    if err:
        return HTMLResponse(
            content=f"""
            <html><head>{obtener_css_base()}</head>
            <body>
                <div class="container" style="max-width: 500px; margin-top: 100px;">
                    <div class="card" style="border-top: 5px solid #f59e0b; text-align: center;">
                        <h3 style="color: #f59e0b;"><i class="fas fa-user-slash"></i> Paciente No Encontrado</h3>
                        <p>Las credenciales del Dr. <b>{NOMBRE_MEDICO_ACTUAL}</b> son correctas, pero la CURP o Folio <b>"{folio}"</b> no existe en nuestra base epidemiológica activa.</p>
                        <a href="/" class="btn-nexus btn-dark" style="margin-top: 15px;">Regresar al Menú</a>
                    </div>
                </div>
            </body>
            </html>
            """,
            status_code=404
        )
    
    # 3. Si el médico se identificó con éxito y el paciente existe, renderizamos el expediente directamente.
    glucosa = float(p_data.get('glu_suero', 0))
    trig = float(p_data.get('trig', 0))
    ctx = evaluar_perfil_clinico(glucosa, trig)

    CSS_PREMIUM_SPA = """
    <style>
    *{ margin:0; padding:0; box-sizing:border-box; }
    body{ font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background:#f1f5f9; display:flex; color:#334155; }
    
    /* Sidebar Fija */
    .sidebar{ width:260px; min-height:100vh; background:#0f172a; color:white; padding:25px; position:fixed; z-index: 100; }
    .sidebar h2{ font-size:24px; margin-bottom:30px; font-weight:800; color:#38bdf8; letter-spacing:1px; display:flex; align-items:center; gap:10px;}
    .sidebar a{ display:flex; align-items:center; gap:12px; color:#cbd5e1; text-decoration:none; padding:12px; border-radius:10px; margin-bottom:8px; transition:.2s; font-size:0.9rem; cursor:pointer;}
    .sidebar a:hover{ background:#1e293b; color:white; }
    .sidebar a.active{ background:#2563eb; color:white; border-left:4px solid #38bdf8; font-weight:600; }
    
    /* Contenedor Principal */
    .main{ margin-left:260px; width:100%; padding:30px; background:#f8fafc; min-height:100vh; }
    
    /* Secciones SPA */
    .seccion { display: none; animation: fadeIn 0.3s ease-in-out; }
    .seccion.active-sec { display: block; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

    .header{ background:white; padding:24px; border-radius:16px; margin-bottom:24px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); display:flex; justify-content:space-between; align-items:center; border:1px solid #e2e8f0; }
    .header h1 { font-size: 1.6rem; color: #1e3a8a; font-weight: 800; }
    .header p { color: #64748b; font-size: 0.9rem; margin-top: 2px; }
    
    .print-btn { padding:12px 18px; background:#2563eb; color:white; border:none; border-radius:10px; cursor:pointer; font-weight:bold; display:flex; align-items:center; gap:8px; font-size:0.85rem; transition: 0.2s; }
    .print-btn:hover { background: #1d4ed8; }
    
    .patient-card{ background:white; border-radius:16px; padding:25px; display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:24px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); border:1px solid #e2e8f0; }
    .patient-card h2 { font-size:1.4rem; color:#0f172a; margin-bottom:12px; font-weight:700;}
    .patient-card p { font-size:0.9rem; margin-bottom:8px; color:#475569;}
    
    .card{ background:white; border-radius:16px; padding:24px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom:24px; border:1px solid #e2e8f0; page-break-inside: avoid; }
    .card h2, .card h3 { font-size:1.2rem; color:#1e293b; margin-bottom:16px; font-weight:700; display:flex; align-items:center; gap:8px; }
    
    .stats{ display:grid; grid-template-columns:repeat(5,1fr); gap:15px; margin-bottom:24px; }
    .stat-box{ background:white; padding:20px; border-radius:16px; text-align:center; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); border:1px solid #e2e8f0; }
    .stat-box h3{ font-size:1.8rem; color:#2563eb; margin-bottom:4px; font-weight:800; }
    .stat-box p{ font-size:0.8rem; color:#64748b; font-weight:600; text-transform:uppercase; }
    
    .table{ width:100%; border-collapse:collapse; font-size:0.9rem; }
    .table th{ background:#f1f5f9; padding:14px; text-align:left; color:#475569; font-weight:700; border-bottom:2px solid #e2e8f0; }
    .table td{ padding:14px; border-bottom:1px solid #e2e8f0; color:#334155; }
    
    .badge{ padding:5px 12px; border-radius:30px; font-size:11px; font-weight:700; display:inline-block; text-transform:uppercase; }
    .success{ background:#dcfce7; color:#166534; }
    .warning{ background:#fef3c7; color:#92400e; }
    .danger{ background:#fee2e2; color:#991b1b; }
    
    @media print {
        @page { size: A4; margin: 10mm; }
        .sidebar, .print-btn { display: none !important; }
        .main { margin: 0 !important; padding: 0 !important; width: 100% !important; display: block !important; }
        .seccion { display: block !important; opacity: 1 !important; visibility: visible !important; margin-top: 0 !important; page-break-inside: auto !important; }
        * { page-break-after: auto !important; }
        .card, .patient-card { page-break-inside: avoid !important; margin-bottom: 10px !important; }
        .header h1 { font-size: 1.2rem !important; margin: 0 !important; }
    }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    """

    sidebar_html = """
    <div class="sidebar">
        <h2><i class="fas fa-heartbeat"></i> NEXUS</h2>
        <a onclick="mostrar('resumen')" class="active"><i class="fas fa-chart-pie"></i> Resumen</a>
        <a onclick="mostrar('consultas')"><i class="fas fa-user-md"></i> Consultas</a>
        <a onclick="mostrar('laboratorio')"><i class="fas fa-flask"></i> Laboratorios</a>
        <a onclick="mostrar('recetas')"><i class="fas fa-file-prescription"></i> Recetas</a>
        <a onclick="mostrar('historial')"><i class="fas fa-history"></i> Historial Clínico</a>
        <a onclick="mostrar('signos')"><i class="fas fa-vitals"></i> Signos Vitales</a>
        <a onclick="mostrar('medicamentos')"><i class="fas fa-pills"></i> Medicamentos</a>
        <hr style="border:0; border-top:1px solid #1e293b; margin:20px 0;">
        <a href="/"><i class="fas fa-sign-out-alt"></i> Cerrar Sesión</a>
    </div>
    """

    header_html = f"""
    <div class="header">
        <div>
            <h1>EXPEDIENTE CLÍNICO ÚNICO</h1>
            <p>Hospital Nexus • Sesión del <b>Dr. {NOMBRE_MEDICO_ACTUAL}</b></p>
        </div>
        <div style="display: flex; gap: 10px;">
            
            <button onclick="window.print()" class="print-btn">
                <i class="fas fa-download"></i> Descargar Expediente
            </button>
        </div>
    </div>
    """

    patient_card_html = f"""
    <div class="patient-card">
        <div>
            <h2><i class="fas fa-user-injured" style="color:#2563eb;"></i> {p_data.get('nombre_completo', 'Usuario')}</h2>
            <p><b>CURP:</b> {p_data.get('CURP', folio)}</p>
            <p><b>Sexo:</b> {p_data.get('sexo', 'N/A').upper()}</p>
            <p><b>Edad:</b> {p_data.get('edad', '45')} años</p>
            <p><b>NSS:</b> {p_data.get('nss', '123456789')}</p>
        </div>
        <div style="border-left: 1px solid #e2e8f0; padding-left: 20px;">
            <h3 style="margin-bottom:10px; color:#475569;"><i class="fas fa-hospital-user"></i> Contexto Institucional</h3>
            <p><b>Folio Registro:</b> {p_data.get('folio_i', 'N/A')}</p>
            <p><b>Unidad:</b> {p_data.get('unidad_medica', 'Clínica de Especialidades')}</p>
            <p><b>Médico a Cargo:</b> Dr. {NOMBRE_MEDICO_ACTUAL}</p>
            <p><b>Estatus Metabólico:</b> <span class="badge {ctx['clase_badge_glucosa']}">{ctx['msg_glucosa']}</span></p>
        </div>
    </div>
    """

    stats_html = """
    <div class="stats">
        <div class="stat-box"><h3>12</h3><p>Consultas</p></div>
        <div class="stat-box"><h3>1</h3><p>Hospitalizaciones</p></div>
        <div class="stat-box"><h3>2</h3><p>Urgencias</p></div>
        <div class="stat-box"><h3>8</h3><p>Estudios</p></div>
        <div class="stat-box"><h3>3</h3><p>Procedimientos</p></div>
    </div>
    """

    modulo_consultas = f"""
    <div class="card">
        <h2><i class="fas fa-calendar-check" style="color:#10b981;"></i> Registro Histórico de Consultas Médicas</h2>
        <table class="table">
            <thead>
                <tr><th>Fecha</th><th>Especialista</th><th>Motivo Clínico</th><th>Estatus</th></tr>
            </thead>
            <tbody>
                <tr><td>20/05/2026</td><td>Dr. {NOMBRE_MEDICO_ACTUAL}</td><td>Control Semestral de Glucemia</td><td><span class="badge success">Completada</span></td></tr>
                <tr><td>14/01/2026</td><td>Dr. {NOMBRE_MEDICO_ACTUAL}</td><td>Ajuste Lipídico Inicial</td><td><span class="badge success">Completada</span></td></tr>
            </tbody>
        </table>
    </div>
    """

    modulo_laboratorios = f"""
    <div class="card">
        <h2><i class="fas fa-flask" style="color:#00a3ad;"></i> Módulo Analítico de Laboratorio</h2>
        <table class="table">
            <thead>
                <tr><th>Estudio</th><th>Resultado Basal</th><th>Estratificación Automática</th><th>Estado Analítico</th></tr>
            </thead>
            <tbody>
                <tr><td><b>Glucosa en Suero</b></td><td>{glucosa} mg/dL</td><td><span class="badge {ctx['clase_badge_glucosa']}">{ctx['msg_glucosa']}</span></td><td><span class="badge success">Procesado</span></td></tr>
                <tr><td><b>Triglicéridos</b></td><td>{trig} mg/dL</td><td><span class="badge {ctx['clase_badge_trig']}">{ctx['msg_trig']}</span></td><td><span class="badge success">Procesado</span></td></tr>
            </tbody>
        </table>
        <div style="margin-top:20px; display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
            <div style="background:#f8fafc; padding:15px; border-radius:12px; border:1px solid #e2e8f0; border-left:5px solid {ctx['color_glucosa']};">
                <h4 style="color:#1e3a8a; margin-bottom:6px;"><i class="fas fa-info-circle"></i> Análisis Glucosa</h4>
                <p style="font-size:0.85rem; line-height:1.4; color:#475569;">{ctx['desc_glucosa']}</p>
            </div>
            <div style="background:#f8fafc; padding:15px; border-radius:12px; border:1px solid #e2e8f0; border-left:5px solid {ctx['color_trig']};">
                <h4 style="color:#7c2d12; margin-bottom:6px;"><i class="fas fa-heartbeat"></i> Análisis Triglicéridos</h4>
                <p style="font-size:0.85rem; line-height:1.4; color:#475569;">{ctx['desc_trig']}</p>
            </div>
        </div>
    </div>
    """

    modulo_recetas = """
    <div class="card">
        <h2><i class="fas fa-file-prescription" style="color:#eab308;"></i> Recetas Médicas Emitidas</h2>
        <table class="table">
            <thead>
                <tr><th>Principio Activo</th><th>Dosificación</th><th>Periodicidad</th><th>Instrucciones</th></tr>
            </thead>
            <tbody>
                <tr><td><b>Metformina</b></td><td>850 mg</td><td>Cada 12 horas</td><td>Administrar junto con los alimentos principales.</td></tr>
                <tr><td><b>Atorvastatina</b></td><td>20 mg</td><td>Cada 24 horas</td><td>Toma nocturna sugerida de manera indefinida.</td></tr>
            </tbody>
        </table>
    </div>
    """

    modulo_historial = """
    <div class="card">
        <h2><i class="fas fa-notes-medical" style="color:#6b21a8;"></i> Antecedentes e Historial Clínico Integral</h2>
        <div style="background:#f8fafc; padding:20px; border-radius:10px; font-size:0.9rem; line-height:1.6; color:#475569;">
            <p><b>Antecedentes Patológicos:</b> Diagnóstico confirmado de alteraciones metabólicas en carbohidratos. Predisposición sistémica a dislipidemia mixta.</p>
            <p style="margin-top:10px;"><b>Notas Generales:</b> Paciente cooperativo. Refiere apego parcial a lineamientos nutricionales previos. Requiere reforzamiento en actividad física regular.</p>
        </div>
    </div>
    """

    modulo_signos = """
    <div class="card">
        <h2><i class="fas fa-heartbeat" style="color:#ef4444;"></i> Última Toma de Signos Vitales</h2>
        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:15px; margin-top:10px;">
            <div style="background:#fee2e2; padding:15px; border-radius:12px; text-align:center;">
                <h4 style="color:#991b1b; font-size:1.3rem;">120/80</h4><p style="font-size:0.75rem; color:#b91c1c;">Tensión Arterial (mmHg)</p>
            </div>
            <div style="background:#e0f2fe; padding:15px; border-radius:12px; text-align:center;">
                <h4 style="color:#0369a1; font-size:1.3rem;">72</h4><p style="font-size:0.75rem; color:#0369a1;">Frecuencia Cardiaca (lpm)</p>
            </div>
            <div style="background:#e2e8f0; padding:15px; border-radius:12px; text-align:center;">
                <h4 style="color:#334155; font-size:1.3rem;">36.5 °C</h4><p style="font-size:0.75rem; color:#475569;">Temperatura Corporal</p>
            </div>
            <div style="background:#dcfce7; padding:15px; border-radius:12px; text-align:center;">
                <h4 style="color:#166534; font-size:1.3rem;">18</h4><p style="font-size:0.75rem; color:#14532d;">Frec. Respiratoria (rpm)</p>
            </div>
        </div>
    </div>
    """

    modulo_medicamentos = """
    <div class="card">
        <h2><i class="fas fa-capsules" style="color:#ec4899;"></i> Conciliación de Medicamentos Activos</h2>
        <ul style="margin-left:20px; font-size:0.95rem; color:#475569; line-height:2;">
            <li><i class="fas fa-check-circle" style="color:#10b981;"></i> Metformina (Fármaco de control glucémico de primera elección)</li>
            <li><i class="fas fa-check-circle" style="color:#10b981;"></i> Atorvastatina (Protección endotelial y estabilización lipídica)</li>
        </ul>
    </div>
    """

    contenido_spa_html = f"""
    <div class="main">
        {header_html}

        <div id="resumen" class="seccion active-sec">
            {patient_card_html}
            {stats_html}
            {modulo_consultas}
            {modulo_laboratorios}
            {modulo_recetas}
            {modulo_historial}
            {modulo_signos}
            {modulo_medicamentos}
        </div>

        <div id="consultas" class="seccion">{modulo_consultas}</div>
        <div id="laboratorio" class="seccion">{modulo_laboratorios}</div>
        <div id="recetas" class="seccion">{modulo_recetas}</div>
        <div id="historial" class="seccion">{modulo_historial}</div>
        <div id="signos" class="seccion">{modulo_signos}</div>
        <div id="medicamentos" class="seccion">{modulo_medicamentos}</div>
    </div>
    """

    scripts_spa_html = """
    <script>
    function mostrar(id){
        let secciones = document.querySelectorAll('.seccion');
        secciones.forEach(sec => {
            sec.classList.remove('active-sec');
        });
        
        let target = document.getElementById(id);
        if(target) {
            target.classList.add('active-sec');
        }
    }

    document.querySelectorAll('.sidebar a').forEach(btn => {
        btn.addEventListener('click', function(){
            if(this.hasAttribute('onclick')) { 
                document.querySelectorAll('.sidebar a').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
            }
        });
    });
    </script>
    """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Portal Clínico Interoperable - {p_data.get('nombre_completo', folio)}</title>
        {CSS_PREMIUM_SPA}
    </head>
    <body>
        {sidebar_html}
        {contenido_spa_html}
        {scripts_spa_html}
    </body>
    </html>
    """


# --- 6. EXPEDIENTE CLÍNICO (ACCESO INDEPENDIENTE) ---

@app.get("/descargar_expediente/{folio}", response_class=HTMLResponse)
async def descargar_expediente(folio: str):
    p_data, err = obtener_paciente(folio)
    if err: return err
    
    glucosa = float(p_data.get('glu_suero', 0))
    trig = float(p_data.get('trig', 0))
    ctx = evaluar_perfil_clinico(glucosa, trig)

    CSS_PREMIUM_SPA = """
    <style>
    *{ margin:0; padding:0; box-sizing:border-box; }
    body{ font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background:#f1f5f9; display:flex; color:#334155; }
    
    /* Sidebar Fija */
    .sidebar{ width:260px; min-height:100vh; background:#0f172a; color:white; padding:25px; position:fixed; z-index: 100; }
    .sidebar h2{ font-size:24px; margin-bottom:30px; font-weight:800; color:#38bdf8; letter-spacing:1px; display:flex; align-items:center; gap:10px;}
    .sidebar a{ display:flex; align-items:center; gap:12px; color:#cbd5e1; text-decoration:none; padding:12px; border-radius:10px; margin-bottom:8px; transition:.2s; font-size:0.9rem; cursor:pointer;}
    .sidebar a:hover{ background:#1e293b; color:white; }
    .sidebar a.active{ background:#2563eb; color:white; border-left:4px solid #38bdf8; font-weight:600; }
    
    /* Contenedor Principal */
    .main{ margin-left:260px; width:100%; padding:30px; background:#f8fafc; min-height:100vh; }
    
    /* Secciones SPA */
    .seccion { display: none; animation: fadeIn 0.3s ease-in-out; }
    .seccion.active-sec { display: block; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

    .header{ background:white; padding:24px; border-radius:16px; margin-bottom:24px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); display:flex; justify-content:space-between; align-items:center; border:1px solid #e2e8f0; }
    .header h1 { font-size: 1.6rem; color: #1e3a8a; font-weight: 800; }
    .header p { color: #64748b; font-size: 0.9rem; margin-top: 2px; }
    
    .print-btn { padding:12px 18px; background:#2563eb; color:white; border:none; border-radius:10px; cursor:pointer; font-weight:bold; display:flex; align-items:center; gap:8px; font-size:0.85rem; transition: 0.2s; }
    .print-btn:hover { background: #1d4ed8; }
    
    .patient-card{ background:white; border-radius:16px; padding:25px; display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:24px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); border:1px solid #e2e8f0; }
    .patient-card h2 { font-size:1.4rem; color:#0f172a; margin-bottom:12px; font-weight:700;}
    .patient-card p { font-size:0.9rem; margin-bottom:8px; color:#475569;}
    
    .card{ background:white; border-radius:16px; padding:24px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom:24px; border:1px solid #e2e8f0; page-break-inside: avoid; }
    .card h2, .card h3 { font-size:1.2rem; color:#1e293b; margin-bottom:16px; font-weight:700; display:flex; align-items:center; gap:8px; }
    
    .stats{ display:grid; grid-template-columns:repeat(5,1fr); gap:15px; margin-bottom:24px; }
    .stat-box{ background:white; padding:20px; border-radius:16px; text-align:center; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); border:1px solid #e2e8f0; }
    .stat-box h3{ font-size:1.8rem; color:#2563eb; margin-bottom:4px; font-weight:800; }
    .stat-box p{ font-size:0.8rem; color:#64748b; font-weight:600; text-transform:uppercase; }
    
    .table{ width:100%; border-collapse:collapse; font-size:0.9rem; }
    .table th{ background:#f1f5f9; padding:14px; text-align:left; color:#475569; font-weight:700; border-bottom:2px solid #e2e8f0; }
    .table td{ padding:14px; border-bottom:1px solid #e2e8f0; color:#334155; }
    
    .badge{ padding:5px 12px; border-radius:30px; font-size:11px; font-weight:700; display:inline-block; text-transform:uppercase; }
    .success{ background:#dcfce7; color:#166534; }
    .warning{ background:#fef3c7; color:#92400e; }
    .danger{ background:#fee2e2; color:#991b1b; }
    
    /* Motor de Impresión A4 */
    @media print {
        @page { size: A4; margin: 10mm; }
        .sidebar, .print-btn { display: none !important; }
        .main { margin: 0 !important; padding: 0 !important; width: 100% !important; display: block !important; }
        .seccion { display: block !important; opacity: 1 !important; visibility: visible !important; margin-top: 0 !important; page-break-inside: auto !important; }
        * { page-break-after: auto !important; }
        .card, .patient-card { page-break-inside: avoid !important; margin-bottom: 10px !important; }
        .header h1 { font-size: 1.2rem !important; margin: 0 !important; }
    }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    """

    sidebar_html = """
    <div class="sidebar">
        <h2><i class="fas fa-heartbeat"></i> NEXUS</h2>
        <a onclick="mostrar('resumen')" class="active"><i class="fas fa-chart-pie"></i> Resumen</a>
        <a onclick="mostrar('consultas')"><i class="fas fa-user-md"></i> Consultas</a>
        <a onclick="mostrar('laboratorio')"><i class="fas fa-flask"></i> Laboratorios</a>
        <a onclick="mostrar('recetas')"><i class="fas fa-file-prescription"></i> Recetas</a>
        <a onclick="mostrar('historial')"><i class="fas fa-history"></i> Historial Clínico</a>
        <a onclick="mostrar('signos')"><i class="fas fa-vitals"></i> Signos Vitales</a>
        <a onclick="mostrar('medicamentos')"><i class="fas fa-pills"></i> Medicamentos</a>
        <hr style="border:0; border-top:1px solid #1e293b; margin:20px 0;">
        <a href="/"><i class="fas fa-sign-out-alt"></i> Salir de Base</a>
    </div>
    """

    header_html = """
    <div class="header">
        <div>
            <h1>EXPEDIENTE CLÍNICO ÚNICO</h1>
            <p>Hospital Nexus • Ecosistema Clínico Corporativo</p>
        </div>
        <button onclick="window.print()" class="print-btn">
            <i class="fas fa-download"></i> Descargar Expediente
        </button>
    </div>
    """

    patient_card_html = f"""
    <div class="patient-card">
        <div>
            <h2><i class="fas fa-user-injured" style="color:#2563eb;"></i> {p_data.get('nombre_completo', 'Usuario')}</h2>
            <p><b>CURP:</b> {p_data.get('CURP', folio)}</p>
            <p><b>Sexo:</b> {p_data.get('sexo', 'N/A').upper()}</p>
            <p><b>Edad:</b> {p_data.get('edad', '45')} años</p>
            <p><b>NSS:</b> {p_data.get('nss', '123456789')}</p>
        </div>
        <div style="border-left: 1px solid #e2e8f0; padding-left: 20px;">
            <h3 style="margin-bottom:10px; color:#475569;"><i class="fas fa-hospital-user"></i> Contexto Institucional</h3>
            <p><b>Folio Registro:</b> {p_data.get('folio_i', 'N/A')}</p>
            <p><b>Unidad:</b> {p_data.get('unidad_medica', 'Clínica de Especialidades')}</p>
            <p><b>Médico a Cargo:</b> Dr. {NOMBRE_MEDICO_ACTUAL}</p>
            <p><b>Estatus Metabólico:</b> <span class="badge {ctx['clase_badge_glucosa']}">{ctx['msg_glucosa']}</span></p>
        </div>
    </div>
    """

    stats_html = """
    <div class="stats">
        <div class="stat-box"><h3>12</h3><p>Consultas</p></div>
        <div class="stat-box"><h3>1</h3><p>Hospitalizaciones</p></div>
        <div class="stat-box"><h3>2</h3><p>Urgencias</p></div>
        <div class="stat-box"><h3>8</h3><p>Estudios</p></div>
        <div class="stat-box"><h3>3</h3><p>Procedimientos</p></div>
    </div>
    """

    modulo_consultas = f"""
    <div class="card">
        <h2><i class="fas fa-calendar-check" style="color:#10b981;"></i> Registro Histórico de Consultas Médicas</h2>
        <table class="table">
            <thead>
                <tr><th>Fecha</th><th>Especialista</th><th>Motivo Clínico</th><th>Estatus</th></tr>
            </thead>
            <tbody>
                <tr><td>20/05/2026</td><td>Dr. {NOMBRE_MEDICO_ACTUAL}</td><td>Control Semestral de Glucemia</td><td><span class="badge success">Completada</span></td></tr>
                <tr><td>14/01/2026</td><td>Dr. {NOMBRE_MEDICO_ACTUAL}</td><td>Ajuste Lipídico Inicial</td><td><span class="badge success">Completada</span></td></tr>
            </tbody>
        </table>
    </div>
    """

    modulo_laboratorios = f"""
    <div class="card">
        <h2><i class="fas fa-flask" style="color:#00a3ad;"></i> Módulo Analítico de Laboratorio</h2>
        <table class="table">
            <thead>
                <tr><th>Estudio</th><th>Resultado Basal</th><th>Estratificación Automática</th><th>Estado Analítico</th></tr>
            </thead>
            <tbody>
                <tr><td><b>Glucosa en Suero</b></td><td>{glucosa} mg/dL</td><td><span class="badge {ctx['clase_badge_glucosa']}">{ctx['msg_glucosa']}</span></td><td><span class="badge success">Procesado</span></td></tr>
                <tr><td><b>Triglicéridos</b></td><td>{trig} mg/dL</td><td><span class="badge {ctx['clase_badge_trig']}">{ctx['msg_trig']}</span></td><td><span class="badge success">Procesado</span></td></tr>
            </tbody>
        </table>
        <div style="margin-top:20px; display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
            <div style="background:#f8fafc; padding:15px; border-radius:12px; border:1px solid #e2e8f0; border-left:5px solid {ctx['color_glucosa']};">
                <h4 style="color:#1e3a8a; margin-bottom:6px;"><i class="fas fa-info-circle"></i> Análisis Glucosa</h4>
                <p style="font-size:0.85rem; line-height:1.4; color:#475569;">{ctx['desc_glucosa']}</p>
            </div>
            <div style="background:#f8fafc; padding:15px; border-radius:12px; border:1px solid #e2e8f0; border-left:5px solid {ctx['color_trig']};">
                <h4 style="color:#7c2d12; margin-bottom:6px;"><i class="fas fa-heartbeat"></i> Análisis Triglicéridos</h4>
                <p style="font-size:0.85rem; line-height:1.4; color:#475569;">{ctx['desc_trig']}</p>
            </div>
        </div>
    </div>
    """

    modulo_recetas = """
    <div class="card">
        <h2><i class="fas fa-file-prescription" style="color:#eab308;"></i> Recetas Médicas Emitidas</h2>
        <table class="table">
            <thead>
                <tr><th>Principio Activo</th><th>Dosificación</th><th>Periodicidad</th><th>Instrucciones</th></tr>
            </thead>
            <tbody>
                <tr><td><b>Metformina</b></td><td>850 mg</td><td>Cada 12 horas</td><td>Administrar junto con los alimentos principales.</td></tr>
                <tr><td><b>Atorvastatina</b></td><td>20 mg</td><td>Cada 24 horas</td><td>Toma nocturna sugerida de manera indefinida.</td></tr>
            </tbody>
        </table>
    </div>
    """

    modulo_historial = """
    <div class="card">
        <h2><i class="fas fa-notes-medical" style="color:#6b21a8;"></i> Antecedentes e Historial Clínico Integral</h2>
        <div style="background:#f8fafc; padding:20px; border-radius:10px; font-size:0.9rem; line-height:1.6; color:#475569;">
            <p><b>Antecedentes Patológicos:</b> Diagnóstico confirmado de alteraciones metabólicas en carbohidratos. Predisposición sistémica a dislipidemia mixta.</p>
            <p style="margin-top:10px;"><b>Notas Generales:</b> Paciente cooperativo. Refiere apego parcial a lineamientos nutricionales previos. Requiere reforzamiento en actividad física regular.</p>
        </div>
    </div>
    """

    modulo_signos = """
    <div class="card">
        <h2><i class="fas fa-heartbeat" style="color:#ef4444;"></i> Última Toma de Signos Vitales</h2>
        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:15px; margin-top:10px;">
            <div style="background:#fee2e2; padding:15px; border-radius:12px; text-align:center;">
                <h4 style="color:#991b1b; font-size:1.3rem;">120/80</h4><p style="font-size:0.75rem; color:#b91c1c;">Tensión Arterial (mmHg)</p>
            </div>
            <div style="background:#e0f2fe; padding:15px; border-radius:12px; text-align:center;">
                <h4 style="color:#0369a1; font-size:1.3rem;">72</h4><p style="font-size:0.75rem; color:#0369a1;">Frecuencia Cardiaca (lpm)</p>
            </div>
            <div style="background:#e2e8f0; padding:15px; border-radius:12px; text-align:center;">
                <h4 style="color:#334155; font-size:1.3rem;">36.5 °C</h4><p style="font-size:0.75rem; color:#475569;">Temperatura Corporal</p>
            </div>
            <div style="background:#dcfce7; padding:15px; border-radius:12px; text-align:center;">
                <h4 style="color:#166534; font-size:1.3rem;">18</h4><p style="font-size:0.75rem; color:#14532d;">Frec. Respiratoria (rpm)</p>
            </div>
        </div>
    </div>
    """

    modulo_medicamentos = """
    <div class="card">
        <h2><i class="fas fa-capsules" style="color:#ec4899;"></i> Conciliación de Medicamentos Activos</h2>
        <ul style="margin-left:20px; font-size:0.95rem; color:#475569; line-height:2;">
            <li><i class="fas fa-check-circle" style="color:#10b981;"></i> Metformina (Fármaco de control glucémico de primera elección)</li>
            <li><i class="fas fa-check-circle" style="color:#10b981;"></i> Atorvastatina (Protección endotelial y estabilización lipídica)</li>
        </ul>
    </div>
    """

    contenido_spa_html = f"""
    <div class="main">
        {header_html}

        <div id="resumen" class="seccion active-sec">
            {patient_card_html}
            {stats_html}
            {modulo_consultas}
            {modulo_laboratorios}
            {modulo_recetas}
            {modulo_historial}
            {modulo_signos}
            {modulo_medicamentos}
        </div>

        <div id="consultas" class="seccion">{modulo_consultas}</div>
        <div id="laboratorio" class="seccion">{modulo_laboratorios}</div>
        <div id="recetas" class="seccion">{modulo_recetas}</div>
        <div id="historial" class="seccion">{modulo_historial}</div>
        <div id="signos" class="seccion">{modulo_signos}</div>
        <div id="medicamentos" class="seccion">{modulo_medicamentos}</div>
    </div>
    """

    scripts_spa_html = """
    <script>
    function mostrar(id){
        let secciones = document.querySelectorAll('.seccion');
        secciones.forEach(sec => {
            sec.classList.remove('active-sec');
        });
        
        let target = document.getElementById(id);
        if(target) {
            target.classList.add('active-sec');
        }
    }

    document.querySelectorAll('.sidebar a').forEach(btn => {
        btn.addEventListener('click', function(){
            if(this.hasAttribute('onclick')) { 
                document.querySelectorAll('.sidebar a').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
            }
        });
    });
    </script>
    """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Portal Clínico Interoperable - {folio}</title>
        {CSS_PREMIUM_SPA}
    </head>
    <body>
        {sidebar_html}
        {contenido_spa_html}
        {scripts_spa_html}
    </body>
    </html>
    """




# --- PORTAL DEL PACIENTE (DISEÑO EMPÁTICO EMOCIONAL) ---

@app.post("/login/paciente", response_class=HTMLResponse)
async def login_paciente(folio: str = Form(...)):
    p_data, err = obtener_paciente(folio)
    if err:
        return err

    p_nombre = p_data.get('nombre_completo', 'Usuario')
    glucosa = float(p_data.get('glu_suero', 0))
    trig = float(p_data.get('trig', 0))
    ctx = evaluar_perfil_clinico(glucosa, trig)

    # Evaluación y tono amigable personalizado
    estado_general = "ESTABLE"
    color_estado = "#22c55e" # Verde
    mensaje_emocional = "¡Vas por muy buen camino! Sigue manteniendo tus hábitos saludables para cuidar de ti."
    progreso_riesgo = 25

    if glucosa >= 126 or trig >= 200:
        estado_general = "REQUIERE ATENCIÓN"
        color_estado = "#ef4444" # Rojo
        mensaje_emocional = "Tu salud metabólica necesita un poco más de atención en este momento. Pequeños cambios hoy harán una gran diferencia."
        progreso_riesgo = 85
    elif glucosa >= 100 or trig >= 150:
        estado_general = "EN OBSERVACIÓN"
        color_estado = "#f59e0b" # Naranja
        mensaje_emocional = "Tu cuerpo te está enviando señales. Hay algunos indicadores que es buena idea que vigilemos juntos."
        progreso_riesgo = 55

    # Explicación clara en lenguaje sencillo
    if glucosa < 100:
        txt_glucosa = "Excelente, tu nivel de azúcar está en un rango óptimo."
    elif glucosa < 126:
        txt_glucosa = "Tu nivel de azúcar está un poco más alto de lo recomendado. Es un gran momento para moderar porciones."
    else:
        txt_glucosa = "Tus niveles de azúcar están elevados. Es muy importante que platiques con tu médico para armar un plan."

    if trig < 150:
        txt_trig = "Tus niveles de grasa en sangre se encuentran bajo control."
    elif trig < 200:
        txt_trig = "Tus triglicéridos están en el límite. Moderar los azúcares y harinas te ayudará a bajarlos rápidamente."
    else:
        txt_trig = "Tus niveles de grasa están notablemente altos. Reducir alimentos fritos y refrescos protegerá tu corazón."

    # Acciones del día recomendadas
    acciones_html = f"""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:12px;"><i class="fas fa-check-circle" style="color:#22c55e; font-size:1.2rem;"></i> <span style="font-size:0.95rem; color:#334155;">Caminar de 20 a 30 minutos para mejorar tu salud.</span></div>
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:12px;"><i class="fas fa-check-circle" style="color:#22c55e; font-size:1.2rem;"></i> <span style="font-size:0.95rem; color:#334155;">Priorizar el agua natural y evitar los refrescos o jugos.</span></div>
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:12px;"><i class="fas fa-check-circle" style="color:#22c55e; font-size:1.2rem;"></i> <span style="font-size:0.95rem; color:#334155;">Agregar una porción extra de verduras en tu siguiente comida.</span></div>
    """
    if estado_general != "ESTABLE":
        acciones_html += f'<div style="display:flex; align-items:center; gap:12px;"><i class="fas fa-exclamation-circle" style="color:{color_estado}; font-size:1.2rem;"></i> <span style="font-size:0.95rem; color:#334155; font-weight:600;">Agendar tu consulta de seguimiento con el Dr. {NOMBRE_MEDICO_ACTUAL}.</span></div>'

    return f"""
    <html>
    <head>
        <title>Mi Portal de Salud | Nexus</title>
        {obtener_css_base()}
        <style>
            body {{ background-color: #f6f8fa; color: #1e293b; }}
            .patient-wrapper {{ max-width: 1100px; margin: 0 auto; padding: 25px 15px; }}
            .app-card {{ background: white; border-radius: 20px; border: none; box-shadow: 0 4px 18px rgba(0,0,0,0.03); padding: 24px; margin-bottom: 20px; transition: transform 0.2s; }}
            .app-card:hover {{ transform: translateY(-2px); }}
            .indicator-badge {{ display: inline-block; padding: 6px 14px; border-radius: 30px; font-weight: 700; font-size: 0.8rem; letter-spacing: 0.5px; margin-bottom: 10px; text-transform: uppercase; }}
            .health-value {{ font-size: 2.8rem; font-weight: 800; color: #0f172a; margin: 8px 0; display: flex; align-items: baseline; gap: 5px; }}
            .health-value span {{ font-size: 1rem; color: #64748b; font-weight: 400; }}
            .grid-moderna {{ display: grid; grid-template-columns: 1.2fr 1fr; gap: 20px; }}
            @media(max-width: 768px) {{ .grid-moderna {{ grid-template-columns: 1fr; }} }}
        </style>
    </head>
    <body>
    <div class="patient-wrapper">
        
        <header style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <img src="/logo_nexus" style="height: 42px;" onerror="this.style.display='none'">
                <span style="font-weight: 800; font-size: 1.2rem; color: #1e40af; letter-spacing: -0.5px;">NEXUS BIENESTAR</span>
            </div>
            <a href="/" class="btn-nexus btn-dark" style="width: auto; padding: 8px 18px; border-radius: 12px; font-size: 0.85rem; background: #e2e8f0; color: #475569;">
                <i class="fas fa-sign-out-alt"></i> Salir
            </a>
        </header>

        <div class="app-card" style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-left: 6px solid #2563eb;">
            <h1 style="margin: 0; font-size: 1.8rem; color: #1e3a8a; font-weight: 800;">¡Hola, {p_nombre}! 👋</h1>
            <p style="margin: 10px 0 0 0; font-size: 1.05rem; color: #1e40af; line-height: 1.5; max-width: 800px;">
                "{mensaje_emocional}"
            </p>
        </div>

        <div class="grid-moderna">
            
            <div>
                <div class="app-card" style="text-align: center; padding: 30px 20px;">
                    <span style="color: #64748b; font-size: 0.9rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Tu Estado General Hoy</span>
                    <h2 style="color: {color_estado}; font-size: 2.4rem; font-weight: 900; margin: 10px 0;">
                        <i class="fas fa-heartbeat"></i> {estado_general}
                    </h2>
                    
                    <div style="width: 100%; background: #f1f5f9; height: 10px; border-radius: 10px; margin-top: 15px; overflow: hidden;">
                        <div style="width: {progreso_riesgo}%; background: {color_estado}; height: 100%; border-radius: 10px; transition: width 0.5s;"></div>
                    </div>
                    <p style="font-size: 0.8rem; color: #94a3b8; margin: 8px 0 0 0;">Indicador de atención metabólica general</p>
                </div>

                <h3 style="font-size: 1.1rem; color: #475569; margin: 25px 0 15px 10px; font-weight: 700;"><i class="fas fa-chart-line"></i> Mis Indicadores Clave</h3>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div class="app-card">
                        <span class="indicator-badge" style="background: {ctx['color_glucosa']}20; color: {ctx['color_glucosa']};">Azúcar en sangre</span>
                        <div class="health-value">{glucosa} <span>mg/dL</span></div>
                        <p style="font-size: 0.88rem; color: #475569; line-height: 1.4; margin: 0;">{txt_glucosa}</p>
                    </div>

                    <div class="app-card">
                        <span class="indicator-badge" style="background: {ctx['color_trig']}20; color: {ctx['color_trig']};">Grasas en sangre</span>
                        <div class="health-value">{trig} <span>mg/dL</span></div>
                        <p style="font-size: 0.88rem; color: #475569; line-height: 1.4; margin: 0;">{txt_trig}</p>
                    </div>
                </div>

                <div style="text-align: center; margin-top: 10px;">
                    <a href="/descargar_expediente/{folio}" style="display: inline-block; color: #2563eb; font-weight: 600; font-size: 0.9rem; text-decoration: none; padding: 10px 20px; border-radius: 12px; background: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
                        <i class="fas fa-folder-open"></i> Ver mi Expediente Clínico Completo
                    </a>
                </div>
            </div>

            <div>
                <div class="app-card" style="border-top: 5px solid #10b981;">
                    <h3 style="margin: 0 0 15px 0; font-size: 1.1rem; color: #0f172a; font-weight: 700;"><i class="fas fa-star" style="color:#f59e0b;"></i> Acciones del Día</h3>
                    <p style="font-size: 0.85rem; color: #64748b; margin-bottom: 15px;">Pequeñas decisiones diarias que transforman tu salud:</p>
                    {acciones_html}
                </div>

                <div class="app-card">
                    <h3 style="margin: 0 0 5px 0; font-size: 1.1rem; color: #0f172a; font-weight: 700;"><i class="fas fa-chart-bar" style="color:#0ea5e9;"></i> Gráfica de Niveles</h3>
                    <div style="height: 180px; margin-top: 15px;"><canvas id="pacienteChart"></canvas></div>
                </div>

                <div style="padding: 0 10px; font-size: 0.8rem; color: #94a3b8; text-align: center;">
                    Nexus Médico Nacional • Información calculada de forma segura bajo estándares interoperables.
                </div>
            </div>

        </div>
    </div>

    <script>
    new Chart(document.getElementById('pacienteChart').getContext('2d'), {{
        type: 'bar',
        data: {{
            labels: ['Azúcar (Glucosa)', 'Grasas (Triglicéridos)'],
            datasets: [{{
                data: [{glucosa}, {trig}],
                backgroundColor: ['#2563eb', '#0ea5e9'],
                borderRadius: 12,
                barThickness: 45
            }}]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                y: {{ beginAtZero: true, grid: {{ color: '#f1f5f9' }} }},
                x: {{ grid: {{ display: false }} }}
            }}
        }}
    }});
    </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)

@app.get("/aviso-privacidad", response_class=HTMLResponse)
async def aviso_privacidad(request: Request):  # <--- Agrega (request: Request) aquí
    return f"""
    <html>
        <head>
            <title>Aviso de Privacidad - NEXUS</title>
            {obtener_css_base()}
        </head>
        <body style="background:#f8fafc; padding: 20px; font-family: sans-serif;">
            <div class="card" style="max-width: 800px; margin: auto; padding: 40px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);">
                <h1 style="color:#0f172a;">Aviso de Privacidad Integral</h1>
                
                <h3 style="color:#1e293b;">1. Identidad y Domicilio</h3>
                <p>NEXUS, con domicilio en Ciudad de México, es responsable del tratamiento de datos personales conforme a la LGPDPPSO.</p>
                
                <h3 style="color:#1e293b;">2. Datos Recabados y Finalidad</h3>
                <p>Recabamos datos clínicos, diagnósticos y niveles bioquímicos. El fin es la integración del Expediente Único de Salud (EUS) para interoperabilidad nacional.</p>
                
                <h3 style="color:#1e293b;">3. Seguridad y Confidencialidad</h3>
                <p>NEXUS garantiza estándares de confidencialidad médica y tecnológica. Aplicamos principios de licitud, proporcionalidad y responsabilidad.</p>
                
                <h3 style="color:#1e293b;">4. Derechos ARCO</h3>
                <p>Los titulares pueden ejercer sus derechos de Acceso, Rectificación, Cancelación y Oposición solicitándolo formalmente al área responsable.</p>
                
                <h3 style="color:#1e293b;">5. Fundamento Jurídico</h3>
                <p>Cumplimos con la Ley General de Protección de Datos Personales en Posesión de Sujetos Obligados, NOM-004-SSA3-2012 y estándares HL7 FHIR.</p>
                
                <hr style="margin: 30px 0; border: 0; border-top: 1px solid #e2e8f0;">
                
                <a href="/" class="btn-nexus" style="background:#0f172a; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;">Volver al inicio</a>
            </div>
        </body>
    </html>
    """