/**
 * chatbot.js
 *
 * Page: chatbot.html (or any page embedding the chatbot UI)
 *
 * Purpose:
 *   Provides the client-side logic for an AI-powered chatbot interface that
 *   communicates with an Amazon Lex bot via AWS API Gateway. Users can type
 *   messages into an input field and receive natural-language responses from
 *   the bot, which can assist with restaurant reservations and related queries.
 *
 * On Load:
 *   - Instantiates the API Gateway SDK client (apigClientFactory).
 *   - Grabs references to the chat messages container, text input, and send button.
 *   - Attaches event listeners so messages can be sent via button click or Enter key.
 *
 * API Endpoints Called:
 *   - POST /chatbot  (via apigClient.chatbotPost)
 *     Sends the user's message and user_id to the backend Lambda, which forwards
 *     the message to Amazon Lex and returns the bot's response.
 *     Requires: Authorization header containing the Cognito idToken.
 */

// Initialize the API Gateway SDK client using the auto-generated apigClientFactory.
// This client abstracts the signing and request formation for all API Gateway calls.
const apigClient = apigClientFactory.newClient();

// --- DOM References ---
// Container element where both user and bot messages are rendered as child divs.
const messagesContainer = document.getElementById('messages');

// Text input field where the user types their message.
const userInput = document.getElementById('userInput');

// Button that triggers the sendMessage() function when clicked.
const sendMessageButton = document.getElementById('sendMessage');

/**
 * addMessage
 *
 * Creates a new message bubble and appends it to the chat window.
 * After appending, auto-scrolls the messages container to the bottom
 * so the latest message is always visible.
 *
 * @param {string} message - The text content to display in the message bubble.
 * @param {string} type    - A CSS class name that controls visual styling.
 *                           Expected values: 'user-message' or 'bot-message'.
 *
 * DOM Manipulated:
 *   - Appends a new <div> with classes 'message' and the given type
 *     to #messages.
 *   - Updates messagesContainer.scrollTop to scroll to the latest message.
 */
function addMessage(message, type) {
    // Create a new div element to represent a single chat bubble.
    const messageElement = document.createElement('div');

    // Apply the base 'message' class plus the caller-supplied type class
    // (e.g., 'user-message' or 'bot-message') for CSS differentiation.
    messageElement.classList.add('message', type);
    messageElement.textContent = message;

    // Append the bubble to the chat window.
    messagesContainer.appendChild(messageElement);

    // Scroll to the bottom of the messages container so the newest
    // message is always in view without requiring manual scrolling.
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * sendMessage
 *
 * Async function that handles the full lifecycle of sending a user message
 * to the Lex chatbot backend and rendering the bot's reply.
 *
 * Steps:
 *   1. Reads and trims the current value of the text input; exits early if empty.
 *   2. Renders the user's message immediately in the chat window.
 *   3. Clears the input field.
 *   4. Retrieves the Cognito idToken and userId from localStorage;
 *      redirects to login.html if either auth token is absent.
 *   5. POSTs the message and user_id to POST /chatbot via the API Gateway client,
 *      passing the Authorization header.
 *   6. Parses the nested JSON response to extract the Lex plain-text reply.
 *   7. Renders the bot's reply in the chat window.
 *   8. Handles three distinct error scenarios with user-facing feedback:
 *      - HTTP error response (including 401 Unauthorized -> redirect to login).
 *      - No response received (network failure).
 *      - Request setup failure (misconfiguration / unexpected exception).
 *
 * @returns {Promise<void>}
 *
 * API Called:
 *   POST /chatbot  (apigClient.chatbotPost)
 *   Request body: { message: string, user_id: string }
 *   Headers:      { Authorization: <idToken> }
 *
 * DOM Manipulated:
 *   - Reads from #userInput.
 *   - Clears #userInput after reading.
 *   - Calls addMessage() to append bubbles to #messages.
 */
async function sendMessage() {
    // Read the user's typed message and remove leading/trailing whitespace.
    const message = userInput.value.trim();

    // Do nothing if the input is empty to avoid sending blank messages.
    if (!message) return;

    // Immediately render the user's message on the right side of the chat window.
    addMessage(message, 'user-message');

    // Clear the input field to prepare for the next message.
    userInput.value = '';

    try {
        // Retrieve the Cognito ID token stored in localStorage after login.
        // This token is required by API Gateway to authenticate the request.
        const idToken = localStorage.getItem("idToken");
        if (!idToken) {
            // If not authenticated, notify the user and redirect to login.
            alert("You need to log in to make a reservation.");
            window.location.href = "login.html";
            return;
        }

        // Retrieve the user's unique identifier (Cognito sub or custom userId)
        // stored in localStorage. Passed to the backend so the Lex session
        // can be associated with the correct user.
        const userId = localStorage.getItem('userId');

        // Build the additional parameters object that the SDK uses to
        // attach headers to the outbound HTTP request.
        const additionalParams = {
            headers: {
                'Authorization': idToken   // Cognito idToken for API Gateway authorization.
            }
        };

        // Construct the POST request body that the Lambda function expects.
        const body = {
            message: message,   // The user's chat message forwarded to Lex.
            user_id: userId     // Used by the backend to maintain Lex session state per user.
        };

        // Call POST /chatbot through the API Gateway SDK client.
        // The first argument ({}) represents path parameters (none needed here).
        const response = await apigClient.chatbotPost({}, body, additionalParams);

        console.log('RESPONSE', response);

        // The API Gateway response wraps the Lambda output in response.data.body
        // as a JSON string, so it must be parsed before accessing fields.
        const responseBody = JSON.parse(response.data.body);

        // Extract the plain-text Lex response from the nested messages array.
        // Lex returns messages under the 'unstructured' content type with a 'text' field.
        const lexResponse = responseBody.messages[0].unstructured.text;

        // Render the bot's reply on the left side of the chat window.
        addMessage(lexResponse, 'bot-message');
    } catch (error) {
        console.error('Full error:', error);

        // --- Tiered error handling for clear user feedback ---

        if (error.response) {
            // The server responded with a non-2xx HTTP status code.
            console.error('Error response:', error.response.data);
            console.error('Status code:', error.response.status);

            if (error.response.status === 401) {
                // 401 Unauthorized: the token has expired or is invalid.
                // Inform the user and redirect them to re-authenticate.
                addMessage('Authorization failed. Please log in again.', 'bot-message');
                window.location.href = "login.html";
            } else {
                // Other server-side errors: surface the message from the response body.
                addMessage(`Sorry, there was an error: ${error.response.data.message || 'Unknown error'}`, 'bot-message');
            }
        } else if (error.request) {
            // The request was sent but no response was received,
            // typically indicating a network connectivity issue.
            console.error('No response received:', error.request);
            addMessage('No response from server. Please check your connection.', 'bot-message');
        } else {
            // An error occurred before the request could be dispatched
            // (e.g., invalid configuration or unexpected runtime exception).
            console.error('Error setting up request:', error.message);
            addMessage('An unexpected error occurred.', 'bot-message');
        }
    }
}

// --- Event Listeners ---

// Trigger sendMessage() when the user clicks the "Send" button.
sendMessageButton.addEventListener('click', sendMessage);

// Allow the user to send a message by pressing the Enter key in the input field,
// providing a natural keyboard-driven chat experience.
userInput.addEventListener('keypress', (event) => {
    if (event.key === 'Enter') {
        sendMessage();
    }
});
