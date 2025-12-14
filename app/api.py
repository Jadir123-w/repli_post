# --- START OF FILE api2.py ---

import os
import sys
import uuid
import logging
import base64
import tempfile
import shutil
import subprocess
from flask import Flask, request, jsonify, send_file, make_response # type: ignore
from werkzeug.exceptions import BadRequest
from flask_cors import CORS # type: ignore
from dotenv import load_dotenv

### NUEVO: Importaciones para el procesamiento avanzado de PDF y OCR ###
from io import BytesIO
import pdfplumber
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Esto permite que las importaciones absolutas 'from app...' funcionen
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Configuración de logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
try:
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
except ValueError:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.error(f"Valor no válido para LOG_LEVEL: {log_level}")

# Cargar variables de entorno
load_dotenv()

# Importaciones del proyecto
try:
    # Las importaciones ahora son absolutas desde el paquete 'app'
    from app.src.database.mongo_manager import MongoManager
    from app.src.memory.conversation_memory import ConversationMemory
    from app.config.settings import SYSTEM_MESSAGE
    from app.chains.graph_definition import create_hr_graph
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    # ### MODIFICADO: Se remueven las herramientas 'process_pdf' y 'extract_text_from_image' que ya no se usarán directamente ###
    from app.src.tools.voice_tool import speech_to_text_tool, text_to_speech_tool, voice_tool_instance
    logging.info("Todos los módulos importados exitosamente")
except ImportError as e:
    logging.critical(f"Error de importación fatal: {e}")
    sys.exit(1)

# Inicializar Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Inicializar MongoDB manager
try:
    mongo_manager = MongoManager()
except Exception as e:
    logging.critical(f"Error al inicializar MongoManager: {e}")
    sys.exit(1)

# Almacenamiento de conversaciones activas
active_conversations = {}


### NUEVO: Función de extracción de texto de PDF con OCR (traída de api1.py y mejorada) ###
# def _extract_text_from_pdf_with_ocr(pdf_content: bytes) -> str:
#     """
#     Extrae texto de un contenido de PDF en bytes.
#     Intenta la extracción directa y, si falla o el texto es escaso, utiliza OCR.
#     """
#     extracted_text = ""
    
#     # --- Intento 1: Extracción directa con pdfplumber ---
#     try:
#         logging.info("[PDF_EXTRACT] Intentando extracción directa con pdfplumber.")
#         with pdfplumber.open(BytesIO(pdf_content)) as pdf:
#             for page in pdf.pages:
#                 page_text = page.extract_text()
#                 if page_text:
#                     extracted_text += page_text + "\n"
#         logging.info(f"[PDF_EXTRACT] pdfplumber extrajo {len(extracted_text)} caracteres.")
#     except Exception as e:
#         logging.warning(f"[PDF_EXTRACT] pdfplumber falló: {e}")
#         extracted_text = ""

#     # --- Intento 2: OCR si la extracción directa falló o fue pobre (y si las librerías están disponibles) ---
#     if OCR_AVAILABLE and (not extracted_text or len(extracted_text.strip()) < 100):
#         logging.warning(f"[PDF_EXTRACT] Texto extraído es insuficiente ({len(extracted_text)} chars). Intentando OCR.")
#         try:
#             images = convert_from_bytes(pdf_content)
#             ocr_text = ""
#             for i, image in enumerate(images):
#                 try:
#                     # Usar español como idioma principal para el OCR
#                     page_text = pytesseract.image_to_string(image, lang='spa+eng')
#                     if page_text.strip():
#                         ocr_text += f"--- Página {i+1} (OCR) ---\n{page_text}\n\n"
#                 except Exception as page_error:
#                     logging.error(f"[PDF_EXTRACT] Error en OCR de página {i+1}: {page_error}")
            
#             if ocr_text.strip():
#                 logging.info(f"[PDF_EXTRACT] OCR exitoso, se extrajeron {len(ocr_text)} caracteres.")
#                 # El texto de OCR es ahora el texto principal
#                 extracted_text = ocr_text
#             else:
#                 logging.warning("[PDF_EXTRACT] OCR no produjo texto útil.")
#                 if not extracted_text:
#                     raise ValueError("No se pudo extraer texto del PDF (extracción normal y OCR fallaron).")

