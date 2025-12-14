# Instrucciones para la Tool de Imágenes (OCR)

Esta herramienta permite extraer texto de imágenes (JPG, PNG) usando OCR con pytesseract y Tesseract OCR.

## Requisitos

1. **Dependencias de Python**
   - Instala los requirements del proyecto:
     ```bash
     pip install -r requirements.txt
     ```
   - Esto instalará `pytesseract` y `pillow`.

2. **Instalar Tesseract OCR (programa externo)**
   Debes instalar el binario de Tesseract OCR en tu sistema operativo:

   ### Linux (Debian/Ubuntu)
   ```bash
   sudo apt-get update
   sudo apt-get install tesseract-ocr tesseract-ocr-spa
   ```
   
   ### Linux (Arch/Manjaro)
   ```bash
   sudo pacman -S tesseract tesseract-data-spa
   ```

   ### MacOS
   ```bash
   brew install tesseract
   # Para soporte en español:
   brew install tesseract-lang
   ```

   ### Windows
   1. Descarga el instalador desde:
      https://github.com/tesseract-ocr/tesseract/wiki
   2. Instala y agrega la carpeta de instalación a la variable de entorno `PATH`.
   3. (Opcional) Descarga los paquetes de idioma si necesitas soporte en español.

## Probar el endpoint de la API

1. Asegúrate de que tu API esté corriendo.
2. Usa Postman, Insomnia o curl para hacer una petición POST a:
   ```
   http://localhost:8080/api/process_image
   ```
3. Envia la imagen como `form-data` con la clave `file`.

### Ejemplo con curl

```bash
curl -X POST http://localhost:8080/api/process_image \
  -F "file=@/ruta/a/tu/imagen.jpg"
```

## Notas
- Si recibes un error como `tesseract is not installed or it's not in your PATH`, asegúrate de haber instalado Tesseract OCR y que esté accesible desde la terminal.
- Puedes instalar otros paquetes de idioma para mejorar el OCR en otros idiomas.

---

**Autor:** Equipo Geraldine Repliker 