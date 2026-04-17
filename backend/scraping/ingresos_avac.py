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

# ─── Constantes de espera ──────────────────────────────────────────────────────
# En GitHub Actions la latencia varía mucho. Usar waits explícitos, no sleeps.
WAIT_LONG   = 30   # timeout para pasos críticos (login, redirect)
WAIT_MEDIUM = 15   # timeout para pasos intermedios
WAIT_SHORT  = 5    # timeout para pasos opcionales (selector de cuenta)
PAUSE_AFTER_CLICK = 2  # pausa mínima después de click para que la página reaccione

# ─── Mapeos de columnas AVAC (español / inglés) ───────────────────────────────
# AVAC (Moodle) puede usar distintos nombres de columna según versión/idioma.
# Mapeamos a nombres internos para no depender de posición fija.
_COL_MAPS = {
    "nombre":        ["nombre", "name", "apellido(s), nombre(s)", "apellidos y nombre"],
    "correo":        ["correo electrónico", "email address", "dirección de correo electrónico",
                      "dirección de correo", "correo", "email", "mail"],
    "ultimo_acceso": ["último acceso al curso", "último acceso al sitio",
                      "last access to site", "last access to course",
                      "último acceso", "last access"],
    "estado":        ["estatus", "estado", "status"],
}

# Columnas que son solo UI (checkbox, imagen) y no generan <td> en el tbody.
# Se detectan para calcular el offset entre headers y celdas.
_SKIP_HEADERS = ["seleccionar"]


def _match_header(header: str, candidates: list) -> bool:
    h = header.strip().lower()
    return any(c in h for c in candidates)


def _parse_participants_table(soup: BeautifulSoup) -> list:
    """
    Parsea la tabla generaltable de participantes de forma robusta.

    FIX (P68): Moodle 4.x agrega una columna <th> "Seleccionar todos" (checkbox)
    en el thead que NO tiene un <td> correspondiente en el tbody. Esto causaba
    un offset de +1 entre los índices de los headers y los de las celdas,
    haciendo que el parser mapeara las columnas incorrectamente.

    Solución: detectar headers sin <td> correspondiente y compensar el offset.
    Además se corrigió _COL_MAPS: "roles"/"rol" ya no matchea como "estado"
    (ahora "estado" solo matchea "estatus", "estado", "status").
    """
    table = soup.select_one("table.generaltable")
    if not table:
        return []

    # Leer encabezados
    raw_headers = [th.get_text(strip=True) for th in table.select("thead tr th")]
    if not raw_headers:
        first_row = table.select_one("tbody tr")
        if first_row:
            raw_headers = [td.get_text(strip=True) for td in first_row.find_all(["th", "td"])]

    # Calcular offset: cuántos headers NO tienen <td> (ej: "Seleccionar todos")
    # En Moodle 4.x hay 7 <th> pero solo 6 <td> por fila
    first_data_row = table.select_one("tbody tr")
    num_cells = len(first_data_row.find_all("td")) if first_data_row else 0
    num_headers = len(raw_headers)
    offset = max(0, num_headers - num_cells)

    logger.debug(f"  Headers: {num_headers}, Cells: {num_cells}, Offset: {offset}")

    # Detectar índice de cada columna de interés (relativo a las celdas <td>)
    idx = {"nombre": None, "correo": None, "ultimo_acceso": None, "estado": None}
    skipped = 0
    for i, hdr in enumerate(raw_headers):
        # Detectar headers que no tienen <td> correspondiente
        h_lower = hdr.strip().lower()
        if any(s in h_lower for s in _SKIP_HEADERS):
            skipped += 1
            continue

        cell_idx = i - skipped  # índice real en las celdas <td>
        for key, candidates in _COL_MAPS.items():
            if idx[key] is None and _match_header(hdr, candidates):
                idx[key] = cell_idx
                break

    logger.debug(f"  Column mapping: {idx}")

    registros = []
    for fila in table.select("tbody tr"):
        celdas = fila.find_all("td")
        if not celdas:
            continue

        # Obtener correo por columna detectada, o fallback a escanear celdas
        if idx["correo"] is not None and idx["correo"] < len(celdas):
            correo = celdas[idx["correo"]].get_text(strip=True)
        else:
            correo = next(
                (c.get_text(strip=True) for c in celdas if "@" in c.get_text()),
                ""
            )

        if not correo or "@" not in correo:
            continue

        def _get(key, fallback_idx=0):
            i = idx[key]
            if i is not None and i < len(celdas):
                return celdas[i].get_text(strip=True)
            if fallback_idx < len(celdas):
                return celdas[fallback_idx].get_text(strip=True)
            return ""

        # Limpiar nombre: Moodle 4.x prefija "Seleccionar 'NOMBRE'" en la celda
        nombre_raw = _get("nombre", 0)
        import re
        nombre_clean = re.sub(r"^Seleccionar\s*'(.+)'$", r"\1", nombre_raw).strip()

        registros.append({
            "Nombre":         nombre_clean or nombre_raw,
            "Correo":         correo,
            "Último acceso":  _get("ultimo_acceso"),
            "Estado":         _get("estado"),
        })

    return registros


