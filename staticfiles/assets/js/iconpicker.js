const jsonPath = '/static/assets/icons/icons.json'; // Ruta del archivo JSON
const iconsPerPage = 54; // Cantidad de iconos por página
let allIcons = []; // Lista completa de iconos
let filteredIcons = []; // Lista filtrada para búsqueda
let currentPage = 1; // Página actual
let iconsLoaded = false; // Indicador de si los iconos ya se cargaron

const iconListContainer = document.getElementById('icon-list');
const iconSearchInput = document.getElementById('iconSearch');
const prevPageButton = document.getElementById('prevPage');
const nextPageButton = document.getElementById('nextPage');
const paginationInfo = document.getElementById('paginationInfo');

// Función para cargar y procesar el archivo JSON
function loadIcons() {
    if (iconsLoaded) return; // Evitar cargar nuevamente si ya se cargaron

    fetch(jsonPath)
        .then(response => response.json())
        .then(data => {
            // Convertir los iconos a una lista
            Object.entries(data).forEach(([iconName, details]) => {
                const styles = details.styles || [];
                styles.forEach(style => {
                    allIcons.push(`fa-${style} fa-${iconName}`);
                });
            });
            filteredIcons = allIcons; // Inicialmente todos los iconos están disponibles
            iconsLoaded = true; // Marcar como cargados
            renderIcons(); // Renderizar la primera página
        })
        .catch(error => console.error('Error al cargar los iconos:', error));
}

// Renderizar iconos en la página actual
function renderIcons() {
    const startIndex = (currentPage - 1) * iconsPerPage;
    const endIndex = startIndex + iconsPerPage;
    const iconsToShow = filteredIcons.slice(startIndex, endIndex);

    iconListContainer.innerHTML = ''; // Limpiar contenido previo
    iconsToShow.forEach(iconClass => {
        const iconName = iconClass.split(' ')[1].replace('fa-', ''); // Obtener el nombre del icono
        const iconDiv = document.createElement('div');
        iconDiv.className = 'col-2 text-center mb-3';
        iconDiv.innerHTML = `
            <i class="${iconClass} fa-2x" style="cursor: pointer;" onclick="selectIcon('${iconClass}')"></i>
            <div class="icon-name" style="font-size: 0.7rem; color: #555;">${iconName}</div>
        `;
        iconListContainer.appendChild(iconDiv);
    });

    // Actualizar controles de paginación
    paginationInfo.textContent = `Página ${currentPage} de ${Math.ceil(filteredIcons.length / iconsPerPage)}`;
    prevPageButton.disabled = currentPage === 1;
    nextPageButton.disabled = currentPage === Math.ceil(filteredIcons.length / iconsPerPage);
}

// Seleccionar un icono
function selectIcon(iconClass) {
    // Actualiza el botón y el input relacionado
    const currentInput = window.currentInput; // El input relacionado con el botón
    const currentButton = currentInput.nextElementSibling;

    currentInput.value = iconClass; // Actualiza el valor del input
    currentButton.innerHTML = `<i class="${iconClass}"></i> Seleccionado`; // Muestra el icono en el botón

    // Cierra el modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('iconModal'));
    modal.hide();
}

document.addEventListener('DOMContentLoaded', () => {
    // Buscar iconos por nombre
    iconSearchInput.addEventListener('input', () => {
        const query = iconSearchInput.value.toLowerCase();
        filteredIcons = allIcons.filter(icon => icon.includes(query));
        currentPage = 1; // Reiniciar a la primera página de resultados
        renderIcons();
    });

    // Funciones de cambio de página
    prevPageButton.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderIcons();
        }
    });

    nextPageButton.addEventListener('click', () => {
        if (currentPage < Math.ceil(filteredIcons.length / iconsPerPage)) {
            currentPage++;
            renderIcons();
        }
    });

    document.querySelectorAll('.iconpicker').forEach(input => {
        // Crear un contenedor para el icono y el botón
        const wrapper = document.createElement('div');
        wrapper.className = 'd-flex align-items-center'; // Contenedor con flexbox para alineación
    
        // Crear el elemento para mostrar el icono
        const iconDisplay = document.createElement('span');
        iconDisplay.className = 'me-2'; // Margen derecho para separar del botón
    
        // Si el input ya tiene un valor, mostrar el icono
        if (input.value) {
            iconDisplay.innerHTML = `<i class="${input.value} fa-2x"></i>`;
        }
    
        // Crear el botón para seleccionar el icono
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-xs btn-info iconpicker-btn';
        button.innerHTML = '<i class="fa fa-search me-2"></i>Seleccionar icono';
    
        // Al hacer clic en el botón, abrir el modal
        button.addEventListener('click', () => {
            window.currentInput = input; // Guardar el input relacionado
            window.currentIconDisplay = iconDisplay; // Guardar el icono relacionado
            const modal = new bootstrap.Modal(document.getElementById('iconModal'));
            modal.show();
        });
    
        // Ocultar el input y agregar el icono y el botón al contenedor
        input.style.display = 'none';
        wrapper.appendChild(iconDisplay);
        wrapper.appendChild(button);
        input.parentNode.insertBefore(wrapper, input.nextSibling);
    });
    
    // Seleccionar un icono (expuesta globalmente)
    window.selectIcon = function (iconClass) {
        const currentInput = window.currentInput; // El input relacionado
        const currentIconDisplay = window.currentIconDisplay; // El icono relacionado
    
        // Actualizar el valor del input y el icono mostrado
        currentInput.value = iconClass;
        currentIconDisplay.innerHTML = `<i class="${iconClass} fa-2x"></i>`;
    
        // Cierra el modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('iconModal'));
        modal.hide();
    };

    // Detectar cuando se abre el modal
    const iconModal = document.getElementById('iconModal');
    iconModal.addEventListener('shown.bs.modal', loadIcons); // Cargar iconos al abrir el modal
});

