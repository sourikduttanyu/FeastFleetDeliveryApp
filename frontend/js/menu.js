/**
 * menu.js
 *
 * Page: menu.html
 *
 * Purpose:
 *   Renders the menu for a specific restaurant, allowing authenticated users to
 *   select item quantities and add them to their cart. On each quantity change,
 *   the cart is immediately synced with the backend.
 *
 * On Load:
 *   - Reads the "query" URL parameter (used as the restaurant ID).
 *   - Reads "idToken" and "userId" from localStorage to authenticate the user.
 *   - Redirects to login.html if no idToken is found.
 *   - Calls getMenuItem() to fetch and render the restaurant's menu.
 *
 * API Endpoints:
 *   - GET  https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/menu/{query}
 *       Fetches the full menu for the given restaurant ID.
 *   - GET  https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/cart/get?user_id={userId}
 *       Retrieves the current user's active cart contents.
 *   - POST https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/cart/add
 *       Creates or replaces the user's cart with the currently selected items.
 */

document.addEventListener("DOMContentLoaded", () => {

    // Extract the restaurant ID passed via the URL query string (e.g., menu.html?query=rest123)
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get("query");
    if (!query) {
        console.error("No query found in URL");
    }

    // Retrieve the JWT auth token stored after login; used in all authenticated API calls
    const idToken = localStorage.getItem("idToken");
        if (!idToken) {
            // Block unauthenticated users from accessing the menu page
            alert("You need to log in to make a reservation.");
            window.location.href = "login.html";
            return;
        }

    // Retrieve the logged-in user's unique ID, stored in localStorage at login time
    const userId = localStorage.getItem("userId");

    // Kick off menu rendering using the restaurant ID and user credentials
    getMenuItem(query, userId, idToken);

});

/**
 * getCartInfo
 *
 * Fetches the current user's active cart from the backend.
 * Called before updating the cart so that any restaurant conflict can be detected.
 *
 * API: GET /cart/get?user_id={userId}
 * Auth: Bearer token via Authorization header.
 *
 * @param {string} userId  - The unique ID of the logged-in user.
 * @param {string} idToken - The JWT token used for authorization.
 * @returns {Promise<Object>} The raw response body containing the cart object.
 */
async function getCartInfo(userId, idToken) {
    try {
        const response = await fetch(`https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/cart/get?user_id=${encodeURIComponent(userId)}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${idToken}`, // Add Authorization header
            },
        });

        console.log('GET CART INFO ', response);

        if (!response.ok) {
            throw new Error(`Failed to fetch cart content. Status: ${response.status}`);
        }

        const responseBody = await response.json();

        return responseBody;
    }
    catch (error) {
        console.log(error);
    }
}

/**
 * getMenuItem
 *
 * Fetches the menu for a given restaurant and dynamically renders each menu item
 * inside the ".menu-container" DOM element. Also wires up all quantity input
 * controls (+/- buttons and number inputs) so that changes immediately trigger
 * a cart update.
 *
 * API: GET /menu/{query}
 * Auth: Bearer token via Authorization header.
 *
 * DOM Targets:
 *   - .menu-container  : Cleared and repopulated with the restaurant name banner
 *                        and one ".item" card per menu entry.
 *   - .quantity-input  : Number inputs for each menu item; changing value syncs cart.
 *   - .decrease        : Buttons that decrement the corresponding quantity input.
 *   - .increase        : Buttons that increment the corresponding quantity input.
 *
 * @param {string} query  - The restaurant ID, sourced from the URL query parameter.
 * @param {string} userId - The logged-in user's ID, from localStorage.
 * @param {string} idToken - The JWT auth token, from localStorage.
 */
