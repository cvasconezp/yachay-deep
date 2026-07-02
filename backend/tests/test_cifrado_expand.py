"""[Cifrado en reposo — Fase 2 Expand] Doble escritura transparente.

Verifica que al crear/actualizar Student y User, las columnas *_cif quedan
cifradas (descifran al valor original) y *_bidx contiene el blind index correcto.
El texto plano sigue intacto (fase reversible).
"""
from datetime import date

from backend import crypto
from backend.models.student import Student
from backend.models.user import User, UserRole
from backend.auth.jwt import hash_password


def test_student_dual_write_cifra_y_indexa(db):
    s = Student(
        cedula="1723456789", nombre="María Ñañez", correo="Maria@X.com",
        correo_institucional="mnanez@ups.edu.ec", telefono="0999999999",
        genero="F", autoidentificacion_etnica="Kichwa", ciudad="Quito",
    )
    db.add(s)
    db.commit()
    db.refresh(s)

    # texto plano intacto
    assert s.cedula == "1723456789"
    # cifrado: descifra al original y NO es igual al texto plano
    assert s.cedula_cif and s.cedula_cif != "1723456789"
    assert crypto.decrypt(s.cedula_cif) == "1723456789"
    assert crypto.decrypt(s.correo_cif) == "Maria@X.com"
    assert crypto.decrypt(s.autoidentificacion_etnica_cif) == "Kichwa"
    # blind index: coincide y normaliza (case/espacios)
    assert s.cedula_bidx == crypto.blind_index("1723456789")
    assert s.correo_bidx == crypto.blind_index("maria@x.com  ")
    # campos sin blind index igual se cifran
    assert crypto.decrypt(s.telefono_cif) == "0999999999"


def test_student_sin_valor_no_rompe(db):
    s = Student(nombre="Sin Cedula")  # cedula None
    db.add(s)
    db.commit()
    db.refresh(s)
    assert s.cedula_cif is None
    assert s.cedula_bidx is None
    assert crypto.decrypt(s.nombre_cif) == "Sin Cedula"


def test_user_totp_secret_cifrado(db):
    u = User(email="doc@x.edu", nombre="Doc", hashed_password=hash_password("x"),
             role=UserRole.monitor, totp_secret="JBSWY3DPEHPK3PXP")
    db.add(u)
    db.commit()
    db.refresh(u)
    assert u.totp_secret == "JBSWY3DPEHPK3PXP"           # plano intacto
    assert u.totp_secret_cif != "JBSWY3DPEHPK3PXP"       # cifrado
    assert crypto.decrypt(u.totp_secret_cif) == "JBSWY3DPEHPK3PXP"


def test_update_actualiza_cifrado(db):
    s = Student(cedula="111")
    db.add(s); db.commit()
    s.cedula = "222"
    db.commit(); db.refresh(s)
    assert crypto.decrypt(s.cedula_cif) == "222"
    assert s.cedula_bidx == crypto.blind_index("222")
