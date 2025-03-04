import re
import time
import base64
import cv2
import numpy as np
import easyocr
import os
from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

app = Flask(__name__)

# Inicializamos el lector de EasyOCR una sola vez
reader = easyocr.Reader(["en"])

# Caché simple en memoria: { placa: { "result": ..., "time": timestamp } }
cache = {}
CACHE_TTL = 20  # Tiempo en segundos (puedes ajustar este valor)

def get_cached_result(placa):
    entry = cache.get(placa)
    if entry and (time.time() - entry["time"]) < CACHE_TTL:
        return entry["result"]
    return None

def set_cached_result(placa, result):
    cache[placa] = {"result": result, "time": time.time()}

def consultar_vehiculo(placa):
    """
    Realiza el proceso completo:
      1. Abre la página de SUNARP.
      2. Resuelve el captcha usando EasyOCR.
      3. Ingresa la placa y el captcha.
      4. Realiza la búsqueda y extrae la imagen de resultado en Base64.
    Retorna un diccionario con el resultado.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    driver.get("https://www2.sunarp.gob.pe/consulta-vehicular/inicio")

    max_intentos = 35
    intento = 1

    def leer_captcha():
        captcha_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "image"))
        )
        captcha_src = captcha_element.get_attribute("src")
        captcha_b64 = captcha_src.split(",")[1]
        # Procesa la imagen en memoria sin escribir en disco
        img_data = base64.b64decode(captcha_b64)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        _, img_thresh = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY_INV)
        result = reader.readtext(img_thresh)
        if not result:
            return ""
        captcha_text = "".join([res[1] for res in result])
        captcha_text = re.sub(r"\s+", "", captcha_text).strip()
        captcha_text = re.sub(r"[^A-Za-z0-9]", "", captcha_text)
        return captcha_text

    def ingresar_datos(placa_text, captcha_text):
        input_placa = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "nroPlaca"))
        )
        input_placa.clear()
        input_placa.send_keys(placa_text)
        input_captcha = driver.find_element(By.ID, "codigoCaptcha")
        input_captcha.clear()
        input_captcha.send_keys(captcha_text)

    def click_buscar():
        try:
            search_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-sunarp-green.ant-btn-primary.ant-btn-lg"))
            )
            search_button.click()
        except TimeoutException:
            print("❌ El botón de búsqueda no se habilitó.")

    def manejar_popup_error():
        try:
            ok_button = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.swal2-confirm.swal2-styled"))
            )
            ok_button.click()
            return True
        except TimeoutException:
            return False

    def error_ingrese_captcha():
        try:
            WebDriverWait(driver, 2).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@role='alert' and contains(text(), 'Ingrese el captcha')]")
                )
            )
            return True
        except TimeoutException:
            return False

    def obtener_imagen_resultado():
        result_img_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//app-form-datos-consulta//img"))
        )
        return result_img_element.get_attribute("src").split(",")[1]

    resultado = None
    try:
        while intento <= max_intentos:
            print(f"=== Intento #{intento} ===")
            if intento > 1:
                print("🔄 Refrescando la página para obtener un nuevo captcha...")
                driver.refresh()
                time.sleep(2)
            captcha_text = leer_captcha()
            print(f"Captcha leído: '{captcha_text}'")
            if len(captcha_text) < 6:
                print("❌ Captcha muy corto o inválido. Reintentando...")
                intento += 1
                continue
            ingresar_datos(placa, captcha_text)
            click_buscar()
            time.sleep(1)
            if manejar_popup_error():
                print("❌ Popup: Captcha inválido. Reintentando...")
                intento += 1
                continue
            if error_ingrese_captcha():
                print("❌ Mensaje: 'Ingrese el captcha'. Reintentando...")
                intento += 1
                continue
            try:
                final_b64 = obtener_imagen_resultado()
                resultado = {
                    "status": "success",
                    "message": "Consulta realizada con éxito",
                    "Developer": "https://t.me/SetaxOne",
                    "Placa": placa,
                    "base64": "data:image/png;base64," + final_b64
                }
                break
            except NoSuchElementException:
                print("❌ No se encontró imagen de resultado. Terminando...")
                resultado = {
                    "status": "error",
                    "message": "No se encontró imagen del resultado Sunarp Placa",
                    "Placa": placa
                }
                break
            finally:
                intento += 1
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        resultado = {
            "status": "error",
            "message": f"Error inesperado: {e}",
            "Placa": placa
        }
    finally:
        driver.quit()

    if resultado is None:
        resultado = {
            "status": "error",
            "message": "No se pudo conectar correctamente al servidor - Intenta Nuevamente",
            "Developer": "https://t.me/SetaxOne",
            "Placa": placa
        }
    return resultado

# ============================================
# RUTA DE LA API (GET)
# ============================================
@app.route("/sunarp/placa=<placa>", methods=["GET"])
def sunarp_api(placa):
    """
    Ejemplo de consulta:
      http://localhost:5000/sunarp/placa=ABC123
    Retorna un JSON con:
      - status: "success" o "error"
      - message: mensaje descriptivo
      - Placa: la placa consultada
      - base64: la imagen de resultado en Base64 (con prefijo)
      - time_response: tiempo de respuesta en segundos
    """
    # Verifica si hay resultado cacheado para la placa
    cached = get_cached_result(placa)
    if cached:
        cached["time_response"] = 0.0  # Se asume respuesta inmediata desde caché
        return jsonify(cached)

    start_time = time.time()
    resultado = consultar_vehiculo(placa)
    elapsed = time.time() - start_time
    resultado["time_response"] = round(elapsed, 3)
    # Guarda en caché el resultado si es exitoso
    if resultado.get("status") == "success":
        set_cached_result(placa, resultado)
    return jsonify(resultado)

if __name__ == "__main__":
    # En Render se utiliza el puerto asignado por la variable de entorno PORT, 
    # por defecto se asigna 10000 si no existe.
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
