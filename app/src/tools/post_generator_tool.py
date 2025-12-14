"""
Post Generator Tool para RepliKers Forum
Genera posts profesionales optimizados para el foro interno de RepliKers
usando Gemini AI para análisis y generación de contenido.
Incluye lectura de PDFs, validación de URLs de imágenes y subida a PostgreSQL.
"""

import os
import json
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime
import PyPDF2
from io import BytesIO
import time
import random
import html
import base64

import google.generativeai as genai
import google.api_core.exceptions
from langchain_core.messages import ToolMessage

# Importar configuraciones
from config.settings import (
    MARCELLA_GOOGLE_API_KEY, 
    LLM_MODEL_NAME,
    BLOG_API_URL,
    BLOG_VERIFICATION_CODE
)

# Configurar Gemini
genai.configure(api_key=MARCELLA_GOOGLE_API_KEY)


class PostGeneratorTool:
    """
    Herramienta completa para generación de posts del foro RepliKers.
    Maneja análisis de contenido, validación de seguridad, lectura de PDFs,
    validación de URLs de imágenes y subida automática a PostgreSQL.
    """

    def __init__(self):
        """Inicializa la herramienta con el modelo Gemini configurado."""
        self.model = genai.GenerativeModel(LLM_MODEL_NAME)
        self.posts_history = []  # Historial de posts generados en la sesión
        print("✅ PostGeneratorTool inicializado correctamente")

    def safe_generate_content(self, prompt: str, max_retries: int = 3) -> genai.types.GenerateContentResponse:
        """
        Genera contenido de manera segura con reintentos para manejar rate limits.
        """
        for i in range(max_retries):
            try:
                return self.model.generate_content(prompt)
            except google.api_core.exceptions.ResourceExhausted:
                wait = 2 ** i + random.uniform(0, 1)
                print(f"⚠️ Rate limit detectado. Esperando {wait:.2f} segundos...")
                time.sleep(wait)
            except Exception as e:
                if i == max_retries - 1:
                    raise e
                time.sleep(1)
        raise Exception("Max reintentos alcanzados para generar contenido.")

    def read_pdf_content(
        self,
        pdf_path: str,
        tool_call_id: Optional[str] = None
    ) -> ToolMessage:
        """
        Lee y extrae el contenido de texto de un archivo PDF.

        Args:
            pdf_path: Ruta al archivo PDF local
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con el texto extraído del PDF
        """
        try:
            if not os.path.exists(pdf_path):
                return ToolMessage(
                    content=f"Error: El archivo PDF no existe en la ruta: {pdf_path}",
                    tool_call_id=tool_call_id or "read_pdf_content"
                )

            # Abrir y leer el PDF
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Extraer texto de todas las páginas
                text_content = ""
                total_pages = len(pdf_reader.pages)
                
                for page_num in range(total_pages):
                    page = pdf_reader.pages[page_num]
                    text_content += page.extract_text() + "\n\n"
                
                if not text_content.strip():
                    return ToolMessage(
                        content="Error: No se pudo extraer texto del PDF. Puede estar vacío o ser una imagen escaneada.",
                        tool_call_id=tool_call_id or "read_pdf_content"
                    )
                
                success_message = f"✅ PDF leído exitosamente\n\nPáginas procesadas: {total_pages}\nCaracteres extraídos: {len(text_content)}\n\n--- CONTENIDO ---\n\n{text_content.strip()}"
                
                return ToolMessage(
                    content=success_message,
                    tool_call_id=tool_call_id or "read_pdf_content"
                )

        except PyPDF2.errors.PdfReadError:
            return ToolMessage(
                content="Error: El archivo PDF está corrupto o no es válido.",
                tool_call_id=tool_call_id or "read_pdf_content"
            )
        except Exception as e:
            return ToolMessage(
                content=f"Error leyendo PDF: {str(e)}",
                tool_call_id=tool_call_id or "read_pdf_content"
            )

    def read_pdf_from_bytes(
        self,
        pdf_bytes: Union[bytes, bytearray, str],
        tool_call_id: Optional[str] = None
    ) -> ToolMessage:
        """
        Lee y extrae el contenido de texto de un PDF desde bytes o base64 (archivo subido).

        Args:
            pdf_bytes: Contenido del PDF en bytes, bytearray o base64 string
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con el texto extraído del PDF
        """
        try:
            # Decodificar si es base64
            if isinstance(pdf_bytes, str):
                pdf_bytes = base64.b64decode(pdf_bytes)

            # Crear un objeto BytesIO desde los bytes
            pdf_file = BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extraer texto de todas las páginas
            text_content = ""
            total_pages = len(pdf_reader.pages)
            
            for page_num in range(total_pages):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n\n"
            
            if not text_content.strip():
                return ToolMessage(
                    content="Error: No se pudo extraer texto del PDF. Puede estar vacío o ser una imagen escaneada.",
                    tool_call_id=tool_call_id or "read_pdf_from_bytes"
                )
            
            success_message = f"✅ PDF procesado exitosamente\n\nPáginas: {total_pages}\nCaracteres: {len(text_content)}\n\n--- CONTENIDO ---\n\n{text_content.strip()}"
            
            return ToolMessage(
                content=success_message,
                tool_call_id=tool_call_id or "read_pdf_from_bytes"
            )

        except base64.binascii.Error:
            return ToolMessage(
                content="Error: El string proporcionado no es base64 válido.",
                tool_call_id=tool_call_id or "read_pdf_from_bytes"
            )
        except Exception as e:
            return ToolMessage(
                content=f"Error procesando PDF: {str(e)}",
                tool_call_id=tool_call_id or "read_pdf_from_bytes"
            )

    def validate_image_url(
        self,
        image_url: str,
        tool_call_id: Optional[str] = None
    ) -> ToolMessage:
        """
        Valida que una URL de imagen sea accesible y sea realmente una imagen.

        Args:
            image_url: URL de la imagen a validar
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con el resultado de la validación
        """
        try:
            # Validar formato básico de URL
            url_pattern = re.compile(
                r'^https?://'  # http:// o https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # dominio
                r'localhost|'  # o localhost
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # o IP
                r'(?::\d+)?'  # puerto opcional
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            if not url_pattern.match(image_url):
                return ToolMessage(
                    content=f"❌ URL inválida: {image_url}\n\nLa URL debe comenzar con http:// o https://",
                    tool_call_id=tool_call_id or "validate_image_url"
                )

            # Intentar hacer una petición HEAD para verificar que la URL existe
            response = requests.head(image_url, timeout=10, allow_redirects=True)
            
            if response.status_code != 200:
                return ToolMessage(
                    content=f"❌ URL no accesible (Código {response.status_code}): {image_url}",
                    tool_call_id=tool_call_id or "validate_image_url"
                )
            
            # Verificar que sea una imagen
            content_type = response.headers.get('content-type', '').lower()
            valid_image_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']
            
            if not any(img_type in content_type for img_type in valid_image_types):
                return ToolMessage(
                    content=f"❌ La URL no apunta a una imagen válida.\n\nContent-Type recibido: {content_type}\n\nFormatos aceptados: JPG, PNG, GIF, WebP, SVG",
                    tool_call_id=tool_call_id or "validate_image_url"
                )
            
            return ToolMessage(
                content=f"✅ URL de imagen válida\n\nURL: {image_url}\nTipo: {content_type}\nEstado: Accesible",
                tool_call_id=tool_call_id or "validate_image_url"
            )

        except requests.exceptions.ConnectionError:
            return ToolMessage(
                content=f"❌ Error de conexión: No se pudo acceder a {image_url}\n\nVerifica tu conexión a internet.",
                tool_call_id=tool_call_id or "validate_image_url"
            )
        except requests.exceptions.Timeout:
            return ToolMessage(
                content=f"❌ Tiempo de espera agotado: {image_url} tardó demasiado en responder.",
                tool_call_id=tool_call_id or "validate_image_url"
            )
        except Exception as e:
            return ToolMessage(
                content=f"❌ Error validando URL: {str(e)}",
                tool_call_id=tool_call_id or "validate_image_url"
            )

    def analyze_content(
        self,
        content: str,
        content_type: str = "text",
        tool_call_id: Optional[str] = None
    ) -> ToolMessage:
        """
        Analiza el contenido proporcionado para extraer ideas clave y estructura.

        Args:
            content: Contenido a analizar (texto extraído de PDF, texto directo, etc.)
            content_type: Tipo de contenido ("text", "pdf", "image")
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con el análisis estructurado del contenido
        """
        try:
            analysis_prompt = f"""
            Analiza el siguiente contenido y proporciona un resumen estructurado.

            Contenido a analizar:
            {content}

            Proporciona el análisis en texto natural con la siguiente estructura:

            TEMA CENTRAL: [máximo 10 palabras]

            IDEAS PRINCIPALES:
            - [Idea 1]
            - [Idea 2]
            - [Idea 3-5]

            PROPÓSITO: [educar, informar, compartir experiencia, etc.]

            PÚBLICO OBJETIVO: [descripción del público]

            DATOS RELEVANTES:
            - [Dato/ejemplo 1]
            - [Dato/ejemplo 2]

            TONO: [técnico, experiencial, analítico, etc.]

            POSIBLES LLAMADOS A LA ACCIÓN:
            - [CTA 1]
            - [CTA 2]

            Responde en texto natural y estructurado, NO en formato JSON.
            """

            response = self.safe_generate_content(analysis_prompt)
            analysis_text = response.text.strip()

            return ToolMessage(
                content=analysis_text,
                tool_call_id=tool_call_id or "analyze_content"
            )

        except Exception as e:
            return ToolMessage(
                content=f"Error en análisis: {str(e)}",
                tool_call_id=tool_call_id or "analyze_content"
            )

    def generate_security_questions(
        self,
        content: str,
        tool_call_id: Optional[str] = None
    ) -> ToolMessage:
        """
        Genera 3 preguntas de seguridad basadas en el contenido para validar autoría.

        Args:
            content: Contenido original proporcionado por el usuario
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con las 3 preguntas de seguridad en texto plano
        """
        try:
            questions_prompt = f"""
            Basándote en el siguiente contenido, genera EXACTAMENTE 3 preguntas de seguridad
            que solo el autor original podría responder con confianza.

            Las preguntas deben:
            - Ser específicas sobre detalles del contenido
            - Relacionarse con el contexto o propósito del material
            - Ser imposibles de responder sin conocimiento profundo del tema
            - Evitar preguntas que se puedan responder con "sí" o "no"
            - Requerir explicación o elaboración

            Contenido:
            {content}

            Presenta las 3 preguntas numeradas en texto plano, sin formato JSON.
            Ejemplo:
            1. [Pregunta específica sobre el contenido]
            2. [Pregunta sobre contexto o decisiones del autor]
            3. [Pregunta sobre resultados o aprendizajes específicos]
            """

            response = self.safe_generate_content(questions_prompt)
            questions_text = response.text.strip()

            return ToolMessage(
                content=questions_text,
                tool_call_id=tool_call_id or "generate_security_questions"
            )

        except Exception as e:
            return ToolMessage(
                content=f"Error generando preguntas: {str(e)}",
                tool_call_id=tool_call_id or "generate_security_questions"
            )

    def validate_security_answers(
        self,
        content: str,
        questions: List[str],
        answers: List[str],
        tool_call_id: Optional[str] = None
    ) -> ToolMessage:
        """
        Valida las respuestas de seguridad del usuario usando IA.

        Args:
            content: Contenido original
            questions: Lista de preguntas de seguridad
            answers: Lista de respuestas del usuario
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con resultado de validación en texto plano
        """
        try:
            if len(questions) != 3 or len(answers) != 3:
                return ToolMessage(
                    content="Error: Se requieren exactamente 3 preguntas y 3 respuestas para la validación.",
                    tool_call_id=tool_call_id or "validate_security_answers"
                )

            validation_prompt = f"""
            Evalúa si las respuestas del usuario demuestran conocimiento genuino del contenido.

            CONTENIDO ORIGINAL:
            {content}

            PREGUNTAS Y RESPUESTAS:

            1. Pregunta: {questions[0]}
               Respuesta del usuario: {answers[0]}

            2. Pregunta: {questions[1]}
               Respuesta del usuario: {answers[1]}

            3. Pregunta: {questions[2]}
               Respuesta del usuario: {answers[2]}

            CRITERIOS DE EVALUACIÓN:
            - Coherencia: ¿La respuesta tiene sentido en relación al contenido?
            - Especificidad: ¿Da detalles concretos o es vaga?
            - Conocimiento: ¿Demuestra comprensión profunda del tema?

            Evalúa cada respuesta como "aprobada", "dudosa" o "rechazada".
            Si 2 o más respuestas son dudosas o rechazadas, la validación completa es RECHAZADA.

            Proporciona tu evaluación en texto natural con la siguiente estructura:

            EVALUACIÓN DE RESPUESTAS:

            Pregunta 1: [aprobada/dudosa/rechazada]
            Justificación: [explicación breve]

            Pregunta 2: [aprobada/dudosa/rechazada]
            Justificación: [explicación breve]

            Pregunta 3: [aprobada/dudosa/rechazada]
            Justificación: [explicación breve]

            RESULTADO FINAL: [APROBADA/RECHAZADA]
            Razón: [explicación del resultado general]

            NO uses formato JSON, responde en texto natural.
            """

            response = self.safe_generate_content(validation_prompt)
            validation_text = response.text.strip()

            return ToolMessage(
                content=validation_text,
                tool_call_id=tool_call_id or "validate_security_answers"
            )

        except Exception as e:
            return ToolMessage(
                content=f"Error en validación: {str(e)}",
                tool_call_id=tool_call_id or "validate_security_answers"
            )

    def generate_post(
        self,
        content: str,
        analysis: str,
        objective: str = "compartir conocimiento",
        length: str = "medio",
        cta_type: str = "invitar a comentar",
        tool_call_id: Optional[str] = None
    ) -> ToolMessage:
        """
        Genera el post optimizado para el foro de RepliKers en formato Markdown.

        Args:
            content: Contenido original del usuario
            analysis: Análisis previo del contenido (texto)
            objective: Objetivo del post
            length: Extensión deseada (breve/medio/extenso)
            cta_type: Tipo de llamado a la acción
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con el post generado en Markdown
        """
        try:
            # Determinar rango de palabras según extensión
            length_ranges = {
                "breve": (200, 300),
                "medio": (400, 600),
                "extenso": (700, 1000)
            }
            min_words, max_words = length_ranges.get(length.lower(), (400, 600))

            generation_prompt = f"""
            Genera un post profesional para el foro interno de RepliKers basándote en el siguiente contenido.

            CONTENIDO ORIGINAL:
            {content}

            ANÁLISIS DEL CONTENIDO:
            {analysis}

            PARÁMETROS DEL POST:
            - Objetivo: {objective}
            - Extensión: {length} ({min_words}-{max_words} palabras)
            - Tipo de CTA: {cta_type}

            REQUISITOS ESTRICTOS:
            1. Formato Markdown profesional (usa # para títulos, ## para subtítulos, **negritas**, *cursivas*, - listas, etc. SIN emojis)
            2. Estructura profesional con:
               - Título impactante (5-12 palabras) con # 
               - Introducción gancho (2-3 líneas)
               - Cuerpo desarrollado con párrafos cortos (máx 5 líneas cada uno)
               - Conclusión o reflexión (2-3 líneas)
               - Call to Action claro y relevante (1-2 líneas)
            3. Extensión EXACTA entre {min_words} y {max_words} palabras
            4. Tono profesional pero accesible
            5. Mantener fidelidad al mensaje original
            6. Incluir datos o ejemplos concretos del contenido
            7. Optimizado para comunidad de profesionales de RepliKers

            CALL TO ACTION debe ser:
            - Específico al tipo solicitado: {cta_type}
            - Natural y orgánico al contenido
            - Invitar a participación constructiva

            Genera el post completo en Markdown.
            
            Al final, incluye en líneas separadas:
            ---
            Palabras: [número]
            Tiempo de lectura: [número] minutos

            NO uses formato JSON. Genera el post directamente como texto.
            """

            response = self.safe_generate_content(generation_prompt)
            post_text = response.text.strip()

            # Guardar en historial
            post_record = {
                "timestamp": datetime.now().isoformat(),
                "objective": objective,
                "length": length,
                "cta_type": cta_type,
                "post_content": post_text
            }
            self.posts_history.append(post_record)

            return ToolMessage(
                content=post_text,
                tool_call_id=tool_call_id or "generate_post"
            )

        except Exception as e:
            return ToolMessage(
                content=f"Error generando post: {str(e)}",
                tool_call_id=tool_call_id or "generate_post"
            )

    def improve_post(
        self,
        current_post: str,
        improvement_request: str,
        tool_call_id: Optional[str] = None
    ) -> ToolMessage:
        """
        Mejora o ajusta un post existente según solicitud del usuario.

        Args:
            current_post: Post actual a mejorar
            improvement_request: Descripción específica de qué mejorar
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con el post mejorado en Markdown
        """
        try:
            improvement_prompt = f"""
            Mejora el siguiente post según la solicitud del usuario.

            POST ACTUAL:
            {current_post}

            SOLICITUD DE MEJORA:
            {improvement_request}

            MANTÉN:
            - Formato Markdown profesional sin emojis
            - Estructura profesional
            - Tono apropiado para foro de RepliKers
            - Call to Action efectivo

            Genera el post mejorado completo en Markdown.
            
            Al final, menciona brevemente qué cambios realizaste.

            NO uses formato JSON. Responde directamente con el post mejorado.
            """

            response = self.safe_generate_content(improvement_prompt)
            improved_text = response.text.strip()

            return ToolMessage(
                content=improved_text,
                tool_call_id=tool_call_id or "improve_post"
            )

        except Exception as e:
            return ToolMessage(
                content=f"Error mejorando post: {str(e)}",
                tool_call_id=tool_call_id or "improve_post"
            )

    def calculate_post_metrics(
        self,
        post_content: str,
        tool_call_id: Optional[str] = None
    ) -> ToolMessage:
        """
        Calcula métricas del post (palabras, tiempo de lectura, etc.)

        Args:
            post_content: Contenido del post
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con las métricas en texto plano
        """
        try:
            # Contar palabras
            words = len(post_content.split())

            # Calcular tiempo de lectura (promedio 200 palabras por minuto)
            reading_time = max(1, round(words / 200))

            # Contar párrafos
            paragraphs = len([p for p in post_content.split('\n\n') if p.strip()])

            # Contar líneas
            lines = len([l for l in post_content.split('\n') if l.strip()])

            metrics_text = f"""
MÉTRICAS DEL POST:

Palabras: {words}
Tiempo de lectura estimado: {reading_time} minuto(s)
Párrafos: {paragraphs}
Líneas: {lines}
Caracteres totales: {len(post_content)}
Caracteres sin espacios: {len(post_content.replace(" ", ""))}
            """

            return ToolMessage(
                content=metrics_text.strip(),
                tool_call_id=tool_call_id or "calculate_post_metrics"
            )

        except Exception as e:
            return ToolMessage(
                content=f"Error calculando métricas: {str(e)}",
                tool_call_id=tool_call_id or "calculate_post_metrics"
            )

    def get_post_history(self, tool_call_id: Optional[str] = None) -> ToolMessage:
        """
        Obtiene el historial de posts generados en la sesión actual.

        Args:
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con el historial de posts en texto plano
        """
        if not self.posts_history:
            return ToolMessage(
                content="No hay posts en el historial de esta sesión.",
                tool_call_id=tool_call_id or "get_post_history"
            )

        history_text = f"HISTORIAL DE POSTS GENERADOS ({len(self.posts_history)} total):\n\n"
        
        for i, post in enumerate(self.posts_history, 1):
            history_text += f"""
POST #{i}
Fecha: {post['timestamp']}
Objetivo: {post['objective']}
Extensión: {post['length']}
Tipo de CTA: {post['cta_type']}
---
"""
        
        return ToolMessage(
            content=history_text.strip(),
            tool_call_id=tool_call_id or "get_post_history"
        )

    def upload_blog_to_postgresql(
        self,
        title: str,
        content: str,
        image_url: str,
        date: Optional[str] = None,
        tool_call_id: Optional[str] = None
    ) -> ToolMessage:
        """
        Sube un blog automáticamente a PostgreSQL mediante la API de Node.js.
        Valida obligatoriamente la URL de la imagen antes de subir.
        Cumple con el esquema de BD y endpoints descritos en la documentación:
        - Tabla Blogs con campos: title, date, imageUrl, content (Markdown), slug (auto-generado)
        - Requiere verificationCode del .env
        - Endpoint: POST /api/blog

        Args:
            title: Título del blog (máx 200 caracteres)
            content: Contenido del blog en formato Markdown
            image_url: URL de la imagen principal del blog (OBLIGATORIO)
            date: Fecha de publicación (formato YYYY-MM-DD). Si no se proporciona, usa la fecha actual
            tool_call_id: ID de la llamada de herramienta

        Returns:
            ToolMessage con el resultado de la operación
        """
        try:
            # Validar longitud del título (según recomendaciones para BD)
            if len(title) > 200:
                return ToolMessage(
                    content="❌ ERROR: Título demasiado largo (máximo 200 caracteres).",
                    tool_call_id=tool_call_id or "upload_blog_to_postgresql"
                )

            # Sanitizar contenido para evitar inyecciones (escapar HTML)
            content = html.escape(content)

            # Validar que la URL de imagen esté presente
            if not image_url or not image_url.strip():
                return ToolMessage(
                    content="❌ ERROR: La URL de la imagen es OBLIGATORIA para publicar el post.\n\nProporciona una URL válida de imagen.",
                    tool_call_id=tool_call_id or "upload_blog_to_postgresql"
                )

            # Validar la URL de la imagen
            print(f"🔍 Validando URL de imagen: {image_url}")
            validation_result = self.validate_image_url(image_url)
            
            if "❌" in validation_result.content:
                return ToolMessage(
                    content=f"❌ ERROR: URL de imagen inválida\n\n{validation_result.content}\n\nCorrige la URL y vuelve a intentar.",
                    tool_call_id=tool_call_id or "upload_blog_to_postgresql"
                )
            
            print("✅ URL de imagen validada correctamente")

            # Usar fecha actual si no se proporciona
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")

            # Preparar los datos del blog para PostgreSQL según documentación
            blog_data = {
                "title": title,
                "date": date,
                "imageUrl": image_url,
                "content": content
            }
            
            # Agregar verificationCode solo si está configurado (requerido por documentación)
            if BLOG_VERIFICATION_CODE:
                blog_data["verificationCode"] = BLOG_VERIFICATION_CODE
                print(f"🔐 Usando código de verificación configurado")
            else:
                return ToolMessage(
                    content="❌ ERROR: No hay código de verificación configurado en .env. Es requerido para la API.",
                    tool_call_id=tool_call_id or "upload_blog_to_postgresql"
                )

            # Hacer el request POST a la API de Node.js
            print(f"📤 Enviando blog a: {BLOG_API_URL}")
            response = requests.post(
                BLOG_API_URL,
                json=blog_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            # Procesar la respuesta según documentación
            if response.status_code == 201:
                blog_response = response.json()
                success_message = f"""
✅ BLOG SUBIDO EXITOSAMENTE A POSTGRESQL

Detalles del blog creado:
- ID: {blog_response.get('id', 'N/A')}
- Título: {blog_response.get('title', 'N/A')}
- Slug: {blog_response.get('slug', 'N/A')}
- Fecha: {blog_response.get('date', 'N/A')}
- Imagen: {blog_response.get('imageUrl', 'N/A')}
- Creado: {blog_response.get('createdAt', 'N/A')}

El blog ha sido publicado correctamente en PostgreSQL.
                """
                print("✅ Blog publicado exitosamente")
                return ToolMessage(
                    content=success_message.strip(),
                    tool_call_id=tool_call_id or "upload_blog_to_postgresql"
                )
            
            elif response.status_code == 403:
                return ToolMessage(
                    content="❌ ERROR 403: Código de verificación inválido o falta autenticación.\n\nVerifica BLOG_VERIFICATION_CODE en tu archivo .env",
                    tool_call_id=tool_call_id or "upload_blog_to_postgresql"
                )
            
            else:
                error_data = response.json() if response.content else {}
                error_message = error_data.get('message', 'Error desconocido')
                return ToolMessage(
                    content=f"❌ ERROR {response.status_code}: {error_message}",
                    tool_call_id=tool_call_id or "upload_blog_to_postgresql"
                )

        except requests.exceptions.ConnectionError:
            return ToolMessage(
                content=f"❌ ERROR DE CONEXIÓN: No se pudo conectar al servidor Node.js en {BLOG_API_URL}\n\nVerifica que el backend esté corriendo en el puerto correcto.",
                tool_call_id=tool_call_id or "upload_blog_to_postgresql"
            )
        
        except requests.exceptions.Timeout:
            return ToolMessage(
                content="❌ ERROR: La solicitud tardó demasiado tiempo. El servidor no respondió a tiempo.",
                tool_call_id=tool_call_id or "upload_blog_to_postgresql"
            )
        
        except Exception as e:
            return ToolMessage(
                content=f"❌ ERROR INESPERADO al subir el blog a PostgreSQL: {str(e)}",
                tool_call_id=tool_call_id or "upload_blog_to_postgresql"
            )


# Instancia global de la herramienta
post_generator = PostGeneratorTool()


# Funciones wrapper para integración con LangChain
def read_pdf_content_tool(
    pdf_path: str,
    tool_call_id: Optional[str] = None
) -> ToolMessage:
    """Wrapper para read_pdf_content"""
    return post_generator.read_pdf_content(pdf_path, tool_call_id)


def read_pdf_from_bytes_tool(
    pdf_bytes: Union[bytes, bytearray, str],
    tool_call_id: Optional[str] = None
) -> ToolMessage:
    """Wrapper para read_pdf_from_bytes"""
    return post_generator.read_pdf_from_bytes(pdf_bytes, tool_call_id)


def validate_image_url_tool(
    image_url: str,
    tool_call_id: Optional[str] = None
) -> ToolMessage:
    """Wrapper para validate_image_url"""
    return post_generator.validate_image_url(image_url, tool_call_id)

def analyze_content_tool(
    content: str,
    content_type: str = "text",
    tool_call_id: Optional[str] = None
) -> ToolMessage:
    """Wrapper para analyze_content"""
    return post_generator.analyze_content(content, content_type, tool_call_id)

def generate_security_questions_tool(
    content: str,
    tool_call_id: Optional[str] = None
) -> ToolMessage:
    """Wrapper para generate_security_questions"""
    return post_generator.generate_security_questions(content, tool_call_id)

def validate_security_answers_tool(
    content: str,
    questions: List[str],
    answers: List[str],
    tool_call_id: Optional[str] = None
) -> ToolMessage:
    """Wrapper para validate_security_answers"""
    return post_generator.validate_security_answers(
        content, questions, answers, tool_call_id
    )
    
def generate_post_tool(
    content: str,
    analysis: str,
    objective: str = "compartir conocimiento",
    length: str = "medio",
    cta_type: str = "invitar a comentar",
    tool_call_id: Optional[str] = None
) -> ToolMessage:
    """Wrapper para generate_post"""
    return post_generator.generate_post(
        content, analysis, objective, length, cta_type, tool_call_id
    )
    
def improve_post_tool(
    current_post: str,
    improvement_request: str,
    tool_call_id: Optional[str] = None
) -> ToolMessage:
    """Wrapper para improve_post"""
    return post_generator.improve_post(current_post, improvement_request, tool_call_id)

def calculate_post_metrics_tool(
    post_content: str,
    tool_call_id: Optional[str] = None
) -> ToolMessage:
    """Wrapper para calculate_post_metrics"""
    return post_generator.calculate_post_metrics(post_content, tool_call_id)

def get_post_history_tool(tool_call_id: Optional[str] = None) -> ToolMessage:
    """Wrapper para get_post_history"""
    return post_generator.get_post_history(tool_call_id)

def upload_blog_to_postgresql_tool(
    title: str,
    content: str,
    image_url: str,
    date: Optional[str] = None,
    tool_call_id: Optional[str] = None
) -> ToolMessage:
    """Wrapper para upload_blog_to_postgresql"""
    return post_generator.upload_blog_to_postgresql(
        title, content, image_url, date, tool_call_id
    )

__all__ = [
    "post_generator",
    "read_pdf_content_tool",
    "read_pdf_from_bytes_tool",
    "validate_image_url_tool",
    "analyze_content_tool",
    "generate_security_questions_tool",
    "validate_security_answers_tool",
    "generate_post_tool",
    "improve_post_tool",
    "calculate_post_metrics_tool",
    "get_post_history_tool",
    "upload_blog_to_postgresql_tool",
]