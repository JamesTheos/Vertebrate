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
                        if (action === 'release') {
                            window.location.href = '/overview';
                        } else {
                            // Update the order status in the list
                            const orderRow = event.target.closest('tr');
                            orderRow.querySelector('td:nth-child(4)').textContent = 'Aborted';
                        }
                    } else {
                        alert(data.error || 'An error occurred');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred');
                });
            }
        });
    }
    
});