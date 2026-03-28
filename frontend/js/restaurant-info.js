/**
 * restaurant-info.js
 *
 * Page: restaurant-info.html (individual restaurant profile page)
 *
 * Purpose:
 *   Fetches and displays the profile details (name, address, cuisine type) for
 *   a specific restaurant. Also wires up navigation buttons so the user can jump
 *   directly to the restaurant's menu page or start a reservation, preserving the
 *   restaurant ID and name in the destination URL.
 *
 * On Load:
 *   - Reads the "query" URL parameter (used as the restaurant ID).
 *   - Calls getRestaurantInfo() to fetch and render the restaurant's details.
 *   - Attaches click handlers to all #menu-button and #reservation-button elements
 *     so they navigate to the correct sub-pages with the restaurant ID in the URL.
 *
 * API Endpoints:
 *   - GET https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/restaurants/{query}
 *       Returns the full profile of a single restaurant (name, address, cuisine).
 *       Note: This endpoint does not require an Authorization header.
 */

document.addEventListener("DOMContentLoaded", () => {

    // Extract the restaurant ID from the URL query string (e.g., restaurant-info.html?query=rest123)
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('query');
    if (!query) {
        console.error('No query found in URL');
    }

    // Fetch and render the restaurant's profile information
    getRestaurantInfo(query);

    // Wire all elements with id="menu-button" to navigate to menu.html,
    // forwarding the restaurant ID so menu.js knows which menu to load
    document.querySelectorAll('#menu-button').forEach(button => {
        button.addEventListener('click', () => {
            window.location.href = `menu.html?query=${encodeURIComponent(query)}`;
        });
    });

    // Wire all elements with id="reservation-button" to navigate to the reservation
    // creation page, passing the restaurant ID via URL parameter
    document.querySelectorAll('#reservation-button').forEach(button => {
        button.addEventListener('click', () => {
            window.location.href = `reservation-creation.html?query=${encodeURIComponent(query)}`;
        });
    });

    // A second, more specific click handler for #reservation-button that also
    // passes the restaurant's display name alongside its ID. This reads the name
    // directly from the DOM element populated by getRestaurantInfo(), so it must
    // run after that function has rendered the content.
    // Add event listener to the reservation button
    document.getElementById('reservation-button').addEventListener('click', () => {
        const restaurantName = document.getElementById("restaurant-name").textContent;
        window.location.href = `reservation-creation.html?restaurant_id=${encodeURIComponent(query)}&restaurant_name=${encodeURIComponent(restaurantName)}`;
    });


});

/**
 * getRestaurantInfo
 *
 * Fetches the profile details for a single restaurant from the backend and
 * dynamically renders the name, address, and cuisine type inside the
 * ".rest-info" DOM container. Returns the raw API response for potential
 * upstream use.
 *
 * API: GET /restaurants/{query}
 * Auth: None required (public endpoint).
 *
 * DOM Targets:
 *   - .rest-info : Cleared and repopulated with an <h1> for the restaurant name
 *                  and <p> tags for address and cuisine type.
 *   - #restaurant-name    : Used by the reservation button handler (above) to
 *                           read the display name after rendering.
 *
 * @param {string} query - The restaurant ID, sourced from the URL query parameter.
 * @returns {Promise<Object|null>} The raw API response object on success, or null on failure.
 */
async function getRestaurantInfo(query) {
    const apiUrl = `https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/restaurants/`;
    const infoContainer = document.querySelector('.rest-info'); // Use querySelector for a single element
    infoContainer.innerHTML = ''; // Clear previous content
    try {
        // Append the restaurant ID directly to the base URL path (RESTful route)
        const response = await fetch(`${apiUrl}${query}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch restaurant data for ID: ${query}`);
        }
        const restaurantData = await response.json();
        console.log(restaurantData);
        // The API returns a double-serialized body string; parse it to access the actual data
        const parsedData = JSON.parse(restaurantData.body);
        console.log(parsedData);
        if (parsedData) {
            // Build and inject HTML for the restaurant profile card
            const resultItem = `
                <h1 id="restaurant-name">${parsedData.restaurantDetails.name}</h1>
                <p id="restaurant-address">Address: ${parsedData.restaurantDetails.address}</p>
                <p id="restaurant-cuisine">Cuisine Type: ${parsedData.restaurantDetails.cuisine}.</p>
            `;
            infoContainer.innerHTML = resultItem; // Update the container with new data
        }
        return restaurantData;
    } catch (error) {
        console.error(error);
        return null;
    }
}
