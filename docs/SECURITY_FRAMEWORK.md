> ⚠️ **DEPRECADO / DESACTUALIZADO.** Este documento fue reemplazado por **[SECURITY.md](./SECURITY.md)**. Se conserva solo como referencia histórica; no lo uses ni lo actualices. (chore/estandar-casa, 2026-07)

# Framework de Seguridad y Protección de Datos

**Yachay Deep — Sistema de Alerta Temprana Académica**

Versión 1.0 · Mayo 2026

---

## 1. Introducción

Este documento define las políticas, controles técnicos y procedimientos de seguridad implementados en Yachay Deep. Sirve como referencia interna para el equipo de desarrollo y operaciones, y como evidencia de cumplimiento para instituciones que evalúan la plataforma.

### 1.1 Alcance

El framework cubre los tres componentes del sistema:

| Componente | Tecnología | Hosting |
|---|---|---|
| Frontend | React 18 + Vite + Tailwind CSS | Vercel (CDN global) |
| Backend API | Python / FastAPI | Railway (contenedor Docker) |
| Base de datos | PostgreSQL 15 | Railway (instancia aislada) |

### 1.2 Principios rectores

- **Mínimo privilegio**: cada rol accede solo a lo que necesita.
- **Defensa en profundidad**: múltiples capas de protección redundantes.
- **Datos mínimos**: solo recopilamos información académica necesaria para la alerta temprana.
- **Cifrado por defecto**: toda comunicación y almacenamiento sensible es cifrado.

---

## 2. Autenticación y Gestión de Sesiones

### 2.1 JSON Web Tokens (JWT)

Las sesiones se gestionan mediante JWT con las siguientes características:

- **Algoritmo**: HS256 con clave secreta de entorno (no hardcoded).
- **Tiempo de vida**: 8 horas, no renovable — requiere nuevo login.
- **Almacenamiento**: cookies `HttpOnly` + `Secure` + `SameSite=Lax`.
- **Payload mínimo**: solo `user_id`, `role` y `exp`. Sin datos personales en el token.

### 2.2 Contraseñas

- **Hashing**: BCrypt mediante `passlib` con cost factor adaptativo.
- **Nunca en texto plano**: ni en base de datos, ni en logs, ni en respuestas API.
- **Sin recuperación**: las contraseñas son irrecuperables por diseño (hash irreversible).

### 2.3 PIN de bloqueo por inactividad

- PIN de 6 dígitos, almacenado como hash BCrypt independiente.
- Bloqueo automático tras 5 minutos de inactividad del usuario.
- Rate limiting de 5 intentos/minuto en el endpoint de verificación.

### 2.4 Rate Limiting

| Endpoint | Límite | Ventana |
|---|---|---|
| `/api/login` | 5 intentos | 1 minuto |
| `/api/verify-pin` | 5 intentos | 1 minuto |
| Endpoints generales | Sin límite explícito | — |

Implementado con `slowapi` a nivel de IP.

---

## 3. Control de Acceso (RBAC)

### 3.1 Roles del sistema

| Rol | Descripción | Permisos clave |
|---|---|---|
| **admin** | Administrador institucional | Gestión de usuarios, configuración global, endpoints de debug, reportes completos |
| **coordinador** | Coordinador de carrera | Ver todos los estudiantes de su carrera, asignar tutores, reportes de carrera |
| **docente** | Profesor/tutor | Ver estudiantes asignados, registrar intervenciones, ver calificaciones de sus cursos |
| **monitor** | Monitor/tutor par | Ver estudiantes asignados (lectura limitada), registrar seguimientos |

### 3.2 Implementación técnica

- Cada endpoint protegido usa `Depends(require_role(...))` de FastAPI.
- Los endpoints administrativos y de debug requieren `Depends(require_admin)`.
- La verificación de rol se ejecuta en cada request — no hay caché de permisos.
- Los tokens JWT incluyen el rol, pero se revalida contra la base de datos.

### 3.3 Aislamiento de datos

- Un docente solo ve estudiantes de los cursos donde es profesor.
- Un coordinador solo ve estudiantes de su carrera/sede.
- Los endpoints de listado filtran automáticamente por el contexto del usuario autenticado.

---

## 4. Protección de Datos

### 4.1 Datos que almacenamos

| Categoría | Ejemplos | Sensibilidad |
|---|---|---|
| Identidad académica | Nombre, cédula, correo institucional | Media |
| Información curricular | Carrera, sede, nivel, período | Baja |
| Rendimiento académico | Calificaciones por unidad y actividad | Media |
| Actividad en plataforma | Frecuencia de acceso a Moodle | Baja |
| Indicadores calculados | Índice de riesgo, alertas generadas | Media |
| Intervenciones | Registro de tutorías y seguimientos | Media |

