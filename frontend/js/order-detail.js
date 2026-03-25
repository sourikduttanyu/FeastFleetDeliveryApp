/**
 * order-detail.js
 *
 * Page: order-detail.html (individual order detail view)
 *
 * Purpose:
 *   Fetches and displays the full details of a single order, including item
 *   breakdown, restaurant information, and live delivery tracking data (ETA and
 *   last-updated timestamp). The order is identified via the "orderId" URL parameter.
 *
 * On Load:
 *   - Reads "idToken" from localStorage to authenticate the request.
 *   - Redirects to login.html if no idToken is found.
 *   - Reads "orderId" from the URL query string.
 *   - Calls fetchOrderDetails() to load and render the full order view.
 *
 * API Endpoints:
 *   - GET https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/orders/{orderId}
 *       Returns the full order record including order_info, restaurant_info,
 *       and optionally delivery_info.
 */

/**
 * fetchOrderDetails
 *
 * Authenticates the user, extracts the order ID from the URL, then fetches the
 * complete order record from the backend. Populates all relevant DOM elements
 * with order metadata, line items, restaurant details, and delivery tracking info.
 * Gracefully handles a missing delivery_info block by displaying fallback text.
 *
 * API: GET /orders/{orderId}
 * Auth: Bearer token via Authorization header.
 *
 * DOM Targets:
 *   - #orderId            : Displays the order's unique identifier.
 *   - #orderStatus        : Displays the current status of the order.
 *   - #orderItems         : Cleared and repopulated with one ".order-item" div per line item,
 *                           showing quantity, item name, and price.
 *   - #totalPrice         : Displays the formatted total cost of the order.
 *   - #restaurantName     : Displays the name of the restaurant that fulfilled the order.
 *   - #restaurantAddress  : Displays the restaurant's physical address.
 *   - #eta                : Displays the estimated delivery time, or "Not available".
 *   - #lastUpdated        : Displays the last delivery status update time, or "-".
 *
 * @returns {Promise<void>}
 */
async function fetchOrderDetails() {
    try {
        console.log('Current URL search params:', window.location.search);

        // Retrieve the JWT auth token stored at login; required for the Authorization header
        const idToken = localStorage.getItem("idToken");
        if (!idToken) {
            // Redirect unauthenticated users before making any API calls
            alert("You need to log in to make a reservation.");
            window.location.href = "login.html";
            return;
        }

        // Extract the order ID from the URL query string (e.g., order-detail.html?orderId=abc123)
        const urlParams = new URLSearchParams(window.location.search);
        const orderId = urlParams.get('orderId'); // Matches 'orderId' in the URL
        console.log('Extracted orderId:', orderId);

        if (!orderId) {
            // Cannot load order details without a valid order ID
            alert('No order ID provided');
            return;
        }

        const API_URL = 'https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/orders';

        console.log('Fetching from:', `${API_URL}/${orderId}`);
        // Fetch the specific order by appending the order ID to the base URL
        const response = await fetch(`${API_URL}/${orderId}`, {
            headers: {
                'Authorization': `Bearer ${idToken}`, // Replace with the actual token
            }
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch order details: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('API Response:', JSON.stringify(data, null, 2));

        // Validate response structure
        // Guard against a missing order_info block before attempting to render
        if (!data.order_info) {
            console.error('Missing order_info:', data);
            alert('Order details not available');
            return;
        }

        // Populate order details
        // Directly set text content for simple scalar fields
        document.getElementById('orderId').textContent = data.order_info.order_id;
        document.getElementById('orderStatus').textContent = data.order_info.status;

        const orderItemsContainer = document.getElementById('orderItems');
        orderItemsContainer.innerHTML = ''; // Clear previous content

        // Render one row per line item: "2x Burger $12.99"
        data.order_info.items.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.className = 'order-item';
            itemElement.innerHTML = `
                <span>${item.quantity}x ${item.item_name}</span>
                <span>$${item.price}</span>
            `;
            orderItemsContainer.appendChild(itemElement);
        });

        // Populate order total and restaurant metadata
        document.getElementById('totalPrice').textContent = `$${data.order_info.total_price}`;
        // Use "N/A" as a safe fallback if restaurant name or address fields are absent
        document.getElementById('restaurantName').textContent = data.restaurant_info.name || 'N/A';
        document.getElementById('restaurantAddress').textContent = data.restaurant_info.address || 'N/A';

        // Populate delivery tracking fields only if delivery_info is present in the response
        if (data.delivery_info) {
            const lastUpdatedTimestamp = data.delivery_info.last_updated;
            document.getElementById('eta').textContent = data.delivery_info.eta || 'Not available';
            // Format the raw timestamp into a readable date-time string if it exists
            document.getElementById('lastUpdated').textContent = lastUpdatedTimestamp
                ? formatTimestamp(lastUpdatedTimestamp)
                : '-';
        } else {
            // delivery_info is absent when the order has not yet been picked up
            document.getElementById('eta').textContent = 'Not available';
            document.getElementById('lastUpdated').textContent = '-';
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error loading order details');
    }
}

/**
 * formatTimestamp
 *
 * Converts a raw timestamp value into a human-readable local date and time
 * string in the format "YYYY-MM-DD HH:MM". Used to display the last delivery
 * status update time on the order detail page.
 *
 * Note: Month is 0-indexed in JavaScript's Date API, so 1 is added before
 * padding to produce the correct 2-digit month string.
 *
 * @param {string|number} timestamp - A value accepted by the Date constructor
 *                                    (ISO string, Unix milliseconds, etc.).
 * @returns {string} A formatted datetime string, e.g. "2026-03-25 14:05".
 */
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-based
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}`;
}

// Trigger the order detail fetch and render sequence once the DOM is fully loaded
document.addEventListener('DOMContentLoaded', fetchOrderDetails);
