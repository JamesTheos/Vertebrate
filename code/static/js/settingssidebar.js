document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.querySelector('#sidebar');
    const settingsSidebar = document.querySelector('#settings-sidebar');
    const activeSidebar = localStorage.getItem('activeSidebar');

    
    if (activeSidebar === 'sidebar') {
        sidebar.classList.add('show-sidebar');
    } else if (activeSidebar === 'settingsSidebar') {
        settingsSidebar.classList.add('show-sidebar');
    } else {
        sidebar.classList.add('show-sidebar');
    }

    
    function toggleSidebar() {
        if (sidebar.classList.contains('show-sidebar')) {
            sidebar.classList.remove('show-sidebar');
            settingsSidebar.classList.add('show-sidebar');
            localStorage.setItem('activeSidebar', 'settingsSidebar');
        } else {
            sidebar.classList.add('show-sidebar');
            settingsSidebar.classList.remove('show-sidebar');
            localStorage.setItem('activeSidebar', 'sidebar');
        }
    }

    // Beispiel für das Hinzufügen eines Event-Listeners zum Umschalten der Sidebar
    const toggleButton = document.querySelector('.settings');
    if (toggleButton) {
        toggleButton.addEventListener('click', toggleSidebar);
    }
});
