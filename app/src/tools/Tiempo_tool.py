import requests
from typing import Dict, List, Optional, Union
from datetime import datetime
from langchain_core.tools import tool

@tool
def get_tiempo(pais: str) -> Dict:
    """
    Obtiene la hora actual de un país específico.
    
    Args:
        pais (str): Nombre del país
        
    Returns:
        Dict con la información de la hora
    """
    client = ClienteTiempoAPI()
    return client._make_request(f"time/{pais}")

class ClienteTiempoAPI:
    def __init__(self, base_url: str = "https://tiempo-api-922839482240.us-central1.run.app"):
        """
        Inicializa el cliente de la API de tiempo.
        
        Args:
            base_url (str): URL base de la API. Por defecto usa la URL de producción.
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def _make_request(self, endpoint: str, method: str = "GET", **kwargs) -> Dict:
        """
        Realiza una petición a la API.
        
        Args:
            endpoint (str): Endpoint de la API
            method (str): Método HTTP
            **kwargs: Argumentos adicionales para requests
            
        Returns:
            Dict: Respuesta de la API
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "status_code": getattr(e.response, 'status_code', None)}
    
    def get_paises(self) -> Dict[str, Union[List[str], int]]:
        """
        Obtiene la lista de países disponibles.
        
        Returns:
            Dict con la lista de países y el total
        """
        return self._make_request("paises")
    
    def get_info_pais(self, pais: str) -> Dict:
        """
        Obtiene información detallada de un país incluyendo su hora actual.
        
        Args:
            pais (str): Nombre del país
            
        Returns:
            Dict con la información del país
        """
        tiempo = self.get_tiempo(pais)
        if "error" in tiempo:
            return tiempo
        
        return {
            "pais": tiempo["pais"],
            "hora_actual": tiempo["hora_actual"],
            "zona_horaria": tiempo["zona_horaria"],
            "fecha": tiempo["hora_actual"].split()[0],
            "hora": tiempo["hora_actual"].split()[1]
        }

# API de Zona Horaria Latinoamérica
# Endpoints disponibles:
# 1. GET /time/{pais} - Obtener la hora actual de un país
#    Ejemplo: GET https://tiempo-api-922839482240.us-central1.run.app/time/Argentina
#    Respuesta: {"pais": "Argentina", "hora_actual": "2023-10-01 12:34:56", "zona_horaria": "America/Argentina/Buenos_Aires"}
#
# 2. POST /consulta - Consultar la hora con formato específico
#    Ejemplo: POST https://tiempo-api-922839482240.us-central1.run.app/consulta
#    Body: {"pais": "Argentina", "formato": "completo"}
#    Respuesta: {"pais": "Argentina", "hora_actual": "2023-10-01 12:34:56", "zona_horaria": "America/Argentina/Buenos_Aires", "fecha": "2023-10-01", "hora": "12:34:56"}
#
# 3. GET /paises - Listar países disponibles
#    Ejemplo: GET https://tiempo-api-922839482240.us-central1.run.app/paises
#    Respuesta: {"paises": ["Argentina", "Bolivia", "Brasil", "Chile", "Colombia", "Costa Rica", "Cuba", "Ecuador", "El Salvador", "Guatemala", "Honduras", "México", "Nicaragua", "Panamá", "Paraguay", "Perú", "República Dominicana", "Uruguay", "Venezuela"], "total": 19}
#
# 4. GET / - Bienvenida
#    Ejemplo: GET https://tiempo-api-922839482240.us-central1.run.app/
#    Respuesta: {"message": "Bienvenido a la API de Zona Horaria Latinoamérica", "paises_disponibles": ["Argentina", "Bolivia", "Brasil", "Chile", "Colombia", "Costa Rica", "Cuba", "Ecuador", "El Salvador", "Guatemala", "Honduras", "México", "Nicaragua", "Panamá", "Paraguay", "Perú", "República Dominicana", "Uruguay", "Venezuela"]}

 