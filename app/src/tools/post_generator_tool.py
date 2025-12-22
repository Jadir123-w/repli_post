import requests
import logging
import os
import sys
from pathlib import Path
from langchain_core.tools import tool
from typing import Optional, Any, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Función para obtener la ruta base del proyecto
def get_project_root():
    current_file = Path(__file__).resolve()
    # Subir niveles: tools -> src -> app -> raíz
    return current_file.parent.parent.parent.parent

# Obtener la ruta base del proyecto
APP_ROOT = get_project_root()

# Añadir el directorio raíz al sys.path para poder importar 'app.config'
if str(APP_ROOT) not in sys.path:
    sys.path.append(str(APP_ROOT))
    logger.info(f"Añadiendo {APP_ROOT} a sys.path")

# Importar configuraciones desde settings
from app.config.settings import BLOG_API_URL

class PostGenerator:
    def read_pdf_content(self, pdf_path: str):
        """Lee el contenido de un PDF usando las herramientas existentes."""
        try:
            # Importar aquí para evitar importaciones circulares si hr_tools importa este archivo
            from app.src.tools.hr_tools import process_pdf
            content = process_pdf(pdf_path)
            # Retornar un objeto con atributo .content para compatibilidad con el script de ejemplo
            return type('obj', (object,), {'content': content})
        except Exception as e:
            logger.error(f"Error leyendo PDF: {e}")
            raise

    def analyze_content(self, text: str, content_type: str = "pdf"):
        """Analiza el contenido (Placeholder/Mock por ahora)."""
        logger.info(f"Analizando contenido de tipo {content_type}...")
        # En una implementación real, esto llamaría al LLM
        analysis = "Análisis del contenido: El documento trata sobre temas legales y corporativos."
        return type('obj', (object,), {'content': analysis})

    def generate_post(self, content: str, analysis: str, objective: str, length: str, cta_type: str):
        """Genera un post (Placeholder/Mock por ahora)."""
        logger.info(f"Generando post con objetivo: {objective}")
        # En una implementación real, esto llamaría al LLM
        generated_content = f"""# Título Generado Automáticamente

Este es un post generado basado en el contenido proporcionado.

## Introducción
{content[:200]}...

## Análisis
{analysis}

## Conclusión
{cta_type}
"""
        return type('obj', (object,), {'content': generated_content})

    def upload_blog_to_api(self, title: str, content: str, image_url: str, date: Optional[str] = None) -> Any:
        """Sube el blog a la API del frontend."""
        # Log prominente de inicio
        print("\n" + "="*80)
        print("🚀 HERRAMIENTA UPLOAD_BLOG_TOOL INVOCADA")
        print("="*80)
        
        logger.info(f"🚀 Iniciando subida de blog: '{title}'")
        logger.info(f"📡 URL de API configurada: {BLOG_API_URL}")
        
        # Si no se proporciona fecha, usar la fecha actual
        if not date:
            from datetime import datetime
            date = datetime.now().strftime("%Y-%m-%d")
            logger.info(f"📅 Fecha no proporcionada, usando fecha actual: {date}")
            print(f"📅 Fecha automática: {date}")
        
        # Construir payload según los parámetros que espera el backend
        # Backend REQUIERE: title, date, imageUrl, content
        payload = {
            "title": title,
            "date": date,  # ¡REQUERIDO por el backend!
            "imageUrl": image_url,  # Backend espera "imageUrl" no "image"
            "content": content
        }
        
        print(f"📝 Título: {title}")
        print(f"🖼️  Imagen: {image_url[:60]}...")
        print(f"📄 Contenido: {len(content)} caracteres")
        print("-"*80)
        
        try:
            logger.info(f"📤 Enviando petición POST a {BLOG_API_URL}")
            print(f"📤 Enviando petición a: {BLOG_API_URL}")
            logger.info(f"📦 Payload: title='{title}', date='{date}', imageUrl='{image_url[:50]}...'")
            
            response = requests.post(BLOG_API_URL, json=payload, timeout=30)
            
            logger.info(f"📥 Respuesta recibida: Status {response.status_code}")
            print(f"📥 Status HTTP: {response.status_code}")
            
            if response.status_code in [200, 201]:
                try:
                    response_data = response.json()
                    blog_id = response_data.get('id', 'unknown')
                    logger.info(f"✅ Blog subido exitosamente. ID: {blog_id}")
                    
                    print("-"*80)
                    print(f"✅ ¡ÉXITO! Blog publicado con ID: {blog_id}")
                    print("="*80 + "\n")
                    
                    return type('obj', (object,), {'content': f"✅ Blog '{title}' subido exitosamente. ID: {blog_id}"})
                except Exception as json_error:
                    logger.warning(f"No se pudo parsear JSON de respuesta exitosa: {json_error}")
                    print("-"*80)
                    print(f"✅ Blog publicado exitosamente (sin ID en respuesta)")
                    print("="*80 + "\n")
                    return type('obj', (object,), {'content': f"✅ Blog '{title}' subido exitosamente (sin ID en respuesta)"})
            else:
                error_msg = f"❌ Error al subir blog: {response.status_code} - {response.text}"
                logger.error(error_msg)
                logger.error(f"💡 Verifica que el backend esté funcionando correctamente en: {BLOG_API_URL}")
                
                print("-"*80)
                print(f"❌ ERROR: Status {response.status_code}")
                print(f"Respuesta: {response.text[:200]}")
                print("="*80 + "\n")
                
                return type('obj', (object,), {'content': error_msg})
                
        except requests.exceptions.ConnectionError as e:
            error_msg = f"❌ Error de conexión: No se pudo conectar a {BLOG_API_URL}. Asegúrate de que el frontend esté corriendo."
            logger.error(error_msg)
            logger.error(f"Detalles del error: {str(e)}")
            return type('obj', (object,), {'content': error_msg})
        except requests.exceptions.Timeout:
            error_msg = f"❌ Timeout: La petición a {BLOG_API_URL} tardó demasiado."
            logger.error(error_msg)
            return type('obj', (object,), {'content': error_msg})
        except Exception as e:
            error_msg = f"❌ Excepción al subir blog: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(traceback.format_exc())
            return type('obj', (object,), {'content': error_msg})
        
    def edit_blog_in_api(self, blog_id: str, title: Optional[str] = None, content: Optional[str] = None, image_url: Optional[str] = None) -> Any:
        """Edita un blog existente y confirma el título afectado."""
        print("\n" + "="*80)
        print(f"📝 EDITANDO PUBLICACIÓN ID: {blog_id}")
        print("="*80)

        # Construir payload solo con campos no nulos
        payload = {k: v for k, v in {
            "title": title,
            "content": content,
            "imageUrl": image_url
        }.items() if v is not None}

        edit_url = f"{BLOG_API_URL}/{blog_id}"

        try:
            logger.info(f"📤 Enviando actualización (PATCH) a {edit_url}")
            # Usamos PATCH para actualizaciones parciales
            response = requests.patch(edit_url, json=payload, timeout=30)
            
            if response.status_code in [200, 204]:
                # Intentamos obtener el título para confirmar al cliente
                updated_title = title if title else "contenido del post"
                logger.info(f"✅ Edición exitosa para ID: {blog_id}")
                
                return type('obj', (object,), {
                    'content': f"✅ Se ha editado exitosamente la publicación: '{updated_title}' (ID: {blog_id})."
                })
            else:
                error_msg = f"❌ Error al editar: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return type('obj', (object,), {'content': error_msg})
                
        except Exception as e:
            error_msg = f"❌ Excepción al intentar editar: {str(e)}"
            logger.error(error_msg)
            return type('obj', (object,), {'content': error_msg})

# Instancia global para usar en el script de ejemplo
post_generator = PostGenerator()

# Herramienta LangChain para ser usada por el agente
@tool
def upload_blog_tool(title: str, content: str, image_url: str) -> str:
    """
    Sube un blog al sitio web (frontend).
    Úsalo cuando necesites publicar un artículo o post generado.
    
    Args:
        title: El título del blog post.
        content: El contenido completo del blog post (puede incluir Markdown).
        image_url: La URL de la imagen de portada para el blog.
    """
    result = post_generator.upload_blog_to_api(title, content, image_url)
    return result.content
@tool
def edit_blog_tool(blog_id: str, title: Optional[str] = None, content: Optional[str] = None, image_url: Optional[str] = None) -> str:
    """
    Edita un blog post existente en el sitio web.
    Es obligatorio proporcionar el blog_id obtenido al publicar. 
    Solo envía los campos que deseas cambiar (title, content o image_url).
    Esta herramienta confirmará el título de la publicación editada.
    """
    result = post_generator.edit_blog_in_api(blog_id, title, content, image_url)
    return result.content
