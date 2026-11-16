# EntreCOL+ | ColPlus-Solutions

Sistema de gestión de información empresarial desarrollado como proyecto integrador, orientado a la administración, consulta y análisis de información relacionada con el personal, la nómina y el catálogo de entretenimiento de la organización.

## Descripción del proyecto

**EntreCOL+**, también identificado como **ColPlus-Solutions**, es una solución de software que busca centralizar y organizar diferentes procesos de información empresarial mediante una base de datos relacional y servicios de backend.

El sistema contempla la gestión de empleados, sus datos personales y laborales, las novedades que afectan su nómina y la información relacionada con sus afiliaciones de salud y pensión. Adicionalmente, incorpora un módulo de entretenimiento para administrar información de películas y libros, junto con herramientas de consulta, generación de reportes y análisis de datos.

El proyecto está estructurado para facilitar la integración entre sus componentes, mantener la integridad de la información y permitir que los datos puedan ser consultados y administrados desde una aplicación cliente mediante una API REST.

## Objetivos

### Objetivo general

Desarrollar un sistema de información empresarial que permita administrar y consultar de manera organizada los datos del personal, los procesos relacionados con nómina y novedades, y los registros de películas y libros, utilizando una base de datos relacional y servicios de backend.

### Objetivos específicos

- Centralizar la información de empleados, personas, cargos, dependencias y afiliaciones.
- Facilitar la administración de novedades y la consulta de información relacionada con nómina.
- Generar reportes estadísticos y comparativos para apoyar el análisis de la información empresarial.
- Administrar los registros de películas, libros, géneros, autores y participantes.
- Implementar servicios REST para las operaciones de consulta, creación, actualización y eliminación de información.
- Incorporar mecanismos de autenticación, auditoría y validación de datos.
- Permitir la carga incremental de información mediante archivos en diferentes formatos.

## Módulos principales

### 1. Gestión de personal y nómina

Este módulo contempla la administración de los empleados y su información laboral. Incluye operaciones CRUD para los registros de empleados y novedades, además de consultas que permiten obtener información individual y general.

Entre los reportes previstos se encuentran:

- Listado y cantidad total de empleados.
- Distribución de empleados por dependencia y cargo.
- Información personal y laboral de cada empleado.
- Datos de afiliación a EPS y fondos de pensión.
- Frecuencias y comparaciones de afiliaciones por dependencia.
- Consultas de novedades según rangos de fechas.
- Datos agrupados para generar gráficos estadísticos.

### 2. Gestión de películas y libros

Este módulo está orientado a la administración del catálogo de entretenimiento. Contempla operaciones CRUD para películas y libros, así como filtros y consultas que permitan analizar sus características.

Entre sus funcionalidades previstas se encuentran:

- Administración de películas y libros.
- Búsqueda mediante diferentes criterios.
- Consulta de películas según género y periodo.
- Clasificación de películas por cantidad de géneros asociados.
- Listados de libros según sus calificaciones.
- Reportes estadísticos de películas por género y libros por año de publicación.

### 3. Carga de archivos y procesamiento ETL

El sistema contempla un mecanismo de carga incremental de información mediante archivos `.xlsx`, `.dat` y `.json`.

Este proceso debe permitir recibir los archivos, ejecutar las funciones de procesamiento correspondientes y registrar un resumen de los datos procesados y los posibles errores encontrados.

### 4. Autenticación y auditoría

El proyecto contempla mecanismos de autenticación para controlar el acceso a los servicios privados de la aplicación.

También incorpora un componente de auditoría destinado a registrar acciones relevantes realizadas en el sistema, incluyendo operaciones administrativas y procesos de carga de archivos.

## Tecnologías y herramientas

Las tecnologías contempladas en el desarrollo del proyecto son:

| Tecnología | Utilización |
|---|---|
| Python | Lenguaje de programación del backend. |
| Flask / FastAPI | Framework para la construcción de servicios web, según la configuración del proyecto. |
| MySQL 8.0+ | Sistema gestor de base de datos relacional. |
| SQL | Consultas, procedimientos almacenados y operaciones sobre los datos. |
| API REST | Comunicación entre los servicios del backend y los componentes clientes. |
| JSON | Formato de intercambio de información. |
| Git y GitHub | Control de versiones y trabajo colaborativo. |
| Postman / Thunder Client | Pruebas y validación de los endpoints. |

## Base de datos

La base de datos está diseñada para organizar la información en diferentes entidades relacionadas mediante claves primarias y foráneas.

Entre las tablas contempladas se encuentran:

**Personal y nómina:**
- `personas`
- `empleados`
- `cargos`
- `dependencias`
- `eps`
- `arl`
- `fondos_pension`
- `afiliaciones_empleado`
- `nominas`
- `detalle_nomina`
- `novedades`
- `tipos_novedad`

**Entretenimiento:**
- `peliculas`
- `generos`
- `pelicula_generos`
- `artistas`
- `pelicula_participantes`
- `libros`
- `autores`
- `editoriales`
- `idiomas`

**Administración y control:**
- `usuarios`
- `auditoria`
- `archivos`
- `errores_carga`

La estructura permite relacionar los registros y realizar consultas que integren información de diferentes entidades.

## API REST

El backend contempla servicios REST para exponer las funcionalidades del sistema. Las operaciones principales utilizan los métodos HTTP:

