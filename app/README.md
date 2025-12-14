# Diagrama de Funcionamiento de Repliker

## Arquitectura y Flujo de Trabajo de Repliker

Repliker es un sistema de asistencia legal inteligente que utiliza tecnologías avanzadas para proporcionar asesoramiento jurídico especializado. A continuación, se presenta un diagrama detallado que explica su funcionamiento:

```
+---------------------------------------------+
|                                             |
|            ARQUITECTURA REPLIKER            |
|                                             |
+---------------------------------------------+
                      |
        +-------------+-------------+
        |                           |
+-------v-------+           +-------v-------+
|               |           |               |
| INTERFAZ API  |<--------->|  MOTOR LLM    |
| (Flask)       |           | (Google       |
|               |           |  Gemini)      |
+-------+-------+           +-------+-------+
        |                           |
        |                           |
+-------v-------+           +-------v-------+
|               |           |               |
| GESTIÓN DE    |           | GRAFO DE      |
| CONVERSACIÓN  |<--------->| CONVERSACIÓN  |
| (LangChain)   |           | (LangGraph)   |
|               |           |               |
+-------+-------+           +-------+-------+
        |                           |
        |                           |
+-------v-------+           +-------v-------+
|               |           |               |
| PROCESAMIENTO |           | SISTEMA RAG   |
| DE DOCUMENTOS |<--------->| (Embeddings)  |
| (PDF/Imágenes)|           |               |
+-------+-------+           +-------+-------+
        |                           |
        |                           |
+-------v-------+           +-------v-------+
|               |           |               |
| HERRAMIENTAS  |           | ALMACENAMIENTO|
| EXTERNAS      |<--------->| (MongoDB)     |
| (Email, Pagos)|           |               |
+---------------+           +---------------+
```

## Componentes Principales

### 1. Interfaz API (Flask)
- **Función**: Proporciona endpoints HTTP para interactuar con el sistema.
- **Endpoints principales**:
  - `/api/conversation`: Gestiona el inicio, continuación y exportación de conversaciones.
  - `/api/process_pdf`: Procesa documentos PDF y los integra en la conversación.
  - `/health`: Verifica el estado del sistema.

### 2. Motor LLM (Google Gemini)
- **Función**: Núcleo de inteligencia artificial que genera respuestas contextuales.
- **Características**:
  - Utiliza el modelo Gemini 2.0 Flash para generar respuestas.
  - Configurado con temperatura controlada para respuestas precisas.
  - Integra conocimiento especializado en derecho corporativo, derechos reales y derecho de familia.

### 3. Gestión de Conversación
- **Función**: Mantiene el estado y flujo de las conversaciones.
- **Componentes**:
  - `ConversationMemory`: Almacena y recupera el historial de mensajes.
  - Sistema de mensajes estructurados (HumanMessage, AIMessage, SystemMessage).
  - Exportación de conversaciones en formatos TXT y JSON.

### 4. Grafo de Conversación (LangGraph)
- **Función**: Define el flujo lógico y toma de decisiones durante la conversación.
- **Nodos principales**:
  - `chatbot_node`: Procesa mensajes y genera respuestas.
  - `rag_processor_node`: Realiza análisis RAG sobre documentos.
  - Nodos de herramientas: Ejecutan funciones específicas como verificación de países.

### 5. Procesamiento de Documentos
- **Función**: Extrae y analiza información de documentos legales.
- **Capacidades**:
  - Procesamiento de PDFs con extracción de texto.
  - Análisis de imágenes mediante Google Vision API.
  - Detección de documentos legales vs. no legales.

### 6. Sistema RAG (Retrieval Augmented Generation)
- **Función**: Enriquece las respuestas con información relevante de documentos legales.
- **Componentes**:
  - Generación de embeddings para documentos legales.
  - Almacenamiento en Google Cloud Storage.
  - Comparación semántica de documentos con consultas.

### 7. Herramientas Externas
- **Función**: Amplía las capacidades del sistema con servicios adicionales.
- **Herramientas disponibles**:
  - `send_email_tool`: Envío de correos electrónicos.
  - `generate_payment_link`: Generación de enlaces de pago.
  - `verify_country`: Verificación de países permitidos.

### 8. Almacenamiento (MongoDB)
- **Función**: Persiste datos de conversaciones y usuarios.
- **Datos almacenados**:
  - Historial completo de conversaciones.
  - Información de usuarios y sus consultas.
  - Estado de las conversaciones activas.

## Flujo de Trabajo

1. **Inicio de Conversación**:
   - El usuario inicia una conversación a través de la API.
   - Se crea un nuevo hilo de conversación con ID único.
   - Se inicializa el estado con el mensaje del sistema.

2. **Procesamiento de Mensajes**:
   - El usuario envía un mensaje de texto o documento.
   - El mensaje se añade al historial de conversación.
   - El grafo de conversación procesa el mensaje.

3. **Análisis de Documentos**:
   - Si se sube un documento, se procesa según su tipo (PDF/imagen).
   - Se extrae el texto y se analiza su contenido.
   - Se determina si es un documento legal o no.

4. **Generación de Respuestas**:
   - El LLM genera una respuesta basada en el contexto y el historial.
   - Si es necesario, se enriquece la respuesta con información RAG.
   - Se pueden invocar herramientas específicas según la necesidad.

5. **Persistencia**:
   - Todas las interacciones se guardan en MongoDB.
   - El estado de la conversación se mantiene para futuras interacciones.
   - Las conversaciones pueden exportarse para su análisis.

## Características Especiales

- **Verificación de Países**: El sistema solo atiende consultas de países latinoamericanos específicos.
- **Análisis RAG**: Compara documentos con ejemplos de buenas prácticas legales.
- **Procesamiento de Pagos**: Integración con sistema de pagos para servicios premium.
- **Multimodalidad**: Capacidad para procesar tanto texto como imágenes.

## Tecnologías Utilizadas

- **Backend**: Python, Flask
- **IA**: Google Gemini, LangChain, LangGraph
- **Almacenamiento**: MongoDB, Google Cloud Storage
- **Procesamiento de Documentos**: PyPDF, PDFPlumber, Google Vision API
- **Comunicación**: Email SMTP, API de Pagos

