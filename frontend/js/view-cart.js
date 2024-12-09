document.addEventListener('DOMContentLoaded', () => {
    fetch('navbar.html')
        .then(response => response.text())
        .then(data => {
            document.getElementById('navbar').innerHTML = data;
        })
        .catch(error => console.error('Error loading navbar:', error));
    getCartContent('user1')
});
async function getCartContent(userId) {
    try {
        const response = await fetch(`https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/cart/get?user_id=${encodeURIComponent(userId)}`, {
            method: 'GET',
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch cart content. Status: ${response.status}`);
        }
        
        const responseBody = await response.json();
        const cart = JSON.parse(responseBody.body).cart;
        
        const items = cart.item_list;
        console.log('Cart content:', cart);
        const itemContainer = document.getElementById("items");
        const summaryContainer = document.getElementById("summary") 
        itemContainer.innerHTML = "";
        summaryContainer.innerHTML = "";
        items.forEach(item => {
            const itemElement = `
                <div class="item">
                    <img src="${item.imgSrc}" alt="${item.alt}" />
                    <div class="details">
                        <h3>${item.item_name}</h3>
                        <p>$${item.item_price} dollars</p>
                        <div class="quantity">
                            <input type="number" value="${item.item_quantity}" min="0" step="1" />
                        </div>
                    </div>
                    <p class="price">$${(item.item_price * item.item_quantity).toFixed(2)}</p>
                </div>
            `;

            // Append the HTML to the container
            itemContainer.innerHTML += itemElement;
        });
        summaryContainer.innerHTML += `
        <h3>Order summary</h3>
          <p>Subtotal: ${cart.total_price}</p>
          <p><strong>Total: ${cart.total_price }</strong></p>
          <button>Continue to payment</button>`;
        
        
    } catch (error) {
        console.error('Error:', error);
    }
}