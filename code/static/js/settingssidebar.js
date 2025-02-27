document.addEventListener('DOMContentLoaded', function() {
    const button = document.querySelector('.settings');
    const settingsidebar = document.querySelector('.settings-sidebar');
    const sidebar = document.querySelector('.sidebar');

    button.addEventListener('click', function() {
        settingsidebar.classList.toggle('show-sidebar');
        sidebar.classList.toggle('show-sidebar');
        button.classList.toggle('active');
    });
});