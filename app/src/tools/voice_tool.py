# src/tools/voice_tool.py
import os
import sys
import logging
import tempfile
import base64
from pathlib import Path
from typing import Annotated, Dict, Any, Optional
from langchain_core.tools import InjectedToolCallId, tool
from langchain_core.messages import ToolMessage
import wave
import io
from google.cloud import texttospeech
from google.cloud import speech_v1

# Función para obtener la ruta base del proyecto
def get_project_root():
    current_file = Path(__file__).resolve()
    app_dir = current_file.parent.parent.parent
    return app_dir

# Obtener la ruta base del proyecto
APP_ROOT = get_project_root()

# Añadir el directorio 'app' al sys.path para poder importar 'config'
if str(APP_ROOT) not in sys.path:
    sys.path.append(str(APP_ROOT))

# Importar configuración
try:
    from config.settings import MARCELLA_GOOGLE_API_KEY
except ImportError:
    # Fallback para cuando se ejecuta desde test_tools
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from config.settings import MARCELLA_GOOGLE_API_KEY

# Configurar logging
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN DE VOCES
# ============================================================================

# Voces disponibles para español peruano
PERUVIAN_VOICES = {
    "es-PE-Standard-A": {
        "name": "es-PE-Standard-A",
        "language_code": "es-PE",
        "gender": "FEMALE",
        "description": "Voz femenina estándar peruana (recomendada)",
        "quality": "high",
        "speaking_rate": 0.9,
        "pitch": 0.0,
        "volume_gain_db": 0.0
    },
    "es-PE-Standard-B": {
        "name": "es-PE-Standard-B",
        "language_code": "es-PE",
        "gender": "MALE",
        "description": "Voz masculina estándar peruana",
        "quality": "high",
        "speaking_rate": 0.9,
        "pitch": 0.0,
        "volume_gain_db": 0.0
    },
    "es-PE-Wavenet-A": {
        "name": "es-PE-Wavenet-A",
        "language_code": "es-PE",
        "gender": "FEMALE",
        "description": "Voz femenina Wavenet peruana (máxima calidad)",
        "quality": "premium",
        "speaking_rate": 0.9,
        "pitch": 0.0,
        "volume_gain_db": 0.0
    },
    "es-PE-Wavenet-B": {
        "name": "es-PE-Wavenet-B",
        "language_code": "es-PE",
        "gender": "MALE",
        "description": "Voz masculina Wavenet peruana (máxima calidad)",
        "quality": "premium",
        "speaking_rate": 0.9,
        "pitch": 0.0,
        "volume_gain_db": 0.0
    }
}

# Voces alternativas en español (no específicamente peruanas)
SPANISH_VOICES = {
    "es-ES-Standard-A": {
        "name": "es-ES-Standard-A",
        "language_code": "es-ES",
        "gender": "FEMALE",
        "description": "Voz femenina española estándar",
        "quality": "high",
        "speaking_rate": 0.9,
        "pitch": 0.0,
        "volume_gain_db": 0.0
    },
    "es-ES-Wavenet-A": {
        "name": "es-ES-Wavenet-A",
        "language_code": "es-ES",
        "gender": "FEMALE",
        "description": "Voz femenina española Wavenet (máxima calidad)",
        "quality": "premium",
        "speaking_rate": 0.9,
        "pitch": 0.0,
        "volume_gain_db": 0.0
    }
}

# Configuración por defecto
DEFAULT_VOICE = "es-ES-Standard-A"
DEFAULT_LANGUAGE_CODE = "es-PE"

# Configuración de audio
AUDIO_CONFIG = {
    "encoding": "MP3",
    "sample_rate_hertz": 16000,
    "speaking_rate": 0.9,  # Ligeramente más lento para claridad
    "pitch": 0.0,  # Tono normal
    "volume_gain_db": 0.0,  # Volumen normal
    "effects_profile_id": ["headphone-class-device"]  # Optimizado para auriculares
}

