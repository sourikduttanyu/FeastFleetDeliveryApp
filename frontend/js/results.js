/**
 * results.js — Search Results Page Script
 *
 * Serves: results.html (the page that displays restaurant search results)
 *
 * On Load:
 *   - Parses the URL query string to extract the search parameters (query,
 *     type, location) and the authenticated user's ID from localStorage.
 *   - Immediately calls fetchResults() to retrieve matching restaurant IDs
 *     from the backend search API.
 *   - Attaches a click handler to the in-page search button so the user can
 *     perform a new keyword search without returning to the home page.
 *
 * API Endpoints Called:
 *   1. GET https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/restaurants/search
 *        Query params: type, query, location, userId
 *        Returns: a list of restaurant IDs matching the search criteria.
 *
 *   2. GET https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/restaurants/{id}
 *        Called once per restaurant ID returned by the search endpoint.
 *        Returns: detailed information for a single restaurant.
 *
 * DOM Manipulated:
 *   - #resultsContainer — populated with restaurant card HTML for each result
 *   - #info             — updated with the search query heading
 *   - #search-button    — listens for in-page re-search clicks
 *   - #searchInput      — reads the keyword for in-page re-searches
 */

// Wait for the full DOM to be ready before reading URL params or querying DOM elements.
document.addEventListener("DOMContentLoaded", () => {

    // --- Parse URL query parameters passed from index.html or a previous search ---
    const urlParams = new URLSearchParams(window.location.search);
    const query    = urlParams.get('query');    // The search term (keyword or cuisine type)
    const type     = urlParams.get('type');     // Search mode: "name" or "cuisineType"
    const location = urlParams.get('location'); // User's zip code for geo-filtering

    // Retrieve the logged-in user's ID from localStorage (set during login)
    const userId = localStorage.getItem('userId');


    console.log(query, type, location)

    // Only proceed if a query was actually supplied; otherwise log an error
    if (query) {
        fetchResults(query, type, location, userId);
    } else {
        console.error('No query found in URL');
    }

    // DOM references for the in-page search bar
    const searchButton = document.getElementById("search-button");
    const searchInput  = document.getElementById("searchInput");

    /**
     * In-Page Search Button Click Handler
     *
     * Allows the user to perform a new keyword search directly from the results
     * page without navigating back to the home page.
     *
     * Behavior:
     *   - Reads the keyword from #searchInput.
     *   - Redirects to results.html with updated query parameters, preserving
     *     the current location and userId.
     *   - Alerts the user if the keyword field is empty.
     */
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

/**
 * fetchResults
 *
 * Calls the restaurant search API to retrieve a list of restaurant IDs that
 * match the given search parameters. On success, passes the raw response data
 * to renderResults() for display.
 *
 * @param {string} query    - The search keyword or cuisine category string.
 * @param {string} type     - The search mode: "name" (keyword) or "cuisineType".
 * @param {string} location - The user's zip code used for proximity filtering.
 * @param {string} userId   - The authenticated user's unique ID (from localStorage).
 *
 * API: GET /dev/restaurants/search?type=&query=&location=&userId=
 *
 * Returns: void — results are rendered to the DOM via renderResults().
 */
function fetchResults(query, type, location, userId) {
    // Construct the full search API URL with all required query parameters
    const apiUrl = `https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/restaurants/search?type=${encodeURIComponent(type)}&query=${encodeURIComponent(query)}&location=${encodeURIComponent(location)}&userId=${encodeURIComponent(userId)}`;

    fetch(apiUrl, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        // Throw immediately on non-2xx HTTP status codes
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json(); // Parse the JSON response body
    })
    .then(data => {
        // Hand off the response payload and original query string to the renderer
        renderResults(query, data);
    })
    .catch(error => {
        console.error('Error fetching category data:', error);
    });
}

/**
 * renderResults
 *
 * Async function that receives the search API response, extracts individual
 * restaurant IDs, fetches full details for each restaurant in parallel, and
 * injects restaurant card HTML into the #resultsContainer element.
 *
 * @param {string} query - The original search term, used for the results heading.
 * @param {Object} data  - The raw API gateway response object. data.body is a
 *                         JSON string containing a "restaurantIds" array.
 *
 * API: GET /dev/restaurants/{id}  — called once per restaurant ID.
 *
 * DOM:
 *   - Writes a search heading into #info.
 *   - Appends a ".restaurant-card" anchor block to #resultsContainer for each
 *     successfully fetched restaurant.
 */
async function renderResults(query, data) {
    // Parse the body to get restaurantIds
    // The API Gateway wraps the Lambda response body as a JSON string,
    // so a second JSON.parse() is required to access the actual payload.
    const parsedData = JSON.parse(data.body);
    console.log(parsedData.restaurantIds);

    // Base URL for individual restaurant detail lookups
    const apiUrl = `https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/restaurants/`;

    // DOM containers where results and the heading will be injected
    const resultsContainer = document.getElementById('resultsContainer');
    const infoContainer    = document.getElementById('info');

    // Display a heading showing the user what they searched for
    infoContainer.innerHTML = `<h3>Search Results for "${query}"</h3>`;

    // Iterate through restaurantIds and fetch their data
    // Map each restaurant ID to a fetch promise so all requests can run concurrently
    const restaurantPromises = parsedData.restaurantIds.map(async (id) => {
        try {
            // Fetch the detail record for a single restaurant by its ID
            const response = await fetch(`${apiUrl}${id}`);
            if (!response.ok) {
                throw new Error(`Failed to fetch restaurant data for ID: ${id}`);
            }
            const restaurantData = await response.json();
            return restaurantData; // Returns the raw API Gateway response object
        } catch (error) {
            console.error(error);
            return null; // Return null for failed fetches so Promise.all doesn't short-circuit
        }
    });

    // Wait for all fetch requests to complete
    // Promise.all runs all requests concurrently and resolves when every one finishes
    const restaurants = await Promise.all(restaurantPromises);
    console.log(restaurants)

    // Render each restaurant's data
    restaurants.forEach((restaurant) => {
        // Each restaurant response also has a JSON-stringified body that must be parsed
        const parsedRestaurant = JSON.parse(restaurant.body)
        console.log(parsedRestaurant.restaurantDetails)
        const restaurantInfo = parsedRestaurant.restaurantDetails

        if (restaurant) {
            // Build a restaurant card as an HTML string and append it to the results container.
            // The card links to restaurant-info.html, passing the restaurant_id as a query param.
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
            // Append the new card to whatever is already in the container
            resultsContainer.innerHTML += resultItem;
        }
    });
}
