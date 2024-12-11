// Load the navbar from navbar.html
document.addEventListener("DOMContentLoaded", () => {
    
    document.querySelectorAll('.category').forEach(button => {
        button.addEventListener('click', () => {
            const location = locationInput.value.trim();
            if (location) {
                const category = button.getAttribute('value'); // Get the category value from the button
                window.location.href = `results.html?type=cuisineType&query=${encodeURIComponent(category)}&location=${encodeURIComponent(location)}`;
            }
            else {
                alert("Please enter your current zip code")
            }
            
        });
    });
    const searchButton = document.querySelector("#search-button");
    const locationInput = document.querySelector("input[placeholder='Current Location']");
    const keywordInput = document.querySelector("input[placeholder='Enter Key words....']");

    searchButton.addEventListener("click", () => {
        const location = locationInput.value.trim();
        const keyword = keywordInput.value.trim();
        if (!location) {
            alert('Please enter your current zip code!');
            return;
        }
        if (keyword) {
        const nextPageUrl = `results.html?type=name&query=${encodeURIComponent(keyword)}&location=${encodeURIComponent(location)}`;;
        window.location.href = nextPageUrl;
        } else {
            alert("Please enter keywords to search.");
        }
    });

});