async function fetchOrders() {
    try {
        const API_URL = 'https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev';
        


        const idToken = localStorage.getItem("idToken");
        if (!idToken) {
            alert("You need to log in to make a reservation.");
            window.location.href = "login.html";
            return;
        }

        const userId = localStorage.getItem("userId");

        const fullUrl = `${API_URL}/orders?user_id=${encodeURIComponent(userId)}`;

        console.log('Fetching from:', fullUrl);
        // Add the Authorization header with the ID token
        const response = await fetch(fullUrl, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${idToken}`, // Include the ID token in the Authorization header
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch orders: ${response.status}`);
        }

        
        const data = await response.json();
        console.log('Received data:', data);  // Log the raw response

        if (data.statusCode === 400) {
            console.error('Bad request:', data.body);
            throw new Error(data.body.message || 'Bad request');
        }

        const currentOrdersContainer = document.getElementById('currentOrders');
        const historyOrdersContainer = document.getElementById('historyOrders');
        
        currentOrdersContainer.innerHTML = '';
        historyOrdersContainer.innerHTML = '';

        // Parse the body string into an object since it's double stringified
        const ordersData = JSON.parse(data.body);
        console.log('Parsed orders:', ordersData);  // Log the parsed orders

        if (!ordersData.orders || !Array.isArray(ordersData.orders)) {
            console.error('Invalid orders data:', ordersData);
            throw new Error('Invalid response format');
        }

        ordersData.orders.forEach(order => {
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
    card.onclick = () => window.location.href = `order-detail.html?orderId=${encodeURIComponent(order.order_id)}`;

    card.innerHTML = `
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