async function getMenuItem(query, userId, idToken) {
    const apiUrl = `https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/menu/${query}`;
    const infoContainer = document.querySelector(".menu-container");
    infoContainer.innerHTML = "";
    const selectedItems = {}; // Tracks items with quantity > 0, keyed by their index in the menu list

    try {
        const response = await fetch(apiUrl, {
            headers: {
                'Authorization': `Bearer ${idToken}`, // Add Authorization header
            },
        });

        console.log('GET MENU ITEM RESPONSE ', response);

        if (!response.ok) {
            throw new Error(`Failed to fetch restaurant data for ID: ${query}`);
        }
        const menuData = await response.json();
        // The API returns a double-serialized body string; parse it to access the actual data
        const parsedData = JSON.parse(menuData.body);
        if (parsedData) {
            const item_list = parsedData.menu;
            // Use the first item's restaurant_name field to display a banner heading
            const restaurant_name = item_list[0].restaurant_name;
            const name_banner = `<h1>${restaurant_name}</h1>`;
            infoContainer.innerHTML += name_banner;


            // Render menu items
            // Each item gets a data-id and data-index attribute to map DOM elements back to item_list indices
            item_list.forEach((item, index) => {
                const resultItem = `
                    <div class="item" data-id="${index}">
                        <img src="images/food.jpeg" alt="Food Image" />
                        <div class="item-info">
                            <h2>${item.item_name}</h2>
                            <div class="price-container">
                                <span>$${item.price}</span>
                                <div class="quantity-controls">
                                    <button class="decrease" data-index="${index}">-</button>
                                    <input type="number" value="0" min="0" class="quantity-input" data-index="${index}" />
                                    <button class="increase" data-index="${index}">+</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                infoContainer.innerHTML += resultItem;
            });

            // Add event listeners for quantity change
            // When a user types directly into the number input, update selectedItems and sync the cart
            document.querySelectorAll(".quantity-input").forEach((input) => {
                input.addEventListener("input", (event) => {
                    // data-index attribute maps this input back to its position in item_list
                    const index = event.target.dataset.index;
                    const value = parseInt(event.target.value, 10);
                    if (value > 0) { // Only track items with a positive quantity
                        selectedItems[index] = item_list[index];
                        selectedItems[index].quantity = value; // Add quantity to the item
                    } else {
                        delete selectedItems[index]; // Remove item if quantity <= 0
                    }
                    console.log("Selected items:", selectedItems);
                    // Immediately push the updated selection to the backend cart
                    updateCart(selectedItems, query, userId, idToken)
                        .then(response => console.log('Cart updated:', response))
                        .catch(error => console.error('Error updating cart:', error));

                });
            });

            // Add event listeners for +/- buttons
            // The decrease button prevents quantity from dropping below 0 using Math.max
            document.querySelectorAll(".decrease").forEach((button) => {
                button.addEventListener("click", (event) => {
                    const index = event.target.dataset.index;
                    const input = document.querySelector(`.quantity-input[data-index="${index}"]`);
                    const value = Math.max(0, parseInt(input.value, 10) - 1);
                    input.value = value;
                    // Dispatch a synthetic "input" event so the quantity change handler above fires
                    input.dispatchEvent(new Event("input")); // Trigger input event to update selectedItems
                });
            });

            // The increase button has no upper-bound cap; quantity can increase indefinitely
            document.querySelectorAll(".increase").forEach((button) => {
                button.addEventListener("click", (event) => {
                    const index = event.target.dataset.index;
                    const input = document.querySelector(`.quantity-input[data-index="${index}"]`);
                    const value = parseInt(input.value, 10) + 1;
                    input.value = value;
                    // Dispatch a synthetic "input" event so the quantity change handler above fires
                    input.dispatchEvent(new Event("input")); // Trigger input event to update selectedItems
                });
            });
        }
    } catch (error) {
        console.error(error);
    }
}

/**
 * showModal
 *
 * Programmatically creates and displays a confirmation modal dialog with a title,
 * message, and two buttons (Confirm / Cancel). Used to warn the user before
 * replacing their cart contents with items from a different restaurant.
 *
 * The modal is appended to document.body and removed when the user responds.
 *
 * DOM Targets:
 *   - document.body : Modal overlay is appended here and cleaned up on close.
 *
 * @param {string} title   - The heading text to display in the modal.
 * @param {string} message - The body text explaining the conflict or action.
 * @returns {Promise<boolean>} Resolves to true if user clicks "Confirm", false if "Cancel".
 */
function showModal(title, message) {
    console.log("dif")
    return new Promise((resolve) => {
        // Create modal elements dynamically
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div class="modal-overlay">
                <div class="modal">
                    <h2>${title}</h2>
                    <p>${message}</p>
                    <button id="confirm">Confirm</button>
                    <button id="cancel">Cancel</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Add event listeners
        // On confirm: remove modal and resolve promise with true
        modal.querySelector('#confirm').addEventListener('click', () => {
            document.body.removeChild(modal);
            resolve(true);
        });
        // On cancel: remove modal and resolve promise with false
        modal.querySelector('#cancel').addEventListener('click', () => {
            document.body.removeChild(modal);
            resolve(false);
        });
    });
}

/**
 * updateCart
 *
 * Syncs the user's currently selected menu items to the backend cart.
 * Before updating, it fetches the existing cart to check for a restaurant
 * conflict. If the existing cart belongs to a different restaurant, it prompts
 * the user via showModal before proceeding. If the user cancels, no update occurs.
 *
 * API: POST /cart/add
 * Auth: Bearer token via Authorization header.
 * Body: { userid, restaurant_id, item_list: [{ item_id, item_name, item_quantity, item_price }] }
 *
 * @param {Object} selectedItems   - A dictionary of selected items keyed by menu index.
 *                                   Each value includes item metadata and a `quantity` field.
 * @param {string} restaurant_id   - The restaurant ID for the current menu page (from URL param).
 * @param {string} userId          - The logged-in user's ID, from localStorage.
 * @param {string} idToken         - The JWT auth token, from localStorage.
 * @returns {Promise<Object|undefined>} The API response body on success, or undefined if cancelled/failed.
 */
async function updateCart(selectedItems, restaurant_id, userId, idToken) {
    try {
        // Fetch the user's current cart to check if it belongs to a different restaurant
        const original_cart_reponse = await getCartInfo(userId, idToken);
        const original_cart = JSON.parse(original_cart_reponse.body).cart;

        if (original_cart && original_cart.restaurant_id !== restaurant_id) {
            // Show modal to inform the customer about cart conflict before overwriting
            const confirm = await showModal(
                'Cart Conflict',
                'Your cart contains items from another restaurant. Adding items from this restaurant will replace your current cart. Do you want to proceed?'
            );

            if (!confirm) {
                console.log('User canceled the update.');
                return; // Exit function if user cancels
            }
        }
        console.log(original_cart);
        console.log('selectedItems:', selectedItems, 'Type:', typeof selectedItems);
        // Convert the selectedItems dictionary (keyed by index) into an array for the API payload
        const itemsArray = Object.values(selectedItems);
        const requestData = {
            userid: userId,
            restaurant_id: restaurant_id,
            item_list: itemsArray.map(item => ({
                item_id: item.item_id,
                item_name: item.item_name,
                item_quantity: item.quantity,
                item_price: item.price,
            })),
        };
        console.log(JSON.stringify(requestData, null, 2));
        const cartUpdateUrl = `https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/cart/add`;
        const response = await fetch(cartUpdateUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`,
            },
            body: JSON.stringify(requestData),
        });

        console.log('UPDATE RESPONSE ', response);

        if (!response.ok) {
            throw new Error(`Error updating cart: ${response.statusText}`);
        }
        const responseBody = await response.json();
        console.log('Cart updated successfully:', responseBody);
        return responseBody;
    }
    catch (error) {
        console.log(error);
    }
}
