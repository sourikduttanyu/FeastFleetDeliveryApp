async function fetchOrderDetails() {
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const orderId = urlParams.get('order_id');
        
        if (!orderId) {
            alert('No order ID provided');
            return;
        }

        const response = await fetch(`[YOUR_API_GATEWAY_URL]/view-order?order_id=${orderId}`);
        const data = await response.json();

        // Update order header section
        document.getElementById('orderId').textContent = data.order_info.order_id;
        document.getElementById('orderStatus').textContent = data.order_info.status;

        // Update order details section
        const orderItemsContainer = document.getElementById('orderItems');
        orderItemsContainer.innerHTML = '';
        data.order_info.items.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.className = 'order-item';
            itemElement.innerHTML = `
                <span>${item.quantity}x ${item.item_name}</span>
                <span>$${item.price}</span>
            `;
            orderItemsContainer.appendChild(itemElement);
        });
        document.getElementById('totalPrice').textContent = data.order_info.total_price;

        // Update restaurant section
        document.getElementById('restaurantName').textContent = data.restaurant_info.name;
        document.getElementById('restaurantAddress').textContent = data.restaurant_info.address;

        // Update delivery tracking section
        if (data.delivery_info) {
            document.getElementById('eta').textContent = data.delivery_info.eta || 'Not available';
            document.getElementById('lastUpdated').textContent = data.delivery_info.last_updated || '-';
        }

    } catch (error) {
        console.error('Error:', error);
        alert('Error loading order details');
    }
}

document.addEventListener('DOMContentLoaded', fetchOrderDetails);