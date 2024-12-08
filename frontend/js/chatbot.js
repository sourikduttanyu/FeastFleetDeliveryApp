document.addEventListener('DOMContentLoaded', () => {
    fetch('navbar.html')
        .then(response => response.text())
        .then(data => {
            document.getElementById('navbar').innerHTML = data;
        })
        .catch(error => console.error('Error loading navbar:', error));

    const messages = document.getElementById('messages');
    const userInput = document.getElementById('userInput');
    const sendMessage = document.getElementById('sendMessage');

    sendMessage.addEventListener('click', () => {
        const userMessage = userInput.value.trim();
        if (userMessage) {
            const userMessageElement = document.createElement('div');
            userMessageElement.className = 'message user-message';
            userMessageElement.textContent = userMessage;
            messages.appendChild(userMessageElement);
            userInput.value = '';

            // Simulate bot response
            const botMessageElement = document.createElement('div');
            botMessageElement.className = 'message bot-message';
            botMessageElement.textContent = 'Thank you for your message! How can I assist you?';
            messages.appendChild(botMessageElement);

            // Scroll to the bottom
            messages.scrollTop = messages.scrollHeight;
        }
    });
});