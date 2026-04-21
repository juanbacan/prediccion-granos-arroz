function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const sidebarMarginLeft = parseInt(window.getComputedStyle(sidebar).marginLeft);
    const width = window.innerWidth;
    const content = document.querySelector('.content');

    if (sidebarMarginLeft === 0) {
        sidebar.style.marginLeft = '-350px';
        content.style.display = 'flex';
        // Poner el icono de menu
        document.querySelector('#btn-change-sidebar').innerHTML = '<i class="fas fa-bars"></i>';

        // Del boton con id btn-toggle-sidebar-content cambiar el innerHTML a <i class="fa-solid fa-chevron-right"></i>
        document.querySelector('#btn-toggle-sidebar-content').innerHTML = '<i class="fas fa-chevron-right"></i>';
    } else {
        sidebar.style.marginLeft = '0';
        if (width < 600) {
            content.style.display = 'none';
        }
        // Poner el icono de cerrar
        document.querySelector('#btn-change-sidebar').innerHTML = '<i class="fas fa-times"></i>';

        // Del boton con id btn-toggle-sidebar-content cambiar el innerHTML a <i class="fa-solid fa-chevron-left"></i>
        document.querySelector('#btn-toggle-sidebar-content').innerHTML = '<i class="fas fa-chevron-left"></i>';
    }
}

window.addEventListener('resize', function() {
    const sidebar = document.querySelector('.sidebar');
    const width = window.innerWidth;

    if (width > 992) {
        sidebar.style.marginLeft = '0';

        // Mostrar los botones con clase btn-toggle-sidebar
        let btns = document.querySelectorAll('.btn-toggle-sidebar');
        btns.forEach(btn => {
            btn.style.display = 'none';
        });

        let btnsContent = document.querySelectorAll('.btn-sidebar');
        btnsContent.forEach(btn => {
            btn.style.display = 'block';
        });

    } else {
        sidebar.style.marginLeft = '-350px';
        // Ocultar los botones con clase btn-toggle-sidebar
        let btns = document.querySelectorAll('.btn-toggle-sidebar');
        btns.forEach(btn => {
            btn.style.display = 'block';
        });

        let btnsContent = document.querySelectorAll('.btn-sidebar');
        btnsContent.forEach(btn => {
            btn.style.display = 'none';
        });
    }
});


document.addEventListener("DOMContentLoaded", function() {
    // Encuentra todos los acordeones
    let accordions = document.querySelectorAll(".accordion-collapse.show");

    // Si hay algún acordeón abierto, desplazarse hacia él
    if (accordions.length > 0) {
        // Tomar el primer acordeón que esté abierto
        let activeAccordion = accordions[0];
        // Encontrar el elemento con la clase 'active' dentro del acordeón
        let activeItem = activeAccordion.querySelector(".list-group-item.active");

        if (activeItem) {
            // Desplazarse suavemente al elemento activo dentro del acordeón
            activeItem.scrollIntoView({
                behavior: 'smooth',
                block: 'center' // Ajusta según dónde quieras que quede el elemento
            });
        }
    }
});