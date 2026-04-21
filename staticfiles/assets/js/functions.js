var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl)
});

async function fetchRequest(url, params, csrftoken=csrf_token) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        body: JSON.stringify(params),
        credentials: 'same-origin',
    });

    if (resp.status !== 200) {
        return {
            result: false,
            mensaje: 'Error al realizar la petición'
        }
    }
    const data = await resp.json();
    return data;
}

function fetchRequest2(options) {
    return new Promise((resolve, reject) => {
        let url = options.url;
        headers = {'Content-Type': 'application/json', 'X-CSRFToken': csrf_token};
        if (options.headers) headers = Object.assign(headers, options.headers);
        let init = { method: options.method || 'GET', headers: headers };
        
        if (options.data) {
            if (init.method === 'GET') {
                url += '?' + new URLSearchParams(options.data).toString();
            } else {
                init.body = JSON.stringify(options.data);
                init.headers['Content-Type'] = 'application/json';
            }
        }
        if (options.timeout) init.timeout = options.timeout;

        fetch(url, init)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => Promise.reject(data));
                }
                return response.json();
            })
            .then(data => {
                if (options.success) {
                    options.success(data);
                } else {
                    resolve(data);
                }
            })
            .catch(error => {
                if (options.error) {
                    options.error(error);
                } else {
                    reject(error);
                }
            });
        });
}


// Main *****************************************
function ready(callback){
    // in case the document is already rendered
    if (document.readyState!='loading') callback();
    // modern browsers
    else if (document.addEventListener) document.addEventListener('DOMContentLoaded', callback);
    // IE <= 8
    else document.attachEvent('onreadystatechange', function(){
        if (document.readyState=='complete') callback();
    });
}

function bloqueoInterfaz() {
    // console.log("Bloqueando Interfaz");
    document.getElementById( 'loading-static' ).style.display = 'flex';
}
function desbloqueoInterfaz() {
    // console.log("Desbloqueando Interfaz");
    document.getElementById( 'loading-static' ).style.display = 'none';
}

function showErrorMessage(mensaje="Ha ocurrido un error inesperado en el servidor", titulo="Error") {
    document.getElementById('error-title').innerHTML = titulo;
    document.getElementById('error-message').innerHTML = mensaje;
    document.getElementById( 'error-static' ).style.display = 'flex';
}

function hideErrorMessage() {
    document.getElementById( 'error-static' ).style.display = 'none';
}

// const modalEdicion = document.getElementById('modalEdicion');

async function handleResponse(resp, data, modalName='modalEdicion') {
    if (resp.ok){
        const scripts = data.match(/<script[^>]*>([\s\S]*?)<\/script>/gi);
        const dataClean = data.replace(scripts, '');
        const modalEdicion = document.getElementById(modalName);
        modalEdicion.innerHTML = dataClean;
        const myModal = new bootstrap.Modal(modalEdicion);
        myModal.show();
        if(!scripts) return;
        const tagWhiteList = ["<img", "<iframe", "img.src", "iframe.src"];
        scripts.forEach(script => {
            const isInWhitelist = tagWhiteList.some(tag => script.includes(tag));
            if (script.includes('src') && !isInWhitelist) {
                try{
                    const src = script.match(/src="([^"]*)"/)[1];
                    const newScript = document.createElement('script');
                    newScript.src = src;
                    document.body.appendChild(newScript);
                    // loadedScripts.push(src);
                } catch (error) {
                    console.log('Error al cargar el script');
                    console.log(error);
                    console.log(script);
                }
            } else {
                try{
                    const scriptClean = script.replace(/<script[^>]*>|<\/script>/gi, '');
                    const newScript = document.createElement('script');
                    newScript.innerHTML = scriptClean;
                    modalEdicion.appendChild(newScript);
                    // loadedScripts.push(scriptClean);
                } catch (error){
                    console.log('Error al cargar el script');
                    console.log(error);
                    console.log(script);
                }
            }
        });
    } else{
        desbloqueoInterfaz();
    }
}
function resetFormModals() {
    // Elimina todos los event listeners previos para evitar duplicados
    const modals = document.getElementsByClassName('formmodal');
    for (let i = 0; i < modals.length; i++) {
        const modal = modals[i];
        // Clona el elemento para eliminar los event listeners existentes
        const newModal = modal.cloneNode(true);
        modal.parentNode.replaceChild(newModal, modal);
    }

    // Agrega los nuevos event listeners
    const updatedModals = document.getElementsByClassName('formmodal');
    for (let i = 0; i < updatedModals.length; i++) {
        updatedModals[i].addEventListener('click', async function(e) {
            try {
                e.preventDefault();
                const nhref = updatedModals[i].getAttribute('nhref');
                if (!nhref) return;
                bloqueoInterfaz();
                console.log('Cargando formulario desde servidor');
                const resp = await fetch(nhref);
                const data = await resp.text();
                const modal = document.querySelector('.modal.show');
                if (modal) {
                    const modalBS = bootstrap.Modal.getInstance(modal);
                    modalBS.hide();
                }
                handleResponse(resp, data);
                desbloqueoInterfaz();
            } catch {
                desbloqueoInterfaz();
            }
        });
    }
}

