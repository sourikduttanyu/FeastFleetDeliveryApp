/**
 * navbar.js — Shared Navbar Script
 *
 * Serves: All pages that include a <div id="navbar"></div> placeholder
 *         (index.html, results.html, restaurant-info.html, etc.)
 *
 * On Load:
 *   - Fetches the shared navbar markup from navbar.html via a fetch() call and
 *     injects it into the #navbar placeholder element.
 *   - After the navbar HTML is injected, calls initializeNavbarAuth() to wire
 *     up the dynamic login/logout link based on the user's session state.
 *
 * API Endpoints Called:
 *   - GET navbar.html  — fetches the shared navbar HTML fragment (local file).
 *   - POST /auth/logout  (via the AWS API Gateway SDK: apigClient.authLogoutPost)
 *       Request body: { access_token }
 *       Called only when a logged-in user clicks the "Logout" link.
 *
 * DOM Manipulated:
 *   - #navbar     — innerHTML is replaced with the fetched navbar markup
 *   - #auth-link  — text content and href are updated based on auth state;
 *                   a click listener is attached when the user is logged in
 *
 * localStorage Keys Read:
 *   - accessToken — presence indicates the user has an active session
 *
 * localStorage Keys Removed on Logout:
 *   - idToken, accessToken, refreshToken, email, userId
 */

// Wait for the full DOM to be ready before fetching and injecting the navbar.
document.addEventListener('DOMContentLoaded', () => {
    // Load the navbar from navbar.html
    // The navbar is stored as a separate HTML fragment to allow it to be
    // reused across all pages without duplicating markup.
    fetch('navbar.html')
        .then((response) => response.text()) // Read the response as plain text (HTML string)
        .then((data) => {
            // Insert the navbar into the DOM
            // Inject the fetched HTML string into the designated navbar placeholder
            document.getElementById('navbar').innerHTML = data;

            // Initialize the navbar functionality
            // Auth-dependent logic must run AFTER the navbar HTML exists in the DOM
            initializeNavbarAuth();
        })
        .catch((error) => console.error('Error loading navbar:', error));
});

/**
 * initializeNavbarAuth
 *
 * Checks whether the user is currently authenticated by looking for an
 * "accessToken" key in localStorage. Based on this, it updates the #auth-link
 * element in the navbar to show either "Login" or "Logout".
 *
 * If logged in:
 *   - Sets the link text to "Logout".
 *   - Attaches a click handler that calls the logout API, clears all auth
 *     tokens from localStorage, and redirects the user to login.html.
 *
 * If not logged in:
 *   - Sets the link text to "Login" and points the href to login.html.
 *
 * DOM: Reads and mutates #auth-link (text, href, click listener).
 *
 * API (when logged in and logout is clicked):
 *   POST /auth/logout  — invalidates the Cognito session server-side.
 *
 * Returns: void
 */
function initializeNavbarAuth() {
    // Locate the dynamic login/logout anchor in the freshly-injected navbar
    const authLink = document.getElementById('auth-link');

    if (!authLink) {
        // Guard: if the navbar template is missing the #auth-link element, bail early
        console.error('auth-link element not found!');
        return;
    }

    // Simulated authentication check
    // If an accessToken exists in localStorage, the user has an active session
    const isLoggedIn = localStorage.getItem('accessToken') !== null; // Check if accessToken exists

    if (isLoggedIn) {
        // If the user is logged in, show "Logout"
        authLink.textContent = 'Logout';
        // Use javascript:void(0) to prevent the link from navigating before the
        // async logout handler completes
        authLink.href = 'javascript:void(0);'; // Prevent navigation for logout

        /**
         * Logout Click Handler
         *
         * Reads the stored accessToken from localStorage and sends it to the
         * logout API to invalidate the Cognito session server-side. On a
         * successful response, all auth-related localStorage entries are
         * removed and the user is redirected to login.html.
         *
         * @param {Event} (implicit click event)
         */
        authLink.addEventListener('click', async () => {
            try {
                // Get the access token from localStorage
                // This token is sent to the server to invalidate the Cognito session
                const accessToken = localStorage.getItem('accessToken');

                if (!accessToken) {
                    // Edge case: auth link showed "Logout" but token was already gone
                    alert('No active session found. Redirecting to login.');
                    window.location.href = 'login.html';
                    return;
                }

                // Initialize the API client
                // apigClientFactory is provided by the AWS API Gateway-generated SDK
                const apigClient = apigClientFactory.newClient();

                // Call the API using the logout endpoint
                // Sends the accessToken so the backend can globally sign out the user
                const response = await apigClient.authLogoutPost({}, { access_token: accessToken }, {});

                if (response.status === 200) {
                    // Clear tokens from localStorage so the app treats the user as signed out
                    // All five keys that were stored during login are removed here
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
                // Catch network errors or unexpected runtime exceptions
                console.error('Error:', error);
                alert('An unexpected error occurred. Please try again later.');
            }
        });
    } else {
        // If the user is not logged in, show "Login" as a standard navigation link
        authLink.textContent = 'Login';
        authLink.href = 'login.html'; // Redirect to login page
    }
}