# Configuración de reconocimiento de voz
SPEECH_CONFIG = {
    "language_code": "es-PE",
    "enable_automatic_punctuation": True,
    "enable_word_time_offsets": False,
    "enable_word_confidence": True,
    "model": "latest_long",  # Mejor para conversaciones largas
    "use_enhanced": True  # Usar modelo mejorado si está disponible
}

def get_voice_config(voice_name: str = None) -> dict:
    """
    Obtiene la configuración de una voz específica

    Args:
        voice_name: Nombre de la voz (si es None, usa la voz por defecto)

    Returns:
        Configuración de la voz
    """
    if voice_name is None:
        voice_name = DEFAULT_VOICE

    # Buscar en voces peruanas primero
    if voice_name in PERUVIAN_VOICES:
        return PERUVIAN_VOICES[voice_name]

    # Buscar en voces españolas
    if voice_name in SPANISH_VOICES:
        return SPANISH_VOICES[voice_name]

    # Si no se encuentra, devolver la voz por defecto
    return PERUVIAN_VOICES[DEFAULT_VOICE]

def get_available_voices() -> dict:
    """
    Obtiene todas las voces disponibles

    Returns:
        Diccionario con todas las voces disponibles
    """
    return {
        "peruvian": PERUVIAN_VOICES,
        "spanish": SPANISH_VOICES,
        "default": DEFAULT_VOICE
    }

def is_premium_voice(voice_name: str) -> bool:
    """
    Verifica si una voz es premium (Wavenet)

    Args:
        voice_name: Nombre de la voz

    Returns:
        True si es premium, False si es estándar
    """
    voice_config = get_voice_config(voice_name)
    return voice_config.get("quality") == "premium"

def get_best_peruvian_female_voice() -> str:
    """
    Obtiene la mejor voz femenina peruana disponible

    Returns:
        Nombre de la mejor voz femenina peruana
    """
    # Priorizar Wavenet por calidad
    for voice_name, config in PERUVIAN_VOICES.items():
        if config["gender"] == "FEMALE" and config["quality"] == "premium":
            return voice_name

    # Si no hay Wavenet, usar Standard
    for voice_name, config in PERUVIAN_VOICES.items():
        if config["gender"] == "FEMALE":
            return voice_name

    # Fallback a la voz por defecto
    return DEFAULT_VOICE

# ============================================================================
# CLASE PRINCIPAL DE HERRAMIENTA DE VOZ
# ============================================================================

