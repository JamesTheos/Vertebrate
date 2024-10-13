document.addEventListener('DOMContentLoaded', function() {
    const steps = [
        { id: 'step1', name: 'Start Process', endpoint: '/workflow/start' },
        { id: 'step2', name: 'Select Scene', endpoints: { scene1: '/workflow/scene1', scene2: '/workflow/scene2' } },
        { id: 'step3', name: 'End Process', endpoint: '/workflow/end' },
        { id: 'restart', name: 'Restart Workflow', endpoint: '/workflow/restart' }
    ];

    let currentStep = parseInt(localStorage.getItem('currentStep')) || 0;

    function renderWorkflowSteps() {
        const workflowOverview = document.getElementById('workflow-overview');
        workflowOverview.innerHTML = '';
        steps.forEach((step, index) => {
            const stepElement = document.createElement('div');
            stepElement.classList.add('workflow-step');
            stepElement.id = step.id;
            stepElement.innerHTML = `
                <div class="step-content">
                    <h3>${step.name}</h3>
                    ${index === 1 ? `
                        <button onclick="nextStep('scene1')" id="scene1-btn" disabled>Scene 1</button>
                        <button onclick="nextStep('scene2')" id="scene2-btn" disabled>Scene 2</button>
                    ` : index === steps.length - 1 ? `
                        <button onclick="resetWorkflow()" id="${step.id}-btn" style="background-color: orange;" disabled>Restart</button>
                    ` : `
                        <button onclick="nextStep('${step.endpoint.split('/').pop()}')" id="${step.id}-btn" disabled>${step.name.split(' ')[0]}</button>
                    `}
                </div>
            `;
            workflowOverview.appendChild(stepElement);
        });
    }

    function updateWorkflowStep(stepIndex) {
        steps.forEach((step, index) => {
            const stepElement = document.getElementById(step.id);
            const buttons = stepElement.querySelectorAll('button');
            if (index < stepIndex) {
                stepElement.classList.add('completed');
                stepElement.classList.remove('active');
                buttons.forEach(button => button.disabled = true);
            } else if (index === stepIndex) {
                stepElement.classList.add('active');
                stepElement.classList.remove('completed');
                buttons.forEach(button => button.disabled = false);
            } else {
                stepElement.classList.remove('active', 'completed');
                buttons.forEach(button => button.disabled = true);
            }
        });

        const currentStepElement = document.getElementById('current-step');
        currentStepElement.innerHTML = `<h3>${steps[stepIndex].name}</h3>`;
    }

    window.nextStep = function(action) {
        if (currentStep < steps.length) {
            const step = steps[currentStep];
            let endpoint;
            if (step.endpoints) {
                endpoint = step.endpoints[action];
            } else {
                endpoint = step.endpoint;
            }
            fetch(endpoint, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateWorkflowStep(currentStep);
                        currentStep++;
                        localStorage.setItem('currentStep', currentStep);
                        if (currentStep < steps.length) {
                            updateWorkflowStep(currentStep);
                        }
                    }
                });
        }
    }

    window.resetWorkflow = function() {
        currentStep = 0;
        localStorage.setItem('currentStep', currentStep);
        renderWorkflowSteps();
        updateWorkflowStep(currentStep);
    }

    // Initialize the workflow steps and the first step
    renderWorkflowSteps();
    updateWorkflowStep(currentStep);
});