| Método | Operación |
|---|---|
| GET | Consultar información y generar reportes. |
| POST | Registrar nuevos datos y ejecutar cargas. |
| PUT | Actualizar registros existentes. |
| DELETE | Eliminar registros. |

Los módulos de la API contemplados en el desarrollo son:

| Ruta base | Funcionalidad |
|---|---|
| `/api/auth` | Autenticación de usuarios. |
| `/api/nomina` | Gestión de empleados, novedades y reportes de nómina. |
| `/api/entretenimiento` | Administración y consulta de películas y libros. |
| `/api/etl` | Recepción y procesamiento de archivos. |

Las rutas específicas y los parámetros disponibles dependerán de la implementación de cada módulo.

## Estructura del proyecto

La guía de desarrollo establece los siguientes componentes principales del backend:

```text
entrcol-system/
│
├── backend/
│   ├── app.py
│   │
│   ├── database/
│   │   ├── connection.py
│   │   └── queries.py
│   │
│   ├── routes/
│   │   ├── auth.py
│   │   ├── nomina.py
│   │   ├── entretenimiento.py
│   │   └── etl.py
│   │
│   ├── services/
│   │   └── audit_logger.py
│   │
│   └── etl/
│
├── sql/
│   └── 03_stored_procedures.sql
│
└── README.md
```

Esta representación muestra los componentes contemplados en la guía y no pretende sustituir el árbol real de archivos del repositorio.

## Configuración y ejecución

Para trabajar con el proyecto se deben tener disponibles las herramientas y dependencias utilizadas por su implementación.

### Requisitos previos

- Python instalado.
- MySQL 8.0 o superior.
- Git instalado y configurado.
- Acceso al repositorio de GitHub.
- Dependencias del backend instaladas.
- Base de datos configurada y disponible.

### Obtener el proyecto

Clonar el repositorio:

```bash
git clone https://github.com/SixExpert277/TEORIA-DE-BASE-DE-DATOS-.git
```

Ingresar al directorio:

```bash
cd TEORIA-DE-BASE-DE-DATOS-
```

### Configurar la base de datos

1. Iniciar el servicio MySQL.
2. Crear o seleccionar la base de datos correspondiente.
3. Ejecutar los scripts SQL del proyecto en el orden requerido.
4. Configurar los parámetros de conexión en el componente correspondiente.
5. Verificar que las tablas y relaciones estén creadas correctamente.

### Preparar el backend

Crear un entorno virtual de Python:

```bash
python -m venv venv
```

Activarlo en Windows:

```bash
venv\Scripts\activate
```

Instalar las dependencias definidas por el proyecto:

```bash
pip install -r requirements.txt
```

El archivo de dependencias, los parámetros de conexión y el comando definitivo para iniciar el servidor deben corresponder a la configuración real del repositorio.

## Seguridad y buenas prácticas

Durante el desarrollo se consideran las siguientes prácticas:

- Utilizar consultas SQL parametrizadas para reducir el riesgo de inyección SQL.
- Proteger los endpoints privados mediante autenticación.
- Evitar almacenar contraseñas y claves API directamente en el código.
- Validar los datos recibidos antes de procesarlos.
- Registrar las operaciones relevantes mediante el sistema de auditoría.
- Mantener la integridad referencial de la base de datos.
- Manejar adecuadamente los errores y las respuestas HTTP.
- Revisar y probar los cambios antes de incorporarlos al proyecto.

## Control de versiones y colaboración

El proyecto utiliza Git y GitHub para organizar el trabajo colaborativo.

Los cambios deben desarrollarse en ramas independientes y posteriormente integrarse mediante Pull Requests.

No está permitido realizar cambios directamente sobre la rama `main`.

Para el desarrollo de los módulos de backend se propone utilizar la rama:

```bash
git checkout -b feat/backend-api-rest
```

Para registrar y enviar los cambios:

```bash
git status
git add .
git commit -m "feat: actualizar funcionalidades del sistema"
git push origin feat/backend-api-rest
```

Una vez publicados los cambios, se debe crear un Pull Request hacia `main` para su revisión y aprobación.

## Estado del proyecto

El desarrollo se organiza por módulos y entregables. Entre los componentes definidos para el backend se encuentran:

- **Issue #7:** API REST para nómina, novedades y consultas analíticas.
- **Issue #8:** API REST para películas, libros, procesamiento ETL y consultas de auditoría.

La definición de estos entregables establece el alcance funcional esperado. La disponibilidad y el funcionamiento de cada característica deben comprobarse en el código y mediante pruebas antes de considerarse finalizados.

## Contribución

Para contribuir al proyecto:

1. Obtener la versión más reciente del repositorio.
2. Crear una rama de trabajo independiente.
3. Realizar los cambios correspondientes.
4. Comprobar que el código funcione correctamente.
5. Registrar los cambios mediante commits descriptivos.
6. Publicar la rama en GitHub.
7. Crear un Pull Request para revisión.

Se debe mantener la organización del proyecto y respetar las convenciones establecidas para cada módulo.

## Equipo de desarrollo

Proyecto académico integrador desarrollado de manera colaborativa.

**Organización:** EntreCOL+ / ColPlus-Solutions  
**Repositorio:** [TEORIA-DE-BASE-DE-DATOS-](https://github.com/SixExpert277/TEORIA-DE-BASE-DE-DATOS-.git)

---

**EntreCOL+ | ColPlus-Solutions**  
Sistema de información empresarial para la gestión y consulta organizada de datos.
