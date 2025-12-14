import os
from typing import Annotated, Dict, Any
from langchain_core.tools import InjectedToolCallId, tool
from langchain_core.messages import ToolMessage
from .gemini_utils import process_gemini_response
import logging
import google.generativeai as genai
from PIL import Image
import io

# Si tienes el cliente oficial de Gemini, importa aquí. Ejemplo:
# from google.generativeai import GenerativeModel
# model = GenerativeModel('gemini-2.5-pro')

class ImageGeminiTool:
    """
    Tool para analizar imágenes usando Gemini 2.5 Pro: extrae texto, detecta objetos y los describe.
    """
    def __init__(self, gemini_model=None):
        """
        Args:
            gemini_model: Instancia del modelo Gemini (opcional, para inyección de dependencias o test).
        """
        self.gemini_model = gemini_model  # Si tienes un cliente Gemini, pásalo aquí

    def run(self, image_path):
        """
        Analiza la imagen y retorna texto extraído, objetos detectados y descripciones.
        Args:
            image_path (str): Ruta de la imagen a analizar.
        Returns:
            dict: {
                'text': str,
                'objects': list[dict]  # [{'label': str, 'description': str, 'box': [x1, y1, x2, y2] (opcional)}]
            }
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"La imagen no existe: {image_path}")

        # Cargar la imagen en binario
        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        # Construir el prompt multimodal para Gemini
        prompt = (
            "Analiza la siguiente imagen. 1) Extrae todo el texto visible. "
            "2) Detecta y lista los objetos presentes, indicando si son personas, lugares, cosas, animales, etc. "
            "3) Da una breve descripción de la escena. "
            "Responde en formato JSON con las claves: 'text', 'objects' (lista de objetos con 'label' y 'description'), y 'scene_description'."
        )

        # Llamada al modelo Gemini (esto depende de tu integración)
        # Aquí va un ejemplo genérico, reemplaza por tu llamada real:
        response = self._call_gemini(prompt, image_bytes)
        result_text = process_gemini_response(response)

        # Intentar parsear el resultado como JSON
        import json
        try:
            result = json.loads(result_text)
        except Exception:
            # Si no es JSON válido, devolver el texto plano
            result = {'raw_response': result_text}
        return result

    def _call_gemini(self, prompt, image_bytes):
        """
        Llama al modelo Gemini con el prompt y la imagen. Debes implementar esto según tu integración.
        """
        # Ejemplo de integración (debes reemplazarlo por tu código real):
        # response = self.gemini_model.generate_content([prompt, image_bytes])
        # return response
        raise NotImplementedError("Debes implementar la integración con Gemini aquí.")

@tool
def process_image_with_gemini(
    image_path: str, tool_call_id: Annotated[str, InjectedToolCallId]
) -> str:
    """
    Analiza una imagen usando Gemini 2.5 Pro: extrae texto, detecta objetos y describe la escena.
    Recibe la ruta de la imagen y devuelve un string (JSON serializado o texto plano).
    """
    logging.info(f"[process_image_with_gemini] Procesando imagen: {image_path}")
    try:
        if not os.path.exists(image_path):
            error_msg = f"Error: La imagen '{image_path}' no fue encontrada."
            logging.error(f"[process_image_with_gemini] {error_msg}")
            return error_msg

        # Leer la imagen en binario
        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        # Prompt para Gemini
        prompt = (
            "Analiza la siguiente imagen. 1) Extrae todo el texto visible. "
            "2) Detecta y lista los objetos presentes, indicando si son personas, lugares, cosas, animales, etc. "
            "3) Da una breve descripción de la escena. "
            "Responde en formato JSON con las claves: 'text', 'objects' (lista de objetos con 'label' y 'description'), y 'scene_description'."
        )

        # Llamada al modelo Gemini (debes implementar esta función según tu integración)
        response = _call_gemini_image(prompt, image_bytes)
        result_text = process_gemini_response(response)

        # Intentar parsear el resultado como JSON
        import json
        try:
            parsed = json.loads(result_text)
            # Si es JSON válido, lo devolvemos serializado bonito
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            # Si no es JSON válido, devolver el texto plano
            return result_text

    except Exception as e:
        error_msg = f"Error al procesar la imagen: {str(e)}"
        logging.error(f"[process_image_with_gemini] {error_msg}")
        return error_msg

def _call_gemini_image(prompt, image_bytes):
    # Convertir los bytes a un objeto PIL.Image.Image
    image = Image.open(io.BytesIO(image_bytes))
    model = genai.GenerativeModel('gemini-2.5-pro')
    response = model.generate_content([prompt, image])
    return response

# Ejemplo de uso:
# tool = ImageGeminiTool(gemini_model=mi_modelo_gemini)
# resultado = tool.run('ruta/a/imagen.jpg') 