### 4.2 Datos que NO almacenamos

- Contraseñas de Moodle ni de ningún sistema externo.
- Datos financieros, de pago o bancarios.
- Historial médico o psicológico.
- Datos biométricos.
- Información de familiares.
- Contenido de tareas, archivos enviados o foros.
- Direcciones de domicilio o teléfonos personales.

### 4.3 Cifrado en reposo

- PostgreSQL en Railway utiliza cifrado de disco a nivel de infraestructura (AES-256).
- Las contraseñas y PINs se almacenan como hashes BCrypt irreversibles.
- Las variables de entorno (secrets) se almacenan cifradas en Railway y GitHub Actions.

### 4.4 Cifrado en tránsito

- **HTTPS obligatorio** en todos los componentes (TLS 1.2+).
- Vercel: certificados Let's Encrypt auto-renovados.
- Railway: certificados TLS gestionados automáticamente.
- Comunicación API ↔ BD: conexión cifrada dentro de la red privada de Railway.
- **HSTS habilitado**: fuerza HTTPS y previene downgrade attacks.

---

## 5. Headers de Seguridad HTTP

El backend inyecta los siguientes headers en todas las respuestas:

| Header | Valor | Propósito |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'` | Previene inyección de scripts externos |
| `X-Frame-Options` | `DENY` | Previene clickjacking (iframe embedding) |
| `X-Content-Type-Options` | `nosniff` | Previene MIME-type sniffing |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Fuerza HTTPS por 1 año |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limita filtración de URLs en referrer |
| `X-XSS-Protection` | `1; mode=block` | Capa adicional anti-XSS (legacy browsers) |

---

## 6. Protección contra Ataques Comunes

### 6.1 SQL Injection

- **ORM exclusivo**: todas las consultas usan SQLAlchemy ORM con parámetros bindeados.
- No existe SQL crudo (`raw queries`) en el codebase.
- Los inputs se validan con Pydantic schemas antes de llegar al ORM.

### 6.2 Cross-Site Scripting (XSS)

- Cookies `HttpOnly` — JavaScript no puede leer tokens de sesión.
- Content Security Policy restringe fuentes de scripts.
- React escapa HTML por defecto en el renderizado.
- No se usa `dangerouslySetInnerHTML` en ningún componente.

### 6.3 Cross-Site Request Forgery (CSRF)

- Cookies con `SameSite=Lax` mitigan CSRF en navegadores modernos.
- La API requiere autenticación vía cookie — no acepta tokens en headers arbitrarios.

### 6.4 Fuerza bruta

- Rate limiting en endpoints de autenticación (5/min).
- BCrypt con cost factor alto hace inviable el cracking masivo de hashes.
- No se revelan mensajes de error que confirmen existencia de usuarios.

---

## 7. Infraestructura y Operaciones

### 7.1 Arquitectura de despliegue

```
[Usuario] → HTTPS → [Vercel CDN] → HTTPS → [Railway API] → TLS → [Railway PostgreSQL]
                     (estático)              (contenedor)          (instancia dedicada)
```

### 7.2 Frontend (Vercel)

