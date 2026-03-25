/**
 * order-list.js
 *
 * Page: order-list.html (order history / active orders dashboard)
 *
 * Purpose:
 *   Fetches all orders belonging to the authenticated user and splits them into
 *   two visual sections: active/in-progress orders and delivered order history.
 *   Each order is rendered as a clickable card that navigates to the order detail page.
 *
 * On Load:
 *   - Reads "idToken" and "userId" from localStorage.
 *   - Redirects to login.html if no idToken is found.
 *   - Calls fetchOrders() to load and render all orders.
 *
 * API Endpoints:
 *   - GET https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/orders?user_id={userId}
 *       Returns all orders (current and historical) for the logged-in user.
 */

/**
 * fetchOrders
 *
 * Authenticates the user via localStorage, then fetches the full list of orders
 * from the backend. Iterates over each order and routes it to either the
 * "#currentOrders" or "#historyOrders" DOM container based on its status.
 * Orders with status "DELIVERED" go to history; all others go to current orders.
 *
 * API: GET /orders?user_id={userId}
 * Auth: Bearer token via Authorization header.
 *
 * DOM Targets:
 *   - #currentOrders  : Container for active/in-progress order cards (non-DELIVERED).
 *   - #historyOrders  : Container for completed/delivered order cards.
 *
 * @returns {Promise<void>}
 */
async function fetchOrders() {
    try {
        const API_URL = 'https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev';

        // Retrieve the JWT auth token stored at login; required for the Authorization header
        const idToken = localStorage.getItem("idToken");
        if (!idToken) {
            // Block unauthenticated access and redirect to the login page
            alert("You need to log in to make a reservation.");
            window.location.href = "login.html";
            return;
        }

        // Retrieve the logged-in user's unique ID to scope the orders query
        const userId = localStorage.getItem("userId");

        // Build the full API URL with the user ID as a query parameter
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

        // Handle application-level error codes that arrive with HTTP 200
        if (data.statusCode === 400) {
            console.error('Bad request:', data.body);
            throw new Error(data.body.message || 'Bad request');
        }

        const currentOrdersContainer = document.getElementById('currentOrders');
        const historyOrdersContainer = document.getElementById('historyOrders');

        // Clear stale content before rendering fresh order data
        currentOrdersContainer.innerHTML = '';
        historyOrdersContainer.innerHTML = '';

        // Parse the body string into an object since it's double stringified
        // The API wraps its JSON payload inside a stringified body field
        const ordersData = JSON.parse(data.body);
        console.log('Parsed orders:', ordersData);  // Log the parsed orders

        // Guard against malformed or unexpected API response shapes
        if (!ordersData.orders || !Array.isArray(ordersData.orders)) {
            console.error('Invalid orders data:', ordersData);
            throw new Error('Invalid response format');
        }

        // Route each order to the correct container based on its delivery status
        ordersData.orders.forEach(order => {
            const orderCard = createOrderCard(order);
            if (order.status === 'DELIVERED') {
                // Completed orders go to the history section
                historyOrdersContainer.appendChild(orderCard);
            } else {
                // All other statuses (e.g., PENDING, IN_PROGRESS) are treated as active
                currentOrdersContainer.appendChild(orderCard);
            }
        });

    } catch (error) {
        console.error('Error:', error);
        alert('Error loading orders');
    }
}

/**
 * createOrderCard
 *
 * Builds and returns a single order card DOM element for a given order object.
 * The card displays the restaurant name, item count, total price, and a
 * human-readable timestamp. Clicking the card navigates to the order detail page,
 * passing the order ID as a URL parameter.
 *
 * DOM: Creates a new <div class="order-card"> element (not yet attached to the DOM).
 *
 * @param {Object} order                - A single order object from the API response.
 * @param {string} order.order_id       - Unique identifier for the order; used in the detail page URL.
 * @param {string} order.restaurant_name - Display name of the restaurant.
 * @param {number} order.items_count    - Total number of distinct items in the order.
 * @param {number} order.total_price    - Total monetary value of the order.
 * @param {string} order.timestamp      - ISO timestamp of when the order was placed.
 * @param {string} order.status         - Current status of the order (e.g., "DELIVERED").
 * @returns {HTMLDivElement} The constructed order card element ready to be appended to the DOM.
 */
function createOrderCard(order) {
    const card = document.createElement('div');
    card.className = 'order-card';
    // Clicking the card navigates to the detail page, passing the order ID via URL param
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

/**
 * formatOrderTime
 *
 * Converts a raw ISO timestamp and order status into a user-friendly date string.
 * The label prefix changes based on whether the order has been delivered or is
 * still active (e.g., "Delivered on Mar 25" vs. "Ordered on Mar 25").
 *
 * @param {string} timestamp - An ISO 8601 date string representing when the order occurred.
 * @param {string} status    - The current order status; "DELIVERED" triggers the past-tense label.
 * @returns {string} A formatted string such as "Delivered on Mar 25" or "Ordered on Mar 25".
 */
function formatOrderTime(timestamp, status) {
    const date = new Date(timestamp);
    // Format as abbreviated month + day (e.g., "Mar 25")
    const formattedDate = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return status === 'DELIVERED' ?
        `Delivered on ${formattedDate}` :
        `Ordered on ${formattedDate}`;
}

// Load orders when page loads
document.addEventListener('DOMContentLoaded', fetchOrders);
