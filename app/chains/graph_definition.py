# chains/graph_definition.py
import sys
import os
import re # <-- Added import for regular expressions
from typing import Annotated, List, Optional, Dict
from typing_extensions import TypedDict
import traceback # Import traceback for better error logging


from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


# Importa configuraciones y herramientas
try:
    # Assumes execution context where 'config' and 'src' are findable
    from app.config.settings import MARCELLA_GOOGLE_API_KEY, LLM_MODEL_NAME, LLM_TEMPERATURE, SYSTEM_MESSAGE
    # from app.src.tools import hr_tools_list # Importa la lista de herramientas - COMENTADO TEMPORALMENTE
    hr_tools_list = []  # Lista vacía temporal mientras las tools están comentadas
except ImportError as e:
    print(f"Error importando dependencias en graph_definition.py: {e}")
    print(f"sys.path actual: {sys.path}")
    print("Asegúrate de que la estructura de carpetas es correcta y __init__.py existen.")
    # raise  # Comentado para evitar que falle la aplicación

# --- Debug Mode ---
# Set DEBUG_MODE via environment variable or keep it hardcoded
DEBUG_MODE = os.environ.get("LANGGRAPH_DEBUG", "False").lower() == "true"
# DEBUG_MODE = True # Uncomment to force debug mode

# --- Definición del Estado del Grafo ---
class State(TypedDict):
    """
    Represents the state of the conversation and processing in the graph.
    """
    messages: Annotated[List[BaseMessage], add_messages] # Message history, auto-added
    user_name: Optional[str] # User's name (optional)
    country: Optional[str]   # User's country (optional)
    country_verified: bool   # Flag: indicates if the country is valid
    cv_summary: Optional[str] # Summary or full text extracted from CV
    cv_analysis: Optional[Dict[str, any]] # Result of RAG analysis on CV
    cv_info: Optional[Dict[str, any]] # Structured CV info (future use)

# --- Configuración del LLM ---
def get_llm_with_tools():
    """Creates and configures the LLM instance with bound tools."""
    if not MARCELLA_GOOGLE_API_KEY:
        raise ValueError("Google API Key not configured. Check config/settings.py and .env")

    llm = ChatGoogleGenerativeAI(
        model=LLM_MODEL_NAME,
        google_api_key=MARCELLA_GOOGLE_API_KEY,
        temperature=LLM_TEMPERATURE,
        convert_system_message_to_human=False # Usually correct for Gemini
    )
    # Bind the tools defined in hr_tools_list to the LLM
    return llm.bind_tools(hr_tools_list)

# --- Nodos del Grafo ---

