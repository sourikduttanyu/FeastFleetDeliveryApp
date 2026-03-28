/**
 * reservations-view.js
 *
 * Page: view-reservations.html (user's reservations dashboard)
 *
 * Purpose:
 *   Fetches all reservations belonging to the currently authenticated user
 *   and renders them into two separate sections: upcoming reservations and
 *   past reservations. Each reservation is displayed as a clickable card
 *   that navigates to the individual reservation detail page.
 *
 * On Load (DOMContentLoaded — async):
 *   1. Checks for a valid Cognito idToken in localStorage; redirects to
 *      login.html if the user is not authenticated.
 *   2. Calls GET /reservations via the API Gateway SDK client, passing the
 *      idToken as a Bearer Authorization header.
 *   3. Splits the response into upcoming_reservations and past_reservations
 *      arrays and renders a card for each entry in the respective container.
 *
 * API Endpoints Called:
 *   - GET /reservations
 *       (apigClient.reservationsGet)
 *       Headers:  { Authorization: "Bearer <idToken>" }
 *       Returns:  { past_reservations: [...], upcoming_reservations: [...] }
 *       Each reservation object contains: reservation_id, restaurant_name,
 *       restaurant_address, res_date, time, and party_size.
 */

document.addEventListener("DOMContentLoaded", async () => {
    // Container element for cards representing future/upcoming reservations.
    const upcomingReservationsContainer = document.getElementById("upcoming-reservations");

    // Container element for cards representing past/completed reservations.
    const pastReservationsContainer = document.getElementById("past-reservations");

    // Retrieve the Cognito ID token stored in localStorage after login.
    // This token is required by API Gateway to authenticate the request.
    const idToken = localStorage.getItem("idToken");
    if (!idToken) {
        // Not authenticated — redirect to login before attempting any API calls.
        alert("You need to log in to view reservations.");
        window.location.href = "login.html";
        return;
    }

    try {
        // Instantiate the API Gateway SDK client.
        const apigClient = apigClientFactory.newClient();

        // Attach the Bearer token in the Authorization header so API Gateway
        // can validate the Cognito identity before invoking the Lambda function.
        const additionalParams = {
            headers: {
                Authorization: `Bearer ${idToken}`,
            },
        };

        // Call GET /reservations to retrieve all reservations for the authenticated user.
        // First argument ({}) is path params (none needed).
        // Second argument (null) is the request body — not used for GET requests.
        const response = await apigClient.reservationsGet({}, null, additionalParams);
        console.log("API Response:", response);

        if (response.status === 200) {
            // The Lambda response body is a JSON string nested inside response.data.body;
            // destructure with default empty arrays so the forEach calls below are safe
            // even when one or both arrays are absent from the response.
            const { past_reservations = [], upcoming_reservations = [] } = JSON.parse(response.data.body);

            /**
             * createReservationCard
             *
             * Helper function that builds a single reservation card DOM element.
             * The card displays a thumbnail image alongside key reservation details
             * and is wired with a click handler that navigates to the detail page
             * for that specific reservation.
             *
             * The reservation_id is URL-encoded before being appended as a query
             * parameter to handle IDs that may contain special characters (e.g.,
             * UUIDs with hyphens or composite keys).
             *
             * @param {Object} reservation - A reservation object from the API response.
             *   Expected fields:
             *     - reservation_id    {string}  Unique identifier used to build the detail URL.
             *     - restaurant_name   {string}  Display name of the restaurant.
             *     - party_size        {number}  Number of guests in the reservation.
             *     - res_date          {string}  Reservation date (e.g., "2025-08-15").
             *     - time              {string}  Reservation time (e.g., "19:00").
             *     - restaurant_address {string} Street address of the restaurant.
             *
             * @returns {HTMLDivElement} A fully constructed .reservation-card element
             *   ready to be appended to the DOM.
             */
            const createReservationCard = (reservation) => {
                // Create the outer card container div.
                const card = document.createElement("div");
                card.classList.add("reservation-card");

                // Populate the card with a thumbnail image and a details block.
                // innerHTML is used here for conciseness since all values come
                // from a trusted API response rather than user-supplied input.
                card.innerHTML = `
                    <img src="images/dumplings.png" alt="Restaurant Image">
                    <div class="reservation-details">
                        <h3>${reservation.restaurant_name}</h3>
                        <p><strong>People:</strong> ${reservation.party_size}</p>
                        <p><strong>Date:</strong> ${reservation.res_date}</p>
                        <p><strong>Time:</strong> ${reservation.time}</p>
                        <p><strong>Address:</strong> ${reservation.restaurant_address}</p>
                    </div>
                `;

                // Attach a click listener that navigates to the individual reservation
                // detail page, passing the encoded reservation_id as a query parameter.
                // encodeURIComponent handles any special characters in the ID so
                // the URL remains valid and can be decoded on the detail page.
                card.addEventListener("click", () => {
                    const encodedReservationId = encodeURIComponent(reservation.reservation_id);
                    window.location.href = `view-reservation.html?reservation_id=${encodedReservationId}`;
                });

                return card;
            };

            // Render each upcoming reservation into the upcoming section.
            upcoming_reservations.forEach((reservation) => {
                const card = createReservationCard(reservation);
                upcomingReservationsContainer.appendChild(card);
            });

            // Render each past reservation into the past section.
            past_reservations.forEach((reservation) => {
                const card = createReservationCard(reservation);
                pastReservationsContainer.appendChild(card);
            });
        } else {
            console.error("Failed to fetch reservations:", response);
            alert("Failed to fetch reservations. Please try again later.");
        }
    } catch (error) {
        console.error("Error fetching reservations:", error);
        alert("An unexpected error occurred. Please try again.");
    }
});