class VoiceTool:
    """Herramienta para conversión de voz usando Google Cloud APIs"""

    def __init__(self):
        self.google_api_key = MARCELLA_GOOGLE_API_KEY
        self.speech_client = None
        self.tts_client = None
        self._initialize_clients()

    def _initialize_clients(self):
        """Inicializa los clientes de Google Cloud"""
        try:
            # Configurar credenciales si están disponibles
            if os.path.exists(os.path.join(APP_ROOT, 'config', 'conauti-core-8c0a52a81bdb.json')):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(
                    APP_ROOT, 'config', 'conauti-core-8c0a52a81bdb.json'
                )

            self.speech_client = speech_v1.SpeechClient()
            self.tts_client = texttospeech.TextToSpeechClient()
            logger.info("Clientes de Google Cloud Speech y TTS inicializados correctamente")

        except ImportError:
            logger.warning("Google Cloud Speech/TTS no disponible. Instala: pip install google-cloud-speech google-cloud-texttospeech")
            self.speech_client = None
            self.tts_client = None
        except Exception as e:
            logger.error(f"Error inicializando clientes de Google Cloud: {e}")
            self.speech_client = None
            self.tts_client = None

    def speech_to_text(self, audio_data: bytes, language_code: str = "es-ES") -> str:
        """
        Convierte audio a texto usando Google Cloud Speech-to-Text

        Args:
            audio_data: Datos de audio en bytes (WAV, FLAC, etc.)
            language_code: Código de idioma (es-ES por defecto)

        Returns:
            Texto transcrito del audio
        """
        if not self.speech_client:
            raise RuntimeError("Cliente de Speech-to-Text no disponible")

        try:
            # Configurar el audio
            audio = speech_v1.RecognitionAudio(content=audio_data)
            # Configuración sin sample_rate_hertz ni encoding
            config = speech_v1.RecognitionConfig(
                language_code=language_code,
                enable_automatic_punctuation=SPEECH_CONFIG["enable_automatic_punctuation"],
                enable_word_time_offsets=SPEECH_CONFIG["enable_word_time_offsets"],
                enable_word_confidence=SPEECH_CONFIG["enable_word_confidence"],
                model=SPEECH_CONFIG["model"],
                use_enhanced=SPEECH_CONFIG["use_enhanced"]
            )

            # Realizar la transcripción
            response = self.speech_client.recognize(config=config, audio=audio)

            # Extraer el texto
            transcript = ""
            for result in response.results:
                transcript += result.alternatives[0].transcript + " "

            return transcript.strip()

        except Exception as e:
            logger.error(f"Error en speech-to-text: {e}")
            raise

    def text_to_speech(self, text: str, voice_name: str = None,
                      output_format: str = "MP3") -> bytes:
        """
        Convierte texto a audio usando Google Cloud Text-to-Speech

        Args:
            text: Texto a convertir a voz
            voice_name: Nombre de la voz (si es None, usa la mejor voz femenina peruana)
            output_format: Formato de salida (MP3, WAV, etc.)

        Returns:
            Datos de audio en bytes
        """
        if not self.tts_client:
            raise RuntimeError("Cliente de Text-to-Speech no disponible")

        # Usar la mejor voz femenina peruana por defecto
        if voice_name is None:
            voice_name = get_best_peruvian_female_voice()

        # Obtener configuración de la voz
        voice_config = get_voice_config(voice_name)

        try:
            # Configurar la síntesis de voz
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Configurar la voz usando la configuración centralizada
            voice = texttospeech.VoiceSelectionParams(
                language_code=voice_config["language_code"],
                name=voice_config["name"],
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE if voice_config["gender"] == "FEMALE" else texttospeech.SsmlVoiceGender.MALE
            )

            # Configurar el formato de audio usando la configuración centralizada
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=voice_config["speaking_rate"],
                pitch=voice_config["pitch"],
                volume_gain_db=voice_config["volume_gain_db"]
            )

            # Realizar la síntesis
            response = self.tts_client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )

            return response.audio_content

        except Exception as e:
            logger.error(f"Error en text-to-speech: {e}")
            raise

# Instancia global de la herramienta de voz
voice_tool_instance = VoiceTool()

# ============================================================================
# HERRAMIENTAS DE LANCHAIN
# ============================================================================

@tool
def speech_to_text_tool(
    audio_base64: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    language_code: str = "es-ES"
) -> Dict[str, Any]:
    """
    Convierte audio a texto usando Google Cloud Speech-to-Text.

    Args:
        audio_base64: Audio codificado en base64 (formato WAV, MP3, FLAC)
        language_code: Código de idioma (es-ES por defecto, siempre forzado)
        tool_call_id: ID de la llamada de la herramienta

    Returns:
        Diccionario con el texto transcrito y metadatos
    """
    print(f"--- [Herramienta speech_to_text] Procesando audio en es-ES (forzado) ---")

    try:
        # Decodificar audio de base64
        audio_data = base64.b64decode(audio_base64)

        # Convertir a texto
        transcript = voice_tool_instance.speech_to_text(audio_data, language_code="es-ES")

        result = f"Audio transcrito exitosamente: '{transcript}'"
        print(f"[Herramienta] Transcripción: {transcript}")

        return {
            "transcript": transcript,
            "language_code": language_code,
            "audio_length_bytes": len(audio_data),
            "messages": [ToolMessage(content=result, tool_call_id=tool_call_id)]
        }

    except Exception as e:
        error_msg = f"Error al transcribir audio: {str(e)}"
        logger.error(error_msg)
        return {
            "transcript": "",
            "error": error_msg,
            "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)]
        }

