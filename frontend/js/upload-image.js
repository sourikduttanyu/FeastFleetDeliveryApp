/**
 * upload-image.js
 *
 * Page: upload-image.html (food photo upload / restaurant discovery page)
 *
 * Purpose:
 *   Allows users to upload a food photo and receive AI-powered restaurant
 *   recommendations based on the image content. The image is converted to
 *   a base64 string client-side and sent to a backend Lambda function that
 *   performs image recognition (e.g., via Amazon Rekognition) and returns
 *   matching restaurants.
 *
 * On Load:
 *   - Attaches a 'change' listener to the file input so a preview of the
 *     selected image is shown immediately before uploading.
 *   - Attaches a 'click' listener to the upload button to trigger the
 *     base64 encoding and API submission flow.
 *
 * API Endpoints Called:
 *   - POST https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/images/upload/
 *     Accepts a JSON body with a base64-encoded image string.
 *     Returns a list of recommended restaurants matching the uploaded food image.
 *     Note: Uses the native fetch() API rather than the apigClientFactory SDK.
 */

// The direct HTTPS endpoint for the image upload Lambda function.
// This uses native fetch() instead of the SDK client because the endpoint
// does not require Cognito authorization headers.
const API_URL = "https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/images/upload/";

// --- DOM References ---

// The hidden <input type="file"> element that triggers the OS file picker.
const imageUpload = document.getElementById('imageUpload');

// The <img> element used to display a preview of the selected image.
const previewImage = document.getElementById('previewImage');

// The upload icon (typically a "+" or camera icon) shown before an image is selected.
// It is hidden once a preview is available so only the preview is visible.
const uploadIcon = document.querySelector('.upload-icon');

/**
 * Image Preview Listener (anonymous — attached to #imageUpload 'change' event)
 *
 * Fires whenever the user selects a file from the OS file picker.
 * Uses the FileReader API to read the selected file as a data URL
 * (base64-encoded string), which is then set as the src of the preview image.
 *
 * DOM Manipulated:
 *   - Sets #previewImage.src to the base64 data URL of the selected file.
 *   - Makes #previewImage visible (display: 'block').
 *   - Hides the .upload-icon element so the preview takes its place.
 */
imageUpload.addEventListener('change', (event) => {
    // event.target.files is a FileList; index 0 gets the first (and only) selected file.
    const file = event.target.files[0];

    if (file) {
        // FileReader reads the binary file data asynchronously in the browser.
        const reader = new FileReader();

        // onload fires once readAsDataURL() has finished converting the file.
        reader.onload = () => {
            // reader.result contains the full data URL, e.g.:
            // "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."
            // Setting it as the img src renders the preview instantly.
            previewImage.src = reader.result;
            previewImage.style.display = 'block';

            // Hide the placeholder upload icon now that a preview is shown.
            uploadIcon.style.display = 'none';
        };

        // Start reading the file; triggers the onload callback when complete.
        reader.readAsDataURL(file);
    }
});

/**
 * Upload Button Click Handler (anonymous — attached to #uploadButton 'click' event)
 *
 * Handles the full image upload lifecycle:
 *   1. Validates that a file has been selected.
 *   2. Uses FileReader to convert the image file to a base64 string.
 *   3. Strips the data URL metadata prefix (e.g., "data:image/jpeg;base64,")
 *      so only the raw base64 payload is sent to the API.
 *   4. POSTs the base64 string as JSON to the image upload API endpoint.
 *   5. Parses the doubly-nested JSON response body (API Gateway wraps
 *      Lambda's string body in an outer JSON envelope).
 *   6. Calls renderRestaurants() if matching restaurants are returned.
 *
 * API Called:
 *   POST /dev/images/upload/
 *   Request body: { body: "<base64ImageString>" }
 *   Response body (after double-parse): { restaurants: [...] }
 *
 * DOM Manipulated:
 *   - Reads the selected file from #imageUpload.
 *   - Calls renderRestaurants() which modifies #resultsContainer.
 *
 * @returns {Promise<void>}
 */
