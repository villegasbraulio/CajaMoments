# Caja Moments

Sistema web de Fase 1 para caja diaria de salon de eventos: cuentas/billeteras, movimientos de caja, cierres diarios por cuenta, proveedores, personal eventual, impuestos, recordatorios, evento basico y reportes.

Quedo preparado para:

- desarrollo local con SQLite
- produccion en Render con PostgreSQL
- produccion en Vercel como `frontend + backend` separados
- frontend React estatico
- login basico por token para proteger la API

## Stack

- Backend: Django 4.2 + Django REST Framework
- Base inicial: SQLite3
- Frontend: React + Vite
- Estilos: Bootstrap 5 + CSS propio
- Dinero: `DecimalField`, nunca `FloatField`
- Zona horaria: `America/Argentina/Mendoza`

## Estructura

```text
backend/
  config/              Configuracion Django
  cashflow/            Dominio de caja diaria, servicios, API, admin, tests
  build.sh             Build para Render
render.yaml            Blueprint de Render
frontend/
  src/                 SPA React
```

## Backend local

Crear entorno e instalar dependencias:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

Migrar y cargar datos iniciales maestros:

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py seed_initial_data --skip-examples
```

Si queres cargar datos demo de ejemplo:

```bash
../.venv/bin/python manage.py seed_initial_data
```

Crear usuario para entrar al frontend y al admin:

```bash
../.venv/bin/python manage.py createsuperuser
```

O crear uno conocido con el comando incluido:

```bash
../.venv/bin/python manage.py ensure_admin_user --username admin --password 'CajaMoments2026!' --email admin@cajamoments.local
```

Correr backend:

```bash
../.venv/bin/python manage.py runserver 0.0.0.0:8000
```

API:

```text
http://localhost:8000/api/
```

Admin:

```text
http://localhost:8000/admin/
```

Login frontend:

- usa el mismo usuario creado con `createsuperuser`
- el frontend llama a `/api/auth/login/` y guarda un token

Healthcheck:

```text
http://localhost:8000/api/health/
```

Tests:

```bash
cd backend
../.venv/bin/python manage.py test
```

## Frontend local

Instalar dependencias y correr:

```bash
cd frontend
npm install
npm run dev
```

Abrir:

```text
http://localhost:5173
```

Si la API corre en otra URL:

```bash
VITE_API_BASE_URL=http://localhost:8000/api npm run dev
```

Build:

```bash
npm run build
```

## Variables de entorno

Ejemplos:

- [backend/.env.example](/Users/braulio/CajaMoments/backend/.env.example)
- [frontend/.env.example](/Users/braulio/CajaMoments/frontend/.env.example)

Variables importantes backend:

- `SECRET_KEY`
- `DEBUG`
- `DATABASE_URL`
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`

Variable importante frontend:

- `VITE_API_BASE_URL`

## Seeds

El comando `seed_initial_data` carga siempre:

- Cuentas: EFECTIVO, BNA, MERCADO PAGO, NARANJA, PLAZO FIJO, FRASCOS, USD
- Codigos: COBRO_EVENTO, SEÑA_EVENTO, PAGO_PROVEEDOR, PERSONAL_EVENTUAL, COCINA, LIMPIEZA, CABINA, IMPUESTOS, SERVICIOS, TRANSFERENCIA_INTERNA, INVERSION_PLAZO_FIJO, INVERSION_FRASCO, RENDIMIENTO_INVERSION, AJUSTE_CAJA, OTRO_INGRESO, OTRO_EGRESO
- Impuestos: Servicios, Monotributo, IVA, Ingresos Brutos, Autonomos, Municipal
- Roles: Mozo, Cocina, Cabina, Limpieza anterior, Limpieza posterior, Armado, Produccion, Barra, Otro

Si NO usas `--skip-examples`, tambien carga:

- proveedores de ejemplo
- empleados de ejemplo
- cliente de ejemplo
- evento de ejemplo

## Decisiones tecnicas

- El nucleo es `CashMovement`: todo movimiento real de dinero pasa por el libro mayor de caja.
- Los saldos no se editan historicamente: se calculan como saldo inicial + movimientos confirmados.
- Los movimientos `VOIDED` no impactan saldos y no se borran fisicamente.
- Si hay que corregir saldo, se crea un movimiento con codigo `AJUSTE_CAJA`.
- Los cierres son por fecha + cuenta. Una cuenta cerrada para un dia bloquea nuevos cambios en esa fecha/cuenta.
- Las transferencias crean dos movimientos: `TRANSFER_OUT` en origen y `TRANSFER_IN` en destino. La comision, si existe, es un egreso separado.
- Los pagos a proveedores y empleados generan movimientos de caja y entradas relacionadas.
- Los proveedores pueden quedar con saldo negativo: eso representa saldo a favor o pago adelantado.
- USD es una cuenta separada y no se convierte a ARS en Fase 1.
- La logica de negocio vive en `cashflow/services.py`, no incrustada en views.
- Los endpoints DRF quedan listos para que el frontend evolucione sin rehacer el dominio.
- En produccion se usa `DATABASE_URL` para PostgreSQL y `WhiteNoise` para estaticos del backend.
- La API requiere autenticacion por token, salvo login y healthcheck.

