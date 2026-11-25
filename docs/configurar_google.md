# Configurar el inicio de sesión con Google

Esto solo lo hace el equipo **una vez**. El resultado es el fichero `app/credentials.json`, que se entrega al profesor aparte (no se sube a GitHub).

Todo se hace con la cuenta del proyecto **proyectofinaldeeplearning@gmail.com** en <https://console.cloud.google.com>.

1. **Crear proyecto**: selector de proyectos → *Proyecto nuevo* → nombre `PropertyFix` → *Crear*.
2. **Activar las APIs** (menú *APIs y servicios → Biblioteca*; busca cada una y pulsa *Habilitar*):
   - Gmail API
   - Google Calendar API
   - Google Drive API
   - Google Sheets API
3. **Pantalla de consentimiento** (*APIs y servicios → Pantalla de consentimiento de OAuth*, o *Google Auth Platform*):
   - Tipo de usuario: **Externo**.
   - Nombre de la app: `PropertyFix`. Correo de asistencia y de contacto: la cuenta del proyecto.
   - Estado de publicación: **Prueba** (no hace falta verificar la app).
   - **Usuarios de prueba**: añade **solo** `proyectofinaldeeplearning@gmail.com`. Es la única cuenta autorizada a iniciar sesión con Google (decisión del equipo): el profesor prueba la app con ella. La web funciona con la cuenta que inicia sesión, así que bastaría con añadir otra cuenta aquí para que trabajase con su propio Gmail, Calendar y Drive.
4. **Crear el cliente OAuth** (*Credenciales → Crear credenciales → ID de cliente de OAuth*):
   - Tipo: **Aplicación web**. Nombre: `PropertyFix local`.
   - *URI de redireccionamiento autorizados*: `http://localhost:8000/auth/callback`
   - *Crear* → **Descargar JSON**.
5. Renombra el fichero descargado a **`credentials.json`** y colócalo en la carpeta **`app/`**.
6. Reinicia la app. En la pantalla de acceso aparecerá **«Iniciar sesión con Google»**.

## Al iniciar sesión por primera vez

Google mostrará el aviso *«Google no ha verificado esta aplicación»*, porque está en modo prueba. Pulsa **Continuar**, marca todos los permisos y acepta.

| Permiso | Para qué lo usa PropertyFix |
|---|---|
| Enviar correo en tu nombre (`gmail.send`) | Confirmación de la reserva y orden de trabajo |
| Ver tus correos (`gmail.readonly`) | Tarea en bucle: detectar incidencias que llegan por email |
| Ver y editar eventos (`calendar.events`) y ver disponibilidad (`calendar.freebusy`) | Buscar hueco y crear la cita |
| Ver y gestionar los archivos de Drive que crea esta app (`drive.file`) | Documento del presupuesto y hoja de registro (no ve el resto de tu Drive) |

El token se guarda solo en `app/runtime/tokens/` (excluido de GitHub). En modo prueba Google lo caduca a los 7 días: basta con volver a iniciar sesión.
