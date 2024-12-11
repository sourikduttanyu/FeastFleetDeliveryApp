document.addEventListener("DOMContentLoaded", () => {

    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get("query");
    if (!query) {
        console.error("No query found in URL");
    }

    const idToken = localStorage.getItem("idToken");
        if (!idToken) {
            alert("You need to log in to make a reservation.");
            window.location.href = "login.html";
            return;
        }

    const userId = localStorage.getItem("userId");

    getMenuItem(query, userId, idToken);

});

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

async function getMenuItem(query, userId, idToken) {
    const apiUrl = `https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/menu/${query}`;
    const infoContainer = document.querySelector(".menu-container");
    infoContainer.innerHTML = "";
    const selectedItems = {}; // 用於存儲數量大於 0 的項目
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
        const parsedData = JSON.parse(menuData.body);
        if (parsedData) {
            const item_list = parsedData.menu;
            const restaurant_name = item_list[0].restaurant_name;
            const name_banner = `<h1>${restaurant_name}</h1>`;
            infoContainer.innerHTML += name_banner;
            

            // Render menu items
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
            document.querySelectorAll(".quantity-input").forEach((input) => {
                input.addEventListener("input", (event) => {
                    const index = event.target.dataset.index;
                    const value = parseInt(event.target.value, 10);
                    if (value > 0) { // 修改條件為大於 0
                        selectedItems[index] = item_list[index];
                        selectedItems[index].quantity = value; // Add quantity to the item
                    } else {
                        delete selectedItems[index]; // Remove item if quantity <= 0
                    }
                    console.log("Selected items:", selectedItems);
                    updateCart(selectedItems, query, userId, idToken)
                        .then(response => console.log('Cart updated:', response))
                        .catch(error => console.error('Error updating cart:', error));
                    
                });
            });

            // Add event listeners for +/- buttons
            document.querySelectorAll(".decrease").forEach((button) => {
                button.addEventListener("click", (event) => {
                    const index = event.target.dataset.index;
                    const input = document.querySelector(`.quantity-input[data-index="${index}"]`);
                    const value = Math.max(0, parseInt(input.value, 10) - 1);
                    input.value = value;
                    input.dispatchEvent(new Event("input")); // Trigger input event to update selectedItems
                });
            });

            document.querySelectorAll(".increase").forEach((button) => {
                button.addEventListener("click", (event) => {
                    const index = event.target.dataset.index;
                    const input = document.querySelector(`.quantity-input[data-index="${index}"]`);
                    const value = parseInt(input.value, 10) + 1;
                    input.value = value;
                    input.dispatchEvent(new Event("input")); // Trigger input event to update selectedItems
                });
            });
        }
    } catch (error) {
        console.error(error);
    }
}

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
        modal.querySelector('#confirm').addEventListener('click', () => {
            document.body.removeChild(modal);
            resolve(true);
        });
        modal.querySelector('#cancel').addEventListener('click', () => {
            document.body.removeChild(modal);
            resolve(false);
        });
    });
}

async function updateCart(selectedItems, restaurant_id, userId, idToken) {
    try {
        const original_cart_reponse = await getCartInfo(userId, idToken);
        const original_cart = JSON.parse(original_cart_reponse.body).cart;

        if (original_cart && original_cart.restaurant_id !== restaurant_id) {
            // Show modal to inform the customer
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