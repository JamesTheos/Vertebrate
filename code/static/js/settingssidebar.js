document.addEventListener('DOMContentLoaded', function() {
    const button = document.querySelector('.settings');
    const settingsidebar = document.querySelector('.settings-sidebar');
    const sidebar = document.querySelector('.sidebar');

    // Restore sidebar visibility from localStorage
    if (localStorage.getItem('settingsidebarVisible') === 'true') {
        settingsidebar.classList.add('show-sidebar');
        sidebar.classList.remove('show-sidebar');
        button.classList.add('active');
    }

    button.addEventListener('click', function() {
        const isVisible = settingsidebar.classList.toggle('show-sidebar');
        sidebar.classList.toggle('show-sidebar');
        button.classList.toggle('active');

        // Save sidebar visibility to localStorage
        localStorage.setItem('settingsidebarVisible', isVisible);
    });
});