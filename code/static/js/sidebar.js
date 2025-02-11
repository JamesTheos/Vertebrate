const menu = document.querySelector('.menu-content');
const menuItems = document.querySelectorAll('.submenu-item');
const submenutitles = document.querySelectorAll('.submenu .menu-topic');

menuItems.forEach((item, index) => {	
    item.addEventListener('click', () => {
        menu.classList.add('submenu-active');
        item.classList.add('show-submenu');
        menuItems.forEach((it2, ind2) => {
            if (index !== ind2) {
                it2.classList.remove('show-submenu');
            }
        })
    });
});


submenutitles.forEach((title) => {
    title.addEventListener('click', () => {
        menu.classList.remove('submenu-active');
    });

});