document.getElementById('uploadButton').addEventListener('click', async () => {
    // Retrieve the file currently selected in the file input.
    const file = imageUpload.files[0];

    // Guard: abort if no file has been selected yet.
    if (!file) {
        alert('Please select an image before uploading.');
        return;
    }

    try {
        // Use FileReader again here to convert the image to base64 for the API call.
        // A second FileReader instance is created rather than reusing the preview one
        // to keep the upload flow independent of the preview flow.
        const reader = new FileReader();

        // onloadend fires after readAsDataURL() finishes (same as onload but also
        // fires on error/abort, making it slightly safer for upload scenarios).
        reader.onloadend = async () => {
            // reader.result is a full data URL: "data:<mime>;base64,<data>"
            // Split on the comma and take index 1 to strip the metadata prefix,
            // leaving only the pure base64-encoded image data for the API.
            const base64Image = reader.result.split(',')[1];

            // POST the base64 image string to the image recognition API.
            // native fetch() is used here because the endpoint does not require
            // the AWS SDK request signing that apigClientFactory provides.
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                // Wrap base64 data in a JSON body with the key 'body',
                // as expected by the Lambda function's event structure.
                body: JSON.stringify({
                    body: base64Image
                }),
            });

            // If the HTTP response status is not in the 2xx range, throw an
            // error with the status text and raw response body for debugging.
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Error: ${response.statusText} - ${errorText}`);
            }

            // Parse the outer JSON envelope returned by API Gateway.
            const responseBody = await response.json();
            console.log('API Response:', responseBody);

            // The Lambda returns its output as a JSON *string* in responseBody.body,
            // so it must be parsed a second time to access the actual data object.
            const parsedBody = JSON.parse(responseBody.body);
            console.log('Parsed API Response Body:', parsedBody);

            // Extract the restaurants array; default to empty array if not present.
            const restaurants = parsedBody.restaurants || [];

            if (restaurants.length > 0) {
                alert('Image uploaded successfully!');
                // Pass the array to the rendering function to build the results list.
                renderRestaurants(restaurants);
            } else {
                alert('No restaurants found for the uploaded image.');
            }
        };

        // Kick off the async file read. The onloadend handler above will fire
        // once the conversion is complete.
        reader.readAsDataURL(file);
    } catch (error) {
        console.error('Upload failed:', error);
        alert('Failed to upload the image. Please try again.');
    }
});

/**
 * renderRestaurants
 *
 * Clears the results container and builds a card-based UI listing all
 * restaurants returned by the image recognition API. Each card is a
 * clickable link that navigates to the restaurant's detail page.
 *
 * @param {Array<Object>} restaurants - Array of restaurant objects returned by the API.
 *   Each object is expected to contain:
 *     - restaurant_id  {string}  Unique identifier used to build the detail page URL.
 *     - name           {string}  Display name of the restaurant.
 *     - address        {string}  Street address shown on the card.
 *     - cuisine        {string}  Cuisine type label shown on the card.
 *
 * DOM Manipulated:
 *   - Clears and repopulates #resultsContainer with a heading and one
 *     .restaurant-card <div> per restaurant.
 *   - Each card contains a thumbnail image, restaurant name, address,
 *     and cuisine type, all wrapped in an anchor tag linking to
 *     restaurant-info.html?query=<restaurant_id>.
 */
function renderRestaurants(restaurants) {
    // Get the container element that will hold all restaurant result cards.
    const resultsContainer = document.getElementById('resultsContainer');

    // Clear any previously rendered results and add a section heading.
    resultsContainer.innerHTML = "<div><h3>Recommended Restaurants:</h3></div>";

    // Iterate over each restaurant object and build its HTML card string.
    restaurants.forEach((restaurant) => {
        // Build the HTML for a single restaurant card using a template literal.
        // The restaurant_id is passed as a query parameter so restaurant-info.html
        // can fetch the full restaurant details on that page load.
        const resultItem = `
            <div class="restaurant-card">
                <a href="restaurant-info.html?query=${restaurant.restaurant_id}">
                    <div class="image">
                        <img src="images/restaurant.jpg" alt="${restaurant.name}">
                    </div>
                    <div class="info">
                        <h3 class="restaurant-name">${restaurant.name}</h3>
                        <p class="address">${restaurant.address}</p>
                        <p><strong>Cuisine:</strong> ${restaurant.cuisine}</p>
                    </div>
                </a>
            </div>
        `;

        // Append the card HTML string to the results container.
        // += is used instead of appendChild() because resultItem is an HTML string,
        // not a DOM node. Note: repeated innerHTML += re-parses the entire container
        // each iteration, which is acceptable for small result sets.
        resultsContainer.innerHTML += resultItem;
    });
}