- CDN global con edge locations — baja latencia desde cualquier ubicación.
- Contenido 100% estático — no almacena ni procesa datos de usuarios.
- Despliegue automático desde rama `main` de GitHub.
- Protección DDoS incluida en el plan de Vercel.
- Certificados HTTPS auto-renovados (Let's Encrypt).

### 7.3 Backend + BD (Railway)

- Contenedores Docker aislados — sin acceso a otros servicios.
- PostgreSQL en instancia dedicada (no compartida).
- Red privada entre API y BD — la base de datos no está expuesta a Internet.
- Variables de entorno cifradas (JWT secret, DB credentials, API keys).
- Logs de acceso y monitoreo de métricas disponibles en dashboard.
- Backups automáticos diarios gestionados por Railway.

### 7.4 Gestión de secretos

| Secreto | Ubicación | Acceso |
|---|---|---|
| `JWT_SECRET` | Railway env vars (cifrado) | Solo el contenedor API |
| `DATABASE_URL` | Railway env vars (cifrado) | Solo el contenedor API |
| Credenciales de scraping | GitHub Actions secrets | Solo el workflow CI/CD |
| API keys de terceros | Railway env vars (cifrado) | Solo el contenedor API |

Ningún secreto está hardcoded en el código fuente ni en el repositorio.

---

## 8. CI/CD y Pruebas de Seguridad

### 8.1 Pipeline de despliegue

1. Push a `main` en GitHub.
2. GitHub Actions ejecuta tests automatizados.
3. Si pasan, Railway despliega automáticamente el backend.
4. Vercel despliega automáticamente el frontend.

### 8.2 Suites de pruebas de seguridad

| Suite | Qué verifica |
|---|---|
| `test_security_auth` | Login, tokens inválidos, expiración de sesiones, cookies seguras |
| `test_security_headers` | Presencia y valores correctos de todos los headers de seguridad |
| `test_security_injection` | Resistencia a SQL injection y manipulación de parámetros |
| `test_security_rbac` | Cada rol solo accede a endpoints permitidos |
| `test_security_xss` | Inputs maliciosos son sanitizados correctamente |

Estas pruebas se ejecutan automáticamente con cada push a `main`.

---

## 9. Respuesta a Incidentes

### 9.1 Clasificación

| Nivel | Descripción | Ejemplo | Tiempo de respuesta |
|---|---|---|---|
| **Crítico** | Acceso no autorizado a datos | Breach de BD, escalación de privilegios | Inmediato (< 1 hora) |
| **Alto** | Vulnerabilidad explotable | XSS confirmado, endpoint sin auth | < 4 horas |
| **Medio** | Debilidad identificada | Header faltante, log excesivo | < 24 horas |
| **Bajo** | Mejora preventiva | Actualización de dependencia | Próximo sprint |

### 9.2 Procedimiento

1. **Detección**: monitoreo de logs, reporte de usuario, o hallazgo en auditoría.
2. **Contención**: aislar el componente afectado (revocar tokens, bloquear IP, detener servicio).
3. **Investigación**: análisis de logs, alcance del impacto, datos afectados.
4. **Remediación**: fix desplegado, tests agregados para prevenir recurrencia.
5. **Comunicación**: notificar a instituciones afectadas si hubo exposición de datos.
6. **Post-mortem**: documentar causa raíz, acciones tomadas y lecciones aprendidas.

---

## 10. Cumplimiento y Privacidad

### 10.1 Principios de privacidad

- **Minimización**: solo recopilamos datos académicos necesarios para el sistema de alertas.
- **Propósito limitado**: los datos se usan exclusivamente para detección temprana de riesgo académico.
- **Retención limitada**: los datos de períodos anteriores pueden archivarse o eliminarse según política institucional.
- **Transparencia**: los usuarios pueden consultar qué datos se almacenan sobre ellos.

### 10.2 Derechos de los titulares

El sistema permite a las instituciones cumplir con solicitudes de:

- **Acceso**: exportar datos de un estudiante.
- **Rectificación**: corregir datos incorrectos vía panel administrativo.
- **Eliminación**: eliminar registros de un estudiante (admin).
- **Portabilidad**: exportar datos en formato estándar (CSV/JSON).

### 10.3 Marco regulatorio de referencia

- Ley Orgánica de Protección de Datos Personales (Ecuador, 2021).
- Principios generales de GDPR como referencia de mejores prácticas.
- Políticas de protección de datos de cada institución contratante.

---

## 11. Resumen de Controles

| Área | Control | Estado |
|---|---|---|
| Autenticación | JWT + HttpOnly cookies + BCrypt | ✅ Implementado |
| Cifrado en tránsito | TLS 1.2+ / HSTS | ✅ Implementado |
| Cifrado en reposo | Railway encrypted storage | ✅ Implementado |
| Control de acceso | RBAC con 4 roles + permisos granulares | ✅ Implementado |
| Protección XSS | HttpOnly cookies + CSP + React escape | ✅ Implementado |
| Protección SQL injection | ORM (SQLAlchemy) — sin SQL crudo | ✅ Implementado |
| Rate limiting | 5 intentos/min en login y PIN | ✅ Implementado |
| Bloqueo por inactividad | PIN de 6 dígitos + 5 min timeout | ✅ Implementado |
| Security headers | CSP, X-Frame, HSTS, Referrer-Policy | ✅ Implementado |
| Tests automatizados | 5 suites: auth, headers, injection, RBAC, XSS | ✅ Implementado |
| Gestión de secretos | Variables de entorno cifradas (Railway/GitHub) | ✅ Implementado |
| Backups | Automáticos diarios (Railway) | ✅ Implementado |
| Respuesta a incidentes | Procedimiento definido con 4 niveles | ✅ Documentado |

---

## 12. Historial de Revisiones

| Versión | Fecha | Cambios |
|---|---|---|
| 1.0 | 2026-05-20 | Versión inicial del framework |

---

*Documento interno — Yachay Deep / PachaTech*