def chatbot_node(state: State):
    """
    Main node interacting with the LLM to generate responses or decide tool usage.
    """
    if DEBUG_MODE:
        print("\n--- [Grafo] Entrando en Nodo: chatbot_node ---")
        print(f"--- [Grafo] Estado actual (keys): {list(state.keys())}")
        # Show last 2 messages for context
        last_messages = state.get('messages', [])[-2:]
        print(f"--- [Grafo] Últimos mensajes ({len(last_messages)}):")
        for m in last_messages:
            print(f"    {m.pretty_repr()}")


    current_messages = list(state.get("messages", [])) # Use list() for a mutable copy

    # --- Initial/Empty State Handling ---
    if not current_messages:
        if DEBUG_MODE:
            print("[WARN] chatbot_node: Message state is empty. Adding system message.")
        if SYSTEM_MESSAGE:
            system_msg = SystemMessage(content=SYSTEM_MESSAGE)
            current_messages = [system_msg]
        else:
            print("[ERROR] chatbot_node: Message state empty and SYSTEM_MESSAGE not defined.")
            return {} # Avoid LLM call if no messages and no system prompt

    # --- Ensure System Message ---
    # Check if the first message is SystemMessage or has type 'system'. If not, prepend it.
    # This handles cases where the initial state might not have included it.
    if not current_messages or not isinstance(current_messages[0], SystemMessage):
        is_system_like = False
        if current_messages and hasattr(current_messages[0], 'type') and current_messages[0].type == 'system':
            is_system_like = True

        if not is_system_like and SYSTEM_MESSAGE:
            if DEBUG_MODE:
                print("[Grafo] chatbot_node: Prepending system message.")
            system_msg = SystemMessage(content=SYSTEM_MESSAGE)
            current_messages.insert(0, system_msg)

    # --- Context Enrichment with CV/RAG Data ---
    last_message = current_messages[-1] if current_messages else None
    should_enrich = bool(state.get("cv_summary") or state.get("cv_analysis"))
    # Avoid adding context again if the last message was a simple AI response.
    # Add context if last message was Human, Tool, or AI message with tool calls.
    is_last_msg_simple_ai = isinstance(last_message, AIMessage) and not last_message.tool_calls

    if should_enrich and not is_last_msg_simple_ai:
        if DEBUG_MODE:
            print("[Grafo] chatbot_node: CV/RAG data detected. Enriching context for LLM.")

        context_parts = []
        cv_text = state.get("cv_summary")
        cv_analysis = state.get("cv_analysis")

        if cv_text:
            limit = 4000
            cv_text_truncated = (cv_text[:limit] + "... [CV truncated]") if len(cv_text) > limit else cv_text
            context_parts.append(f"PROCESSED CV TEXT/SUMMARY:\n{cv_text_truncated}")
            if DEBUG_MODE and len(cv_text) > limit:
                print(f"[Grafo] chatbot_node: CV text truncated to {limit} chars for context.")

        if cv_analysis and isinstance(cv_analysis, dict) and cv_analysis.get("success"):
            similarity_profile = cv_analysis.get("similarity_profile", {})
            good_p = similarity_profile.get("good_percentage", 0)
            good_m = similarity_profile.get("good_matches", 0)
            bad_m = similarity_profile.get("bad_matches", 0)
            analysis_summary = (
                f"COMPARATIVE ANALYSIS (RAG):\n"
                f"- Similarity with good examples: {good_p:.1f}%\n"
                f"- Key matches (good): {good_m}\n"
                f"- Key matches (bad): {bad_m}"
            )
            context_parts.append(analysis_summary)

            examples = cv_analysis.get("context_examples", [])
            if examples:
                context_parts.append("RELEVANT EXAMPLE FRAGMENTS (RAG):")
                limit_examples = 2
                limit_len = 500
                for i, example in enumerate(examples[:limit_examples]):
                    ex_text = getattr(example, 'page_content', str(example)) # Assumes LangChain Doc structure
                    ex_text_truncated = (ex_text[:limit_len] + "...[truncated]") if len(ex_text) > limit_len else ex_text
                    context_parts.append(f"- Example {i+1}: {ex_text_truncated}")

        if context_parts:
            context_instruction = (
                "[Internal Context Addition for response generation. Do not mention this directly to the user "
                "unless relevant to their question about the analysis or CV. "
                "Use this information for more specific advice or interpreting results if asked.]\n\n"
                + "\n\n".join(context_parts) +
                "\n\n[End of Internal Context]"
            )
            context_message = SystemMessage(content=context_instruction, name="internal_context") # Added name for clarity
            # Insert before the last message (usually user question or tool response)
            if len(current_messages) > 0:
                current_messages.insert(-1, context_message)
            else:
                current_messages.append(context_message) # Should not happen if sys msg logic works

            if DEBUG_MODE:
                print(f"[Grafo] chatbot_node: Internal context added:\n{context_instruction[:300]}...")

    # --- Filter Invalid/Empty Messages ---
    final_messages_for_llm = []
    for msg in current_messages:
        valid = False
        content = getattr(msg, 'content', None)
        msg_type = type(msg).__name__

        if isinstance(msg, BaseMessage):
            # Allow messages with string content
            if isinstance(content, str) and content.strip():
                valid = True
            # Allow AIMessages with tool calls, even if content is empty
            elif isinstance(msg, AIMessage) and getattr(msg, 'tool_calls', None):
                valid = True
            # Allow ToolMessages - attempt to stringify content if not already string
            elif isinstance(msg, ToolMessage):
                if not isinstance(content, str):
                    try:
                        # Attempt to modify the message content in-place (might be risky depending on object immutability)
                        # A safer approach might be to create a new ToolMessage if modification fails.
                        stringified_content = str(content)
                        msg.content = stringified_content # Modify content
                        valid = True
                        if DEBUG_MODE: print(f"[WARN] chatbot_node: Converted non-string ToolMessage content to string: {stringified_content[:100]}...")
                    except Exception as e:
                        if DEBUG_MODE: print(f"[WARN] chatbot_node: Failed to convert ToolMessage content to string: {e}. Filtering message.")
                        valid = False
                else:
                    valid = True # It's a ToolMessage with string content

        if valid:
            final_messages_for_llm.append(msg)
        elif DEBUG_MODE:
            msg_repr = msg.pretty_repr() if hasattr(msg, 'pretty_repr') else str(msg)
            print(f"[WARN] chatbot_node: Filtering invalid/empty message: Type={msg_type}, Content='{str(content)[:100]}...'")


    if not final_messages_for_llm:
        if DEBUG_MODE:
            print("[ERROR] chatbot_node: No valid messages remaining after filtering. Aborting LLM call.")
        return {} # Return empty dict to avoid errors downstreams

    # --- START OF REPLACED BLOCK ---

    # --- Llamada al LLM ---
    llm_with_tools = get_llm_with_tools() # Obtiene el LLM configurado
    if DEBUG_MODE:
        print(f"--- [Grafo] Mensajes FINALES enviados al LLM ({len(final_messages_for_llm)}): ---")
        # Imprimir representación más corta en debug
        for i, m in enumerate(final_messages_for_llm):
            tool_calls_present = len(getattr(m, 'tool_calls', [])) > 0 if isinstance(m, AIMessage) else False
            print(f"  {i}: Type={type(m).__name__}, Content='{str(getattr(m, 'content', 'N/A'))[:100]}...', ToolCalls={tool_calls_present}")
        print("--- [Grafo] Llamando al LLM... ---")

    # Invocar el LLM con los mensajes finales procesados
    try:
        response = llm_with_tools.invoke(final_messages_for_llm)
        
        # Asegúrate de que la respuesta sea un AIMessage
        if not isinstance(response, AIMessage):
            response = AIMessage(content=str(response))
        
        # Procesamiento de la respuesta para corregir problemas conocidos
        if isinstance(response, AIMessage) and response.content and isinstance(response.content, str):
            content = response.content
            original_content = content # Keep original for comparison

            # Corregir problema de URLs duplicadas en formato markdown
            url_pattern = r'\[(https?://[^\]]+)\]\(\1\)' # Use backreference \1 to ensure URLs match
            urls_found = re.findall(url_pattern, content) # Find only the URL part

            modified = False
            if urls_found:
                if DEBUG_MODE: 
                    print(f"--- [Grafo] Found duplicated URL patterns to potentially fix: {urls_found}")
                
                def replace_link(match):
                    nonlocal modified # Allow modification of outer scope variable
                    full_match_text = match.group(0) # e.g., [http://...](http://...)
                    actual_url = match.group(1)      # e.g., http://...
                    
                    # Create a link with more descriptive text
                    if 'docs.google.com/document' in actual_url:
                        replacement = f"[Ver CV en Google Docs]({actual_url})"
                    elif 'drive.google.com' in actual_url:
                        replacement = f"[Ver archivo en Google Drive]({actual_url})"
                    else:
                        replacement = f"[Ver enlace]({actual_url})"

                    if replacement != full_match_text:
                        modified = True # Mark that a change happened
                        if DEBUG_MODE: 
                            print(f"--- [Grafo] Replacing link '{full_match_text}' with '{replacement}'")
                        return replacement
                    else:
                        return full_match_text # Return original if no change needed

                content = re.sub(url_pattern, replace_link, content)

            # Si se hicieron cambios, actualizar el contenido del mensaje
            if modified:
                if DEBUG_MODE:
                    print("--- [Grafo] Se corrigió el formato de enlaces duplicados en la respuesta ---")
                response.content = content # Update the response object's content
            elif DEBUG_MODE and urls_found:
                print("--- [Grafo] Duplicated URL patterns found, but replacement logic didn't change them.")

        if DEBUG_MODE:
            resp_repr = response.pretty_repr() if hasattr(response, 'pretty_repr') else str(response)
            print(f"--- [Grafo] Respuesta recibida del LLM: {resp_repr} ---")
            print("--- [Grafo] Saliendo de Nodo: chatbot_node ---")

        return {"messages": [response]}

    except Exception as e:
        print(f"Error en chatbot_node: {e}")
        error_message = AIMessage(content=f"Ocurrió un error: {str(e)}")
        return {"messages": [error_message]}

    # --- END OF REPLACED BLOCK ---


