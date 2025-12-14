# src/memory/conversation_memory.py
import os
import logging
from typing import Dict, List
from pathlib import Path

# Importamos el MongoManager para la persistencia
from ..database.mongo_manager import MongoManager

# Diccionario para almacenar instancias de memoria de conversación por thread_id
_conversation_memories = {}

def get_conversation_memory(thread_id: str):
    """Obtiene o crea una instancia de ConversationMemory para un thread_id específico"""
    global _conversation_memories
    
    # Si ya existe una instancia para este thread_id, la devolvemos
    if thread_id in _conversation_memories:
        return _conversation_memories[thread_id]
    
    # Si no existe, creamos una nueva instancia
    from ..database.mongo_manager import MongoManager
    mongo_manager = MongoManager()
    memory = ConversationMemory(thread_id, mongo_manager)
    _conversation_memories[thread_id] = memory
    
    return memory

class ConversationMemory:
    """Clase para mantener el estado de la conversación y guardar mensajes en MongoDB"""
    
    def __init__(self, thread_id, mongo_manager):
        self.thread_id = thread_id
        self.db = mongo_manager
        
        # Cargar mensajes anteriores desde MongoDB si existen
        try:
            previous_messages = self.db.get_conversation_history(thread_id)
            self.messages = []
            for msg in previous_messages:
                self.messages.append({"role": msg["role"], "content": msg["content"]})
            if self.messages:
                logging.info(f"Cargados {len(self.messages)} mensajes anteriores de la conversación {thread_id}.")
        except Exception as e:
            logging.error(f"Error cargando mensajes anteriores: {str(e)}")
            self.messages = []
        
    def add_message(self, role, content):
        """Añade un mensaje a la memoria de conversación y lo guarda en MongoDB"""
        self.messages.append({"role": role, "content": content})
        try:
            self.db.save_message(self.thread_id, "Geraldine" if role == "assistant" else "Usuario", role, content)
        except Exception as e:
            logging.error(f"Error saving message to MongoDB: {str(e)}")
    
    def get_conversation_history(self):
        """Devuelve el historial de mensajes de la conversación"""
        return self.messages
    
    def export_final_chat(self):
        """Exporta la conversación a archivos de texto y JSON"""
        try:
            # Obtener la ruta base del proyecto
            current_file = Path(__file__).resolve()
            app_dir = current_file.parent.parent.parent
            project_root = app_dir.parent
            
            # Crear directorio de exportaciones si no existe
            exports_dir = os.path.join(project_root, "exports")
            os.makedirs(exports_dir, exist_ok=True)
            
            # Generar nombres de archivo con timestamp
            timestamp = self.thread_id
            txt_filename = os.path.join(exports_dir, f"conversation_{timestamp}.txt")
            json_filename = os.path.join(exports_dir, f"conversation_{timestamp}.json")
            
            # Escribir en archivo de texto
            with open(txt_filename, "w", encoding="utf-8") as txt_file:
                for msg in self.messages:
                    role = "Usuario" if msg["role"] == "user" else "Geraldine"
                    txt_file.write(f"{role}: {msg['content']}\n\n")
            
            # Exportar también como JSON
            import json
            with open(json_filename, "w", encoding="utf-8") as json_file:
                json.dump(self.messages, json_file, ensure_ascii=False, indent=2)
                
            return txt_filename, json_filename
        except Exception as e:
            logging.error(f"Error exporting conversation: {str(e)}")
            raise