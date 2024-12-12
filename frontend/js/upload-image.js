// Define your API Gateway URL
const API_URL = "https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/images/upload/";

// Show image preview
const imageUpload = document.getElementById('imageUpload');
const previewImage = document.getElementById('previewImage');
const uploadIcon = document.querySelector('.upload-icon');

imageUpload.addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = () => {
            previewImage.src = reader.result;
            previewImage.style.display = 'block';
            uploadIcon.style.display = 'none'; // Hide the plus icon
        };
        reader.readAsDataURL(file);
    }
});

// Upload image to API
document.getElementById('uploadButton').addEventListener('click', async () => {
    const file = imageUpload.files[0];
    if (!file) {
        alert('Please select an image before uploading.');
        return;
    }

    try {
        // Convert image to base64
        const reader = new FileReader();
        reader.onloadend = async () => {
            const base64Image = reader.result.split(',')[1]; // Strip metadata prefix

            // Make the API request
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    body: base64Image
                }),
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Error: ${response.statusText} - ${errorText}`);
            }

            // Parse the response body
            const responseBody = await response.json();
            console.log('API Response:', responseBody);

            // Parse the nested body field (since it is a JSON string)
            const parsedBody = JSON.parse(responseBody.body);
            console.log('Parsed API Response Body:', parsedBody);

            const restaurants = parsedBody.restaurants || [];
            if (restaurants.length > 0) {
                alert('Image uploaded successfully!');
                renderRestaurants(restaurants);
            } else {
                alert('No restaurants found for the uploaded image.');
            }
        };
        reader.readAsDataURL(file);
    } catch (error) {
        console.error('Upload failed:', error);
        alert('Failed to upload the image. Please try again.');
    }
});

function renderRestaurants(restaurants) {
    const resultsContainer = document.getElementById('resultsContainer');
    resultsContainer.innerHTML = "<div><h3>Recommended Restaurants:</h3></div>";

    restaurants.forEach((restaurant) => {
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
        resultsContainer.innerHTML += resultItem;
    });
}

