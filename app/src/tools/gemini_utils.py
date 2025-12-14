# gemini_utils.py

def process_gemini_response(response):
    """
    Procesa la respuesta del modelo Gemini de manera consistente.
    
    Args:
        response: La respuesta del modelo Gemini (objeto de respuesta)
        
    Returns:
        str: El texto procesado de la respuesta
    """
    if response is None:
        return ""
    
    # Extraer el texto de la respuesta y eliminar espacios en blanco al inicio y final
    return response.text.strip()