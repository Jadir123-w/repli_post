# app/main.py
import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from src.database.mongo_manager import MongoManager
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from src.tools import hr_tools
from chains import graph_definition
import re
# Función para obtener la ruta base del proyecto
def get_project_root():
    # Obtener la ruta del archivo actual
    current_file = Path(__file__).resolve()
    # El directorio actual es la carpeta app
    app_dir = current_file.parent
    # El directorio raíz del proyecto es el padre de app
    project_root = app_dir.parent
    return project_root, app_dir

# Obtener rutas base
project_root, app_dir = get_project_root()
project_root_str = str(project_root)
app_dir_str = str(app_dir)

# Add the parent directory to the PYTHONPATH
# This allows imports from 'config' and 'src' assuming the script is run from the project root
# or the PYTHONPATH is otherwise configured.
if project_root_str not in sys.path:
    sys.path.append(project_root_str)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load environment variables
# Ensure the path to .env is correct relative to where main.py is run from
# If running main.py directly, this path works. If running from project root, adjust.
env_path = os.path.join(app_dir_str, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"Loaded .env file from: {env_path}")
else:
    print(f"Warning: .env file not found at {env_path}. Trying default location.")
    load_dotenv() # Try loading from default location as fallback

# Variable para controlar el nivel de depuración
DEBUG_MODE = False  # Cambiar a True para habilitar mensajes de depuración detallados

# Define a helper class to maintain conversation state
class ConversationMemory:

    def __init__(self, thread_id, mongo_manager):
        self.thread_id = thread_id
        self.db = mongo_manager

        # Cargar mensajes anteriores desde MongoDB si existen
        try:
            previous_messages = self.db.get_conversation_history(thread_id)
            self.messages = []
            for msg in previous_messages:
                # Ensure content is stored, handle potential missing content key gracefully
                content = msg.get("content", "") # Default to empty string if content is missing
                self.messages.append({"role": msg.get("role", "unknown"), "content": content})
            if self.messages:
                print(f"Cargados {len(self.messages)} mensajes anteriores de la conversación.")
        except Exception as e:
            logging.error(f"Error cargando mensajes anteriores: {str(e)}")
            self.messages = []

    def add_message(self, role, content):
        # Ensure content is serializable (string is safe)
        if not isinstance(content, str):
            logging.warning(f"Attempting to add non-string content (Type: {type(content)}). Converting to string.")
            content = str(content)

        self.messages.append({"role": role, "content": content})
        try:
            # Determine speaker based on role for saving
            speaker = "Geraldine" if role == "assistant" else "Usuario"
            self.db.save_message(self.thread_id, speaker, role, content)
        except Exception as e:
            logging.error(f"Error saving message to MongoDB: {str(e)}")

    def get_conversation_history(self):
        return self.messages

    def export_final_chat(self):
        """Exports the conversation to text and JSON files"""
        try:
            # Create exports directory if it doesn't exist
            exports_dir = os.path.join(project_root_str, "exports")
            os.makedirs(exports_dir, exist_ok=True)

            # Generate filenames with timestamp
            timestamp = self.thread_id # Use thread_id for consistency
            txt_filename = os.path.join(exports_dir, f"conversation_{timestamp}.txt")
            json_filename = os.path.join(exports_dir, f"conversation_{timestamp}.json")

            # Write to text file
            with open(txt_filename, "w", encoding="utf-8") as txt_file:
                for msg in self.messages:
                    # Handle potential missing keys gracefully
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    speaker = "Usuario" if role == "user" else "Geraldine"
                    txt_file.write(f"{speaker}: {content}\n\n")

            # Optionally, also export as JSON
            import json
            with open(json_filename, "w", encoding="utf-8") as json_file:
                json.dump(self.messages, json_file, ensure_ascii=False, indent=2)

            return txt_filename, json_filename
        except Exception as e:
            logging.error(f"Error exporting conversation: {str(e)}")
            raise

try:
    # Importa elementos necesarios desde otros módulos
    from chains.graph_definition import State, create_hr_graph
    from app.config.settings import SYSTEM_MESSAGE # Importa el mensaje del sistema
except ImportError as e:
    print(f"Error fatal al importar módulos en main.py: {e}")
    print("Asegúrate de que la estructura de carpetas es correcta y __init__.py existen.")
    print(f"sys.path actual: {sys.path}")
    sys.exit(1) # Salir si no se pueden importar elementos cruciales

