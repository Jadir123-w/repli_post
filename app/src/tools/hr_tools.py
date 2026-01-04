# src/tools/hr_tools.py
import os
import sys
import pypdf
import pdfplumber
import requests
import logging
from pathlib import Path
from typing import Annotated, Dict, Any, List, Optional, Union
from langchain_core.tools import InjectedToolCallId, tool
from io import BytesIO
import tempfile

# Función para obtener la ruta base del proyecto
def get_project_root():
    current_file = Path(__file__).resolve()
    # Subir cuatro niveles: src/tools -> src -> app -> raíz
    return current_file.parent.parent.parent.parent

# Obtener la ruta base del proyecto
APP_ROOT = get_project_root()

# Añadir el directorio 'app' al sys.path para poder importar 'config'
if str(APP_ROOT) not in sys.path:
    sys.path.append(str(APP_ROOT))
    print(f"Añadiendo {APP_ROOT} a sys.path")

# Importa la lista de países desde la configuración
from config.settings import PERMITTED_COUNTRIES


from utils.config import Config

MARCELLA_GOOGLE_API_KEY = Config.MARCELLA_GOOGLE_API_KEY

@tool
def verify_country(country_name: str) -> Dict[str, Any]:
    """
    Verifica si el país proporcionado por el usuario pertenece a la lista de países permitidos en LATAM.
    Actualiza el estado con el país y si fue verificado.
    """
    print(f"--- [Herramienta] Verificando País: {country_name} ---")
    # Normalize input to match list entries - handle accented characters
    import unicodedata
    
    def normalize_text(text):
        # Normalize accented characters, convert to lowercase, and remove combining marks
        nfkd_form = unicodedata.normalize('NFKD', text.lower().strip())
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

    normalized_input = normalize_text(country_name)
    
    # Normalize the list of allowed countries for comparison
    normalized_permitted_countries = [normalize_text(country) for country in PERMITTED_COUNTRIES]
    
    # Check if the normalized input country is in the normalized list
    verified = normalized_input in normalized_permitted_countries
    
    if verified:
        # Find the original country name for a better response message
        original_country_name = PERMITTED_COUNTRIES[normalized_permitted_countries.index(normalized_input)]
        result = f"Verificación exitosa: '{original_country_name}' se encuentra en la lista de países permitidos. Podemos continuar."
        print(f"[Herramienta] País '{original_country_name}' verificado con éxito.")
    else:
        result = f"Lo siento, '{country_name}' no está en la lista de países donde operamos. No puedo asistirte en este momento."
        print(f"[Herramienta] País '{country_name}' NO permitido.")

    state_update = {
        "country": country_name if verified else None,
        "country_verified": verified,
        "messages": [result],
    }
    return state_update

