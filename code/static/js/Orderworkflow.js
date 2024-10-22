document.addEventListener('DOMContentLoaded', function() {
    const ordersList = document.getElementById('ordersList');

    if (ordersList) {
        ordersList.addEventListener('click', function(event) {
            if (event.target.classList.contains('release-btn') || event.target.classList.contains('abort-btn')) {
                const action = event.target.classList.contains('release-btn') ? 'release' : 'abort';
                const orderId = event.target.getAttribute('data-id');

                fetch('/order-management', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ action, order_id: orderId })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'Action Completed') {
                        // Update the order status in the list
                        const orderItem = event.target.parentElement;
                        const orderData = JSON.parse(orderItem.textContent);
                        orderData.status = action === 'release' ? 'Released' : 'Aborted';
                        orderItem.textContent = JSON.stringify(orderData);
                        // Re-add the buttons
                        const releaseBtn = document.createElement('button');
                        releaseBtn.classList.add('release-btn');
                        releaseBtn.setAttribute('data-id', orderId);
                        releaseBtn.textContent = 'Release';
                        const abortBtn = document.createElement('button');
                        abortBtn.classList.add('abort-btn');
                        abortBtn.setAttribute('data-id', orderId);
                        abortBtn.textContent = 'Abort';
                        orderItem.appendChild(releaseBtn);
                        orderItem.appendChild(abortBtn);
                    }
                });
            }
        });
    }
});