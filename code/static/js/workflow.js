document.addEventListener('DOMContentLoaded', function() {
    const workflowContainer = document.getElementById('workflow-container');
    const workflowOverview = document.getElementById('workflow-overview');

    function createButton(text, onClick) {
        const button = document.createElement('button');
        button.textContent = text;
        button.className = 'button';
        button.onclick = onClick;
        return button;
    }

    function updateWorkflowOverview(step) {
        workflowOverview.innerHTML = `<p>${step}</p>`;
    }

    function step1() {
        workflowContainer.innerHTML = '<p>Confirm starting the process</p>';
        workflowContainer.appendChild(createButton('Yes', () => {
            fetch('/workflow/start', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateWorkflowOverview('Step 1: Process Started');
                        step2();
                    }
                });
        }));
    }

    function step2() {
        workflowContainer.innerHTML = '<p>Which scene is needed?</p>';
        workflowContainer.appendChild(createButton('Scene1', () => {
            fetch('/workflow/scene1', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateWorkflowOverview('Step 2: Scene 1 Selected');
                        step3();
                    }
                });
        }));
        workflowContainer.appendChild(createButton('Scene2', () => {
            fetch('/workflow/scene2', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateWorkflowOverview('Step 2: Scene 2 Selected');
                        step3();
                    }
                });
        }));
    }

    function step3() {
        workflowContainer.innerHTML = '<p>End the process</p>';
        workflowContainer.appendChild(createButton('Yes', () => {
            fetch('/workflow/end', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateWorkflowOverview('Step 3: Process Ended');
                        workflowContainer.innerHTML = '<p>Process ended successfully.</p>';
                    }
                });
        }));
    }

    // Start the workflow
    step1();
});