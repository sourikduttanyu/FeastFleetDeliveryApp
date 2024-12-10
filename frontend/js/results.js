// Load the navbar from navbar.html
document.addEventListener("DOMContentLoaded", () => {
    fetch("navbar.html")
        .then((response) => response.text())
        .then((data) => {
        document.getElementById("navbar").innerHTML = data;

        // Initialize navbar logic after it's added to the DOM
        const navbarScript = document.createElement("script");
        navbarScript.src = "js/navbar.js";
        navbarScript.defer = true;
        document.body.appendChild(navbarScript);
        })
        .catch((error) => console.error("Error loading navbar:", error));
    
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('query');

    if (query) {
        fetchResults(query);
    } else {
        console.error('No query found in URL');
    }
});

function fetchResults(query) {
    const apiUrl = `https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/restaurants/search?cuisineType=${encodeURIComponent(query)}`;

    fetch(apiUrl, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        renderResults(query, data);
    })
    .catch(error => {
        console.error('Error fetching category data:', error);
    });
}

async function renderResults(query, data) {
    // Parse the body to get restaurantIds
    const parsedData = JSON.parse(data.body);
    console.log(parsedData.restaurantIds);

    const apiUrl = `https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/restaurants/`;
    const resultsContainer = document.getElementById('resultsContainer');
    const infoContainer = document.getElementById('info');
    infoContainer.innerHTML = `<h3>Search Results for "${query}"</h3>`;

    // Iterate through restaurantIds and fetch their data
    const restaurantPromises = parsedData.restaurantIds.map(async (id) => {
        try {
            const response = await fetch(`${apiUrl}${id}`);
            if (!response.ok) {
                throw new Error(`Failed to fetch restaurant data for ID: ${id}`);
            }
            const restaurantData = await response.json();
            return restaurantData;
        } catch (error) {
            console.error(error);
            return null;
        }
    });

    // Wait for all fetch requests to complete
    const restaurants = await Promise.all(restaurantPromises);
    console.log(restaurants)
    // Render each restaurant's data
    restaurants.forEach((restaurant) => {
        const parsedRestaurant = JSON.parse(restaurant.body)
        console.log(parsedRestaurant.restaurantDetails)
        const restaurantInfo = parsedRestaurant.restaurantDetails
        if (restaurant) {
            const resultItem = `
                <div class="restaurant-card">
                    <a href="restaurant-info.html?query=${restaurantInfo.restaurant_id}">
                        <div class="info">
                            <p class="small-text">${restaurantInfo.address}</p>
                            <p class="small-text">${restaurantInfo.cuisine}</p>
                        </div>
                        <div class="image">
                            <img src="${restaurant.image}" alt="${restaurantInfo.name}">
                        </div>
                        <h3 class="restaurant-name">${restaurantInfo.name}</h3>
                    </a>

                </div>
            `;
            resultsContainer.innerHTML += resultItem;
        }
    });
}
