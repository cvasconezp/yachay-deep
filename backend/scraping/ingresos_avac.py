"""
Scraping de IngresosAVAC — adaptado para modo headless en GitHub Actions.
Login via flujo OAuth de Microsoft (Azure AD) con TOTP automático (pyotp).
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


def _log_page_state(driver, context: str):
    """Captura estado de la página para diagnóstico cuando algo falla."""
    logger.error(f"[{context}] URL actual: {driver.current_url}")
    logger.error(f"[{context}] Título: {driver.title}")
    snippet = driver.page_source[:2000] if driver.page_source else "(vacío)"
    logger.error(f"[{context}] HTML (primeros 2000 chars):\n{snippet}")


def get_session_headless(username: str, password: str, base_url: str, totp_secret: str = None) -> requests.Session:
    """
    Login automático headless vía flujo OAuth de Microsoft (Azure AD).

    Flujo: AVAC login → "Usuarios de la UPS" → Microsoft email → password → TOTP → redirect a AVAC.

    Requiere AVAC_TOTP_SECRET: el secret base32 de Microsoft Authenticator.
    Para obtenerlo: mysignins.microsoft.com → Información de seguridad → Agregar método
    → Aplicación de autenticación → "Quiero usar otra app" → copiar el secret/clave.
    Guárdalo como GitHub Secret: AVAC_TOTP_SECRET
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    import time as _time

    if not totp_secret:
        raise ValueError(
            "AVAC_TOTP_SECRET es requerido para login automático con Microsoft. "
            "Configura un método TOTP en mysignins.microsoft.com y guarda el secret como GitHub Secret."
        )

    logger.info("🚀 Iniciando Chrome headless...")
    opt = Options()
    opt.add_argument("--headless=new")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--disable-gpu")
    opt.add_argument("--window-size=1920,1080")
    opt.add_argument("--disable-extensions")
    opt.add_argument("--disable-software-rasterizer")

    driver = webdriver.Chrome(options=opt)
    try:
        login_url = f"{base_url}/login/index.php"
        wait = WebDriverWait(driver, 30)
        wait_short = WebDriverWait(driver, 10)

        # ── Paso 1: Cargar página de login AVAC ──
        logger.info(f"Navegando a {login_url}")
        driver.get(login_url)
        logger.info(f"Página cargada — URL: {driver.current_url}, título: {driver.title}")

        # ── Paso 2: Detectar tipo de login (directo Moodle vs OAuth federado) ──
        # Si hay campo #username directo, es login Moodle clásico
        # Si hay botón "Usuarios de la UPS", es login OAuth federado
        try:
            username_field = wait_short.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            # Login Moodle clásico
            logger.info("Login Moodle directo detectado")
            username_field.send_keys(username)
            driver.find_element(By.ID, "password").send_keys(password)
            driver.find_element(By.ID, "loginbtn").click()
            _time.sleep(2)
        except TimeoutException:
            # No hay #username → buscar botón OAuth "Usuarios de la UPS"
            logger.info("Login federado detectado — buscando botón 'Usuarios de la UPS'...")
            try:
                # El botón puede ser un enlace con texto o un potentialidp link
                oauth_btn = None
                for selector in [
                    "a.btn-login",
                    "a.login-identityprovider-btn",
                    ".potentialidp a",
                    "a[href*='auth/oidc']",
                    "a[href*='oauth2']",
                    "a[href*='saml']",
                ]:
                    try:
                        oauth_btn = driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except Exception:
                        pass

                if oauth_btn is None:
                    # Fallback: buscar por texto
                    links = driver.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        if "UPS" in link.text or "Usuarios" in link.text:
                            oauth_btn = link
                            break

                if oauth_btn is None:
                    _log_page_state(driver, "No se encontró botón OAuth")
                    raise RuntimeError(
                        "No se encontró el botón 'Usuarios de la UPS' ni el formulario de login directo"
                    )

                logger.info(f"Clic en: '{oauth_btn.text.strip()}'")
                oauth_btn.click()

                # ── Paso 3: Microsoft login — ingresar email ──
                logger.info("Esperando página de login Microsoft...")
                email_field = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='loginfmt']"))
                )
                logger.info(f"Campo email encontrado — URL: {driver.current_url}")
                email_field.clear()
                email_field.send_keys(username)

                # Clic en "Siguiente"
                next_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit'], #idSIButton9"))
                )
                next_btn.click()
                _time.sleep(2)

                # ── Paso 4: Seleccionar tipo de cuenta (si aparece) ──
                # Microsoft a veces pregunta "Cuenta profesional o educativa" vs "Cuenta personal"
                try:
                    work_account = wait_short.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "#aadTile, #aadTileTitle, div[data-test-id='aadTile']"))
                    )
                    logger.info("Seleccionando cuenta profesional/educativa...")
                    work_account.click()
                    _time.sleep(2)
                except TimeoutException:
                    pass  # No apareció selector de tipo de cuenta

                # ── Paso 5: Ingresar contraseña ──
                logger.info("Esperando campo de contraseña...")
                try:
                    password_field = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'], input[name='passwd']"))
                    )
                    password_field.clear()
                    password_field.send_keys(password)

                    submit_btn = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit'], #idSIButton9, span[class='submit']"))
                    )
                    submit_btn.click()
                    logger.info("Contraseña enviada")
                    _time.sleep(2)
                except TimeoutException:
                    _log_page_state(driver, "No se encontró campo de contraseña")
                    raise

            except RuntimeError:
                raise
            except TimeoutException:
                _log_page_state(driver, "Timeout en flujo OAuth Microsoft")
                raise
            except Exception as e:
                _log_page_state(driver, f"Error inesperado en OAuth: {type(e).__name__}")
                raise

        # ── Paso 6: MFA — TOTP o "Stay signed in?" ──
        logger.info("Verificando si se requiere MFA...")
        _time.sleep(2)

        # Detectar pantalla TOTP de Microsoft o Moodle
        totp_field = None
        totp_selectors = [
            "input[name='otc']",           # Microsoft Authenticator TOTP
            "#idTxtBx_SAOTCC_OTC",         # Microsoft "Enter code"
            "input[name='totp']",
            "#otp", "#totpcode",
            "input[name='verificationcode']",
            "input[type='text'][autocomplete='one-time-code']",
            "input[name='passcode']",
        ]
        for selector in totp_selectors:
            try:
                totp_field = driver.find_element(By.CSS_SELECTOR, selector)
                if totp_field.is_displayed():
                    break
                totp_field = None
            except Exception:
                pass

        if totp_field:
            logger.info("🔐 Pantalla MFA/TOTP detectada — generando código...")
            try:
                import pyotp
            except ImportError:
                raise ImportError("Instala pyotp: pip install pyotp")

            code = pyotp.TOTP(totp_secret).now()
            logger.info(f"🔑 Código TOTP generado: {code[:2]}****")
            totp_field.clear()
            totp_field.send_keys(code)

            # Clic en verificar/submit
            for btn_sel in [
                "input[type='submit']", "#idSubmit_SAOTCC_Continue",
                "button[type='submit']", "#idSIButton9",
            ]:
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, btn_sel)
                    if btn.is_displayed():
                        btn.click()
                        break
                except Exception:
                    pass
            _time.sleep(3)
        else:
            logger.info("No se detectó pantalla TOTP (puede que no sea necesario)")

        # ── Paso 7: "Stay signed in?" / "Mantener la sesión iniciada?" ──
        try:
            stay_btn = wait_short.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#idSIButton9, #idBtn_Back, input[value='Yes'], input[value='No']"))
            )
            logger.info(f"Pantalla 'Stay signed in' detectada — aceptando...")
            stay_btn.click()
            _time.sleep(2)
        except TimeoutException:
            pass  # No apareció

        # ── Paso 8: Verificar login exitoso en AVAC ──
        logger.info(f"Esperando redirect a AVAC... URL actual: {driver.current_url}")
        try:
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".usermenu, .usertext, #user-menu-toggle, [data-region='usermenu'], .userbutton")
            ))
        except TimeoutException:
            _log_page_state(driver, "Login no completado — no se detectó menú de usuario en AVAC")
            raise RuntimeError("Login completó el flujo OAuth pero AVAC no muestra sesión activa")

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
            soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
            enlace = soup.select_one(".coursebox a[href*='view.php?id=']")

            if not enlace:
                no_encontrados.append(codigo_curso)
                logger.warning(f"⚠️  [{index}/{len(codigos)}] Curso {codigo_curso} no encontrado en AVAC")
                continue

            course_id = parse_qs(urlparse(enlace.get("href")).query).get("id", [None])[0]
            resp_part = session.get(f"{base_url}/user/index.php?id={course_id}&perpage=5000", timeout=30)
            soup_part = BeautifulSoup(resp_part.content, "html.parser", from_encoding="utf-8")

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
