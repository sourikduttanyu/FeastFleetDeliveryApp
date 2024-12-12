// Load the navbar from navbar.html
document.addEventListener("DOMContentLoaded", () => {
    
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('query');
    const type = urlParams.get('type');
    const location = urlParams.get('location');
    const userId = localStorage.getItem('userId');
  

    console.log(query, type, location)
    if (query) {
        fetchResults(query, type, location, userId);
    } else {
        console.error('No query found in URL');
    }

    const searchButton = document.getElementById("search-button");
    const searchInput = document.getElementById("searchInput");
    searchButton.addEventListener("click", () => {
    const keyword = searchInput.value.trim();

    if (keyword) {
      // Redirect to results page with the keyword as a query parameter
      const resultsPageUrl = `results.html?type=name&query=${encodeURIComponent(keyword)}&location=${encodeURIComponent(location)}&userId=${encodeURIComponent(userId)}`;
      window.location.href = resultsPageUrl;
    } else {
      alert("Please enter a keyword to search.");
    }
  });
});

function fetchResults(query, type, location, userId) {
    const apiUrl = `https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/restaurants/search?type=${encodeURIComponent(type)}&query=${encodeURIComponent(query)}&location=${encodeURIComponent(location)}&userId=${encodeURIComponent(userId)}`;

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
                        <div class="image">
                            <img src="images/restaurant.jpg" alt="${restaurantInfo.name}">
                        </div>
                        <div class="info">
                            <h3 class="restaurant-name">${restaurantInfo.name}</h3>
                            <p class="address">${restaurantInfo.address}</p>
                        </div>
                    </a>
                </div>

            `;
            resultsContainer.innerHTML += resultItem;
        }
    });
}