# ─── Retry helper ─────────────────────────────────────────────────────────────
def _get_with_retry(session: requests.Session, url: str,
                    retries: int = 3, timeout: int = 30) -> requests.Response:
    """
    GET con reintentos exponenciales.
    FIX: antes no había retry — un timeout puntual perdía el curso entero.
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            if attempt < retries:
                wait = 2 * attempt
                logger.warning(f"⚠️  Intento {attempt}/{retries} fallido para {url}: {e} — reintentando en {wait}s")
                time.sleep(wait)
    raise last_exc


# ─── Login helpers ────────────────────────────────────────────────────────────

def _resolve_totp(driver, wait, totp_secret: str, step_label: str):
    """
    Maneja MFA/TOTP: si hay pantalla de Authenticator push, cambia a TOTP.
    Extrae en función reutilizable para Paso 4.5 y Paso 4.6.
    FIX: en Paso 4.6 original no existía este bloque — si el segundo login
    pedía MFA por push, el scraping fallaba sin diagnóstico.
    """
    import time as _time
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    totp_inputs = driver.find_elements(By.CSS_SELECTOR, "input[name='otc']")

    if not totp_inputs:
        logger.info(f"🔐 {step_label}: Pantalla de Authenticator push. Intentando cambiar a TOTP...")
        try:
            alt_method_link = WebDriverWait(driver, WAIT_SHORT).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "#signInAnotherWay, a#signInAnotherWay"
                ))
            )
            alt_method_link.click()
            logger.info(f"🔐 {step_label}: Clic en 'Otro método de verificación'")
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
            logger.info(f"🔐 {step_label}: Seleccionada opción TOTP")
            _time.sleep(PAUSE_AFTER_CLICK)

            totp_inputs = WebDriverWait(driver, WAIT_SHORT).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "input[name='otc']")
            )
        except Exception as switch_err:
            logger.warning(f"🔐 {step_label}: No se pudo cambiar a TOTP: {switch_err}")

    if totp_inputs and totp_secret:
        import pyotp
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        totp_code = pyotp.TOTP(totp_secret).now()
        logger.info(f"🔐 {step_label}: Ingresando código TOTP...")
        totp_inputs[0].clear()
        totp_inputs[0].send_keys(totp_code)
        verify_button = WebDriverWait(driver, WAIT_LONG).until(EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            "input[type='submit']#idSIButton9, "
            "button[type='submit']#idSIButton9, "
            "button[type='submit']"
        )))
        verify_button.click()
        logger.info(f"🔐 {step_label} OK: Código TOTP enviado y verificado")
        _time.sleep(PAUSE_AFTER_CLICK + 1)
    elif totp_inputs and not totp_secret:
        raise RuntimeError(
            f"MFA requerido (TOTP) en {step_label} pero AVAC_TOTP_SECRET no está configurado. "
            "Configúralo en GitHub Secrets con el secret base32 de tu app autenticadora. "
            "Para obtenerlo: Seguridad → App Authenticator → 'No puedo usar la app' → "
            "copiar el código secreto que se muestra al configurar manualmente."
        )
    else:
        raise RuntimeError(
            f"MFA requerido en {step_label} pero no se pudo acceder al método TOTP. "
            "Opciones: (1) Configurar TOTP y poner el secret en AVAC_TOTP_SECRET, "
            f"o (2) Usar un App Password en AVAC_PASSWORD. "
            f"URL actual: {driver.current_url}"
        )


def get_session_headless(username: str, password: str, base_url: str,
                         totp_secret: str = None) -> requests.Session:
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

    # ── Screenshots de diagnóstico ────────────────────────────────────────────
    screenshots_dir = os.environ.get("SCRAPING_SCREENSHOTS_DIR", "/tmp/scraping_screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    _step_counter = [0]

    def _save_screenshot(driver, step_name: str):
        """Guarda un screenshot con timestamp para diagnóstico visual."""
        _step_counter[0] += 1
        filename = f"{_step_counter[0]:02d}_{step_name}.png"
        filepath = os.path.join(screenshots_dir, filename)
        try:
            driver.save_screenshot(filepath)
            logger.info(f"📸 Screenshot guardado: {filename} (URL: {driver.current_url})")
        except Exception as e:
            logger.warning(f"📸 No se pudo guardar screenshot {filename}: {e}")

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
        # ── Paso 1: Ir a AVAC login y clic en "Usuarios de la UPS" ────────────
        logger.info("📄 Paso 1: Cargando página de login AVAC...")
        driver.get(f"{base_url}/login/index.php")
        _save_screenshot(driver, "paso1_avac_login")
        sso_button = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//a[contains(.,'Usuarios de la UPS')] | "
            "//button[contains(.,'Usuarios de la UPS')] | "
            "//div[contains(@class,'potentialidp')]//a"
        )))
        logger.info("🔗 Paso 1 OK: Clic en 'Usuarios de la UPS' (redirect a Microsoft SSO)...")
        sso_button.click()

        # ── Paso 2: Microsoft login — ingresar email ──────────────────────────
        logger.info("📧 Paso 2: Esperando página de login Microsoft...")
        email_field = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "input[name='loginfmt']"
        )))
        _save_screenshot(driver, "paso2_microsoft_login")
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
        _save_screenshot(driver, "paso2_despues_siguiente")

        # ── Paso 3: Selector de cuenta (si aparece) ───────────────────────────
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
            logger.info("ℹ️  Paso 3: No apareció selector de cuenta (directo a password)")

        # ── Paso 4: Ingresar contraseña ───────────────────────────────────────
        logger.info("🔑 Paso 4: Esperando campo de contraseña...")
        password_field = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "input[name='passwd']"
        )))
        _save_screenshot(driver, "paso4_campo_password")
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
        _save_screenshot(driver, "paso4_despues_signin")

        # ── Paso 4.5: Manejar MFA/TOTP si aparece ────────────────────────────
        try:
            WebDriverWait(driver, WAIT_SHORT).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "input[name='otc'], "
                    "#idDiv_SAOTCC_Description, "
                    "#idDiv_SAOTCAS_Description, "
                    "#idRichContext_DisplaySign"
                ))
            )
            logger.info("🔐 Paso 4.5: MFA detectado.")
            logger.info(f"🔐 Paso 4.5: URL={driver.current_url}, Título={driver.title}")
            _save_screenshot(driver, "paso4.5_mfa_detectado")
            _resolve_totp(driver, wait, totp_secret, "Paso 4.5")
        except RuntimeError:
            raise
        except Exception:
            logger.info("ℹ️  Paso 4.5: No apareció MFA (password aceptado sin MFA)")

        # ── Paso 4.6: Manejar segundo login en /common/login ──────────────────
        # Después del login en el tenant específico, el flujo OAuth de AVAC
        # puede redirigir a login.microsoftonline.com/common/login para una
        # segunda autenticación. FIX: ahora incluye manejo completo de MFA.
        if 'login.microsoftonline.com/common' in driver.current_url:
            logger.info(f"🔄 Paso 4.6: Segundo login detectado en /common/login")
            logger.info(f"🔄 Paso 4.6: URL={driver.current_url}, Título={driver.title}")
            _save_screenshot(driver, "paso4.6_segundo_login")

            try:
                email_field2 = WebDriverWait(driver, WAIT_SHORT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='loginfmt']"))
                )
                email_field2.clear()
                email_field2.send_keys(username)
                logger.info("🔄 Paso 4.6: Email re-ingresado, clic en 'Siguiente'...")
                next_btn2 = wait.until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "button[type='submit']#idSIButton9, button[type='submit']"
                )))
                next_btn2.click()
                _time.sleep(PAUSE_AFTER_CLICK)
            except Exception:
                logger.info("🔄 Paso 4.6: No hay campo de email (directo a password o selector)")

            try:
                work_acct2 = WebDriverWait(driver, WAIT_SHORT).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//button[contains(.,'rofesional')] | "
                        "//*[@id='aadTile'] | "
                        "//button[contains(.,'Work or school')]"
                    ))
                )
                work_acct2.click()
                logger.info("🔄 Paso 4.6: Cuenta profesional seleccionada")
                _time.sleep(PAUSE_AFTER_CLICK)
            except Exception:
                pass

            try:
                pwd_field2 = WebDriverWait(driver, WAIT_MEDIUM).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='passwd']"))
                )
                pwd_field2.clear()
                pwd_field2.send_keys(password)
                logger.info("🔄 Paso 4.6: Contraseña re-ingresada, clic en 'Iniciar sesión'...")
                signin_btn2 = wait.until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "button[type='submit']#idSIButton9, button[type='submit']"
                )))
                signin_btn2.click()
                logger.info("🔄 Paso 4.6 OK: Credenciales re-ingresadas en /common/login")
                _time.sleep(PAUSE_AFTER_CLICK + 1)
            except Exception as e:
                logger.warning(f"🔄 Paso 4.6: No se encontró campo de password: {e}")

            # FIX: MFA en segundo login — igual que Paso 4.5, usando _resolve_totp
            try:
                WebDriverWait(driver, WAIT_SHORT).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        "input[name='otc'], "
                        "#idDiv_SAOTCC_Description, "
                        "#idDiv_SAOTCAS_Description, "
                        "#idRichContext_DisplaySign"
                    ))
                )
                logger.info("🔐 Paso 4.6: MFA detectado en segundo login.")
                _resolve_totp(driver, wait, totp_secret, "Paso 4.6")
            except RuntimeError:
                raise
            except Exception:
                logger.info("ℹ️  Paso 4.6: No apareció MFA en segundo login")

        # ── Paso 5: "¿Mantener sesión iniciada?" → Sí ─────────────────────────
        try:
            WebDriverWait(driver, WAIT_MEDIUM).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "#KmsiiFrame, [data-bind*='kmpiFrame'], #idSIButton9, #idBtn_Back"
                ))
            )
            logger.info(f"🏠 Paso 5: Página detectada. URL={driver.current_url}")
            _save_screenshot(driver, "paso5_mantener_sesion")
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
            logger.info(f"ℹ️  Paso 5: No apareció pantalla 'mantener sesión'. URL={driver.current_url}")

        # ── Paso 6: Esperar redirect de vuelta a AVAC ─────────────────────────
        _save_screenshot(driver, "paso6_esperando_redirect")
        logger.info(f"⏳ Paso 6: Esperando redirect a AVAC... URL actual={driver.current_url}")
        avac_host = base_url.split("//")[1].split("/")[0]
        WebDriverWait(driver, 60).until(lambda d: avac_host in d.current_url)
        logger.info(f"🌐 Paso 6: URL actual: {driver.current_url}")

        wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            ".usermenu, .usertext, #user-menu-toggle, "
            "[data-region='usermenu'], .userbutton, .logininfo, "
            "[aria-label='Menú de usuario']"
        )))
        _save_screenshot(driver, "paso6_login_exitoso")
        logger.info("✅ Paso 6 OK: Login exitoso en AVAC. Transfiriendo sesión a modo HTTP rápido...")

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
            logger.error(f"  URL actual: {driver.current_url}")
            logger.error(f"  Título de página: {driver.title}")
            screenshot_path = "/tmp/avac_login_error.png"
            driver.save_screenshot(screenshot_path)
            logger.error(f"  Screenshot guardado en: {screenshot_path}")
            html_path = "/tmp/avac_login_error.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.error(f"  HTML guardado en: {html_path}")
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


def get_session_cookie(cookie_value: str, base_url: str) -> requests.Session:
    """
    Login via MoodleSession cookie — bypasses SSO/Selenium completely.

    Use case: Microsoft Conditional Access blocks Selenium login from
    datacenter IPs (GitHub Actions, Railway). The user logs in from their
    browser, copies the MoodleSession cookie, and the scraper uses it directly.

    The cookie can be set via:
    - AVAC_SESSION_COOKIE env var (Railway/GitHub Secret)
    - Admin panel → PUT /admin/system/avac-cookie
    """
    session = requests.Session()
    domain = base_url.split("//")[1].split("/")[0]  # "avac.ups.edu.ec"
    session.cookies.set("MoodleSession", cookie_value, domain=domain)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    })

    # Validate the cookie is still active
    logger.info("🍪 Modo cookie: validando sesión...")
    try:
        resp = session.get(f"{base_url}/my/", timeout=15, allow_redirects=False)
        if resp.status_code == 303 or "login" in resp.headers.get("Location", ""):
            raise RuntimeError(
                "❌ Cookie MoodleSession expirada o inválida. "
                "Inicia sesión en AVAC desde tu navegador y actualiza la cookie."
            )
        # Follow redirect and verify we're logged in
        resp2 = session.get(f"{base_url}/my/", timeout=15)
        if "login/index.php" in resp2.url:
            raise RuntimeError(
                "❌ Cookie MoodleSession expirada o inválida (redirect a login). "
                "Actualiza la cookie desde Admin → Configuración."
            )
        logger.info(f"🍪 Sesión válida (URL: {resp2.url})")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"❌ Error validando cookie: {e}")

    return session


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


def scrape_ingresos(output_dir: str, codigos: list = None,
                    base_url: str = None, db=None) -> dict:
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

    session_cookie = settings.AVAC_SESSION_COOKIE
    username       = settings.AVAC_USERNAME
    password       = settings.AVAC_PASSWORD
    totp_secret    = settings.AVAC_TOTP_SECRET

    if session_cookie:
        logger.info("🍪 Modo cookie (MoodleSession directa — sin Selenium)")
        session = get_session_cookie(session_cookie, base_url)
    elif username and password:
        logger.info("🔑 Modo Selenium (credenciales + SSO automático)")
        session = get_session_headless(username, password, base_url, totp_secret)
    else:
        logger.info("👤 Modo manual — login interactivo requerido")
        session = get_session_manual(base_url)

    procesados, no_encontrados, errores = 0, [], []

    for index, codigo_curso in enumerate(codigos, 1):
        try:
            start_time = time.time()

            resp = _get_with_retry(session, f"{base_url}/course/search.php?areaids=core_course-course&q={codigo_curso}")
            soup = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
            enlace = (
                soup.select_one(".coursebox a[href*='view.php?id=']") or
                soup.select_one("a[href*='/course/view.php?id=']")
            )

            if not enlace:
                no_encontrados.append(codigo_curso)
                logger.warning(f"⚠️  [{index}/{len(codigos)}] Curso {codigo_curso} no encontrado en AVAC")
                continue

            course_id = parse_qs(urlparse(enlace.get("href")).query).get("id", [None])[0]

            resp_part = _get_with_retry(session, f"{base_url}/user/index.php?id={course_id}&perpage=5000")
            soup_part = BeautifulSoup(resp_part.content, "html.parser", from_encoding="utf-8")

            # FIX: parseo robusto por nombre de columna, no por posición
            registros = _parse_participants_table(soup_part)

            if registros:
                df = pd.DataFrame(registros)
                df["Código Curso"]     = codigo_curso
                df["Fecha Extracción"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                df.to_csv(output_path / f"ingresosAVAC_{codigo_curso}.csv", index=False, encoding="utf-8-sig")
                procesados += 1
                logger.info(f"[{index}/{len(codigos)}] ✅ {codigo_curso}: {len(registros)} alumnos en {round(time.time()-start_time, 2)}s")
            else:
                logger.warning(f"[{index}/{len(codigos)}] ⚠️  {codigo_curso}: tabla vacía o sin alumnos con correo")

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