resetFormModals();


document.addEventListener("DOMContentLoaded", function() {
    const form = document.getElementById("mainForm");
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            submitModalForm1('mainForm');
        });
    }
});

const submitModalForm1 = async (formid = 'modalForm1', showError = true) => {
    const form = document.getElementById(formid);
    form.classList.add('was-validated');

    if (!form.checkValidity()) return;

    bloqueoInterfaz();

    try {
        const submitButton = event.submitter; // Captura el botón que disparó el envío
        const formData = new FormData(form); // Crear los datos del formulario

        if (submitButton && submitButton.name) {
            formData.append(submitButton.name, submitButton.value); // Agregar manualmente el botón submit
        }
        const resp = await fetch(form.getAttribute('action'), {
            method: 'POST',
            body: formData
        });

        // Manejo de errores del servidor (400, 500, etc.)
        if (!resp.ok) {
            desbloqueoInterfaz();
            if (resp.status === 400) {
                const errorData = await resp.json();
                if (errorData.forms) {
                    // Del formulario borra todos los elementos con clase field-error-message
                    form.querySelectorAll('.field-error-message').forEach(message => message.remove());
                    // Recorre los errores y los agrega al formulario
                    for (const [field, errors] of Object.entries(errorData.forms)) {
                        const fieldElement = form.querySelector(`[name="${field}"]`);
                        if (fieldElement) {
                            const parent = fieldElement.parentElement;
                            const divError = document.createElement('div');
                            divError.className = 'field-error-message text-danger';
                            if (parent) {
                                errors.forEach(error => {
                                    const message = document.createElement('small');
                                    message.className = 'text-danger fw-bold';
                                    message.innerText = '* ' + error;
                                    divError.appendChild(message);
                                });
                                parent.appendChild(divError);
                            }
                        }
                    }
                    form.classList.remove('was-validated');
                }
                if (showError) showErrorMessage(errorData.mensaje || 'Error de validación en el formulario');
            } else if (resp.status >= 500) {
                if (showError) showErrorMessage('Error interno del servidor. Por favor, inténtelo más tarde.');
            } else {
                if (showError) showErrorMessage(`Error inesperado (${resp.status}).`);
            }
            return;
        }

        const data = await resp.json();

        if (data.result === "ok") {
            if (data.redirected) {
                try {
                    const currentUrl = window.location.href;
                    if (currentUrl === data.url) {
                        location.reload();
                    } else {
                        location.href = data.url;
                    }
                } catch {
                    window.location.replace(data.url);
                }
            } else {
                const myModal = bootstrap.Modal.getInstance(document.getElementById('modalEdicion'));
                if (myModal) myModal.hide();
                desbloqueoInterfaz();
                return data;
            }
        } else if (data.result === "error") {
            if (data.form) {
                try {
                    const contentModalForm = document.getElementById('form-render-modal');
                    contentModalForm.innerHTML = data.form;
                    form.classList.remove('was-validated');
                } catch {
                    console.log('No se pudo actualizar el formulario');
                }
            }
            desbloqueoInterfaz();
            if (showError) showErrorMessage(data.mensaje || 'Ha ocurrido un error inesperado en el servidor');
            return data;
        }
    } catch (error) {
        // Manejo de excepciones (error de red u otros)
        desbloqueoInterfaz();
        if (showError) showErrorMessage('Error de red o servidor no disponible. Por favor, inténtelo más tarde.');
        console.error('Error inesperado:', error);
    }
};

// Bloquear la interfaz al enviar un formulario
// Get all form
const forms = document.getElementsByTagName('form');
for (let i = 0; i < forms.length; i++) {
    forms[i].addEventListener('submit', function(e) {
        bloqueoInterfaz();
    })
}





