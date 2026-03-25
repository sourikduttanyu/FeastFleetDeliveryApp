/**
 * login.js — Login Page Script
 *
 * Serves: login.html (the user authentication / sign-in page)
 *
 * On Load:
 *   - Locates the login form element (.login-form) and the error display
 *     container (#login-error).
 *   - Attaches an async submit handler to the form that sends credentials to
 *     the authentication API.
 *
 * API Endpoints Called:
 *   - POST /auth/login  (via the AWS API Gateway SDK: apigClient.authLoginPost)
 *       Request body: { email, password }
 *       On success: returns an AuthenticationResult object containing
 *                   IdToken, AccessToken, and RefreshToken (AWS Cognito tokens).
 *
 * DOM Manipulated:
 *   - .login-form      — form whose submit event is intercepted
 *   - #login-error     — text content is set to display validation or API errors
 *
 * localStorage Keys Written on Successful Login:
 *   - idToken      — Cognito ID token (used for identifying the user)
 *   - accessToken  — Cognito access token (used for authorizing API calls)
 *   - refreshToken — Cognito refresh token (used to obtain new access tokens)
 *   - email        — The email address the user logged in with
 *   - userId       — The user's unique Cognito sub (subject) identifier,
 *                    decoded from the JWT payload of the ID token
 */

// Wait for the full DOM to be ready before querying form elements.
document.addEventListener('DOMContentLoaded', () => {
    // Select the login form and the error message display container
    const loginForm      = document.querySelector('.login-form');
    const errorContainer = document.getElementById('login-error');

    /**
     * Login Form Submit Handler
     *
     * Intercepts the form's default submission, collects the user's email and
     * password, and sends them to the authentication API via the AWS API
     * Gateway SDK client.
     *
     * On success (HTTP 200):
     *   - Stores all three Cognito tokens in localStorage.
     *   - Decodes the JWT ID token (Base64) to extract the user's unique "sub"
     *     identifier and stores it in localStorage as "userId".
     *   - Redirects the user to index.html.
     *
     * On failure:
     *   - Displays a human-readable error message inside #login-error.
     *
     * @param {Event} event - The form submit event; default behavior is prevented.
     */
    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default form submission

        // Clear any previous error messages so stale errors don't confuse the user
        errorContainer.textContent = '';

        // Collect form data
        // FormData reads each input's "name" attribute to map values
        const formData = new FormData(loginForm);
        const payload = {
            email:    formData.get('email'),
            password: formData.get('password')
        };

        try {
            // Initialize the API client
            // apigClientFactory is provided by the AWS API Gateway-generated SDK
            const apigClient = apigClientFactory.newClient();

            // Call the API using the authLoginPost function
            // Arguments: pathParams (empty), body payload, additionalParams (empty)
            const response = await apigClient.authLoginPost({}, payload, {});

            // Log the full response for debugging
            console.log('API Response:', response);

            // Handle the API response
            if (response.status === 200) {
                // Access the nested AuthenticationResult directly
                // The Cognito response is nested: response.data.body.AuthenticationResult
                const authResult = response.data.body.AuthenticationResult;

                if (authResult && authResult.IdToken && authResult.AccessToken && authResult.RefreshToken) {
                    // Store tokens in localStorage so they can be used across pages
                    // for authenticated API calls and session persistence
                    localStorage.setItem('idToken',      authResult.IdToken);
                    localStorage.setItem('accessToken',  authResult.AccessToken);
                    localStorage.setItem('refreshToken', authResult.RefreshToken);
                    localStorage.setItem('email',        payload.email);

                    // Parse the ID token to get user info
                    // A JWT is three Base64URL-encoded segments separated by dots.
                    // The second segment (index 1) is the payload containing user claims.
                    const tokenPayloadBase64 = authResult.IdToken.split('.')[1];
                    const decodedPayload     = JSON.parse(atob(tokenPayloadBase64));

                    // Extract and store the userId
                    // 'sub' (subject) is the standard JWT claim for a unique user ID,
                    // which AWS Cognito sets to the user's UUID.
                    const userId = decodedPayload.sub;
                    localStorage.setItem('userId', userId);

                    console.log('USER_ID: ', localStorage.getItem('userId'))
                    console.log('EMAIL: ',   localStorage.getItem('email'))

                    alert('Login successful!');
                    window.location.href = 'index.html'; // Redirect to the user's home page
                } else {
                    // Tokens were missing from an otherwise successful response —
                    // indicates an unexpected backend response shape
                    errorContainer.textContent = 'Unexpected response structure. Please try again.';
                    console.error('Tokens missing in response:', response);
                }
            } else {
                // Display error from the backend (e.g. wrong password, user not found)
                const error = response.data.error || 'Login failed. Please try again.';
                errorContainer.textContent = error;
            }
        } catch (error) {
            // Catch network errors or unexpected runtime exceptions
            errorContainer.textContent = 'An unexpected error occurred. Please try again later.';
            console.error('Error:', error);
        }
    });
});
