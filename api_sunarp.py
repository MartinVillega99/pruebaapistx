import re
import time
import base64
import cv2
import numpy as np
import easyocr
import os

from flask import Flask, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

app = Flask(__name__)

def consultar_vehiculo(placa):
    """
    Realiza el proceso completo:
      1. Abre la página de SUNARP con Chromium (modo headless).
      2. Resuelve el captcha usando EasyOCR.
      3. Ingresa la placa y el captcha.
      4. Realiza la búsqueda y extrae la imagen de resultado en Base64.
    Retorna un diccionario con el resultado.
    """

    # Opciones de Selenium para Chromium
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    # Ruta del binario de Chromium (instalado por 'apt-get install chromium-browser')
    options.binary_location = "/usr/bin/chromium-browser"

    # Instancia de ChromeDriver (instalado por 'apt-get install chromium-driver')
    driver = webdriver.Chrome(
        executable_path="/usr/bin/chromedriver",  # Ruta al driver
        options=options
    )

    driver.get("https://www2.sunarp.gob.pe/consulta-vehicular/inicio")

    max_intentos = 35
    intento = 1

    def leer_captcha():
        # Espera a que aparezca la imagen del captcha y la extrae en Base64
        captcha_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "image"))
        )
        captcha_src = captcha_element.get_attribute("src")
        captcha_b64 = captcha_src.split(",")[1]

        # Guarda la imagen original
        with open("captcha.png", "wb") as f:
            f.write(base64.b64decode(captcha_b64))

        # Procesa la imagen para mejorar la lectura (escala de grises y umbral)
        img = cv2.imread("captcha.png", cv2.IMREAD_GRAYSCALE)
        _, img_thresh = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY_INV)
        cv2.imwrite("captcha_processed.png", img_thresh)

        # Reconoce el texto con EasyOCR
        reader = easyocr.Reader(["en"])
        result = reader.readtext("captcha_processed.png")
        if not result:
            return ""
        captcha_text = "".join([res[1] for res in result])
        captcha_text = captcha_text.replace(" ", "").strip()
        # Elimina caracteres que no sean alfanuméricos
        captcha_text = re.sub(r"[^A-Za-z0-9]", "", captcha_text)
        return captcha_text

    def ingresar_datos(placa_text, captcha_text):
        # Ingresa la placa en el campo correspondiente
        input_placa = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "nroPlaca"))
        )
        input_placa.clear()
        input_placa.send_keys(placa_text)
        # Ingresa el captcha en su campo
        input_captcha = driver.find_element(By.ID, "codigoCaptcha")
        input_captcha.clear()
        input_captcha.send_keys(captcha_text)

    def click_buscar():
        try:
            search_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.btn-sunarp-green.ant-btn-primary.ant-btn-lg")
                )
            )
            search_button.click()
        except TimeoutException:
            print("❌ El botón de búsqueda no se habilitó.")

    def manejar_popup_error():
        # Verifica si aparece el popup "Captcha inválido" y hace clic en OK
        try:
            ok_button = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.swal2-confirm.swal2-styled"))
            )
            ok_button.click()
            return True
        except TimeoutException:
            return False

    def error_ingrese_captcha():
        # Verifica si aparece el mensaje "Ingrese el captcha" en la página
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
        """
        Extrae la imagen de resultado y retorna la cadena Base64.
        """
        time.sleep(2)
        result_img_element = driver.find_element(By.XPATH, "//app-form-datos-consulta//img")
        return result_img_element.get_attribute("src").split(",")[1]

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
            driver.quit()
            return {
                "status": "success",
                "message": "Consulta realizada con éxito",
                "Developer": "https://t.me/SetaxOne",
                "Placa": placa,
                "base64": "data:image/png;base64," + final_b64
            }
        except NoSuchElementException:
            print("No se encontró imagen de resultado. Terminando...")
            driver.quit()
            return {
                "status": "error",
                "message": "No se encontró imagen del resultado Sunarp Placa",
                "Placa": placa
            }
        intento += 1

    driver.quit()
    return {
        "status": "error",
        "message": f"No se pudo conectar correctamente al servidor - Intenta Nuevamente",
        "Developer": "https://t.me/SetaxOne",
        "Placa": placa
    }

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
    """
    resultado = consultar_vehiculo(placa)
    return jsonify(resultado)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
