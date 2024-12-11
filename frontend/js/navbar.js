document.addEventListener('DOMContentLoaded', () => {
    // Load the navbar from navbar.html
    fetch('navbar.html')
        .then((response) => response.text())
        .then((data) => {
            // Insert the navbar into the DOM
            document.getElementById('navbar').innerHTML = data;

            // Initialize the navbar functionality
            initializeNavbarAuth();
        })
        .catch((error) => console.error('Error loading navbar:', error));
});

// Function to handle the login/logout logic for the navbar
function initializeNavbarAuth() {
    const authLink = document.getElementById('auth-link');

    if (!authLink) {
        console.error('auth-link element not found!');
        return;
    }

    // Simulated authentication check
    const isLoggedIn = localStorage.getItem('accessToken') !== null; // Check if accessToken exists

    if (isLoggedIn) {
        // If the user is logged in, show "Logout"
        authLink.textContent = 'Logout';
        authLink.href = 'javascript:void(0);'; // Prevent navigation for logout
        authLink.addEventListener('click', async () => {
            try {
                // Get the access token from localStorage
                const accessToken = localStorage.getItem('accessToken');

                if (!accessToken) {
                    alert('No active session found. Redirecting to login.');
                    window.location.href = 'login.html';
                    return;
                }

                // Initialize the API client
                const apigClient = apigClientFactory.newClient();

                // Call the API using the logout endpoint
                const response = await apigClient.authLogoutPost({}, { access_token: accessToken }, {});

                if (response.status === 200) {
                    // Clear tokens from localStorage
                    localStorage.removeItem('idToken');
                    localStorage.removeItem('accessToken');
                    localStorage.removeItem('refreshToken');
                    localStorage.removeItem('email');
                    localStorage.removeItem('userId');

                    alert('You have been logged out.');
                    window.location.href = 'login.html'; // Redirect to login page
                } else {
                    console.error('Logout failed:', response);
                    alert('An error occurred during logout. Please try again.');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An unexpected error occurred. Please try again later.');
            }
        });
    } else {
        // If the user is not logged in, show "Login"
        authLink.textContent = 'Login';
        authLink.href = 'login.html'; // Redirect to login page
    }
}
