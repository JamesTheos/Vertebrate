document.addEventListener('DOMContentLoaded', function() {
    const steps = [
        { id: 'step0', name: 'Select Released Order', endpoint: '/workflow/select' },
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
                    ${index === 0 ? `
                        <label for="released-orders">Select Released Order:</label>
                        <select id="released-orders">
                            <option value="">Select an order</option>
                        </select>
                        <button id="select-order-btn" disabled>Select Order</button>
                    ` : index === 2 ? `
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
            
                updateWorkflowStep(currentStep);
                currentStep++;
                localStorage.setItem('currentStep', currentStep);
                        if (currentStep < steps.length) {
                            updateWorkflowStep(currentStep);
                        }
                    // still needed?
                
        }
    }

    
    const resetButton = document.createElement('button');
    resetButton.id = 'reset-btn';
    resetButton.textContent = 'Reset to Step 0';
    resetButton.style.backgroundColor = 'red';
    resetButton.addEventListener('click', function() {
        resetWorkflow();
    });

    document.body.appendChild(resetButton);

    window.resetWorkflow = function() {
        currentStep = 0;
        localStorage.setItem('currentStep', currentStep);
        renderWorkflowSteps();
        updateWorkflowStep(currentStep);
    }

    // Initialize the workflow steps and the first step
    renderWorkflowSteps();
    updateWorkflowStep(currentStep);

    // Populate the released orders dropdown
    fetch('/api/released-orders')
        .then(response => response.json())
        .then(data => {
            const releasedOrdersDropdown = document.getElementById('released-orders');
            data.orders.forEach(order => {
                const option = document.createElement('option');
                option.value = order.orderNumber;
                option.textContent = order.orderNumber;
                releasedOrdersDropdown.appendChild(option);
            });
        });

    const releasedOrdersDropdown = document.getElementById('released-orders');
    const selectOrderBtn = document.getElementById('select-order-btn');

    releasedOrdersDropdown.addEventListener('change', function() {
        selectOrderBtn.disabled = !releasedOrdersDropdown.value;
    });

    selectOrderBtn.addEventListener('click', function() {
        const selectedOrder = releasedOrdersDropdown.value;
        if (selectedOrder) {
            // Save the selected order to local storage
            localStorage.setItem('selectedOrder', selectedOrder);

            fetch('/workflow/select', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({data: releasedOrdersDropdown.value })
            })
            .then(response => response.json())
        

            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
            // Move to the next step
            currentStep++;
            localStorage.setItem('currentStep', currentStep);
            updateWorkflowStep(currentStep);
        }
    });

        // Event listener for the "Start" button
    const startBtn = document.getElementById('step1-btn');
    startBtn.addEventListener('click', function() {
        const selorder = localStorage.getItem('selectedOrder');
        if (selorder) {
            fetch('/workflow/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ data:  selorder})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Order started successfully');
                } else { 
                    console.error('Error:', data.message);
                    alert('An error occurred');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred');
            });
        } else {
            alert('No order selected');
        }
    });
});