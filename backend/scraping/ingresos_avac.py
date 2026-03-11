"""
Scraping de IngresosAVAC — adaptado para modo headless en GitHub Actions.
Soporta 2FA TOTP automático con pyotp (GitHub Secret: AVAC_TOTP_SECRET).
Los cursos se leen de la base de datos (tabla course_configs), no hardcodeados.
"""
import os
import time
import datetime
import logging
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from pathlib import Path

logger = logging.getLogger(__name__)


def get_session_headless(username: str, password: str, base_url: str, totp_secret: str = None) -> requests.Session:
    """
    Login automático headless con Selenium + 2FA TOTP.

    Para obtener el TOTP secret: en tu app autenticadora, busca la opción
    'Ver clave' o 'Export account' — el secret es la cadena base32 (~32 caracteres).
    Guárdalo como GitHub Secret: AVAC_TOTP_SECRET
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import time as _time

    logger.info("🚀 Iniciando Chrome headless...")
    opt = Options()
    opt.add_argument("--headless=new")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--disable-gpu")
    opt.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=opt)
    try:
        driver.get(f"{base_url}/login/index.php")
        wait = WebDriverWait(driver, 20)

        # Paso 1: usuario y contraseña
        username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
        driver.find_element(By.ID, "password").send_keys(password)
        username_field.send_keys(username)
        driver.find_element(By.ID, "loginbtn").click()
        _time.sleep(2)

        # Paso 2: detectar pantalla 2FA (Moodle usa varios selectores según el plugin)
        totp_field = None
        for selector in [
            "#otp", "#totpcode", "input[name='verificationcode']",
            "input[type='text'][autocomplete='one-time-code']",
            "input[name='passcode']", "input[name='totp']",
        ]:
            try:
                totp_field = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except Exception:
                pass

        if totp_field:
            logger.info("🔐 Pantalla 2FA detectada — generando código TOTP...")
            if not totp_secret:
                raise ValueError(
                    "AVAC requiere 2FA pero AVAC_TOTP_SECRET no está definido en variables de entorno. "
                    "Consulta DEPLOY.md sección '2FA' para obtener el secret de tu app autenticadora."
                )
            try:
                import pyotp
            except ImportError:
                raise ImportError("Instala pyotp: pip install pyotp")

            code = pyotp.TOTP(totp_secret).now()
            logger.info(f"🔑 Código TOTP generado (válido 30s): {code[:2]}****")
            totp_field.clear()
            totp_field.send_keys(code)

            for btn in ["button[type='submit']", "input[type='submit']", "#loginbtn"]:
                try:
                    driver.find_element(By.CSS_SELECTOR, btn).click()
                    break
                except Exception:
                    pass
            _time.sleep(2)

        # Verificar login exitoso
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".usermenu, .usertext, #user-menu-toggle, [data-region='usermenu']")
        ))
        logger.info("✅ Login exitoso. Transfiriendo sesión a modo HTTP rápido...")

        session = requests.Session()
        for cookie in driver.get_cookies():
            session.cookies.set(cookie["name"], cookie["value"])
        session.headers.update({"User-Agent": driver.execute_script("return navigator.userAgent;")})
        return session

    finally:
        driver.quit()


def get_session_manual(base_url: str) -> requests.Session:
    """Login manual — para uso local sin credenciales en env."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opt = Options()
    opt.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=opt)
    try:
        driver.get(f"{base_url}/my/")
        input("\n🔐 Inicia sesión (incluyendo 2FA) y presiona ENTER cuando estés dentro...")
        session = requests.Session()
        for cookie in driver.get_cookies():
            session.cookies.set(cookie["name"], cookie["value"])
        session.headers.update({"User-Agent": driver.execute_script("return navigator.userAgent;")})
        return session
    finally:
        driver.quit()


