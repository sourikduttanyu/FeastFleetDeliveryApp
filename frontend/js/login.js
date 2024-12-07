document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.querySelector('.login-form');
    const errorDiv = document.getElementById('login-error');

    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const email = this.email.value;
        const password = this.password.value;

        try {
            const response = await fetch('https://930lk1e388.execute-api.us-east-1.amazonaws.com/dev/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            });

            const data = await response.json();

            if (response.status === 200) {
                // Store tokens and user info
                localStorage.setItem('token', data.body.AuthenticationResult.IdToken);
                localStorage.setItem('refreshToken', data.body.AuthenticationResult.RefreshToken);
                localStorage.setItem('email', email);
                
                // Parse the ID token to get user info
                const tokenPayload = JSON.parse(atob(data.body.AuthenticationResult.IdToken.split('.')[1]));
                localStorage.setItem('userId', tokenPayload.sub);  // 'sub' claim is the user's unique identifier
                
                // Redirect to main page
                window.location.href = 'index.html';
            } else {
                errorDiv.textContent = data.body || 'Login failed. Please try again.';
                errorDiv.classList.add('active');
            }

        } catch (error) {
            console.error('Login error:', error);
            errorDiv.textContent = 'An error occurred. Please try again later.';
            errorDiv.classList.add('active');
        }
    });
});