document.addEventListener('DOMContentLoaded', function() {
    const textColorPicker = document.getElementById('textColor');
    const bgColorPicker = document.getElementById('bgColor');
    const sbColorPicker = document.getElementById('sbColor');
    const sbTColorPicker = document.getElementById('sbTColor');
    const saveButton = document.getElementById('saveButton');
    const resetButton = document.getElementById('resetButton');

    setColors();
    
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
            location.reload();
        });
    });

    function setColors() {
        fetch('/api/colors')
            .then(response => response.json())
            .then(colors => {
                textColorPicker.value = colors.textColor;
                bgColorPicker.value = colors.bgColor;
                sbColorPicker.value = colors.sbColor;
                sbTColorPicker.value = colors.sbTColor;
            });
    }

    

    // Reset colors to default
    resetButton.addEventListener('click', function() {
        fetch('/api/colors/reset', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(() => {
            location.reload();
        });
        
    });
});