# --- Nodo para Procesamiento RAG ---
def rag_processor_node(state: State):
    """
    Node dedicated to performing RAG analysis on the CV text.
    Activated conditionally after a tool extracts the CV.
    """
    if DEBUG_MODE:
        print("\n--- [Grafo] Entrando en Nodo: rag_processor_node ---")

    cv_summary = state.get("cv_summary")
    cv_analysis_present = state.get("cv_analysis") is not None

    # Proceed only if we have a CV summary and *don't* already have RAG analysis
    if cv_summary and not cv_analysis_present:
        if not isinstance(cv_summary, str) or len(cv_summary) < 50: # Basic validity check
            if DEBUG_MODE:
                print("[WARN] rag_processor_node: cv_summary seems invalid or too short. Skipping RAG.")
            return {} # No changes to state

        if DEBUG_MODE:
            print("[Grafo] rag_processor_node: Initiating RAG analysis...")
            print(f"[Grafo] CV Text for RAG (first 100 chars): {cv_summary[:100]}...")

        # RAG analysis temporalmente comentado mientras las tools están deshabilitadas
        if DEBUG_MODE:
            print("[Grafo] rag_processor_node: RAG analysis temporalmente deshabilitado.")
        
        # analysis_result = None
        # try:
        #     # Local import to avoid hard dependency if RAG isn't used/installed
        #     from src.tools.rag_utils import CVRagSystem

        #     # Consider initializing RAG system (loading vectors) once outside the node for efficiency
        #     # For simplicity, doing it here. Requires MARCELLA_GOOGLE_API_KEY for embeddings potentially.
        #     rag_system = CVRagSystem(api_key=MARCELLA_GOOGLE_API_KEY)
        #     initialized = rag_system.initialize(force_rebuild=False) # Avoid rebuilding index each time if possible

        #     if initialized:
        #         analysis_result = rag_system.analyze_cv(cv_summary)

        #         if analysis_result and isinstance(analysis_result, dict) and analysis_result.get("success"):
        #             if DEBUG_MODE:
        #                 print("[Grafo] rag_processor_node: RAG analysis completed successfully.")
        #                 # Optional detailed logging:
        #                 # sim_prof = analysis_result.get('similarity_profile', {})
        #                 # print(f"[Grafo] RAG Result: Good={sim_prof.get('good_percentage', 0):.1f}%, "
        #                 #       f"Matches(G/B)={sim_prof.get('good_matches',0)}/{sim_prof.get('bad_matches',0)}")
        #             return {"cv_analysis": analysis_result} # Update state with analysis
        #         else:
        #             error_msg = "Invalid result or analysis failed."
        #             if isinstance(analysis_result, dict):
        #                 error_msg = analysis_result.get('error', error_msg)
        #             if DEBUG_MODE:
        #                 print(f"[WARN] rag_processor_node: RAG analysis failed or reported unsuccessful: {error_msg}")
        #             # Do not update cv_analysis state
        #     else:
        #         if DEBUG_MODE:
        #             print("[ERROR] rag_processor_node: Failed to initialize RAG system.")

        # except ImportError:
        #     if DEBUG_MODE:
        #         print("[ERROR] rag_processor_node: RAG module (src.tools.rag_utils.CVRagSystem) not found. Ensure it exists and dependencies are installed.")
        # except Exception as e:
        #     if DEBUG_MODE:
        #         print(f"[ERROR] rag_processor_node: Unexpected error during RAG analysis: {e}")
        #         traceback.print_exc() # Print full stack trace for debugging

    elif cv_analysis_present:
        if DEBUG_MODE:
            print("[Grafo] rag_processor_node: RAG analysis already exists in state. Skipping.")
    else: # No cv_summary
        if DEBUG_MODE:
            print("[Grafo] rag_processor_node: No cv_summary in state. Skipping RAG.")


    if DEBUG_MODE:
        print("--- [Grafo] Saliendo de Nodo: rag_processor_node ---")

    # Return empty dict if no success or condition not met, to avoid altering state
    return {}