@tool
def text_to_speech_tool(
    text: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    voice_name: str = None
) -> Dict[str, Any]:
    """
    Convierte texto a audio usando Google Cloud Text-to-Speech.

    Args:
        text: Texto a convertir a voz
        voice_name: Nombre de la voz (si es None, usa la mejor voz femenina peruana)
        tool_call_id: ID de la llamada de la herramienta

    Returns:
        Diccionario con el audio en base64 y metadatos
    """
    print(f"--- [Herramienta text_to_speech] Convirtiendo texto a voz con {voice_name} ---")

    try:
        # Convertir texto a audio
        audio_data = voice_tool_instance.text_to_speech(text, voice_name)

        # Codificar audio en base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        result = f"Texto convertido a audio exitosamente: '{text[:50]}{'...' if len(text) > 50 else ''}'"
        print(f"[Herramienta] Audio generado: {len(audio_data)} bytes")

        return {
            "audio_base64": audio_base64,
            "audio_format": "MP3",
            "voice_name": voice_name,
            "text_length": len(text),
            "audio_size_bytes": len(audio_data),
            "messages": [ToolMessage(content=result, tool_call_id=tool_call_id)]
        }

    except Exception as e:
        error_msg = f"Error al convertir texto a audio: {str(e)}"
        logger.error(error_msg)
        return {
            "audio_base64": "",
            "error": error_msg,
            "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)]
        }

@tool
def voice_conversation_tool(
    audio_base64: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    voice_name: str = None,
    language_code: str = "es-PE"
) -> Dict[str, Any]:
    """
    Herramienta completa de conversación de voz: convierte audio a texto,
    procesa con IA, y convierte la respuesta a audio.

    Args:
        audio_base64: Audio del usuario codificado en base64
        voice_name: Nombre de la voz para la respuesta (si es None, usa la mejor voz femenina peruana)
        language_code: Código de idioma para transcripción (es-PE)
        tool_call_id: ID de la llamada de la herramienta

    Returns:
        Diccionario con transcripción, respuesta de IA y audio de respuesta
    """
    print(f"--- [Herramienta voice_conversation] Procesando conversación de voz ---")

    try:
        # Paso 1: Audio a texto
        audio_data = base64.b64decode(audio_base64)
        user_text = voice_tool_instance.speech_to_text(audio_data, language_code)

        print(f"[Herramienta] Usuario dijo: {user_text}")

        # Paso 2: Aquí normalmente se procesaría con el grafo de IA
        # Por ahora, devolvemos un mensaje de confirmación
        ai_response = f"Entendí que dijiste: '{user_text}'. Esta es una respuesta de prueba de la herramienta de voz."

        # Paso 3: Texto a audio
        response_audio = voice_tool_instance.text_to_speech(ai_response, voice_name)
        response_audio_base64 = base64.b64encode(response_audio).decode('utf-8')

        result = f"Conversación de voz procesada: '{user_text}' -> '{ai_response}'"
        print(f"[Herramienta] Respuesta generada: {len(response_audio)} bytes")

        return {
            "user_transcript": user_text,
            "ai_response": ai_response,
            "response_audio_base64": response_audio_base64,
            "voice_name": voice_name,
            "language_code": language_code,
            "messages": [ToolMessage(content=result, tool_call_id=tool_call_id)]
        }

    except Exception as e:
        error_msg = f"Error en conversación de voz: {str(e)}"
        logger.error(error_msg)
        return {
            "user_transcript": "",
            "ai_response": "",
            "response_audio_base64": "",
            "error": error_msg,
            "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)]
        }

# Lista de herramientas de voz para exportar
voice_tools_list = [
    speech_to_text_tool,
    text_to_speech_tool,
    voice_conversation_tool
]
