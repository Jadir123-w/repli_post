"""
Ejemplo de uso de la herramienta upload_blog_to_api
Este script demuestra cómo subir blogs automáticamente al backend
"""

import sys
import os

# Agregar el directorio app al path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from src.tools.post_generator_tool import upload_blog_to_api_tool, post_generator


def ejemplo_basico():
    """Ejemplo básico de subida de blog"""
    print("=" * 60)
    print("EJEMPLO 1: Subida Básica de Blog")
    print("=" * 60)
    
    resultado = upload_blog_to_api_tool(
        title="Introducción a la Inteligencia Artificial",
        content="""# Introducción a la Inteligencia Artificial

## ¿Qué es la IA?

La Inteligencia Artificial (IA) es una rama de la informática que busca crear sistemas capaces de realizar tareas que normalmente requieren inteligencia humana.

## Aplicaciones Principales

- **Reconocimiento de voz**: Asistentes virtuales como Siri y Alexa
- **Visión por computadora**: Detección de objetos en imágenes
- **Procesamiento de lenguaje natural**: Chatbots y traducción automática

## Conclusión

La IA está transformando múltiples industrias y continuará evolucionando en los próximos años.
""",
        image_url="https://images.unsplash.com/photo-1677442136019-21780ecad995",
        date="2024-12-05"
    )
    
    print(resultado.content)
    print("\n")


def ejemplo_con_fecha_automatica():
    """Ejemplo sin especificar fecha (usa la actual)"""
    print("=" * 60)
    print("EJEMPLO 2: Subida con Fecha Automática")
    print("=" * 60)
    
    resultado = upload_blog_to_api_tool(
        title="5 Tendencias Tecnológicas para 2025",
        content="""# 5 Tendencias Tecnológicas para 2025

## 1. Computación Cuántica
La computación cuántica promete revolucionar el procesamiento de datos.

## 2. Edge Computing
Procesamiento de datos más cerca de la fuente.

## 3. IA Generativa
Herramientas que crean contenido original.

## 4. Realidad Extendida (XR)
Fusión de realidad virtual y aumentada.

## 5. Blockchain Descentralizado
Nuevas aplicaciones más allá de las criptomonedas.
""",
        image_url="https://images.unsplash.com/photo-1518770660439-4636190af475"
        # No especificamos 'date', usará la fecha actual
    )
    
    print(resultado.content)
    print("\n")


def ejemplo_flujo_completo():
    """Ejemplo del flujo completo: analizar, generar y subir"""
    print("=" * 60)
    print("EJEMPLO 3: Flujo Completo (Analizar → Generar → Subir)")
    print("=" * 60)
    
    contenido_original = """
    En mi experiencia trabajando con equipos remotos, he descubierto que la comunicación 
    asíncrona es clave para la productividad. Herramientas como Slack y Notion nos han 
    permitido mantener a todo el equipo alineado sin necesidad de reuniones constantes.
    
    Los principales beneficios que hemos observado son:
    - Mayor flexibilidad horaria
    - Documentación automática de decisiones
    - Reducción de interrupciones
    - Mejor balance vida-trabajo
    """
    
    # Paso 1: Analizar el contenido
    print("📊 Paso 1: Analizando contenido...")
    analysis = post_generator.analyze_content(contenido_original)
    print(f"Análisis completado.\n")
    
    # Paso 2: Generar post optimizado
    print("✍️ Paso 2: Generando post optimizado...")
    post = post_generator.generate_post(
        content=contenido_original,
        analysis=analysis.content,
        objective="compartir experiencia",
        length="medio",
        cta_type="invitar a compartir experiencias"
    )
    print(f"Post generado.\n")
    
    # Paso 3: Subir el blog
    print("🚀 Paso 3: Subiendo blog al backend...")
    resultado = post_generator.upload_blog_to_api(
        title="Comunicación Asíncrona en Equipos Remotos",
        content=post.content,
        image_url="https://images.unsplash.com/photo-1522071820081-009f0129c71c"
    )
    
    print(resultado.content)
    print("\n")


def ejemplo_manejo_errores():
    """Ejemplo de manejo de errores"""
    print("=" * 60)
    print("EJEMPLO 4: Manejo de Errores")
    print("=" * 60)
    
    # Intentar subir sin imagen (debería fallar en el backend)
    resultado = upload_blog_to_api_tool(
        title="Blog de Prueba",
        content="# Contenido de prueba",
        image_url=""  # URL vacía
    )
    
    print(resultado.content)
    print("\n")


if __name__ == "__main__":
    print("\n🎯 EJEMPLOS DE USO: upload_blog_to_api_tool\n")
    
    try:
        # Ejecutar ejemplos
        ejemplo_basico()
        ejemplo_con_fecha_automatica()
        ejemplo_flujo_completo()
        # ejemplo_manejo_errores()  # Descomenta para probar manejo de errores
        
        print("=" * 60)
        print("✅ Todos los ejemplos completados")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error durante la ejecución: {str(e)}")
        print("\nAsegúrate de que:")
        print("1. El backend esté corriendo en http://localhost:3001")
        print("2. BLOG_VERIFICATION_CODE esté configurado en .env.local")
        print("3. Las variables de entorno estén cargadas correctamente")
