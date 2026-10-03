"""Fixtures para pruebas HTTP del flujo comercial vigente de TortuScript."""
import copy
import hashlib

from tortuscript.auth import AuthRepository


def preparar_sesion_educativa(app, client, email="prueba@example.com", nombre="Ana", token="test-token", complete_onboarding=True):
    """Crea cuenta verificada, inicia sesión, selecciona ChildProfile y completa onboarding."""
    # Las pruebas sustituyen el proveedor externo por un sender inocuo; nunca
    # envían correos reales desde CI.
    if not callable(app.config.get("ACCOUNT_EMAIL_SENDER")):
        app.config["ACCOUNT_EMAIL_SENDER"] = lambda **payload: None
    db = app.config["ACCOUNT_DB"]
    # Rate limits are process-wide in tests; isolate each temporary account database.
    parte, dominio = email.rsplit("@", 1)
    sufijo = hashlib.sha256(str(db).encode("utf-8")).hexdigest()[:10]
    email = f"{parte}-{sufijo}@{dominio}"
    password = "una-clave-larga-123"
    registro = client.post("/cuenta/registro", json={"email": email, "password": password})
    if registro.status_code != 202:
        raise AssertionError(f"registro de fixture: {registro.status_code} {registro.get_data(as_text=True)}")

    account_id = "acc_" + hashlib.sha256(email.strip().lower().encode()).hexdigest()[:24]
    AuthRepository(db).marcar_verificada(account_id)

    login = client.post("/cuenta/login", json={"email": email, "password": password})
    if login.status_code != 200:
        raise AssertionError(f"login de fixture: {login.status_code} {login.get_data(as_text=True)}")
    csrf = login.json["csrf"]

    perfil = client.post(
        "/cuenta/perfiles",
        json={"nombre": nombre},
        headers={"X-Tortu-CSRF": csrf},
    )
    if perfil.status_code != 201:
        raise AssertionError(f"perfil de fixture: {perfil.status_code} {perfil.get_data(as_text=True)}")

    seleccionado = client.post(
        "/cuenta/perfil",
        json={"perfil_id": perfil.json["perfil"]["id"]},
        headers={"X-Tortu-CSRF": csrf},
    )
    if seleccionado.status_code != 200:
        raise AssertionError(f"selección de fixture: {seleccionado.status_code} {seleccionado.get_data(as_text=True)}")

    profile_id = perfil.json["perfil"]["id"]
    if complete_onboarding:
        onboarding = client.post(
            "/api/onboarding",
            json={"nombre": nombre, "experiencia": "nunca", "meta_min": 15},
            headers={"X-Tortu-Token": token},
        )
        if onboarding.status_code != 200:
            raise AssertionError(f"onboarding de fixture: {onboarding.status_code} {onboarding.get_data(as_text=True)}")
    else:
        # Deja el perfil comercial en el estado real de primera visita, con snapshot persistido.
        from tortuscript.progreso import PROGRESO_INICIAL
        from tortuscript.progreso_contrato import ProgresoSnapshot
        from tortuscript.progreso_childprofile import ProgresoChildProfile

        datos = copy.deepcopy(PROGRESO_INICIAL)
        datos["config"]["onboarding"] = False
        snapshot = ProgresoSnapshot(
            profile_id=profile_id,
            schema_version=1,
            updated_at="2026-10-02T00:00:00+00:00",
            data=datos,
        )
        ProgresoChildProfile(app.config["PROGRESS_DIR"]).guardar(snapshot)

    return {"csrf": csrf, "perfil_id": profile_id, "headers": {"X-Tortu-Token": token}}
