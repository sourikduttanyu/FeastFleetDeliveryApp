/**
 * reservation-view.js
 *
 * Page: view-reservation.html (single reservation detail & cancellation page)
 *
 * Purpose:
 *   Displays the full details of a single reservation identified by a URL query
 *   parameter. The user can also cancel their reservation from this page.
 *   Both the detail view and the cancellation action require the user to be
 *   authenticated via a Cognito idToken stored in localStorage.
 *
 * On Load (DOMContentLoaded):
 *   1. Reads `reservation_id` from the URL query string (URL-decoded).
 *   2. Redirects to reservations.html if the reservation ID is missing.
 *   3. Calls loadReservationDetails() to fetch and render the reservation data.
 *
 * API Endpoints Called:
 *   - GET  /reservations/view
 *       (apigClient.reservationsViewGet)
 *       Params:   { reservation_id }
 *       Headers:  { Authorization: "Bearer <idToken>" }
 *       Returns:  a reservation object with restaurant_name, restaurant_address,
 *                 res_date, time, and party_size fields.
 *
 *   - DELETE /reservations
 *       (apigClient.reservationsDelete)
 *       Body:    { reservation_id }
 *       Headers: { Authorization: "Bearer <idToken>" }
 *       Cancels the reservation and redirects to view-reservations.html on success.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Parse query parameters from the current page URL.
    // Expected param: ?reservation_id=<encoded_id>
    const urlParams = new URLSearchParams(window.location.search);

    // Decode the reservation_id in case it contains special characters
    // (e.g., UUIDs with hyphens that were encoded by encodeURIComponent on the list page).
    const reservationId = decodeURIComponent(urlParams.get('reservation_id'));

    // Guard: if no reservation ID is present in the URL, the page cannot function.
    // Redirect the user back to the reservations list immediately.
    if (!reservationId) {
        alert("Reservation ID is missing.");
        window.location.href = "reservations.html";
        return;
    }

    console.log("RES_ID: ", reservationId);

    /**
     * loadReservationDetails
     *
     * Async function that fetches a single reservation's details from the API
     * and populates the corresponding DOM elements on the page.
     *
     * Steps:
     *   1. Checks for a valid Cognito idToken in localStorage; redirects to
     *      login.html if absent.
     *   2. Calls GET /reservations/view with the reservation_id as a query param
     *      and the idToken as a Bearer Authorization header.
     *   3. Parses the response body (a JSON string) and injects each field
     *      into its respective element on the page.
     *
     * API Called:
     *   GET /reservations/view  (apigClient.reservationsViewGet)
     *   Query params: { reservation_id }
     *   Headers:      { Authorization: "Bearer <idToken>" }
     *
     * DOM Manipulated:
     *   - #restaurant-name      -> reservation.restaurant_name
     *   - #restaurant-address   -> reservation.restaurant_address
     *   - #reservation-date     -> reservation.res_date
     *   - #reservation-time     -> reservation.time
     *   - #party-size           -> reservation.party_size
     *
     * @returns {Promise<void>}
     */
    async function loadReservationDetails() {
        try {
            // Instantiate the API Gateway SDK client for this request.
            const apigClient = apigClientFactory.newClient();

            // Retrieve the Cognito ID token used to authenticate the API request.
            const idToken = localStorage.getItem("idToken");
            if (!idToken) {
                // Not authenticated — redirect to login before attempting the API call.
                alert("You need to log in to view reservations.");
                window.location.href = "login.html";
                return;
            }

            // Build the query string parameter object for the GET request.
            const params = {
                reservation_id: reservationId,
            };

            // Attach the Bearer token in the Authorization header so API Gateway
            // can validate the Cognito identity before invoking the Lambda function.
            const additionalParams = {
                headers: {
                    Authorization: `Bearer ${idToken}`,
                },
            };

            // Call GET /reservations/view with the reservation ID and auth header.
            // Second argument (null) is the request body — not used for GET requests.
            const response = await apigClient.reservationsViewGet(params, null, additionalParams);
            console.log('RESPONSE ', response)

            if (response.status === 200) {
                // The Lambda response body is a JSON string nested inside response.data.body;
                // it must be explicitly parsed before accessing individual fields.
                const reservation = JSON.parse(response.data.body);

                // Populate each detail field on the page with the returned reservation data.
                document.getElementById("restaurant-name").textContent = reservation.restaurant_name;
                document.getElementById("restaurant-address").textContent = reservation.restaurant_address;
                document.getElementById("reservation-date").textContent = reservation.res_date;
                document.getElementById("reservation-time").textContent = reservation.time;
                document.getElementById("party-size").textContent = reservation.party_size;
            } else {
                alert("Failed to load reservation details.");
                console.error(response);
            }
        } catch (error) {
            console.error("Error fetching reservation details:", error);
        }
    }

    /**
     * cancelReservation
     *
     * Exposed on the global window object so it can be called directly from
     * an inline onclick attribute in the HTML (e.g., onclick="cancelReservation()").
     *
     * Handles the full reservation cancellation lifecycle:
     *   1. Shows a browser confirm dialog asking the user to confirm the action.
     *   2. Checks for a valid Cognito idToken; redirects to login if absent.
     *   3. Sends DELETE /reservations with the reservation_id in the request body.
     *   4. On success, alerts the user and redirects to view-reservations.html.
     *
     * API Called:
     *   DELETE /reservations  (apigClient.reservationsDelete)
     *   Body:    { reservation_id }
     *   Headers: { Authorization: "Bearer <idToken>" }
     *
     * @returns {Promise<void>}
     */
    window.cancelReservation = async function () {
        // Confirm destructive action with the user before proceeding.
        if (!confirm("Are you sure you want to cancel this reservation?")) {
            return;
        }

        try {
            // Instantiate the API Gateway SDK client for this request.
            const apigClient = apigClientFactory.newClient();

            // Retrieve the Cognito ID token for authenticated API access.
            const idToken = localStorage.getItem("idToken");
            if (!idToken) {
                // Not authenticated — redirect to login before attempting the API call.
                alert("You need to log in to cancel reservations.");
                window.location.href = "login.html";
                return;
            }

            // Build the DELETE request body containing the ID of the reservation to cancel.
            const body = {
                reservation_id: reservationId,
            };

            // Attach the Bearer token in the Authorization header.
            const additionalParams = {
                headers: {
                    Authorization: `Bearer ${idToken}`,
                },
            };

            // Call DELETE /reservations. First argument ({}) is path params (none needed).
            const response = await apigClient.reservationsDelete({}, body, additionalParams);

            if (response.status === 200) {
                // Cancellation successful — inform the user and return to the list page.
                alert("Reservation canceled successfully.");
                window.location.href = "view-reservations.html";
            } else {
                alert("Failed to cancel reservation.");
                console.error(response);
            }
        } catch (error) {
            console.error("Error canceling reservation:", error);
        }
    };

    /**
     * returnToReservations
     *
     * Exposed on the global window object so it can be called from an inline
     * onclick attribute in the HTML (e.g., onclick="returnToReservations()").
     *
     * Navigates the user back to the full reservations list page without
     * performing any API call.
     */
    window.returnToReservations = function () {
        window.location.href = "view-reservations.html";
    };

    // Fetch and display this reservation's details as soon as the page loads.
    loadReservationDetails();
});
