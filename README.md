# Sistema de Gestión de Negocios y Ventas

## Descripción

Este proyecto es un sistema de gestión diseñado para administrar negocios y sus operaciones relacionadas con ventas. Permite a los usuarios registrar negocios, gestionar productos, realizar ventas y generar reportes mensuales. El sistema está construido utilizando **Flask** como framework backend, **Flowbite** y **Tailwind CSS** para el diseño frontend, y una base de datos relacional para almacenar la información.

## Características Principales

- **Registro y Gestión de Negocios:**
  - Agregar, editar y ver detalles de negocios.
  - Subir logos para cada negocio.
- **Gestión de Productos:**
  - Agregar, editar y eliminar productos.
  - Asociar productos con negocios específicos.
- **Sistema de Ventas:**
  - Crear órdenes de venta.
  - Agregar productos a las ventas.
  - Ver detalles de las ventas realizadas.
- **Reportes Mensuales:**
  - Generar reportes de ventas por día y por producto.
  - Exportar reportes a formato Excel.
  Nota: Se añadió un endpoint API para obtener el consumo de materias primas derivado de las ventas de un mes.

  - Ruta: POST /business/<business_id>/report/inventory-consumption
  - Parámetros: month (form o JSON) en formato YYYY-MM
  - Respuesta: JSON con la estructura {"month": "YYYY-MM", "consumption": {inventory_item_id: {name, unit, total_consumed, product_usages}}}

  Ejemplo con curl (fish shell):

  ```fish
  curl -X POST -F "month=2025-09" http://localhost:5000/business/1/report/inventory-consumption
  ```

  O como JSON:

  ```fish
  curl -X POST -H "Content-Type: application/json" -d '{"month":"2025-09"}' http://localhost:5000/business/1/report/inventory-consumption
  ```
- **Diseño Moderno:**
  - Interfaz responsiva y compatible con modo oscuro gracias a **Flowbite** y **Tailwind CSS**.

## Tecnologías Utilizadas

- **Backend:** Flask (Python)
- **Frontend:** Flowbite, Tailwind CSS, Jinja2
- **Base de Datos:** SQLite (u otra base de datos relacional compatible)
- **Exportación de Datos:** Pandas (para exportar a Excel)

## Instalación

### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/tu-proyecto.git
cd tu-proyecto
```

### 2. Crear y Activar el Entorno Conda del Proyecto

```bash
conda create -y -n bookkeeply python=3.12
conda activate bookkeeply
```

### 3. Instalar Dependencias de Python

```bash
pip install -r requirements.txt
```

### 4. Configurar la Base de Datos

```bash
flask db init
flask db migrate
flask db upgrade
```

### 5. Instalar Tailwind CSS y Flowbite

**a. Instalar Node.js y npm**

Asegúrate de tener instalado Node.js y npm en tu sistema. Puedes verificar su instalación ejecutando:

```bash
node -v
npm -v
```

Si no están instalados, descárgalos desde Node.js.

**b. Inicializar npm y Configurar Tailwind CSS**
En la raíz del proyecto, inicializa npm:

```bash
npm init -y
```

Instala Tailwind CSS y sus dependencias:

```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init
```

Crea un archivo `tailwind.config.js` con la siguiente configuración:

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/templates/**/*.html', // Ajusta esta ruta según tus plantillas Jinja2
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

Crea un archivo `src/input.css` con el siguiente contenido:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

Compila Tailwind CSS:

```bash
npx tailwindcss -i ./app/static/css/tailwind.css -o ./app/static/css/styles.css --watch
```

c. Instalar Flowbite

Instala Flowbite como dependencia:

```bash
npm install flowbite
```

Incluye Flowbite en tu archivo `tailwind.config.js`:

```javascript
module.exports = {
  content: [
    './app/templates/**/*.html',
    './node_modules/flowbite/**/*.js', // Agrega Flowbite al contenido
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('flowbite/plugin'), // Agrega el plugin de Flowbite
  ],
}
```

Importa los scripts de Flowbite en tu archivo HTML principal (`base.html`):

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/flowbite/2.2.0/flowbite.min.js"></script>
```

### 6. Ejecutar la Aplicación

```bash
flask run
```

La aplicación estará disponible en `<http://127.0.1:5000>`.

## Estructura del Proyecto

```
tu-proyecto/
├── app/
│   ├── **init**.py          # Inicialización de la aplicación Flask
│   ├── models.py            # Definición de modelos de la base de datos
│   ├── routes.py            # Rutas y lógica del backend
│   ├── forms.py             # Formularios de WTForms
│   ├── static/              # Archivos estáticos (CSS, JS, imágenes)
│   └── templates/           # Plantillas HTML
├── migrations/              # Migraciones de la base de datos
├── config.py                # Configuración de la aplicación
├── requirements.txt         # Dependencias del proyecto
├── package.json             # Dependencias de Node.js
└── README.md                # Este archivo
```

## Uso del Sistema

**1.  Registro de Negocios**

   Accede a la página principal (`/business`) para agregar nuevos negocios.
   Proporciona un nombre, descripción y logo (opcional).

**2. Gestión de Productos**

   Desde el dashboard de un negocio, agrega productos con nombre y precio.
   Edita o elimina productos según sea necesario.

**3. Realizar Ventas**

   Crea nuevas órdenes de venta y agrega productos a ellas.
   Visualiza los detalles de cada venta.

**4. Generar Reportes**

   Selecciona un mes para generar un reporte de ventas.
   Exporta los datos a Excel para análisis externo.

## Contribuciones

Si deseas contribuir al proyecto, sigue estos pasos:

Haz un fork del repositorio.
Crea una nueva rama (```git checkout -b feature/nueva-funcionalidad```).
Realiza tus cambios y haz commit (```git commit -m "Añadir nueva funcionalidad"```).
Sube tus cambios (```git push origin feature/nueva-funcionalidad```).
Abre un Pull Request.

## Licencia

Este proyecto está bajo la licencia MIT. Consulta el archivo `LICENSE` para más detalles.

## Contacto

Si tienes preguntas o sugerencias, no dudes en contactarme:

- Nombre: Tu Nombre
- Correo Electrónico: <jr.avalug@gmail.com.com>
- GitHub: <https://github.com/jravalug>

## Notas Adicionales

- Si necesitas personalizar aún más Tailwind CSS o Flowbite , puedes consultar la documentación oficial:

   -- Tailwind CSS
   -- Flowbite
