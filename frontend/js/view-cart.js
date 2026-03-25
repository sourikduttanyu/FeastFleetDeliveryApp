/**
 * view-cart.js
 *
 * Page: view-cart.html (cart review / checkout page)
 *
 * Purpose:
 *   Displays all items currently in the authenticated user's cart, shows a
 *   running order summary with subtotal and total, and provides a "Continue to
 *   payment" button that submits the order to the backend.
 *
 * On Load:
 *   - Reads "idToken" and "userId" from localStorage.
 *   - Redirects to login.html if no idToken is found.
 *   - Calls getCartContent() to fetch and render the cart.
 *
 * API Endpoints:
 *   - GET  https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/cart/get?user_id={userId}
 *       Retrieves the current cart contents for the logged-in user.
 *   - POST https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/orders
 *       Submits a new order based on the current cart contents.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Retrieve the JWT auth token stored after a successful login
    const idToken = localStorage.getItem("idToken");
    if (!idToken) {
        // Redirect unauthenticated users to the login page before they can view the cart
        alert("You need to log in to access the cart.");
        window.location.href = "login.html";
        return;
    }

    // Retrieve the logged-in user's unique ID from localStorage
    const userId = localStorage.getItem("userId");

    // Fetch and render the user's cart contents
    getCartContent(userId, idToken);
});

/**
 * getCartContent
 *
 * Fetches the user's current cart from the backend and renders each cart item
 * inside the "#items" container. Also populates the "#summary" container with
 * the order subtotal, total price, and a "Continue to payment" button.
 * Attaches a click handler to the payment button that triggers placeOrder().
 *
 * API: GET /cart/get?user_id={userId}
 * Auth: Bearer token via Authorization header.
 *
 * DOM Targets:
 *   - #items    : Cleared and repopulated with one ".item" card per cart entry,
 *                 showing item name, unit price, quantity input, and line total.
 *   - #summary  : Cleared and repopulated with subtotal, total, and checkout button.
 *   - #placeOrderBtn : Dynamically created button wired to placeOrder().
 *
 * @param {string} userId  - The logged-in user's unique ID, from localStorage.
 * @param {string} idToken - The JWT auth token, from localStorage.
 */
async function getCartContent(userId, idToken) {
    try {
        const response = await fetch(`https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/cart/get?user_id=${encodeURIComponent(userId)}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${idToken}`, // Add the authorization header
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch cart content. Status: ${response.status}`);
        }

        const responseBody = await response.json();
        // The API response body is a double-serialized JSON string; parse it to access cart data
        const cart = JSON.parse(responseBody.body).cart;

        const items = cart.item_list;
        console.log('Cart content:', cart);
        const itemContainer = document.getElementById("items");
        const summaryContainer = document.getElementById("summary")
        // Clear any previously rendered content before re-rendering
        itemContainer.innerHTML = "";
        summaryContainer.innerHTML = "";

        // Render one card per item, showing name, unit price, editable quantity, and computed line total
        items.forEach(item => {
            const itemElement = `
                <div class="item">
                    <img src="images/food.jpeg" alt="food" />
                    <div class="details">
                        <h3>${item.item_name}</h3>
                        <p>$${item.item_price} dollars</p>
                        <div class="quantity">
                            <input type="number" value="${item.item_quantity}" min="0" step="1" />
                        </div>
                    </div>
                    <!-- Line total: unit price × quantity, rounded to 2 decimal places -->
                    <p class="price">$${(item.item_price * item.item_quantity).toFixed(2)}</p>
                </div>
            `;

            // Append the HTML to the container
            itemContainer.innerHTML += itemElement;
        });

        // Render the order summary block with subtotal, total, and checkout button
        summaryContainer.innerHTML += `
        <h3>Order summary</h3>
          <p>Subtotal: $${cart.total_price}</p>
          <p><strong>Total: $${cart.total_price }</strong></p>
          <button id="placeOrderBtn">Continue to payment</button>`;

        // Wire the checkout button — passes the full cart object and auth token to placeOrder()
        document.getElementById('placeOrderBtn').addEventListener('click', () => {
            placeOrder(cart, idToken);
        });
    } catch (error) {
        console.error('Error:', error);
    }
}

/**
 * placeOrder
 *
 * Submits the user's current cart as a new order to the backend. On success,
 * shows a confirmation alert and navigates to order-list.html. On failure,
 * shows an error alert so the user can retry.
 *
 * API: POST /orders
 * Auth: Bearer token via Authorization header.
 * Body: { restaurant_id, items: [{ item_id, quantity }], total_price }
 *
 * DOM Side Effects:
 *   - Alerts the user on both success and failure.
 *   - Redirects to order-list.html after a successful order submission.
 *
 * @param {Object} cartContent - The full cart object returned by getCartContent(),
 *                               containing restaurant_id, item_list, and total_price.
 * @param {string} idToken     - The JWT auth token used for the Authorization header.
 */
async function placeOrder(cartContent, idToken) {
    try {
        // Build the order payload; strip down to only the fields the orders API expects
        const requestBody = {
            restaurant_id: cartContent.restaurant_id,
            items: cartContent.item_list.map(item => ({
                item_id: item.item_id,
                quantity: item.item_quantity
            })),
            total_price: cartContent.total_price
        };

        const response = await fetch('https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/orders', { // Replace with your actual API endpoint
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${idToken}`, // Add the authorization header
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`Failed to place order. Status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Order placed successfully:', result);
        alert('Order placed successfully!');
        // Navigate to the order history page so the user can track the new order
        window.location.href='order-list.html'
    } catch (error) {
        console.error('Error placing order:', error);
        alert('Failed to place order. Please try again.');
    }
}
