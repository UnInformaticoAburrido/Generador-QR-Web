# Generador QR

Aplicación web en español para convertir una cadena de texto en un único código QR, previsualizarlo y descargarlo en **PNG o SVG**. Conserva espacios, saltos de línea, ceros iniciales, acentos y emojis. No almacena el contenido ni utiliza servicios externos para generar los códigos.

## Iniciar con Docker Compose

Requisitos: Docker Engine en ejecución, acceso al daemon y Docker Compose v2.20 o posterior. La primera construcción necesita Internet para descargar imágenes y dependencias.

Desde este directorio:

```bash
docker compose up --build -d --wait
```

Abre **http://localhost** (puerto 80). El comando espera a que los dos servicios estén saludables.

Docker publica la web en el puerto 80 de las interfaces del ordenador. Desde otro dispositivo de la misma red, accede a `http://IP_LOCAL_DEL_ORDENADOR`, siempre que el cortafuegos permita las conexiones entrantes a ese puerto.

La página principal contiene un campo de texto y el botón **Subir**. Escribe el contenido y pulsa ese botón: el QR se genera y aparece en la misma página, con opciones para descargarlo en PNG y SVG.

Para cambiar el puerto:

```bash
PUERTO_WEB=8091 docker compose up --build -d --wait
```

También puedes copiar `.env.example` a `.env` y ajustar `PUERTO_WEB`.

El puerto predeterminado es **80**. Si conservas `PUERTO_WEB=8080` o `PUERTO_WEB=8090` en un `.env` anterior o en tu terminal, actualízalo a `80` o utiliza este comando para aplicar el puerto nuevo y recrear el servicio web:

```bash
PUERTO_WEB=80 docker compose up --build -d --wait
```

Si Docker indica `port is already allocated` para el puerto 80, otro servicio lo está utilizando. Para mantener esta web en el puerto 80 tendrás que liberar ese puerto o configurar el servidor que ya lo ocupa para dirigir las peticiones a esta aplicación.

```bash
docker compose ps            # Estado de los servicios
docker compose logs -f       # Registros (Ctrl+C deja los servicios funcionando)
docker compose down          # Detener y eliminar los contenedores de este proyecto
```

Si aparece `permission denied` al acceder a `/var/run/docker.sock`, utiliza una cuenta con acceso al daemon o ejecuta el comando con `sudo` en tu equipo. Si Docker no está en ejecución, arráncalo antes.

## Servicios y directorios

```text
.
├── docker-compose.yml
├── .env.example
└── Codigo/
    ├── api/
    │   ├── Dockerfile
    │   ├── app.py
    │   ├── requirements.txt
    │   ├── requirements-test.txt
    │   └── test_app.py
    └── web/
        ├── Dockerfile
        ├── nginx.conf
        └── public/
            ├── index.html
            ├── styles.css
            └── app.js
```

| Servicio | Función | Montaje desde `Codigo` |
| --- | --- | --- |
| `api` | Flask + Gunicorn + Segno, puerto interno 8000 | `./Codigo/api:/app:ro` |
| `web` | Nginx: interfaz y proxy `/api/`, puerto público 80 | `./Codigo/web/public:/usr/share/nginx/html:ro` y configuración Nginx |

Las imágenes se construyen desde los directorios de cada servicio. Los montajes de solo lectura hacen que Docker consuma el código local. No hace falta base de datos: los QR se generan en memoria.

### Orden y disponibilidad

1. Compose arranca `api` con dos procesos Gunicorn.
2. Su `healthcheck` consulta `/api/health` hasta recibir una respuesta correcta.
3. `web` depende de `api` con `condition: service_healthy`: espera a que termine esa comprobación antes de arrancar.
4. El `healthcheck` de `web` verifica la página y la API a través del proxy. `--wait` espera también esta comprobación.

