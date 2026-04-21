const widthNav = 370;
const widthResize = 992;
let navIsOpen = false;

function openNav1() {
    document.getElementById("sidebar-main").style.width = widthNav + "px";
    document.getElementById("main").style.marginLeft = widthNav + "px";
    navIsOpen = true;
}

function openNav() {
    document.getElementById("sidebar-main").style.width = widthNav + "px";
    navIsOpen = true;
}

function changeNav() {
    if (navIsOpen) {
        closeNav();
    } else {
        openNav();
    }
}

function closeNav() {
    document.getElementById("sidebar-main").style.width = "0";
    document.getElementById("main").style.marginLeft= "0";
    navIsOpen = false;
}

window.addEventListener("resize", function() {
    if (window.innerWidth < widthResize) {
        closeNav();
        document.getElementById("btn-change-sidebar").style.display = "block";
    } else{
        openNav1();
        document.getElementById("btn-change-sidebar").style.display = "none";
    }
});


