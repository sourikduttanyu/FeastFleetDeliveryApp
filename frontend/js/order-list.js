async function fetchOrders() {
    try {
        // Get user_id from local storage or session
        const userId = localStorage.getItem('userId');
        if (!userId) {
            // Redirect to login if no user ID
            window.location.href = 'login.html';
            return;
        }
        const response = await fetch(`https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/view-orders?user_id=${userId}`);
        const data = await response.json();

        const currentOrdersContainer = document.getElementById('currentOrders');
        const historyOrdersContainer = document.getElementById('historyOrders');
        
        currentOrdersContainer.innerHTML = '';
        historyOrdersContainer.innerHTML = '';

        data.orders.forEach(order => {
            const orderCard = createOrderCard(order);
            if (order.status === 'DELIVERED') {
                historyOrdersContainer.appendChild(orderCard);
            } else {
                currentOrdersContainer.appendChild(orderCard);
            }
        });

    } catch (error) {
        console.error('Error:', error);
        alert('Error loading orders');
    }
}

function createOrderCard(order) {
    const card = document.createElement('div');
    card.className = 'order-card';
    card.onclick = () => window.location.href = `order-detail.html?order_id=${order.order_id}`;

    card.innerHTML = `
        <img src="images/restaurant.jpg" alt="Restaurant">
        <div class="order-info">
            <h3>${order.restaurant_name}</h3>
            <p class="order-details">${order.items_count} items | $${order.total_price}</p>
            <p class="order-time">${formatOrderTime(order.timestamp, order.status)}</p>
        </div>
    `;
    
    return card;
}

function formatOrderTime(timestamp, status) {
    const date = new Date(timestamp);
    const formattedDate = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return status === 'DELIVERED' ? 
        `Delivered on ${formattedDate}` : 
        `Ordered on ${formattedDate}`;
}

// Load orders when page loads
document.addEventListener('DOMContentLoaded', fetchOrders);