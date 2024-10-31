document.addEventListener('DOMContentLoaded', function() {
    const steps = [
        { id: 'step0', name: 'Select Released Order', endpoint: '/workflow/select' },
        { id: 'step1', name: 'Start Process', endpoint: '/workflow/start' },
        { id: 'step2', name: 'Select Scene', endpoints: { scene1: '/workflow/scene1', scene2: '/workflow/scene2' } },
        { id: 'step3', name: 'End Step', endpoint: '/workflow/end' },
    ];


    let currentStep = parseInt(localStorage.getItem('currentStep')) || 0;
    let selectedOrder = localStorage.getItem('selectedOrder');

    // Initial Calls
    // Initialize the workflow steps and the first step
    
    
    
    renderWorkflowSteps();
    updateWorkflowStep(currentStep);
    populateReleasedOrders();
   


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
                        <select id="released-orders" ${selectedOrder && currentStep >= 1 && currentStep <= 3 ? 'disabled' : ''}>
                            ${selectedOrder ? `<option value="${selectedOrder}" selected>${selectedOrder}</option>` : '<option value="">Select an order</option>'}
                        </select>
                        <button id="select-order-btn" disabled>Select Order</button>
                    `: index === 1 ? `
                     <button id="step1-btn" disabled>Start</button>
                    `
                    : index === 2 ? `
                        <button id="scene1-btn" disabled>Scene 1</button>
                        <button id="scene2-btn" disabled>Scene 2</button>
                    ` :  `
                        <button id="step3-btn" disabled>Complete</button>
                    `}
                </div>
            `;
            workflowOverview.appendChild(stepElement);
        });


    const releasedOrdersDropdown = document.getElementById('released-orders');
    const selectOrderBtn = document.getElementById('select-order-btn');
    

    

    // Event listener on select order Button and send the selected order
    selectOrderBtn.addEventListener('click', function() {
        // Disable the dropdown menu
        releasedOrdersDropdown.disabled = true;
        const selectedOrder = releasedOrdersDropdown.value;
        console.log('Order outside');
        if (selectedOrder) {
            // Save the selected order to local storage
            localStorage.setItem('selectedOrder', selectedOrder);
            console.log('Order inside');

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
            // Move to the next step
            currentStep++;
            localStorage.setItem('currentStep', currentStep);
            updateWorkflowStep(currentStep);
        } else {
            alert('No order selected');
        }

        
    });
    
        // Event listener for the "scene1" button
        const scene1button = document.getElementById('scene1-btn');
        scene1button.addEventListener('click', function() {
            const selorder = localStorage.getItem('selectedOrder');
            if (selorder) {
                fetch('/workflow/scene1', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ data:  selorder})
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
            } else {
                alert('No order selected');
            }

        });

        // Event listener for the "scene1" button
        const scene2button = document.getElementById('scene2-btn');
        scene2button.addEventListener('click', function() {
            const selorder = localStorage.getItem('selectedOrder');
            if (selorder) {
                fetch('/workflow/scene2', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ data:  selorder})
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
            } else {
                alert('No order selected');
            }
        });


        // Event listener for the "scene1" button
        const endbutton = document.getElementById('step3-btn');
        endbutton.addEventListener('click', function() {
            const selorder = localStorage.getItem('selectedOrder');
            if (selorder) {
                fetch('/workflow/end', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ data:  selorder})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('Order completed successfully');
                    } else { 
                        console.error('Error:', data.message);
                        alert('An error occurred');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred');
                });

                // Move to the next step
                currentStep = 0;
                localStorage.setItem('currentStep', currentStep);
                localStorage.removeItem('selectedOrder');
                renderWorkflowSteps();
                updateWorkflowStep(currentStep);
                
                //Call function for released orders to update the dropdown menu
                populateReleasedOrders();
                
            } else {
                alert('No order selected');
            }
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

    // Function to populate the released orders dropdown
    function populateReleasedOrders() {
        fetch('/api/released-orders')
            .then(response => response.json())
            .then(data => {
                const releasedOrdersDropdown = document.getElementById('released-orders');
                releasedOrdersDropdown.innerHTML = `<option value="">Select an order</option>`;
                if (selectedOrder) {
                    const selectedOption = document.createElement('option');
                    selectedOption.value = selectedOrder;
                    selectedOption.textContent = selectedOrder;
                    selectedOption.selected = true;
                    releasedOrdersDropdown.appendChild(selectedOption);
                }
                else
                {
                    data.orders.forEach(order => {
                        const option = document.createElement('option');
                        option.value = order.orderNumber;
                        option.textContent = order.orderNumber;
        
                        releasedOrdersDropdown.appendChild(option);
                    });
                }

                // Add event listener for the dropdown menu after it is populated
                releasedOrdersDropdown.addEventListener('change', function() {
                    const selectOrderBtn = document.getElementById('select-order-btn');
                    selectOrderBtn.disabled = !releasedOrdersDropdown.value;
                });

               
        });
    }





});