#         except Exception as ocr_error:
#             logging.error(f"[PDF_EXTRACT] Error general durante OCR: {ocr_error}")
#             if not extracted_text:
#                 raise ValueError(f"No se pudo procesar el PDF para OCR: {ocr_error}")
#     elif not OCR_AVAILABLE and (not extracted_text or len(extracted_text.strip()) < 100):
#         logging.warning("[PDF_EXTRACT] El texto extraído es insuficiente y OCR no está disponible.")

#     return extracted_text.strip()


def handle_api_error(error, status_code=500):
    """Manejador centralizado de errores"""
    logging.exception(str(error))
    error_message = str(error) if app.config.get('DEBUG') else "Error interno del servidor"
    return jsonify({"success": False, "error": error_message}), status_code

@app.route('/')
def index():
    """Endpoint principal con información de la API"""
    return jsonify({
        "name": "Geraldine API",
        "version": "2.0",
        "description": "API unificada para interactuar con Geraldine, abogada digital especialista en Derecho Corporativo, Derechos Reales y Derecho de Familia",
        "status": "online",
        "main_endpoint": {
            "path": "/conversation",
            "methods": ["GET", "POST"],
            "description": "Endpoint unificado que maneja todos los tipos de interacciones",
            "capabilities": [
                "Conversación de texto",
                "Procesamiento de archivos (PDF, imágenes)",
                "Conversación de voz (audio → texto → IA → audio)",
                "Gestión de historial de conversaciones",
                "Exportación de conversaciones"
            ],
            "usage": {
                "GET_history": "?thread_id=...&action=history",
                "GET_export": "?thread_id=...&action=export",
                "POST_text": "JSON: {'thread_id': '...', 'message': '...'}",
                "POST_file": "Form-data: thread_id, message, file (PDF/PNG/JPG)",
                "POST_voice": "Form-data: thread_id, audio (WAV/MP3/FLAC/M4A/OGG), voice_name"
            }
        },
        "health": {
            "path": "/health",
            "method": "GET",
            "description": "Verifica el estado de la API"
        }
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar el estado de la API"""
    try:
        # Verificar servicios de voz
        voice_available = voice_tool_instance.speech_client is not None and voice_tool_instance.tts_client is not None

        return jsonify({
            "status": "ok",
            "message": "Geraldine API está funcionando correctamente",
            "services": {
                "database": "ok",
                "voice_services": "ok" if voice_available else "warning",
                "voice_speech_to_text": voice_tool_instance.speech_client is not None,
                "voice_text_to_speech": voice_tool_instance.tts_client is not None,
                "ocr_services": "ok" if OCR_AVAILABLE else "warning"
            }
        })
    except Exception as e:
        return handle_api_error(e)

def process_text_conversation(thread_id, user_message):
    """Procesa una conversación de texto normal"""
    conversation = active_conversations.get(thread_id)
    if not conversation:
        conversation_memory = ConversationMemory(thread_id, mongo_manager)
        graph = create_hr_graph()
        previous_messages = [SystemMessage(content=SYSTEM_MESSAGE)]
        history = conversation_memory.get_conversation_history()
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                previous_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                previous_messages.append(AIMessage(content=content))
        current_state = {
            "messages": previous_messages,
            "user_name": None,
            "country": None,
            "country_verified": False,
            "cv_summary": None,
            "cv_analysis": None,
            "cv_info": None
        }
    else:
        current_state = conversation.get("state")
        conversation_memory = conversation.get("memory")
        graph = create_hr_graph()

    conversation_memory.add_message("user", user_message)
    current_state["messages"].append(HumanMessage(content=user_message))

    try:
        response = graph.invoke(current_state)
        current_state = response
    except Exception as e:
        logging.error(f"Error al invocar el grafo: {e}")
        raise Exception(f"Error al procesar el mensaje: {str(e)}")

    ai_response = None
    for msg in reversed(current_state.get("messages", [])):
        if isinstance(msg, AIMessage):
            ai_response = msg.content
            conversation_memory.add_message("assistant", ai_response)
            break

    if ai_response is None:
        ai_response = "Lo siento, no pude generar una respuesta."
        conversation_memory.add_message("assistant", ai_response)

    active_conversations[thread_id] = {
        "state": current_state,
        "memory": conversation_memory
    }

    return ai_response

# def process_file_conversation(thread_id, user_message, uploaded_file):
#     """Procesa una conversación con archivo (PDF o imagen)"""
#     if uploaded_file.filename == '':
#         raise Exception("Nombre de archivo vacío")

#     # Verificar el tipo de archivo
#     allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg'}
#     file_extension = uploaded_file.filename.rsplit('.', 1)[1].lower()
#     if file_extension not in allowed_extensions:
#         raise Exception("Tipo de archivo no permitido")

#     # Guardar el archivo temporalmente
#     temp_dir = os.path.join(os.getcwd(), 'temp')
#     os.makedirs(temp_dir, exist_ok=True)
#     # Usar un nombre de archivo único para evitar colisiones
#     unique_filename = f"{uuid.uuid4().hex}_{uploaded_file.filename}"
#     file_path = os.path.join(temp_dir, unique_filename)
#     uploaded_file.save(file_path)

#     try:
#         file_text = ""
#         # Procesar el archivo según su tipo
#         if file_extension in {'png', 'jpg', 'jpeg'}:
#             # Se mantiene la excelente lógica de `api2.py` para imágenes con Google Vision
#             try:
#                 from google.cloud import vision
                
#                 client = vision.ImageAnnotatorClient()
                
#                 with open(file_path, 'rb') as image_file:
#                     content = image_file.read()

#                 image = vision.Image(content=content)
#                 text_detection_response = client.text_detection(image=image)
#                 texts = text_detection_response.text_annotations
#                 label_detection_response = client.label_detection(image=image)
#                 labels = label_detection_response.label_annotations

#                 extracted_text = ""
#                 if texts:
#                     extracted_text = texts[0].description
                
#                 extracted_labels = [label.description for label in labels]
                
#                 file_text = f"[Imagen analizada: {uploaded_file.filename}]\n"
#                 if extracted_text:
#                     file_text += f"\nTexto detectado en la imagen:\n{extracted_text}\n"
#                 if extracted_labels:
#                     file_text += f"\nElementos detectados en la imagen:\n- " + "\n- ".join(extracted_labels[:10])

#             except ImportError:
#                 file_text = f"[Contenido de imagen: {uploaded_file.filename}. No se pudo analizar el contenido específico porque la API de Vision no está disponible.]"
#             except Exception as e:
#                 logging.error(f"Error al analizar imagen con Vision API: {e}")
#                 file_text = f"[Imagen recibida: {uploaded_file.filename}. No se pudo analizar completamente debido a un error: {str(e)}]"
        
#         else: # ### MODIFICADO: Lógica para procesar PDF con OCR de respaldo ###
#             # Procesar como PDF usando la nueva función robusta
#             logging.info(f"[PDF_PROCESS] Procesando archivo PDF: {file_path}")
#             try:
#                 with open(file_path, 'rb') as f:
#                     pdf_content = f.read()
#                 file_text = _extract_text_from_pdf_with_ocr(pdf_content)
#                 if not file_text:
#                     file_text = "[El documento PDF fue procesado, pero no se encontró contenido textual extraíble.]"
#             except Exception as e:
#                 logging.error(f"Fallo crítico al procesar PDF {file_path}: {e}")
#                 file_text = f"[Error al procesar el PDF: {e}. No se pudo extraer el contenido.]"


#         # ----- La lógica de negocio de Geraldine se mantiene intacta -----

#         # Verificar si es un comprobante de pago
#         payment_keywords = ["pago", "transferencia", "depósito", "voucher", "comprobante", "recibo", "factura", "cheque", "depósito","Scotiabank", "Yape","Plin", "Bbva", "BCP"]
#         is_payment = any(keyword.lower() in file_text.lower() for keyword in payment_keywords)

#         # Verificar si es un documento legal
#         legal_keywords = [
#             "contrato", "constitución", "poder", "sociedad", "herederos", "divorcio",
#             "notarial", "INDECOPI", "marca", "acta", "junta", "directorio", "alquiler",
#             "compra", "venta", "liquidación", "sucesión", "testamento", "demandado", "demandante",
#             "administrativo", "conciliación", "alimentos", "tenencia", "liquidación", "garantía",
#             "hipoteca", "saneamiento", "due diligence", "protección al consumidor"
#         ]
#         is_legal = any(keyword.lower() in file_text.lower() for keyword in legal_keywords)

#         # Construir el mensaje del usuario combinando el texto y el archivo
#         file_type = "comprobante de pago" if is_payment else "documento legal" if is_legal else "documento"
        
#         # Formatear el mensaje del usuario para ser más claro para el LLM
#         if user_message:
#             combined_message = f"{user_message}\n\n[Contexto Adicional del Usuario: Se ha adjuntado un archivo '{uploaded_file.filename}', que he identificado como un {file_type}. Procedo a analizarlo.]"
#         else:
#             combined_message = f"[Contexto Adicional del Usuario: Se ha adjuntado un archivo '{uploaded_file.filename}', identificado como un {file_type}. Procedo a analizarlo.]"


#         if is_payment:
#             ai_response = "He recibido tu comprobante de pago. Procederé a verificarlo y continuaremos con el proceso de asesoría."
#         elif not is_legal and file_extension == 'pdf': # Solo aplicar esta lógica estricta a PDFs
#             ai_response = "Lo siento, no puedo ayudarte con este tipo de documento. Como abogada digital especialista en Derecho Corporativo, Derechos Reales y Derecho de Familia, solo puedo asistirte con documentos legales relacionados con estas áreas. Por favor, sube un documento legal (como contratos, poderes, actas, documentos de constitución de empresa, sucesiones, etc.) o hazme una consulta específica sobre temas jurídicos."
#         else:
#             # Si es legal (o una imagen que podría ser legal), seguir el flujo normal
#             # El primer `process_text_conversation` ahora solo establece el contexto
#             ai_response = process_text_conversation(thread_id, combined_message)
            
#             # Ahora, inyectamos el contenido real del archivo como un mensaje separado para un análisis profundo
#             conversation = active_conversations.get(thread_id)
#             if not conversation:
#                  raise Exception("Estado de la conversación no encontrado después del mensaje inicial.")

#             conversation_memory = conversation.get("memory")
#             current_state = conversation.get("state")

#             # Añadir el texto extraído del archivo como un nuevo mensaje de "contexto de herramienta"
#             file_content_message = f"[Contenido extraído del archivo '{uploaded_file.filename}']:\n\n{file_text}"
#             conversation_memory.add_message("user", file_content_message) # Guardar en historial como si el usuario lo hubiera pegado
#             current_state["messages"].append(HumanMessage(content=file_content_message))

#             # Volver a invocar el grafo con el contenido completo del archivo para obtener una respuesta detallada
#             graph = create_hr_graph()
#             response = graph.invoke(current_state)
#             current_state = response

#             # Extraer la respuesta final del asistente
#             for msg in reversed(current_state.get("messages", [])):
#                 if isinstance(msg, AIMessage):
#                     ai_response = msg.content
#                     conversation_memory.add_message("assistant", ai_response)
#                     break
            
#             if not ai_response:
#                 ai_response = "He procesado el documento. ¿Cómo puedo ayudarte con la información contenida en él?"
#                 conversation_memory.add_message("assistant", ai_response)

#             active_conversations[thread_id] = {
#                 "state": current_state,
#                 "memory": conversation_memory
#             }

#         return ai_response, file_text

#     finally:
#         # Eliminar el archivo temporal
#         if os.path.exists(file_path):
#             try:
#                 os.remove(file_path)
#             except OSError as e:
#                 logging.error(f"Error al eliminar el archivo temporal {file_path}: {e}")

# # ... (El resto del archivo, incluyendo `process_voice_conversation` y todas las rutas, permanece exactamente igual)

# def process_voice_conversation(thread_id, uploaded_file, voice_name="es-ES-Standard-A"):
#     """Procesa una conversación de voz completa"""
#     if uploaded_file.filename == '':
#         logging.error("[AUDIO] Nombre de archivo vacío")
#         raise Exception("Nombre de archivo vacío")

#     # Verificar el tipo de archivo de audio
#     allowed_extensions = {'wav', 'mp3', 'flac', 'm4a', 'ogg', 'webm', 'opus'}
#     file_extension = uploaded_file.filename.rsplit('.', 1)[1].lower()
#     logging.info(f"[AUDIO] Recibido archivo: {uploaded_file.filename} (ext: {file_extension})")
#     if file_extension not in allowed_extensions:
#         logging.error(f"[AUDIO] Tipo de archivo de audio no permitido: {file_extension}")
#         raise Exception("Tipo de archivo de audio no permitido")

#     # Guardar el archivo temporalmente
#     temp_dir = os.path.join(os.getcwd(), 'temp')
#     os.makedirs(temp_dir, exist_ok=True)
#     file_path = os.path.join(temp_dir, uploaded_file.filename)
#     uploaded_file.save(file_path)
#     logging.info(f"[AUDIO] Guardado en: {file_path}")

#     # Log de tamaño y tipo MIME
#     try:
#         file_size = os.path.getsize(file_path)
#         logging.info(f"[AUDIO] Tamaño del archivo guardado: {file_size} bytes")
#     except Exception as e:
#         logging.error(f"[AUDIO] No se pudo obtener el tamaño del archivo: {e}")

#     # Si es webm u opus, conviértelo a wav MONO
#     if file_extension in {'webm', 'opus'}:
#         wav_path = file_path.rsplit('.', 1)[0] + '_converted.wav'
#         command = [
#             'ffmpeg', '-y', '-i', file_path,
#             '-ac', '1',  # Fuerza MONO
#             '-ar', '16000',  # Frecuencia de muestreo recomendada para STT
#             wav_path
#         ]
#         try:
#             logging.info(f"[AUDIO] Ejecutando conversión ffmpeg: {' '.join(command)}")
#             subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#             file_path = wav_path
#             logging.info(f"[AUDIO] Conversión exitosa. Nuevo archivo: {wav_path}")
#         except Exception as e:
#             logging.error(f"[AUDIO] Error al convertir audio a WAV MONO: {e}")
#             raise Exception(f"Error al convertir audio a WAV MONO: {e}")

#     # Leer el archivo de audio convertido o original
#     try:
#         with open(file_path, 'rb') as f:
#             audio_data = f.read()
#         logging.info(f"[AUDIO] Archivo leído correctamente. Bytes: {len(audio_data)}")
#     except Exception as e:
#         logging.error(f"[AUDIO] Error al leer el archivo: {e}")
#         raise Exception(f"Error al leer el archivo de audio: {e}")
#     audio_base64 = base64.b64encode(audio_data).decode('utf-8')

#     # Convertir audio a texto
#     tool_call_id = str(uuid.uuid4())
#     stt_result = speech_to_text_tool.invoke({
#         "audio_base64": audio_base64,
#         "tool_call_id": tool_call_id,
#         "language_code": "es-ES"
#     })

#     if "error" in stt_result:
#         logging.error(f"[AUDIO] Error al transcribir audio: {stt_result['error']}")
#         raise Exception(f"Error al transcribir audio: {stt_result['error']}")

#     user_text = stt_result["transcript"]

#     # Procesar con IA
#     ai_response = process_text_conversation(thread_id, user_text)

#     # Convertir respuesta a audio
#     tts_tool_call_id = str(uuid.uuid4())
#     tts_result = text_to_speech_tool.invoke({
#         "text": ai_response,
#         "tool_call_id": tts_tool_call_id,
#         "voice_name": voice_name
#     })

#     if "error" in tts_result:
#         logging.error(f"[AUDIO] Error al generar audio: {tts_result['error']}")
#         raise Exception(f"Error al generar audio: {tts_result['error']}")

#     # Generar archivo de audio de respuesta
#     response_audio_data = base64.b64decode(tts_result["audio_base64"])
#     audio_filename = f"voice_{thread_id}_{uuid.uuid4().hex[:8]}.mp3"
#     response_file_path = os.path.join(temp_dir, audio_filename)

#     with open(response_file_path, 'wb') as f:
#         f.write(response_audio_data)

#     # Limpieza: elimina archivos temporales
#     try:
#         if os.path.exists(file_path):
#             os.remove(file_path)
#         if file_extension in {'webm', 'opus'} and 'wav_path' in locals() and os.path.exists(wav_path):
#             os.remove(wav_path)
#     except Exception:
#         logging.exception("Error al eliminar archivos temporales en  `process_voice_conversation`")

#     return {
#         "user_transcript": user_text,
#         "ai_response": ai_response,
#         "audio_file": f"/conversation/audio/{audio_filename}",
#         "voice_name": voice_name,
#         "audio_size_bytes": tts_result["audio_size_bytes"]
#     }

@app.route('/conversation', methods=['GET', 'POST'])
@app.route('/api/conversation', methods=['GET', 'POST'])
def handle_conversation():
    """Endpoint unificado para todas las interacciones con Geraldine"""
    try:
        if request.method == 'GET':
            # Manejar GET para historial y exportación
            thread_id = request.args.get('thread_id')
            action = request.args.get('action', 'history')

            if not thread_id:
                return jsonify({
                    "success": False,
                    "error": "Se requiere el parámetro 'thread_id'"
                }), 400

            # Obtener historial de conversación
            if action == 'history':
                conversation = active_conversations.get(thread_id)
                if conversation:
                    memory = conversation['memory']
                else:
                    memory = ConversationMemory(thread_id, mongo_manager)
                history = memory.get_conversation_history()
                return jsonify({
                    "success": True,
                    "thread_id": thread_id,
                    "messages": history
                })

            # Exportar conversación
            elif action == 'export':
                conversation = active_conversations.get(thread_id)
                if conversation:
                    memory = conversation['memory']
                else:
                    memory = ConversationMemory(thread_id, mongo_manager)
                try:
                    txt_file, json_file = memory.export_final_chat()
                    return jsonify({
                        "success": True,
                        "thread_id": thread_id,
                        "txt_file": txt_file,
                        "json_file": json_file,
                        "message": "Conversación exportada correctamente"
                    })
                except Exception as e:
                    logging.error(f"Error exportando conversación: {e}")
                    return jsonify({
                        "success": False,
                        "error": "Error al exportar la conversación"
                    }), 500
            else:
                return jsonify({
                    "success": False,
                    "error": f"Acción no reconocida: '{action}'. Las acciones válidas son 'history' y 'export'."
                }), 400

        elif request.method == 'POST':
            # Detectar el tipo de contenido
            content_type = request.content_type or ""

            # Si es multipart/form-data, puede ser archivo o voz
            if content_type.startswith('multipart/form-data'):
                thread_id = request.form.get('thread_id')
                user_message = request.form.get('message', '')

                # Verificar si hay archivo de audio
                if 'audio' in request.files:
                    # Es una conversación de voz
                    if not thread_id:
                        thread_id = f"voice_{uuid.uuid4().hex[:8]}"

                    uploaded_file = request.files['audio']
                    voice_name = request.form.get('voice_name', 'es-ES-Standard-A')

                    try:
                        result = process_voice_conversation(thread_id, uploaded_file, voice_name)
                        return jsonify({
                            "success": True,
                            "thread_id": thread_id,
                            "type": "voice",
                            **result
                        })
                    except Exception as e:
                        return jsonify({
                            "success": False,
                            "error": str(e)
                        }), 400

                # Verificar si hay archivo de documento
                elif 'file' in request.files:
                    # Es una conversación con archivo
                    if not thread_id:
                        return jsonify({"success": False, "error": "Se requiere thread_id para procesar archivos"}), 400

                    uploaded_file = request.files['file']

                    try:
                        ai_response, file_text = process_file_conversation(thread_id, user_message, uploaded_file)
                        return jsonify({
                            "success": True,
                            "thread_id": thread_id,
                            "type": "file",
                            "message": ai_response,
                            "file_text": file_text
                        })
                    except Exception as e:
                        return jsonify({
                            "success": False,
                            "error": str(e)
                        }), 400

                else:
                    # Es solo texto
                    if not thread_id:
                        return jsonify({"success": False, "error": "Se requiere thread_id"}), 400

                    if not user_message:
                        return jsonify({"success": False, "error": "Se requiere un mensaje"}), 400

                    try:
                        ai_response = process_text_conversation(thread_id, user_message)
                        return jsonify({
                            "success": True,
                            "thread_id": thread_id,
                            "type": "text",
                            "message": ai_response,
                            "conversation_ended": False
                        })
                    except Exception as e:
                        return jsonify({
                            "success": False,
                            "error": str(e)
                        }), 500

            # Si es application/json, es texto normal
            elif content_type.startswith('application/json'):
                try:
                    data = request.json or {}
                except (BadRequest, ValueError, Exception) as e:
                    data = {}
                    logging.warning(f"JSON malformado recibido: {str(e)}, usando datos vacíos")

                # Iniciar nueva conversación
                if 'thread_id' not in data:
                    thread_id = f"api_{uuid.uuid4().hex[:8]}"
                    conversation_memory = ConversationMemory(thread_id, mongo_manager)
                    graph = create_hr_graph()
                    initial_messages = [SystemMessage(content=SYSTEM_MESSAGE)]
                    initial_user_message = "Hola, me gustaría recibir ayuda."
                    initial_messages.append(HumanMessage(content=initial_user_message))
                    conversation_memory.add_message("user", initial_user_message)
                    current_state = {
                        "messages": initial_messages,
                        "user_name": None,
                        "country": None,
                        "country_verified": False,
                        "cv_summary": None,
                        "cv_analysis": None,
                        "cv_info": None
                    }
                    try:
                        initial_response = graph.invoke(current_state)
                        last_message = initial_response.get("messages", [])[-1] if initial_response.get("messages") else None
                        ai_response = (last_message.content if isinstance(last_message, AIMessage)
                                       else "Bienvenido a la asistencia de Geraldine.")
                        conversation_memory.add_message("assistant", ai_response)
                    except Exception as e:
                        logging.error(f"Error en invocación inicial del grafo: {e}")
                        ai_response = "Lo siento, ha ocurrido un error al iniciar la conversación."
                    active_conversations[thread_id] = {
                        "state": current_state,
                        "memory": conversation_memory
                    }
                    return jsonify({
                        "success": True,
                        "thread_id": thread_id,
                        "type": "text",
                        "message": ai_response
                    })

                # Enviar mensaje en conversación existente
                elif 'message' in data:
                    thread_id = data['thread_id']
                    user_message = data['message']

                    if not thread_id:
                        return jsonify({"success": False, "error": "thread_id inválido"}), 400

                    try:
                        ai_response = process_text_conversation(thread_id, user_message)
                        return jsonify({
                            "success": True,
                            "thread_id": thread_id,
                            "type": "text",
                            "message": ai_response,
                            "conversation_ended": False
                        })
                    except Exception as e:
                        return jsonify({
                            "success": False,
                            "error": str(e)
                        }), 500
                else:
                    return jsonify({
                        "success": False,
                        "error": "Datos incompletos. Se requiere 'message' cuando se proporciona 'thread_id'."
                    }), 400

            else:
                return jsonify({
                    "success": False,
                    "error": "Content-Type no soportado. Use application/json para texto o multipart/form-data para archivos/audio."
                }), 400

    except Exception as e:
        logging.exception(f"Error en la operación de conversación: {e}")
        return jsonify({
            "success": False,
            "error": "Error interno al procesar la solicitud",
            "details": str(e)
        }), 500

# @app.route('/conversation/audio/<filename>', methods=['GET', 'OPTIONS'])
# def download_voice_file(filename):
#     """Endpoint para descargar archivos de audio generados"""
#     if request.method == 'OPTIONS':
#         response = make_response()
#         response.headers['Access-Control-Allow-Origin'] = '*'
#         response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
#         response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
#         return response

#     temp_dir = os.path.join(os.getcwd(), 'temp')
#     file_path = os.path.join(temp_dir, filename)

#     if not os.path.exists(file_path):
#         response = make_response("Not Found", 404)
#         response.headers['Access-Control-Allow-Origin'] = '*'
#         response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
#         response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
#         return response

#     response = make_response(send_file(file_path, mimetype='audio/mpeg', as_attachment=False))
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
#     response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
#     response.headers['Content-Type'] = 'audio/mpeg'
#     return response

# @app.after_request
# def add_cors_headers(response):
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
#     response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
#     return response

# Punto de entrada para ejecución directa
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    app.run(host='0.0.0.0', port=port, debug=debug_mode)