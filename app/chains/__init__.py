# app/chains/__init__.py

# Este archivo permite que el directorio 'chains' sea reconocido como un paquete Python
# y facilita la importación de módulos dentro de este paquete.

try:
    from .graph_definition import create_hr_graph
except ImportError as e:
    import logging
    logging.warning(f"Error al importar graph_definition: {e}")
    # Definir una función de respaldo para evitar errores fatales
    def create_hr_graph(*args, **kwargs):
        logging.error("No se pudo cargar el grafo HR. Usando función de respaldo.")
        return None