# --- Construcción y Compilación del Grafo ---
def create_hr_graph():
    """Builds and compiles the LangGraph graph with defined nodes and edges."""
    if DEBUG_MODE:
        print("\n--- [Grafo] Iniciando construcción del grafo ---")

    graph_builder = StateGraph(State)

    # --- Add Nodes ---
    if DEBUG_MODE: print("[Grafo] Añadiendo nodos: chatbot, rag_processor, tools")
    graph_builder.add_node("chatbot", chatbot_node)
    graph_builder.add_node("rag_processor", rag_processor_node)
    tool_node = ToolNode(tools=hr_tools_list) # ToolNode executes tools selected by LLM
    graph_builder.add_node("tools", tool_node)

    # --- Define Entry Point ---
    if DEBUG_MODE: print("[Grafo] Estableciendo punto de entrada: chatbot")
    graph_builder.set_entry_point("chatbot")

    # --- Define Edges (Control Flow) ---

    # 1. From Chatbot: Use tools or end?
    if DEBUG_MODE: print("[Grafo] Añadiendo borde condicional: chatbot -> (tools | END)")
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition, # LangGraph's function checking for tool_calls in last AIMessage
        {
            "tools": "tools", # If tool_calls exist -> go to 'tools' node
            END: END          # If no tool_calls -> end the cycle (wait for next input)
        }
    )

    # 2. From Tools: Need RAG or back to Chatbot?
    # Reemplaza la función post_tools_decision en graph_definition.py con esto:

    def post_tools_decision(state: State):
        """
        Decides the next step after tool execution.
        If 'cv_summary' was likely added by a tool (present now but 'cv_analysis' isn't), go to RAG.
        Otherwise, return to the chatbot to process the tool's output.
        """
        # Mueve estas definiciones fuera del bloque DEBUG_MODE
        # para que siempre existan independientemente de DEBUG_MODE
        cv_summary_present = state.get("cv_summary") is not None
        cv_analysis_present = state.get("cv_analysis") is not None
        
        if DEBUG_MODE:
            print("--- [Grafo] Entrando en Decisión: post_tools_decision ---")
            last_msg = state['messages'][-1] if state['messages'] else None
            tool_ran = isinstance(last_msg, ToolMessage) # Check if the last message is from a tool
            print(f"--- [Grafo Decision] Tool Ran: {tool_ran}, CV Summary: {cv_summary_present}, CV Analysis: {cv_analysis_present} ---")

        # Check if cv_summary is present AND cv_analysis is NOT present.
        # This implies RAG is needed. We assume tools are the primary source of cv_summary.
        needs_rag = cv_summary_present and not cv_analysis_present

        if needs_rag:
            if DEBUG_MODE:
                print("--- [Grafo Decision] -> Redirigiendo a: rag_processor ---")
            return "rag_processor"
        else:
            if DEBUG_MODE:
                decision = "chatbot (no RAG needed)" if not cv_summary_present else "chatbot (RAG already done)"
                print(f"--- [Grafo Decision] -> Redirigiendo a: {decision} ---")
            return "chatbot"

    if DEBUG_MODE: print("[Grafo] Añadiendo borde condicional: tools -> (rag_processor | chatbot)")
    graph_builder.add_conditional_edges(
        "tools",
        post_tools_decision,
        {
            "rag_processor": "rag_processor",
            "chatbot": "chatbot"
        }
    )

    # 3. From RAG Processor: Always return to Chatbot
    # After attempting RAG (success or fail), go back to chatbot to formulate a response,
    # potentially using the RAG results if they were added to the state.
    if DEBUG_MODE: print("[Grafo] Añadiendo borde: rag_processor -> chatbot")
    graph_builder.add_edge("rag_processor", "chatbot")

    # --- Compile the Graph ---
    if DEBUG_MODE:
        print("--- [Grafo] Compilando el grafo... ---")
    compiled_graph = graph_builder.compile()
    if DEBUG_MODE:
        print("--- [Grafo] Grafo compilado con éxito ---")

    return compiled_graph