# --- Función Principal de Conversación ---
def run_conversation():
    """Inicia y maneja el bucle de conversación con Geraldine."""
    print("Iniciando conversación con Geraldine Vasquez (Abogada Digital)...")

    # Inicializar MongoDB manager
    mongo_manager = MongoManager()

    # Create or get conversation memory
    last_thread = mongo_manager.get_last_active_thread()
    thread_id = last_thread if last_thread else f"cli_{os.urandom(4).hex()}"

    if last_thread:
        print(f"Continuando conversación anterior. ID: {thread_id}\n")
    else:
        print(f"Nueva conversación iniciada. ID: {thread_id}\n")

    # Inicializar memoria de conversación
    conversation_memory = ConversationMemory(thread_id, mongo_manager)

    # Inicializar el sistema RAG
    print("Inicializando sistema RAG para análisis de CVs...")
    rag_system = None # Initialize rag_system to None
    try:
        # Importar y verificar si está disponible
        from src.tools.rag_utils import CVRagSystem
        from app.config.settings import MARCELLA_GOOGLE_API_KEY

        if MARCELLA_GOOGLE_API_KEY:
            rag_system = CVRagSystem(MARCELLA_GOOGLE_API_KEY)
            # Inicializar el sistema RAG con la ruta correcta
            rag_initialized = rag_system.initialize(force_rebuild=False)

            if rag_initialized:
                print("Sistema RAG inicializado correctamente.")
            else:
                print("No se pudo inicializar el sistema RAG. Algunos análisis pueden no estar disponibles.")
                rag_system = None # Ensure rag_system is None if initialization failed
        else:
            print("API Key de Google no configurada. RAG no estará disponible.")
            rag_system = None
    except ImportError:
        print("Módulo RAG no encontrado (src.tools.rag_utils). Funcionalidad de análisis comparativo no disponible.")
        rag_system = None
    except Exception as e:
        print(f"Error al inicializar RAG: {e}")
        rag_system = None

    # Crear el grafo compilado
    print("Compilando el grafo de conversación...")
    graph = create_hr_graph()
    print("Sistema listo para comenzar.")

    # Estado inicial - Cargamos mensajes anteriores si existen, o añadimos un mensaje de inicio
    initial_messages = [SystemMessage(content=SYSTEM_MESSAGE)]

    # Obtener mensajes de la memoria de conversación si existen
    previous_messages = conversation_memory.get_conversation_history()
    if previous_messages: # No need for len > 0 check, empty list is falsy
        print(f"Incorporando {len(previous_messages)} mensajes anteriores al estado inicial.")
        for msg in previous_messages:
            # Ensure content is string before creating Langchain message objects
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if not isinstance(content, str):
                content = str(content) # Convert just in case

            if role == "user":
                initial_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                initial_messages.append(AIMessage(content=content))
            # Add handling for other roles if necessary, e.g., tool messages
            # elif role == "tool":
            #     # Need tool_call_id if recreating ToolMessage, might be complex
            #     # For now, maybe skip or log warning
            #     logging.warning(f"Skipping loading tool message from history: {content}")
            else:
                 logging.warning(f"Mensaje con rol desconocido '{role}' encontrado en el historial.")

    # If no previous messages AND no initial user message added yet, add one.
    # This avoids adding "Hola..." if we loaded history ending in user message.
    if not previous_messages:
         # Check if the last message isn't already a HumanMessage
         if not initial_messages or not isinstance(initial_messages[-1], HumanMessage):
              initial_messages.append(HumanMessage(content="Hola, me gustaría recibir ayuda."))


    current_state = State(
        messages=initial_messages,
        user_name=None,
        country=None,
        country_verified=False,
        cv_summary=None,
        cv_analysis=None,
        cv_info=None
    )

    # Invocar para obtener la primera respuesta de Geraldine if needed
    # Only invoke if the last message in history wasn't from the AI
    should_invoke_initially = True
    if current_state["messages"]:
        last_msg_obj = current_state["messages"][-1]
        # Check if it's AIMessage or if it resembles an AI message structure
        if isinstance(last_msg_obj, AIMessage):
             should_invoke_initially = False
        elif isinstance(last_msg_obj, dict) and last_msg_obj.get("role") == "assistant":
             should_invoke_initially = False


    if should_invoke_initially:
        try:
            if DEBUG_MODE:
                print("--- Invocando grafo inicial ---")
            initial_response = graph.invoke(current_state)
            current_state = initial_response # Actualiza el estado
        except Exception as e:
            print(f"\nError al invocar el grafo inicialmente: {e}")
            logging.exception("Error en la invocación inicial del grafo:")
            print("Verifica la API Key y la configuración del LLM.")
            return # Terminar si la primera invocación falla

        # Mostrar la primera respuesta
        last_message = current_state["messages"][-1] if current_state["messages"] else None
        if isinstance(last_message, AIMessage):
            print(f"\nGeraldine: {last_message.content}")
            # Guardar mensaje de bienvenida en la memoria de conversación
            conversation_memory.add_message("assistant", last_message.content)
        else:
            print(f"\nGeraldine: (Respuesta inicial inesperada)")
            if DEBUG_MODE:
                print(f"Tipo de mensaje: {type(last_message).__name__}")
                print(f"Contenido: {last_message}")
    else:
         # If we didn't invoke, show the last loaded AI message
         last_message = current_state["messages"][-1] if current_state["messages"] else None
         if isinstance(last_message, AIMessage):
             print(f"\nGeraldine: {last_message.content}")
         elif isinstance(last_message, dict) and last_message.get("role") == "assistant":
              print(f"\nGeraldine: {last_message.get('content', '(Mensaje anterior sin contenido)')}")
         else:
             print("\n(Continuando conversación...)")


    # Bucle de conversación
    while True:
        # Lógica para detener si el país fue rechazado
        last_ai_content = ""
        if current_state["messages"]:
            last_message = current_state["messages"][-1]

            # --- START MODIFIED SECTION ---
            # Manejar diferentes tipos de mensajes de forma más robusta
            content_to_check = None
            message_source_type = type(last_message).__name__ # For logging

            if isinstance(last_message, list):
                message_source_type = f"list[{type(last_message[0]).__name__}]" if last_message else "list[empty]"
                # Caso de lista: extraer contenido del primer elemento
                if last_message and len(last_message) > 0:
                    first_item = last_message[0]
                    if hasattr(first_item, 'content'):
                        content_to_check = first_item.content
                    elif isinstance(first_item, str):
                        content_to_check = first_item
                    else:
                        # Attempt to convert unknown item type to string
                        print(f"[Advertencia] Tipo de primer elemento en lista no esperado: {type(first_item)}. Intentando convertir a string.")
                        try:
                            content_to_check = str(first_item)
                        except Exception as e:
                             print(f"[Error] No se pudo convertir el elemento de la lista a string: {e}")
                             content_to_check = "" # Default to empty string on conversion failure

            elif isinstance(last_message, AIMessage):
                # Si es un AIMessage normal
                content_to_check = last_message.content
            elif hasattr(last_message, 'content'):
                # Caso genérico para otros tipos de mensajes con atributo content
                # (e.g., HumanMessage, potentially ToolMessage if content is simple string)
                content_to_check = last_message.content
            else:
                # Fallback if the message object structure is completely unexpected
                 print(f"[Advertencia] Tipo de mensaje final no manejable para verificación de contenido: {message_source_type}. Intentando convertir a string.")
                 try:
                     content_to_check = str(last_message)
                 except Exception as e:
                      print(f"[Error] No se pudo convertir el mensaje final a string: {e}")
                      content_to_check = "" # Default to empty string

            # Ahora procesa content_to_check de manera segura
            if isinstance(content_to_check, str):
                last_ai_content = content_to_check.lower()
            elif content_to_check is not None:
                print(f"[Advertencia] Contenido del último mensaje ({message_source_type}) no es string: {type(content_to_check)}. Convirtiendo a string.")
                try:
                    last_ai_content = str(content_to_check).lower()
                except Exception as e:
                    print(f"[Error] Fallo al convertir contenido a string y aplicar lower(): {e}")
                    last_ai_content = "" # Fallback seguro
            else:
                # Content was None or extraction failed earlier
                last_ai_content = ""
                if DEBUG_MODE:
                     print(f"[Debug] No se pudo extraer contenido del último mensaje ({message_source_type}) para la verificación.")
            # --- END MODIFIED SECTION ---


        # Check continuation condition based on country verification status
        country_status = current_state.get('country')
        verified = current_state.get('country_verified', False) # Default to False if not present

        # Determine if conversation should stop based on country rejection
        # Stop if country is set but verification failed (verified=False)
        # OR if country is set, verified is True, but the AI response indicates rejection.
        is_rejected = False
        rejection_phrases = ["no puedo asistirte", "no está en la lista", "país no válido", "fuera de nuestra área"]
        if country_status is not None and (not verified or any(phrase in last_ai_content for phrase in rejection_phrases)):
             is_rejected = True


        # Decide whether to continue the loop
        # Continue if:
        # 1. Country is None (still gathering info) OR
        # 2. Country is set but not verified yet OR
        # 3. Country is set, verified, AND NOT rejected
        should_continue = (country_status is None) or \
                          (country_status is not None and not verified) or \
                          (country_status is not None and verified and not is_rejected)


        if not should_continue:
            print(f"\nGeraldine: (La conversación ha finalizado { 'debido al rechazo del país' if is_rejected else 'por condición de parada' } ).")
            # Optional: Add a final AI message if needed, e.g., based on is_rejected
            # if is_rejected and not any(phrase in last_ai_content for phrase in rejection_phrases):
            #     final_msg = "Dado que tu país no está en la lista de permitidos, no puedo continuar con la asistencia. ¡Gracias!"
            #     print(f"\nGeraldine: {final_msg}")
            #     conversation_memory.add_message("assistant", final_msg)
            break


        # Obtener entrada del usuario
        try:
            user_input = input("Tú: ")
        except EOFError: # Manejar fin de archivo si se ejecuta en un pipeline
             print("\nEntrada finalizada.")
             break

        if user_input.lower() in ['salir', 'exit', 'quit']:
            print("\nGeraldine: Ha sido un placer. ¡Hasta luego!")
            # Optional: Save a final parting message from AI?
            # conversation_memory.add_message("assistant", "Ha sido un placer. ¡Hasta luego!")
            break

        # Guardar mensaje del usuario en la memoria de conversación
        conversation_memory.add_message("user", user_input)

        # Añadir mensaje del usuario al estado
        # Make sure messages list only contains Langchain message objects
        current_state["messages"] = current_state["messages"] + [HumanMessage(content=user_input)]

        # Invocar el grafo
        try:
            if DEBUG_MODE:
                print(f"--- Invocando grafo con estado: ---")
                # Avoid printing large message lists in debug unless necessary
                debug_state_repr = {k: v if k != 'messages' else f'<{len(v)} messages>' for k, v in current_state.items()}
                print(debug_state_repr)

            response: State = graph.invoke(current_state)
            current_state = response # Actualizar estado local
            if DEBUG_MODE:
                print(f"--- Grafo devolvió estado: ---")
                debug_state_repr = {k: v if k != 'messages' else f'<{len(v)} messages>' for k, v in current_state.items()}
                print(debug_state_repr)

        except Exception as e:
            print(f"\nError durante la invocación del grafo: {e}")
            logging.exception("Error en la invocación del grafo:")
            print("Continuando la conversación, pero puede haber problemas.")
            # Optionally add a placeholder error message to memory/state?
            # error_message = "(Ocurrió un error procesando la solicitud)"
            # current_state["messages"] = current_state["messages"] + [AIMessage(content=error_message)]
            # conversation_memory.add_message("assistant", error_message)


        # Mostrar la última respuesta del AI
        # The state update might add multiple messages (e.g., AI response + Tool result)
        # We usually only want to show the actual AIMessage to the user.
        ai_response_to_show = None
        if current_state["messages"]:
            # Iterate backwards to find the last AIMessage
            for msg in reversed(current_state["messages"]):
                 if isinstance(msg, AIMessage):
                     ai_response_to_show = msg
                     break # Found the last AI message

        if ai_response_to_show:
            content = ai_response_to_show.content

            # Simple check to avoid printing raw tool call info if present
            # Note: More robust parsing might be needed depending on LLM output format
            if content and "tool_calls" in ai_response_to_show.additional_kwargs:
                 # If tool calls exist in kwargs, the content might be just the text part
                 # Or it might include descriptions. Let's assume content is mostly clean here.
                 pass # Keep content as is for now
            elif content and isinstance(content, str) and ("Tool Calls:" in content or "tool_call" in content.lower()):
                 # Fallback: simple string search if tool calls aren't structured
                 lines = content.split('\n')
                 clean_lines = []
                 in_tool_section = False
                 for line in lines:
                     line_strip = line.strip()
                     if line_strip.startswith("Tool Calls:") or line_strip.startswith("tool_call"):
                         in_tool_section = True
                         continue # Skip this line
                     if in_tool_section and not line_strip: # Skip blank lines after tool calls start
                         continue
                     # Simple heuristic: if a line looks like JSON/dict, maybe skip it too?
                     if not (line_strip.startswith('{') and line_strip.endswith('}')):
                          clean_lines.append(line)
                          in_tool_section = False # Reset if it's normal text again


                 content = '\n'.join(clean_lines).strip()


            print(f"\nGeraldine: {content if content else '(Respuesta vacía o solo llamada a herramienta)'}")

            # Guardar respuesta del asistente en la memoria de conversación
            # Ensure we save the same content we showed
            conversation_memory.add_message("assistant", content if content else "")
        else:
            # Handle cases where the last message wasn't AIMessage (e.g., error, or tool)
             if DEBUG_MODE:
                 last_msg_debug = current_state["messages"][-1] if current_state["messages"] else "None"
                 print(f"\n[DEBUG] No se encontró AIMessage como última respuesta. Último mensaje: {type(last_msg_debug).__name__} - {str(last_msg_debug)[:200]}...")
             # Optionally print a generic message to the user
             # print("\nGeraldine: (Procesando...)")


        # Debug: Estado RAG (solo en modo depuración)
        if DEBUG_MODE:
            cv_summary = current_state.get('cv_summary')
            cv_analysis = current_state.get('cv_analysis')
            if cv_summary is not None or cv_analysis is not None:
                 summary_len = len(cv_summary) if cv_summary else 0
                 has_analysis = cv_analysis is not None
                 analysis_detail = ""
                 if has_analysis and isinstance(cv_analysis, dict):
                      good_percent = cv_analysis.get('similarity_profile', {}).get('good_percentage', 0)
                      analysis_detail = f"Análisis RAG: {good_percent:.1f}% similitud"
                 elif has_analysis:
                      analysis_detail = f"Análisis RAG: (Tipo inesperado: {type(cv_analysis)})"
                 else:
                      analysis_detail = "sin análisis RAG"

                 print(f"[DEBUG] Estado CV: Resumen ({summary_len} chars), {analysis_detail}")


    # Exportar conversación al final
    try:
        txt_file, json_file = conversation_memory.export_final_chat()
        print(f"\nConversación guardada en: {txt_file} y {json_file}")
    except Exception as e:
        # Logging already happened in the method
        print("\nNo se pudo exportar la conversación.")