@tool
def process_pdf(pdf_input: Union[str, BytesIO], page_numbers: Optional[List[int]] = None) -> str:
    """
    Extrae texto de un archivo PDF.
    Puede procesar PDFs desde una ruta local, un enlace de Google Drive, o un BytesIO.
    Puede extraer texto de páginas específicas si se proporcionan sus números (basado en 1).
    Si no se especifican números de página, extrae texto de todo el documento.
    Incluye soporte OCR para extraer texto de imágenes dentro del PDF.

    Args:
        pdf_input (Union[str, BytesIO]): La ruta al archivo PDF, el enlace de Google Drive, o un BytesIO con el contenido del PDF.
        page_numbers (Optional[List[int]]): Una lista opcional de números de página (ej: [1, 3, 5])
                                            para extraer texto. Si es None, se extrae de todas las páginas.
                                            Los números de página son 1-indexados.

    Returns:
        str: El texto extraído del PDF. Si ocurre un error,
             devuelve un mensaje de error descriptivo.
    """
    logging.info(f"[process_pdf] Iniciando procesamiento de PDF")
    
    pdf_path = None # Inicializar pdf_path a None por defecto
    try:
        # Manejar diferentes tipos de entrada
        if isinstance(pdf_input, BytesIO):
            logging.info("[process_pdf] Procesando PDF desde BytesIO")
            pdf_stream = pdf_input
            reader = pypdf.PdfReader(pdf_stream)
            # No se crea archivo temporal en este caso
            pdf_plumber_input = pdf_stream # Usar el mismo stream para pdfplumber

        elif isinstance(pdf_input, str):
            pdf_path = pdf_input # Asignar pdf_path aquí si es string
            # Verificar si es un enlace de Google Drive
            if "drive.google.com" in pdf_path:
                logging.info("[process_pdf] Detectado enlace de Google Drive")
                # Convertir el enlace de Drive a un enlace directo de descarga
                if '/file/d/' in pdf_path:
                    file_id = pdf_path.split('/file/d/')[1].split('/')[0]
                elif 'id=' in pdf_path:
                    file_id = pdf_path.split('id=')[1].split('&')[0]
                else:
                    raise ValueError("Formato de enlace de Drive no reconocido")
                
                # Crear enlace directo de descarga
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                
                # Descargar el archivo
                response = requests.get(download_url)
                if response.status_code != 200:
                    raise Exception(f"Error al descargar el archivo: {response.status_code}")
                
                # Guardar temporalmente
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, f"drive_pdf_{file_id}.pdf")
                
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                
                pdf_path = temp_path # Asignar el path del archivo temporal
                logging.info(f"[process_pdf] Archivo de Drive descargado exitosamente a: {temp_path}")
                reader = pypdf.PdfReader(pdf_path)
                pdf_plumber_input = pdf_path # Usar el path para pdfplumber
            else:
                 # Si es una ruta local
                 reader = pypdf.PdfReader(pdf_path)
                 pdf_plumber_input = pdf_path # Usar el path para pdfplumber
        else:
            raise ValueError("El input debe ser una ruta de archivo (str) o un BytesIO")

        # Verificar si el archivo existe (solo si pdf_path no es None)
        if pdf_path and not os.path.exists(pdf_path):
            raise FileNotFoundError(f"El archivo PDF '{pdf_path}' no fue encontrado.")
        
        # Verificar si es un PDF (solo si pdf_path no es None)
        if pdf_path and not pdf_path.lower().endswith(".pdf"):
            raise ValueError(f"El archivo '{pdf_path}' no parece ser un archivo PDF.")

        try:
            logging.info(f"[process_pdf] Abriendo PDF con pypdf")
            text_parts = []
            
            # Función para extraer texto con OCR si es necesario
            def extract_text_with_ocr(page, page_num):
                try:
                    # Primero intentar con pypdf
                    text = page.extract_text()
                    if text and len(text.strip()) > 0:
                        return text.strip()
                    
                    # Si no hay texto, intentar con pdfplumber
                    # Asegurarse de que el stream esté al inicio si se usa BytesIO
                    if isinstance(pdf_plumber_input, BytesIO):
                        pdf_plumber_input.seek(0)

                    with pdfplumber.open(pdf_plumber_input) as pdf:
                        plumber_page = pdf.pages[page_num - 1]
                        text = plumber_page.extract_text()
                        if text and len(text.strip()) > 0:
                            return text.strip()
                    
                    # Si aún no hay texto, intentar OCR
                    try:
                        import pytesseract
                        from PIL import Image
                        import io
                        
                        # Convertir página a imagen
                        # Asegurarse de que el stream esté al inicio si se usa BytesIO
                        if isinstance(pdf_plumber_input, BytesIO):
                            pdf_plumber_input.seek(0)
                            
                        with pdfplumber.open(pdf_plumber_input) as pdf:
                            plumber_page = pdf.pages[page_num - 1]
                            img = plumber_page.to_image()
                            img_bytes = io.BytesIO()
                            img.save(img_bytes, format='PNG')
                            img_bytes.seek(0)
                            
                            # Realizar OCR
                            image = Image.open(img_bytes)
                            text = pytesseract.image_to_string(image, lang='spa+eng')
                            if text and len(text.strip()) > 0:
                                return text.strip()
                    except ImportError:
                        logging.warning("[process_pdf] pytesseract no está instalado. OCR no disponible.")
                    except Exception as e:
                        logging.warning(f"[process_pdf] Error durante OCR: {str(e)}")
                    
                    return None
                except Exception as e:
                    logging.error(f"[process_pdf] Error al extraer texto de la página {page_num}: {str(e)}")
                    return None
            
            if page_numbers:
                logging.info(f"[process_pdf] Procesando páginas específicas: {page_numbers}")
                # Validar números de página
                for page_num in page_numbers:
                    if not (1 <= page_num <= len(reader.pages)):
                        error_msg = f"Error: El número de página {page_num} está fuera del rango (el PDF tiene {len(reader.pages)} páginas)."
                        logging.error(f"[process_pdf] {error_msg}")
                        return error_msg
                
                # Extraer de páginas específicas
                for page_num in sorted(list(set(page_numbers))):
                    logging.info(f"[process_pdf] Extrayendo texto de la página {page_num}")
                    page = reader.pages[page_num - 1]
                    extracted = extract_text_with_ocr(page, page_num)
                    
                    if extracted:
                        text_parts.append(f"--- Contenido de la Página {page_num} ---\n{extracted}")
                        logging.info(f"[process_pdf] Texto extraído exitosamente de la página {page_num}")
                    else:
                        text_parts.append(f"--- Página {page_num} no contiene texto extraíble ---")
                        logging.warning(f"[process_pdf] No se pudo extraer texto de la página {page_num}")
            else:
                logging.info(f"[process_pdf] Procesando todas las páginas del PDF")
                # Extraer de todas las páginas
                for i, page in enumerate(reader.pages):
                    logging.info(f"[process_pdf] Extrayendo texto de la página {i+1}")
                    extracted = extract_text_with_ocr(page, i+1)
                    
                    if extracted:
                        text_parts.append(f"--- Contenido de la Página {i+1} ---\n{extracted}")
                        logging.info(f"[process_pdf] Texto extraído exitosamente de la página {i+1}")
                    else:
                        text_parts.append(f"--- Página {i+1} no contiene texto extraíble ---")
                        logging.warning(f"[process_pdf] No se pudo extraer texto de la página {i+1}")
            
            if not text_parts:
                logging.warning("[process_pdf] No se pudo extraer texto del PDF.")
                return "No se pudo extraer texto del PDF."
            
            final_text = "\n\n".join(text_parts)
            logging.info(f"[process_pdf] Procesamiento completado exitosamente. Longitud del texto extraído: {len(final_text)} caracteres")

            # Limpiar archivos temporales (solo si se crearon)
            try:
                if pdf_path and (isinstance(pdf_input, str) and "drive.google.com" in pdf_input):
                    os.remove(pdf_path)
                    logging.info(f"[process_pdf] Archivo temporal eliminado: {pdf_path}")
            except Exception as e:
                logging.warning(f"[process_pdf] No se pudo eliminar el archivo temporal: {str(e)}")
            
            return final_text

        except FileNotFoundError as e:
            logging.error(f"[process_pdf] Error de archivo no encontrado: {str(e)}")
            return f"Error: Archivo PDF no encontrado en la ruta: {pdf_path}"
        except Exception as e:
            logging.error(f"[process_pdf] Error inesperado al procesar el PDF: {str(e)}")
            return f"Error al procesar el PDF: {str(e)}"

    except FileNotFoundError as e:
        logging.error(f"[process_pdf] Error de archivo no encontrado: {str(e)}")
        return f"Error: {str(e)}"
    except ValueError as e:
        logging.error(f"[process_pdf] Error de validación: {str(e)}")
        return f"Error: {str(e)}"
    except Exception as e:
        logging.error(f"[process_pdf] Error inesperado al procesar el PDF: {str(e)}")
        return f"Error al procesar el PDF: {str(e)}"


from .email_tool import send_email_tool, send_template_email_tool, send_notification_email_tool
from .Tiempo_tool import get_tiempo
from .image_gemini_tool import process_image_with_gemini
from .post_generator_tool import upload_blog_tool
from .post_generator_tool import edit_blog_tool
from .audio_tool import transcribe_audio_tool
# Actualiza la lista de herramientas para exportar
hr_tools_list = [
    verify_country,
    process_pdf,
    send_email_tool,
    send_template_email_tool,
    send_notification_email_tool,
    get_tiempo,
    process_image_with_gemini,
    transcribe_audio_tool,
    upload_blog_tool,
    edit_blog_tool,
]
