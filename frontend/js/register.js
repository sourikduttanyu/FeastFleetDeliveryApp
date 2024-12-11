document.addEventListener('DOMContentLoaded', () => {
    const registerForm = document.querySelector('.register-form');
    const errorContainer = document.getElementById('register-error');

    registerForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default form submission

        // Clear any previous error messages
        errorContainer.textContent = '';

        // Collect form data
        const formData = new FormData(registerForm);
        const payload = {
            email: formData.get('email'),
            given_name: formData.get('first_name'),
            family_name: formData.get('last_name'),
            phone_number: formData.get('phone'),
            address: formData.get('address'),
            password: formData.get('password'),
            confirm_password: formData.get('confirm_password'),
        };

        if (payload.phone_number[0] !== '+'){
            payload.phone_number = '+' + payload.phone_number;
        }

        // Check if passwords match
        if (payload.password !== payload.confirm_password) {
            errorContainer.textContent = 'Passwords do not match.';
            return;
        }

        try {
            // Initialize the API client
            const apigClient = apigClientFactory.newClient();

            // Call the API using the authRegisterPost function
            const response = await apigClient.authRegisterPost({}, payload, {});

            // Handle the API response
            if (response.status === 200) {
                // Registration successful
                alert('Registration successful!');
                window.location.href = 'login.html'; // Redirect to login page
            } else {
                // Display error from the backend
                const error = await response.data;
                errorContainer.textContent = error.error || 'An error occurred during registration.';
            }
        } catch (error) {
            // Handle any unexpected errors
            errorContainer.textContent = 'An unexpected error occurred. Please try again later.';
            console.error('Error:', error);
        }
    });
});
