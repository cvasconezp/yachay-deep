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


# ─── Constantes de espera ────────────────────────────────────────────────────
# En GitHub Actions la latencia varía mucho. Usar waits explícitos, no sleeps.
WAIT_LONG = 30      # timeout para pasos críticos (login, redirect)
WAIT_MEDIUM = 15    # timeout para pasos intermedios
WAIT_SHORT = 5      # timeout para pasos opcionales (selector de cuenta)
PAUSE_AFTER_CLICK = 2  # pausa mínima después de click para que la página reaccione


def get_session_headless(username: str, password: str, base_url: str, totp_secret: str = None) -> requests.Session:
    """
    Login automático headless via Microsoft SSO (Azure AD / Entra ID).
    Flujo real de AVAC UPS (documentado 2026-03-17):
      1. AVAC /login/index.php → clic "Usuarios de la UPS" (OAuth redirect)
      2. Microsoft login → ingresa email → clic "Siguiente" (<button>, no <input>)
      3. Selector de cuenta → "Cuenta profesional o educativa" (botón genérico, sin #aadTile)
      4. Página UPS → ingresa contraseña → clic "Iniciar sesión" (<button>)
      4.5. Si aparece MFA → TOTP automático con pyotp (si AVAC_TOTP_SECRET configurado)
      5. "¿Mantener sesión?" → "Sí" (<button type="submit">)
      6. Redirect de vuelta a AVAC → logueado (button "Menú de usuario")

    NOTA: Si AVAC_PASSWORD es un App Password, el paso 4.5 se salta automáticamente.
    Si es la contraseña normal, se necesita AVAC_TOTP_SECRET para resolver MFA.

    NOTA SELECTORES: Microsoft SSO usa <button type="submit">, NO <input type="submit">.
    Todos los selectores deben incluir ambos: button[type='submit'], input[type='submit'].
    Los textos están en español: "Siguiente", "Iniciar sesión", "Sí".
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
    wait = WebDriverWait(driver, WAIT_LONG)

    try:
        # ── Paso 1: Ir a AVAC login y clic en "Usuarios de la UPS" ──────────
        logger.info("📄 Paso 1: Cargando página de login AVAC...")
        driver.get(f"{base_url}/login/index.php")

        sso_button = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//a[contains(.,'Usuarios de la UPS')] | "
            "//button[contains(.,'Usuarios de la UPS')] | "
            "//div[contains(@class,'potentialidp')]//a"
        )))
        logger.info("🔗 Paso 1 OK: Clic en 'Usuarios de la UPS' (redirect a Microsoft SSO)...")
        sso_button.click()

        # ── Paso 2: Microsoft login — ingresar email ────────────────────────
        logger.info("📧 Paso 2: Esperando página de login Microsoft...")
        email_field = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "input[name='loginfmt']"
        )))
        email_field.clear()
        email_field.send_keys(username)
        logger.info("📧 Paso 2: Email ingresado, esperando botón 'Siguiente'...")

        next_button = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            "input[type='submit']#idSIButton9, "
            "button[type='submit']#idSIButton9, "
            "input[type='submit'][value='Next'], "
            "input[type='submit'][value='Siguiente'], "
            "button[type='submit']"
        )))
        next_button.click()
        logger.info("📧 Paso 2 OK: Clic en 'Siguiente'")
        _time.sleep(PAUSE_AFTER_CLICK)

        # ── Paso 3: Selector de cuenta (si aparece) ─────────────────────────
        try:
            work_account = WebDriverWait(driver, WAIT_SHORT).until(EC.element_to_be_clickable((
                By.XPATH,
                "//*[@id='aadTile'] | "
                "//*[@data-test-id='aadTile'] | "
                "//div[@id='aadTile'] | "
                "//button[contains(.,'rofesional')] | "
                "//button[contains(.,'Work or school')] | "
                "//div[contains(.,'rofesional') and @role='button']"
            )))
            logger.info("👔 Paso 3: Seleccionando 'Cuenta profesional o educativa'...")
            work_account.click()
            logger.info("👔 Paso 3 OK")
            _time.sleep(PAUSE_AFTER_CLICK)
        except Exception:
            logger.info("ℹ️ Paso 3: No apareció selector de cuenta (directo a password)")

        # ── Paso 4: Ingresar contraseña ────────────────────────────────────
        logger.info("🔑 Paso 4: Esperando campo de contraseña...")
        password_field = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "input[name='passwd']"
        )))
        password_field.clear()
        password_field.send_keys(password)
        logger.info("🔑 Paso 4: Contraseña ingresada, esperando botón 'Iniciar sesión'...")

        sign_in_button = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            "input[type='submit']#idSIButton9, "
            "button[type='submit']#idSIButton9, "
            "input[type='submit'][value='Sign in'], "
            "input[type='submit'][value='Iniciar sesión'], "
            "button[type='submit']"
        )))
        sign_in_button.click()
        logger.info("🔑 Paso 4 OK: Clic en 'Iniciar sesión'")
        _time.sleep(PAUSE_AFTER_CLICK + 1)

        # ── Paso 4.5: Manejar MFA/TOTP si aparece ─────────────────────────
        # Si la contraseña no es App Password, Microsoft pedirá MFA.
        # Soportamos TOTP automático con pyotp.
        try:
            mfa_indicator = WebDriverWait(driver, WAIT_SHORT).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "input[name='otc'], "
                    "#idDiv_SAOTCC_Description, "
                    "#idDiv_SAOTCAS_Description, "
                    "#idRichContext_DisplaySign"
                ))
            )
            logger.info("🔐 Paso 4.5: MFA detectado. Verificando tipo de MFA...")
            logger.info(f"🔐 Paso 4.5: URL={driver.current_url}, Título={driver.title}")

            totp_inputs = driver.find_elements(By.CSS_SELECTOR, "input[name='otc']")

            if not totp_inputs:
                # Pantalla de Authenticator push — cambiar a TOTP
                logger.info("🔐 Paso 4.5: Pantalla de Authenticator push. Intentando cambiar a TOTP...")
                try:
                    alt_method_link = WebDriverWait(driver, WAIT_SHORT).until(
                        EC.element_to_be_clickable((
                            By.CSS_SELECTOR,
                            "#signInAnotherWay, "
                            "a#signInAnotherWay"
                        ))
                    )
                    alt_method_link.click()
                    logger.info("🔐 Paso 4.5: Clic en 'Otro método de verificación'")
                    _time.sleep(PAUSE_AFTER_CLICK)

                    totp_option = WebDriverWait(driver, WAIT_SHORT).until(
                        EC.element_to_be_clickable((
                            By.XPATH,
                            "//*[contains(.,'código de verificación')] | "
                            "//*[contains(.,'verification code')] | "
                            "//*[contains(.,'authenticator app')] | "
                            "//*[contains(.,'app de autenticación')] | "
                            "//*[@data-value='PhoneAppOTP']"
                        ))
                    )
                    totp_option.click()
                    logger.info("🔐 Paso 4.5: Seleccionada opción TOTP")
                    _time.sleep(PAUSE_AFTER_CLICK)

                    totp_inputs = WebDriverWait(driver, WAIT_SHORT).until(
                        lambda d: d.find_elements(By.CSS_SELECTOR, "input[name='otc']")
                    )
                except Exception as switch_err:
                    logger.warning(f"🔐 Paso 4.5: No se pudo cambiar a TOTP: {switch_err}")

            if totp_inputs and totp_secret:
                import pyotp
                totp_code = pyotp.TOTP(totp_secret).now()
                logger.info("🔐 Paso 4.5: Ingresando código TOTP...")
                totp_inputs[0].clear()
                totp_inputs[0].send_keys(totp_code)

                verify_button = wait.until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "input[type='submit']#idSIButton9, "
                    "button[type='submit']#idSIButton9, "
                    "button[type='submit']"
                )))
                verify_button.click()
                logger.info("🔐 Paso 4.5 OK: Código TOTP enviado y verificado")
                _time.sleep(PAUSE_AFTER_CLICK + 1)
            elif totp_inputs and not totp_secret:
                raise RuntimeError(
                    "MFA requerido (TOTP) pero AVAC_TOTP_SECRET no está configurado. "
                    "Configúralo en GitHub Secrets con el secret base32 de tu app autenticadora."
                )
            else:
                raise RuntimeError(
                    "MFA requerido pero no se pudo acceder al método TOTP. "
                    "Opciones: (1) Configurar TOTP y poner el secret en AVAC_TOTP_SECRET, "
                    "o (2) Usar un App Password en AVAC_PASSWORD. "
                    f"URL actual: {driver.current_url}"
                )

        except RuntimeError:
            raise
        except Exception:
            logger.info("ℹ️ Paso 4.5: No apareció MFA (password aceptado sin MFA)")

        # ── Paso 5: "¿Mantener sesión iniciada?" → Sí ───────────────────────
        try:
            kmsi_page = WebDriverWait(driver, WAIT_MEDIUM).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "#KmsiIFrame, "
                    "#idSIButton9, "
                    "#idBtn_Back"
                ))
            )
            logger.info(f"🏠 Paso 5: Página detectada. URL={driver.current_url}")

            stay_signed_in = WebDriverWait(driver, WAIT_SHORT).until(EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "input[type='submit']#idSIButton9, "
                "button[type='submit']#idSIButton9, "
                "input[type='submit'][value='Sí'], "
                "input[type='submit'][value='Yes'], "
                "button[type='submit']"
            )))
            logger.info("🏠 Paso 5: Clic en 'Sí' (mantener sesión)...")
            stay_signed_in.click()
            logger.info("🏠 Paso 5 OK")
            _time.sleep(PAUSE_AFTER_CLICK + 1)
        except Exception:
            logger.info(f"ℹ️ Paso 5: No apareció pantalla 'mantener sesión'. URL={driver.current_url}")

        # ── Paso 6: Esperar redirect de vuelta a AVAC ────────────────────────
        logger.info(f"⏳ Paso 6: Esperando redirect a AVAC... URL actual={driver.current_url}")
        avac_host = base_url.split("//")[1].split("/")[0]

        # Esperar hasta 60 segundos — el redirect OAuth puede tener varios saltos
        WebDriverWait(driver, 60).until(lambda d: avac_host in d.current_url)
        logger.info(f"🌐 Paso 6: URL actual: {driver.current_url}")

        # Verificar login exitoso en AVAC
        wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            ".usermenu, .usertext, #user-menu-toggle, "
            "[data-region='usermenu'], .userbutton, .logininfo, "
            "[aria-label='Menú de usuario']"
        )))
        logger.info("✅ Paso 6 OK: Login exitoso en AVAC. Transfiriendo sesión a modo HTTP rápido...")

        # Transferir cookies de Selenium a requests.Session
        session = requests.Session()
        for cookie in driver.get_cookies():
            session.cookies.set(cookie["name"], cookie["value"])
        session.headers.update({
            "User-Agent": driver.execute_script("return navigator.userAgent;")
        })
        return session

    except Exception as e:
        logger.error(f"❌ Error en login: {e}")
        try:
            logger.error(f"   URL actual: {driver.current_url}")
            page_title = driver.title
            logger.error(f"   Título de página: {page_title}")

            screenshot_path = "/tmp/avac_login_error.png"
            driver.save_screenshot(screenshot_path)
            logger.error(f"   Screenshot guardado en: {screenshot_path}")

            html_path = "/tmp/avac_login_error.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.error(f"   HTML guardado en: {html_path}")
        except Exception:
            pass
        raise
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
                logger.warning(f"⚠️ [{index}/{len(codigos)}] Curso {codigo_curso} no encontrado en AVAC")
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