## Endpoints principales

```text
/api/auth/login/
/api/auth/me/
/api/auth/logout/
/api/health/
/api/accounts/
/api/movement-codes/
/api/cash-movements/
/api/account-transfers/
/api/daily-cash-closes/
/api/daily-account-closes/
/api/providers/
/api/provider-ledger/
/api/employees/
/api/employee-roles/
/api/clients/
/api/events/
/api/event-staff-assignments/
/api/employee-payments/
/api/tax-types/
/api/tax-payments/
/api/reminders/
/api/dashboard/
/api/reports/
```

## Reportes incluidos

- Resumen de caja diaria
- Cierre por cuenta/billetera
- Saldo por cuenta/billetera
- Ingresos vs egresos por periodo
- Egresos por codigo
- Gastos y saldos por proveedor
- Proveedores con saldo a favor
- Personal por evento con pagado/pendiente
- Impuestos pagados y proximos a vencer
- Movimientos anulados
- Transferencias entre cuentas
- Resumen basico por evento

## Deploy en Render

El repo ya incluye [render.yaml](/Users/braulio/CajaMoments/render.yaml) y [backend/build.sh](/Users/braulio/CajaMoments/backend/build.sh).

### Opcion recomendada

1. Subir este proyecto a GitHub.
2. En Render, ir a `Blueprints`.
3. Crear un `New Blueprint Instance`.
4. Seleccionar el repo.
5. Aplicar el blueprint.

Eso crea:

- `caja-moments-db` como PostgreSQL
- `caja-moments-api` como backend Django
- `caja-moments-web` como static site React

### Que hace el deploy

- `backend/build.sh` instala dependencias y corre `collectstatic`
- el backend arranca con `gunicorn`
- si usas plan free, las migraciones y seeds se corren manualmente desde el Shell de Render

### En plan free de Render

- no hay `Shell access`
- no hay `preDeployCommand`

Por eso este proyecto usa `backend/start.sh` como `startCommand`. En cada arranque:

- corre migraciones
- carga seeds maestros
- crea o actualiza el admin automaticamente si existe `ADMIN_PASSWORD`

El blueprint ya deja configurado por defecto:

- usuario: `admin`
- password: `CajaMoments2026!`

Ese usuario sirve para:

- entrar al frontend
- entrar al admin Django

### Recomendaciones para el MVP

- Usa plan con backups para la DB si el cliente va a cargar datos reales.
- Mantene SQLite solo para local.
- Antes de pasar a uso real, configura dominio propio y cambia la contrasena del admin.

## Deploy en Vercel

Para Vercel, la opcion mas prolija en este proyecto es separar:

- un proyecto `backend` en Vercel
- un proyecto `frontend` en Vercel
- una base PostgreSQL externa, por ejemplo Neon

Archivos incluidos:

- [backend/vercel.json](/Users/braulio/CajaMoments/backend/vercel.json)
- [backend/api/index.py](/Users/braulio/CajaMoments/backend/api/index.py)
- [frontend/vercel.json](/Users/braulio/CajaMoments/frontend/vercel.json)

### Backend Django en Vercel

1. Crear una base PostgreSQL en Neon o proveedor similar.
2. En Vercel, crear un proyecto nuevo usando `backend/` como Root Directory.
3. Configurar variables de entorno:

- `DEBUG=False`
- `SECRET_KEY=...`
- `DATABASE_URL=postgres://...`
- `ALLOWED_HOSTS=tu-backend.vercel.app`
- `CORS_ALLOWED_ORIGINS=https://tu-frontend.vercel.app`
- `CSRF_TRUSTED_ORIGINS=https://tu-backend.vercel.app,https://tu-frontend.vercel.app`

4. Deployar el backend.

5. Despues del primer deploy, correr migraciones y seeds desde tu maquina local apuntando al `DATABASE_URL` de produccion:

```bash
cd backend
DATABASE_URL=postgres://... SECRET_KEY=... DEBUG=False ../.venv/bin/python manage.py migrate
DATABASE_URL=postgres://... SECRET_KEY=... DEBUG=False ../.venv/bin/python manage.py seed_initial_data --skip-examples
DATABASE_URL=postgres://... SECRET_KEY=... DEBUG=False ../.venv/bin/python manage.py ensure_admin_user --username admin --password 'TU_PASSWORD_SEGURA' --email admin@tu-dominio.com
```

### Frontend React en Vercel

1. Crear otro proyecto en Vercel usando `frontend/` como Root Directory.
2. Configurar:

- `VITE_API_BASE_URL=https://tu-backend.vercel.app/api`

3. Deployar.

### Notas sobre Vercel

- En este stack, Render es mas simple para operar todo junto.
- Vercel funciona bien para el frontend.
- El backend Django en Vercel sirve para MVP, pero es menos comodo que Render para administracion y operaciones.
