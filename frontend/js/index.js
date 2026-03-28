/**
 * index.js — Home Page Script
 *
 * Serves: index.html (the main landing / home page of FeastFleet)
 *
 * On Load:
 *   - Attaches click handlers to all cuisine category buttons so users can
 *     browse restaurants by food type.
 *   - Attaches a click handler to the keyword search button so users can
 *     search restaurants by name or keyword.
 *
 * API Endpoints Called:
 *   - None directly from this file. Search parameters are passed as query
 *     string arguments to results.html, which then calls the restaurant
 *     search API.
 *
 * DOM Manipulated:
 *   - Reads value from input[placeholder='Current Location'] (zip code field)
 *   - Reads value from input[placeholder='Enter Key words....'] (keyword field)
 *   - Navigates to results.html with search parameters encoded in the URL
 */

// Wait for the full DOM to be parsed before attaching any event listeners.
document.addEventListener("DOMContentLoaded", () => {

    /**
     * Category Button Click Handlers
     *
     * Iterates over every element with the class "category" (cuisine type
     * buttons rendered in the home page grid) and attaches a click listener
     * to each one.
     *
     * On click:
     *   - Reads the current zip code from the location input.
     *   - If a location is provided, redirects to results.html with:
     *       type=cuisineType  — tells results.js to filter by cuisine
     *       query=<category>  — the cuisine value stored on the button's
     *                           "value" attribute (e.g. "Italian", "Chinese")
     *       location=<zip>    — the user-entered zip code
     *   - If no location is entered, prompts the user to supply one.
     *
     * NOTE: locationInput is declared below this forEach block, but because
     * var/let/const inside a DOMContentLoaded callback are function-scoped to
     * the arrow function, locationInput is accessible here via closure —
     * the click handler only executes after DOMContentLoaded finishes, by
     * which point locationInput has already been assigned.
     */
    document.querySelectorAll('.category').forEach(button => {
        button.addEventListener('click', () => {
            const location = locationInput.value.trim();
            if (location) {
                const category = button.getAttribute('value'); // Get the category value from the button
                // Build the results page URL with cuisine type and location as query parameters
                window.location.href = `results.html?type=cuisineType&query=${encodeURIComponent(category)}&location=${encodeURIComponent(location)}`;
            }
            else {
                // Location is required for proximity-based restaurant search
                alert("Please enter your current zip code")
            }

        });
    });

    // Grab references to the search bar inputs and the search button
    const searchButton = document.querySelector("#search-button");
    const locationInput = document.querySelector("input[placeholder='Current Location']");
    const keywordInput = document.querySelector("input[placeholder='Enter Key words....']");

    /**
     * Search Button Click Handler
     *
     * Triggered when the user clicks the main keyword search button on the
     * home page.
     *
     * Behavior:
     *   - Validates that both a location (zip code) and a keyword have been
     *     entered by the user.
     *   - On valid input, redirects to results.html with:
     *       type=name       — tells results.js to filter by restaurant name/keyword
     *       query=<keyword> — the search term entered by the user
     *       location=<zip>  — the user-entered zip code
     *   - Alerts the user if either required field is empty.
     */
    searchButton.addEventListener("click", () => {
        const location = locationInput.value.trim();
        const keyword = keywordInput.value.trim();

        // Location is mandatory — the API requires it for geo-filtering
        if (!location) {
            alert('Please enter your current zip code!');
            return;
        }
        if (keyword) {
            // Encode both values to safely include them in a URL query string
            const nextPageUrl = `results.html?type=name&query=${encodeURIComponent(keyword)}&location=${encodeURIComponent(location)}`;;
            window.location.href = nextPageUrl;
        } else {
            alert("Please enter keywords to search.");
        }
    });

});
