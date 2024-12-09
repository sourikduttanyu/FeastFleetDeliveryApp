document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.querySelector('.login-form');
    const errorContainer = document.getElementById('login-error');

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default form submission

        // Clear any previous error messages
        errorContainer.textContent = '';

        // Collect form data
        const formData = new FormData(loginForm);
        const payload = {
            email: formData.get('email'),
            password: formData.get('password')
        };

        try {
            // Initialize the API client
            const apigClient = apigClientFactory.newClient();

            // Call the API using the authLoginPost function
            const response = await apigClient.authLoginPost({}, payload, {});

            // Log the full response for debugging
            console.log('API Response:', response);

            // Handle the API response
            if (response.status === 200) {
                // Access the nested AuthenticationResult directly
                const authResult = response.data.body.AuthenticationResult;

                if (authResult && authResult.IdToken && authResult.AccessToken && authResult.RefreshToken) {
                    // Store tokens in localStorage
                    localStorage.setItem('idToken', authResult.IdToken);
                    localStorage.setItem('accessToken', authResult.AccessToken);
                    localStorage.setItem('refreshToken', authResult.RefreshToken);
                    localStorage.setItem('email', payload.email);
                
                    // Parse the ID token to get user info
                    const tokenPayloadBase64 = authResult.IdToken.split('.')[1];
                    const decodedPayload = JSON.parse(atob(tokenPayloadBase64));
                    
                    // Extract and store the userId
                    const userId = decodedPayload.sub; // 'sub' is the unique user identifier
                    localStorage.setItem('userId', userId);

                    console.log('USER_ID: ', localStorage.getItem('userId'))
                    console.log('EMAIL: ', localStorage.getItem('email'))

                    alert('Login successful!');
                    window.location.href = 'index.html'; // Redirect to the user's home page
                } else {
                    errorContainer.textContent = 'Unexpected response structure. Please try again.';
                    console.error('Tokens missing in response:', response);
                }
            } else {
                // Display error from the backend
                const error = response.data.error || 'Login failed. Please try again.';
                errorContainer.textContent = error;
            }
        } catch (error) {
            // Handle any unexpected errors
            errorContainer.textContent = 'An unexpected error occurred. Please try again later.';
            console.error('Error:', error);
        }
    });
});
