/**
 * register.js — Registration Page Script
 *
 * Serves: register.html (the new user sign-up / account creation page)
 *
 * On Load:
 *   - Locates the registration form element (.register-form) and the error
 *     display container (#register-error).
 *   - Attaches an async submit handler to the form that validates input and
 *     sends user data to the registration API.
 *
 * API Endpoints Called:
 *   - POST /auth/register  (via the AWS API Gateway SDK: apigClient.authRegisterPost)
 *       Request body: { email, given_name, family_name, phone_number, address,
 *                       password, confirm_password }
 *       On success (HTTP 200): user account is created in AWS Cognito and the
 *                              page redirects to login.html.
 *
 * DOM Manipulated:
 *   - .register-form   — form whose submit event is intercepted
 *   - #register-error  — text content is set to display validation or API errors
 */

// Wait for the full DOM to be ready before querying form elements.
document.addEventListener('DOMContentLoaded', () => {
    // Select the registration form and the error message display container
    const registerForm   = document.querySelector('.register-form');
    const errorContainer = document.getElementById('register-error');

    /**
     * Registration Form Submit Handler
     *
     * Intercepts the form's default submission, collects and validates all
     * registration fields, then sends the data to the registration API via
     * the AWS API Gateway SDK client.
     *
     * Validation performed client-side before the API call:
     *   1. Ensures the phone number starts with '+' (E.164 format required by
     *      AWS Cognito). Prepends '+' if it is missing.
     *   2. Ensures the "password" and "confirm_password" fields match.
     *
     * On success (HTTP 200):
     *   - Alerts the user and redirects to login.html.
     *
     * On failure:
     *   - Displays a human-readable error message inside #register-error.
     *
     * @param {Event} event - The form submit event; default behavior is prevented.
     */
    registerForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default form submission

        // Clear any previous error messages so stale errors don't confuse the user
        errorContainer.textContent = '';

        // Collect form data
        // FormData reads each input's "name" attribute to map field values
        const formData = new FormData(registerForm);
        const payload = {
            email:            formData.get('email'),
            given_name:       formData.get('first_name'),
            family_name:      formData.get('last_name'),
            phone_number:     formData.get('phone'),
            address:          formData.get('address'),
            password:         formData.get('password'),
            confirm_password: formData.get('confirm_password'),
        };

        // AWS Cognito requires phone numbers in E.164 format (e.g. "+15551234567").
        // If the user omitted the leading '+', prepend it automatically.
        if (payload.phone_number[0] !== '+'){
            payload.phone_number = '+' + payload.phone_number;
        }

        // Check if passwords match before hitting the API to save a round trip
        if (payload.password !== payload.confirm_password) {
            errorContainer.textContent = 'Passwords do not match.';
            return; // Abort submission early — no API call is made
        }

        try {
            // Initialize the API client
            // apigClientFactory is provided by the AWS API Gateway-generated SDK
            const apigClient = apigClientFactory.newClient();

            // Call the API using the authRegisterPost function
            // Arguments: pathParams (empty), body payload, additionalParams (empty)
            const response = await apigClient.authRegisterPost({}, payload, {});

            // Handle the API response
            if (response.status === 200) {
                // Registration successful — redirect the user to the login page
                alert('Registration successful!');
                window.location.href = 'login.html'; // Redirect to login page
            } else {
                // Display error from the backend (e.g. email already exists)
                const error = await response.data;
                errorContainer.textContent = error.error || 'An error occurred during registration.';
            }
        } catch (error) {
            // Catch network errors or unexpected runtime exceptions
            errorContainer.textContent = 'An unexpected error occurred. Please try again later.';
            console.error('Error:', error);
        }
    });
});
