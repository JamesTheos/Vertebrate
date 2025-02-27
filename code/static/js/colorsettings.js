document.addEventListener('DOMContentLoaded', function() {
    const textColorPicker = document.getElementById('textColor');
    const bgColorPicker = document.getElementById('bgColor');
    const sbColorPicker = document.getElementById('sbColor');
    const sbTColorPicker = document.getElementById('sbTColor');
    const saveButton = document.getElementById('saveButton');
    const resetButton = document.getElementById('resetButton');

    // Set default colors
    const defaultColors = {
        textColor: '#000000',
        bgColor: '#ffffff',
        sbColor: '#ffffff',
        sbTColor: '#ffffff'
    };

    // Function to apply colors
    function applyColors(colors) {
        textColorPicker.value = colors.textColor;
        bgColorPicker.value = colors.bgColor;
        sbColorPicker.value = colors.sbColor;
        sbTColorPicker.value = colors.sbTColor;

        document.documentElement.style.setProperty('--text-color', colors.textColor);
        document.documentElement.style.setProperty('--content-background', colors.bgColor);
        document.documentElement.style.setProperty('--sidebar-background', colors.sbColor);
        document.documentElement.style.setProperty('--header-background', colors.sbColor);
        document.documentElement.style.setProperty('--button-background', colors.sbColor);
        document.documentElement.style.setProperty('--background-color', colors.sbColor);
        document.documentElement.style.setProperty('--button-text-color', colors.sbTColor);
        document.documentElement.style.setProperty('--sidebar-text-color', colors.sbTColor);
        document.documentElement.style.setProperty('--header-text-color', colors.sbTColor);
    }

    // Load colors from local storage
    const localColors = {
        textColor: localStorage.getItem('textColor') || defaultColors.textColor,
        bgColor: localStorage.getItem('bgColor') || defaultColors.bgColor,
        sbColor: localStorage.getItem('sbColor') || defaultColors.sbColor,
        sbTColor: localStorage.getItem('sbTColor') || defaultColors.sbTColor
    };
    applyColors(localColors);

    // Load colors from server
    fetch('/api/colors')
        .then(response => response.json())
        .then(colors => {
            applyColors(colors);
        });

    // Save colors to server and local storage
    saveButton.addEventListener('click', function() {
        const colors = {
            textColor: textColorPicker.value,
            bgColor: bgColorPicker.value,
            sbColor: sbColorPicker.value,
            sbTColor: sbTColorPicker.value
        };

        fetch('/api/colors', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(colors)
        })
        .then(response => response.json())
        .then(() => {
            applyColors(colors);
            localStorage.setItem('textColor', colors.textColor);
            localStorage.setItem('bgColor', colors.bgColor);
            localStorage.setItem('sbColor', colors.sbColor);
            localStorage.setItem('sbTColor', colors.sbTColor);
        });
    });

    // Reset colors to default
    resetButton.addEventListener('click', function() {
        applyColors(defaultColors);

        fetch('/api/colors/reset', {
            method: 'POST'
        });

        localStorage.removeItem('textColor');
        localStorage.removeItem('bgColor');
        localStorage.removeItem('sbColor');
        localStorage.removeItem('sbTColor');
    });
});