# --- Punto de Entrada Principal ---
if __name__ == "__main__":
    try:
        run_conversation()
        print("\n--- Fin de la Conversación ---")

        # Opción para visualizar el grafo solo en modo depuración
        if DEBUG_MODE:
            visualize = input("¿Deseas intentar generar la visualización del grafo? (s/N): ")
            if visualize.lower() == 's':
                try:
                    # Attempt imports only if needed
                    from IPython.display import Image, display # type: ignore
                    # langgraph might already be imported via graph_definition, but check anyway
                    import langgraph
                    print("Generando visualización del grafo...")
                    try:
                        # Re-create graph instance for visualization if needed
                        graph_to_visualize = create_hr_graph()
                        # Check if draw_mermaid_png is available and works
                        if hasattr(graph_to_visualize.get_graph(), 'draw_mermaid_png'):
                             png_data = graph_to_visualize.get_graph().draw_mermaid_png()
                             if png_data:
                                 display(Image(png_data))
                                 print("Gráfico mostrado arriba (si estás en un entorno compatible como Jupyter/Colab).")
                             else:
                                 print("No se pudo generar la imagen PNG del grafo.")
                                 print("Intentando mostrar sintaxis Mermaid...")
                                 print("\n--- Sintaxis Mermaid del Grafo ---")
                                 print(graph_to_visualize.get_graph().draw_mermaid())
                                 print("--- Fin Sintaxis ---")
                        else:
                             print("Método draw_mermaid_png no disponible. Mostrando sintaxis Mermaid...")
                             print("\n--- Sintaxis Mermaid del Grafo ---")
                             print(graph_to_visualize.get_graph().draw_mermaid())
                             print("--- Fin Sintaxis ---")

                    except Exception as e:
                        print(f"\nError generando visualización: {e}")
                        logging.exception("Error en la visualización del grafo:")
                        # Fallback to mermaid syntax if PNG fails
                        try:
                             graph_to_visualize = create_hr_graph()
                             print("\n--- Sintaxis Mermaid del Grafo (Fallback) ---")
                             print(graph_to_visualize.get_graph().draw_mermaid())
                             print("--- Fin Sintaxis ---")
                        except Exception as inner_e:
                             print(f"No se pudo obtener ni la sintaxis Mermaid: {inner_e}")

                except ImportError:
                    print("Módulos necesarios (IPython, langgraph) no instalados. No se puede visualizar.")
    except KeyboardInterrupt:
        print("\nPrograma terminado por el usuario.")
    except Exception as e:
        logging.error(f"Error inesperado en la ejecución principal: {str(e)}")
        logging.exception("Detalles del error inesperado:") # Log traceback
        print(f"\nError inesperado y fatal: {str(e)}")
    finally:
        print("Cerrando aplicación.")
        sys.exit(0)