def get_active_codigos(db=None) -> list:
    """
    Lee los códigos de cursos activos desde la BD (tabla course_configs).
    Si no hay BD disponible, retorna lista vacía.
    """
    if db is None:
        return []
    try:
        from ..models.course_config import CourseConfig
        configs = db.query(CourseConfig).filter(CourseConfig.activo == True).all()
        codigos = [c.codigo_avac for c in configs]
        logger.info(f"📋 {len(codigos)} cursos activos leídos desde BD")
        return codigos
    except Exception as e:
        logger.warning(f"No se pudieron leer cursos desde BD: {e}")
        return []


def scrape_ingresos(output_dir: str, codigos: list = None, base_url: str = None, db=None) -> dict:
    """Scraping principal de ingresos AVAC."""
    from ..config import settings

    base_url = base_url or settings.AVAC_BASE_URL
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Obtener lista de cursos — primero desde BD, fallback a parámetro
    if codigos is None:
        codigos = get_active_codigos(db)
    if not codigos:
        logger.error("❌ No hay cursos configurados. Agrega cursos en Admin → Configuración de Cursos.")
        return {"procesados": 0, "errores": [{"error": "Sin cursos configurados"}], "no_encontrados": []}

    username = settings.AVAC_USERNAME
    password = settings.AVAC_PASSWORD
    totp_secret = settings.AVAC_TOTP_SECRET

    if username and password:
        logger.info("🔑 Modo automático (credenciales desde variables de entorno)")
        session = get_session_headless(username, password, base_url, totp_secret)
    else:
        logger.info("👤 Modo manual — login interactivo requerido")
        session = get_session_manual(base_url)

    procesados, no_encontrados, errores = 0, [], []

    for index, codigo_curso in enumerate(codigos, 1):
        try:
            start_time = time.time()
            resp = session.get(f"{base_url}/course/search.php?search={codigo_curso}", timeout=30)
            soup = BeautifulSoup(resp.text, "html.parser")
            enlace = soup.select_one(".coursebox a[href*='id=']")

            if not enlace:
                no_encontrados.append(codigo_curso)
                logger.warning(f"⚠️  [{index}/{len(codigos)}] Curso {codigo_curso} no encontrado en AVAC")
                continue

            course_id = parse_qs(urlparse(enlace.get("href")).query).get("id", [None])[0]
            resp_part = session.get(f"{base_url}/user/index.php?id={course_id}&perpage=5000", timeout=30)
            soup_part = BeautifulSoup(resp_part.text, "html.parser")

            registros = []
            for fila in soup_part.select("table.generaltable tbody tr"):
                if "@" not in fila.get_text():
                    continue
                celdas = fila.find_all("td")
                if len(celdas) >= 6:
                    registros.append({
                        "Nombre": celdas[0].get_text(strip=True),
                        "Correo": celdas[1].get_text(strip=True),
                        "Último acceso": celdas[4].get_text(strip=True),
                        "Estado": celdas[5].get_text(strip=True),
                    })

            if registros:
                df = pd.DataFrame(registros)
                df["Código Curso"] = codigo_curso
                df["Fecha Extracción"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                df.to_csv(output_path / f"ingresosAVAC_{codigo_curso}.csv", index=False, encoding="utf-8-sig")
                procesados += 1

            logger.info(f"[{index}/{len(codigos)}] ✅ {codigo_curso}: {len(registros)} alumnos en {round(time.time()-start_time,2)}s")

        except Exception as e:
            logger.error(f"❌ Error en {codigo_curso}: {e}")
            errores.append({"curso": codigo_curso, "error": str(e)})

    if no_encontrados:
        pd.DataFrame({"codigo": no_encontrados}).to_csv(output_path / "cursos_no_encontrados.csv", index=False)

    logger.info(f"🏁 Completado: {procesados} OK, {len(errores)} errores, {len(no_encontrados)} no encontrados")
    return {"procesados": procesados, "errores": errores, "no_encontrados": no_encontrados}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scrape_ingresos(output_dir=os.environ.get("DATA_PATH_INGRESOS", "./data/IngresosAVAC"))