# --- Example Usage (for testing or direct execution) ---
if __name__ == "__main__":
    print("Executing graph_definition.py as main script.")
    print("This defines the graph but doesn't run it interactively.")
    print("Creating a graph instance to verify compilation...")

    # Set debug mode for this execution if needed
    # DEBUG_MODE = True

    try:
        hr_graph = create_hr_graph()
        print("\nGraph created and compiled successfully.")

        # Optional: Visualize the graph if dependencies are installed
        # (requires `pip install pygraphviz` or `pip install matplotlib`, and system Graphviz)
        try:
            print("\nAttempting to generate graph diagram...")
            # Obtener la ruta base del proyecto usando Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            output_dir = os.path.join(project_root, "output")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            output_path_png = os.path.join(output_dir, "hr_graph_flow.png")
            output_path_mermaid = os.path.join(output_dir, "hr_graph_flow.mermaid.txt")

            # Generate PNG using Mermaid rendering (often more reliable than pygraphviz)
            try:
                print(f"Generating PNG diagram to {output_path_png}...")
                image_bytes = hr_graph.get_graph().draw_mermaid_png()
                if image_bytes:
                    with open(output_path_png, "wb") as f:
                        f.write(image_bytes)
                    print(f"PNG diagram saved to: {output_path_png}")
                else:
                    print("Failed to generate PNG using draw_mermaid_png().")
            except Exception as mermaid_png_error:
                print(f"Error generating PNG with draw_mermaid_png(): {mermaid_png_error}")
                print("Ensure playwright and its browser dependencies are installed (`playwright install`)")


            # Always try to save Mermaid syntax as a fallback or alternative
            try:
                print(f"Generating Mermaid syntax to {output_path_mermaid}...")
                mermaid_syntax = hr_graph.get_graph().draw_mermaid()
                with open(output_path_mermaid, "w") as f:
                    f.write(mermaid_syntax)
                print(f"Mermaid syntax saved to: {output_path_mermaid}")
            except Exception as mermaid_txt_error:
                print(f"Error generating Mermaid syntax: {mermaid_txt_error}")


        except ImportError as viz_import_error:
            print(f"\nWarning: Visualization dependencies missing ({viz_import_error}). Skipping diagram generation.")
            print("Install 'pygraphviz' or ensure 'playwright' is installed for PNG generation.")
        except Exception as viz_error:
            print(f"\nError during graph visualization generation: {viz_error}")
            traceback.print_exc()


    except Exception as e:
        print(f"\nError during graph creation or compilation: {e}")
        traceback.print_exc()

    print("\nTo use the graph, import 'create_hr_graph' from this module in your main application (e.g., app/main.py)")