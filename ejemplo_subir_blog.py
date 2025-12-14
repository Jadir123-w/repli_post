"""
Ejemplo de uso de la herramienta de publicación de blogs
Este script demuestra cómo subir blogs automáticamente al backend (PostgreSQL)
"""

import sys
import os

# Agregar el directorio app al path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from src.tools.post_generator_tool import post_generator

PDF_PATH = r"C:\Users\Usuario\Downloads\freelancer_backend_perfil.pdf"

def publicar_desde_pdf():
    print("=" * 80)
    print("GENERANDO POST DESDE PDF")
    print("=" * 80)
    
    if not os.path.exists(PDF_PATH):
        print(f"❌ No se encontró el PDF en: {PDF_PATH}")
        print("Verifica la ruta o mueve el archivo allí.")
        return
    
    print(f"📄 Leyendo PDF: {PDF_PATH}")
    
    # Paso 1: Leer el contenido del PDF
    try:
        pdf_result = post_generator.read_pdf_content(PDF_PATH)
        texto_pdf = pdf_result.content
        print("✅ PDF leído correctamente")
        print(f"Texto extraído (primeros 500 caracteres):\n{texto_pdf[:500]}...\n")
    except Exception as e:
        print(f"❌ Error leyendo el PDF: {e}")
        return
    
    # Paso 2: Analizar el contenido
    print("📊 Analizando el contenido del PDF...")
    analysis = post_generator.analyze_content(texto_pdf, content_type="pdf")
    print("Análisis completado.\n")
    
        # Paso 3: Generar post optimizado
    print("✍️ Generando post profesional con Repli...")
    post_message = post_generator.generate_post(
        content=texto_pdf,
        analysis=analysis.content,
        objective="presentar perfil profesional y atraer clientes",
        length="largo",
        cta_type="invitar a conectar o contratar"
    )
    print("✅ Post generado por Repli\n")
    
    # El post completo viene en post_message.content
    raw_post = post_message.content.strip()
    
    # Extraer título (primera línea, normalmente con ** o #)
    lines = raw_post.split('\n')
    title = lines[0].strip('# *').strip()
    content = '\n'.join(lines[1:]).strip()
    
    # Mostrar todo bonito
    print("=" * 80)
    print(f"TÍTULO GENERADO POR REPLI: {title}")
    print("=" * 80)
    print("CONTENIDO COMPLETO:")
    print(content)
    print("=" * 80)
    
    # Paso 4: Publicar
    confirmar = input("\n¿Quieres publicar este post en RepliKers ahora? (s/n): ").strip().lower()
    if confirmar in ['s', 'si', 'sí', 'y', 'yes']:
        print("\n🚀 Publicando en RepliKers...")
        resultado = post_generator.upload_blog_to_api(
            title=title,
            content=raw_post,  # Enviamos todo el post tal como Repli lo generó
            image_url="https://images.unsplash.com/photo-1460925895917-afdab827c52f",  # fallback profesional
            date=None
        )
        print("\n" + resultado.content)
    else:
        print("\nPost no publicado. Puedes copiar el contenido arriba.")
    
    print(resultado.content)
    print("\n")s


def ejemplo_manejo_errores():
    """Ejemplo de manejo de errores"""
    print("=" * 60)
    print("EJEMPLO 4: Manejo de Errores")
    print("=" * 60)
    
    # Intentar subir sin imagen (puede fallar dependiendo del backend)
    resultado = post_generator.upload_blog_to_api(
        title="Blog de Prueba",
        content="# Contenido de prueba",
        image_url=""  # URL vacía
    )
    
    print(resultado.content)
    print("\n")


if __name__ == "__main__":
    print("\n🎯 EJEMPLOS DE USO: upload_blog_to_api\n")
    
    try:
        # Ejecutar ejemplos
        publicar_desde_pdf()
        # ejemplo_manejo_errores()  # Descomenta para probar manejo de errores
        
        print("=" * 60)
        print("✅ Todos los ejemplos completados")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error durante la ejecución: {str(e)}")
        print("\nAsegúrate de que:")
        print("1. El backend esté corriendo en http://localhost:3000")
        print("2. BLOG_VERIFICATION_CODE esté configurado en .env.local")
        print("3. Las variables de entorno estén cargadas correctamente")