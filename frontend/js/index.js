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
    
    document.querySelectorAll('.category').forEach(button => {
        button.addEventListener('click', () => {
            const category = button.getAttribute('value'); // Get the category value from the button
            window.location.href = `results.html?type=cuisineType&query=${encodeURIComponent(category)}`;
        });
    });
    const searchButton = document.querySelector("#search-button");
    const locationInput = document.querySelector("input[placeholder='Current Location']");
    const keywordInput = document.querySelector("input[placeholder='Enter Key words....']");

    searchButton.addEventListener("click", () => {
        const location = locationInput.value.trim();
        const keyword = keywordInput.value.trim();

        if (keyword) {
        const nextPageUrl = `results.html?type=name&query=${encodeURIComponent(keyword)}`;;
        window.location.href = nextPageUrl;
        } else {
        alert("Please enter keywords to search.");
        }
    });

});