La dependencia usa `restart: true` para reiniciar la web en operaciones explícitas de Compose sobre la API. Nginx vuelve a resolver el nombre `api` mediante el DNS de Docker, por lo que admite cambios de IP tras recrear el contenedor. Ambos servicios tienen `restart: unless-stopped` para reiniciar procesos que terminan inesperadamente.

`depends_on` coordina el arranque gestionado por Compose. Durante una caída posterior, la web muestra un error recuperable y su estado de salud refleja el fallo; un estado `unhealthy` por sí solo no reinicia un contenedor.

Los cambios en HTML, CSS y JavaScript se leen directamente del montaje (recarga el navegador). Después de modificar Python, ejecuta `docker compose restart api`; después de cambiar dependencias, Dockerfiles o configuración, ejecuta `docker compose up --build -d --wait` (si solo cambia `nginx.conf`, usa `docker compose restart web`).

## Capacidad del QR

Se generan QR estándar, versiones 1 a 40, con corrección de errores **L** para priorizar capacidad. La librería elige automáticamente versión y modo según el contenido. No hay un `maxlength` arbitrario en el formulario: el servidor intenta codificar y devuelve HTTP 422 si el texto no cabe.

| Contenido | Máximo por QR con esta configuración |
| --- | --- |
| Solo dígitos `0–9` | 7089 dígitos |
| Alfabeto QR: `A–Z`, `0–9`, espacio y `$%*+-./:` | 4296 caracteres |
| Texto ASCII en modo byte (por ejemplo, minúsculas) | 2953 bytes |
| Texto no ASCII | 2952 bytes UTF-8, con declaración ECI de codificación |

Un carácter Unicode puede ocupar varios bytes: por ejemplo, caben 1476 letras `é` o 738 emojis `😀`. La mezcla de caracteres puede cambiar el modo de codificación; los máximos numérico y alfanumérico solo aplican cuando todo el contenido pertenece a ese modo. El contador indica caracteres Unicode y bytes UTF-8, no un porcentaje de capacidad.

Los PNG tienen ocho píxeles por módulo; ambos formatos incluyen un margen blanco de cuatro módulos. Para QR muy densos, descarga el archivo y muéstralo o imprímelo con suficiente tamaño. Los lectores deben soportar UTF-8/ECI para interpretar correctamente todo el texto Unicode.

El límite HTTP de 128 KiB admite cualquier contenido que quepa en un QR, incluso con escapes JSON; rechaza peticiones excesivas con HTTP 413. El servidor no recorta ni transforma el texto recibido. El navegador normaliza los saltos de línea de su textarea a `\n`.

## API

```bash
curl http://localhost/api/health
curl -X POST http://localhost/api/qr \
  -H 'Content-Type: application/json' \
  -d '{"text":"¡Hola, mundo!"}'
```

`POST /api/qr` devuelve `png` y `svg` como URL de datos, junto con `version`, `mode`, `error_correction`, `characters`, `bytes` y `modules`. Los errores tienen el campo `error`: 400 para texto ausente, vacío o inválido; 415 para contenido que no es JSON; 422 para exceso de capacidad; 413 para una petición demasiado grande. La API interna no publica un puerto en el host.

## Pruebas

Con Docker (instala las dependencias de prueba en un contenedor temporal):

```bash
docker compose run --rm --no-deps --user root api sh -c \
  'pip install --no-cache-dir -r requirements-test.txt && python -m unittest -v'
```

O con Python 3.13 o posterior:

```bash
python3 -m venv .venv
.venv/bin/pip install -r Codigo/api/requirements-test.txt
.venv/bin/python -m unittest discover -s Codigo/api -v
```

Las pruebas comprueban errores de entrada, capacidad exacta y exceso en los modos numérico, alfanumérico y byte, límites Unicode y conservación del texto. Los PNG se leen con ZXing, un decodificador independiente de la librería generadora.

## Referencias

- [Docker Compose: orden de arranque y `service_healthy`](https://docs.docker.com/compose/how-tos/startup-order/).
- [Segno: codificación, ECI y detección de exceso de capacidad](https://segno.readthedocs.io/en/latest/api.html).
