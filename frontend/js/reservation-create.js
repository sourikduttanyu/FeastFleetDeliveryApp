/**
 * reservation-create.js
 *
 * Page: reservation-create.html (restaurant reservation booking page)
 *
 * Purpose:
 *   Drives the reservation creation flow for a specific restaurant. The restaurant
 *   is identified via URL query parameters. On load, the page fetches available
 *   time slots for the current date and default party size, then lets the user
 *   pick a slot and submit a reservation. The page dynamically refreshes available
 *   slots whenever the user changes the date or party size.
 *
 * On Load (DOMContentLoaded):
 *   1. Reads `restaurant_id` and `restaurant_name` from the URL query string.
 *   2. Injects the restaurant name into the calendar section heading.
 *   3. Sets the date picker to today's date.
 *   4. Populates the party-size <select> with options 1–50.
 *   5. Calls fetchAvailability() to load time slots for the current defaults.
 *
 * API Endpoints Called:
 *   - GET  /reservations/availability
 *       (apigClient.reservationsAvailabilityGet)
 *       Params: restaurant_id, date, party_size
 *       Returns: available_times array, optional message, opening_hour, closing_hour
 *
 *   - POST /reservations
 *       (apigClient.reservationsPost)
 *       Body: { restaurant_id, res_date, time, party_size }
 *       Headers: { Authorization: "Bearer <idToken>" }
 *       Creates a reservation and returns a 200 status on success.
 */

document.addEventListener("DOMContentLoaded", () => {
    // --- DOM References ---
    const dateInput = document.getElementById("date");               // Date picker <input type="date">
    const partySizeSelect = document.getElementById("party-size");   // Party size <select> dropdown
    const timeList = document.getElementById("time-list");           // Container where time slot buttons are rendered
    const reserveButton = document.getElementById("reserve-button"); // Submit button for the reservation form

    // Parse query parameters from the current page URL.
    // Expected params: ?restaurant_id=<id>&restaurant_name=<name>
    const urlParams = new URLSearchParams(window.location.search);

    // const restaurantId = "3c17f456-34f5-4a9b-94c4-ecd74c403950"; // Replace with the actual restaurant ID

    // Extract the restaurant's unique ID — passed to all API calls.
    const restaurantId = urlParams.get('restaurant_id');

    // Extract the human-readable restaurant name for display in the heading.
    const restaurant_name = urlParams.get('restaurant_name');

    // If a restaurant name was provided in the URL, inject it into the
    // calendar section heading so the user knows which restaurant they're booking.
    if(restaurant_name){
        const container = document.querySelector(".calendar-section h2");
        container.innerHTML = restaurant_name;
    }

    console.log('RESTAURANT ID', restaurantId);

    // --- Default form values ---

    // Default the date picker to today's date in YYYY-MM-DD format.
    // toISOString() returns a UTC timestamp; split("T")[0] extracts just the date portion.
    const today = new Date().toISOString().split("T")[0];
    dateInput.value = today;

    // Populate party size options (1 to 50) dynamically so the HTML
    // doesn't need 50 hard-coded <option> tags.
    for (let i = 1; i <= 50; i++) {
        const option = document.createElement("option");
        option.value = i;
        option.textContent = i;
        partySizeSelect.appendChild(option);
    }
    // Default selection: 1 person.
    partySizeSelect.value = 1;

    /**
     * fetchAvailability
     *
     * Async function that calls GET /reservations/availability with the currently
     * selected date and party size. On a successful response it either shows a
     * status message (e.g., "restaurant is closed") or renders the available time
     * slots by calling populateTimeSlots().
     *
     * Triggered on: page load, date input change, party size change.
     *
     * API Called:
     *   GET /reservations/availability
     *   Query params: { restaurant_id, date, party_size }
     *   Response body (parsed): {
     *     available_times: Array,   // List of [availability, timeString] tuples
     *     message: string|null,     // Set when the restaurant is closed or hours unavailable
     *     opening_hour: string,
     *     closing_hour: string
     *   }
     *
     * @returns {Promise<void>}
     */
    async function fetchAvailability() {
        // Read the current values from the date picker and party size dropdown.
        const selectedDate = dateInput.value;
        const partySize = partySizeSelect.value;

        try {
            // Instantiate the API Gateway SDK client for this request.
            const apigClient = apigClientFactory.newClient();

            // Build query string parameters for the availability endpoint.
            const params = {
                restaurant_id: restaurantId,
                date: selectedDate,
                party_size: partySize
            };

            // Call GET /reservations/availability.
            // Second argument ({}) is the request body (none for GET).
            // Third argument ({}) is additional params (no auth needed for availability).
            const response = await apigClient.reservationsAvailabilityGet(params, {}, {});
            console.log("API Response:", response);

            if (response.status === 200) {
                // API Gateway wraps the Lambda response body as a JSON string,
                // so it must be parsed explicitly before accessing its fields.
                const responseBody = JSON.parse(response.data.body);
                const { available_times, message, opening_hour, closing_hour } = responseBody;

                if (message) {
                    // A message field is returned when the restaurant is closed on the
                    // selected date or when operating hours cannot be determined.
                    displayMessage(message);
                } else {
                    // Valid availability data was returned — render the time slots.
                    populateTimeSlots(available_times, opening_hour, closing_hour);
                }
            } else {
                console.error("Failed to fetch availability:", response);
            }
        } catch (error) {
            console.error("Error fetching availability:", error);
        }
    }

    /**
     * displayMessage
     *
     * Clears the time slot list and shows a single red informational message
     * in its place. Used when the restaurant is closed on the selected date
     * or operating hours are unavailable.
     *
     * @param {string} message - The text to display (e.g., "Restaurant is closed on this day.").
     *
     * DOM Manipulated:
     *   - Clears #time-list.
     *   - Appends a red-colored <div> containing the message to #time-list.
     */
    function displayMessage(message) {
        // Clear any previously rendered time slots before showing the message.
        timeList.innerHTML = "";

        const messageDiv = document.createElement("div");
        messageDiv.textContent = message;
        messageDiv.style.color = "red"; // Red color signals a non-bookable state to the user.
        timeList.appendChild(messageDiv);
    }

    /**
     * populateTimeSlots
     *
     * Clears the time slot container and renders a clickable button for each
     * available time slot returned by the availability API. Slots marked as
     * unavailable ("U") are rendered as greyed-out non-interactive elements.
     * Clicking an available slot marks it as selected (and deselects others),
     * which is required before the user can submit the reservation.
     *
     * @param {Array<[string, string]>} times  - Array of [availability, timeString] tuples.
     *   availability: "A" (available) or "U" (unavailable).
     *   timeString: human-readable time label, e.g., "7:00 PM".
     * @param {string} openingHour  - The restaurant's opening time (informational, not rendered directly here).
     * @param {string} closingHour  - The restaurant's closing time (informational, not rendered directly here).
     *
     * DOM Manipulated:
     *   - Clears and repopulates #time-list with one .time-slot <div> per time entry.
     *   - Adds class 'unavailable' to slots that cannot be booked.
     *   - Adds 'selected' class to a slot when the user clicks it;
     *     removes 'selected' from all other slots to enforce single-selection.
     */
    function populateTimeSlots(times, openingHour, closingHour) {
        // Clear any previous time slots (from a prior date/party-size fetch).
        timeList.innerHTML = "";

        // Guard against malformed API responses where times is not an array.
        if (!Array.isArray(times)) {
            console.error("Invalid times array:", times);
            alert("Failed to load time slots. Please try again later.");
            return;
        }

        // Destructure each entry in the times array as a [availability, time] tuple.
        times.forEach(([availability, time]) => {
            const timeSlot = document.createElement("div");
            timeSlot.classList.add("time-slot");
            timeSlot.textContent = time; // Display the human-readable time label (e.g., "7:00 PM").

            if (availability === "U") {
                // Mark this slot as unavailable so CSS can style it (e.g., greyed out).
                // No click listener is attached, preventing selection of full slots.
                timeSlot.classList.add("unavailable");
            } else {
                // For available slots, attach a click handler that implements
                // radio-button-style single selection across all time slots.
                timeSlot.addEventListener("click", () => {
                    // Deselect all currently selected slots before applying the new selection.
                    // This ensures only one time slot can be selected at a time.
                    document.querySelectorAll(".time-slot").forEach((slot) =>
                        slot.classList.remove("selected")
                    );

                    // Mark the clicked slot as the active selection.
                    timeSlot.classList.add("selected");
                });
            }

            timeList.appendChild(timeSlot);
        });
    }

    /**
     * convertToMilitaryTime
     *
     * Converts a 12-hour time string (e.g., "7:30 PM") to a 24-hour / military
     * time string (e.g., "19:30") for submission to the reservations API, which
     * expects times in HH:MM format.
     *
     * @param {string} time - A 12-hour time string with AM/PM suffix, e.g., "12:00 PM".
     * @returns {string}    - A zero-padded 24-hour time string, e.g., "12:00" or "00:30".
     *
     * Edge cases handled:
     *   - "12:xx PM" stays as 12 (noon — no addition needed).
     *   - "12:xx AM" converts to 00 (midnight).
     */
    function convertToMilitaryTime(time) {
        // Split "7:30 PM" into timePart ("7:30") and period ("PM").
        const [timePart, period] = time.split(" ");

        // Split "7:30" into numeric hours and minutes.
        let [hours, minutes] = timePart.split(":").map(Number);

        if (period === "PM" && hours !== 12) {
            // For PM times that are not noon, add 12 to convert to 24-hour format.
            // e.g., 7 PM -> 19, 11 PM -> 23.
            hours += 12;
        } else if (period === "AM" && hours === 12) {
            // Special case: 12 AM (midnight) must become 00, not 12.
            hours = 0;
        }

        // Pad single-digit hours and minutes with a leading zero (e.g., "9" -> "09").
        return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
    }

    /**
     * Reserve Button Click Handler (anonymous — attached to #reserve-button 'click')
     *
     * Handles reservation form submission:
     *   1. Reads the selected date, party size, and the currently selected time slot.
     *   2. Validates that a time slot has been selected.
     *   3. Converts the display time to military (24-hour) format for the API.
     *   4. Retrieves the Cognito idToken; redirects to login if absent.
     *   5. POSTs the reservation data to POST /reservations with the Bearer token.
     *   6. On success, redirects the user to view-reservations.html.
     *
     * API Called:
     *   POST /reservations  (apigClient.reservationsPost)
     *   Body: { restaurant_id, res_date, time (HH:MM), party_size (int) }
     *   Headers: { Authorization: "Bearer <idToken>" }
     *
     * DOM Read:
     *   - #date (dateInput.value)
     *   - #party-size (partySizeSelect.value)
     *   - .time-slot.selected (the currently highlighted time slot element)
     *
     * @returns {Promise<void>}
     */
    reserveButton.addEventListener("click", async () => {
        const selectedDate = dateInput.value;
        const partySize = partySizeSelect.value;

        // Use optional chaining (?.) to safely read textContent even if no slot is selected.
        const selectedTime = document.querySelector(".time-slot.selected")?.textContent;

        // Guard: the user must select a time slot before submitting.
        if (!selectedTime) {
            alert("Please select a time slot.");
            return;
        }

        // Convert the displayed 12-hour time (e.g., "7:00 PM") to military format
        // (e.g., "19:00") as required by the reservations API.
        const militaryTime = convertToMilitaryTime(selectedTime);

        try {
            const apigClient = apigClientFactory.newClient();

            // Retrieve the Cognito ID token for authenticated API access.
            // The idToken (not the accessToken) is required for this endpoint.
            const idToken = localStorage.getItem("idToken");
            if (!idToken) {
                alert("You need to log in to make a reservation.");
                window.location.href = "login.html";
                return;
            }

            // Build the POST body with all required reservation fields.
            const body = {
                restaurant_id: restaurantId,
                res_date: selectedDate,
                time: militaryTime,
                // parseInt with radix 10 ensures the string value from the <select>
                // is sent as a number (integer), not a string, to the API.
                party_size: parseInt(partySize, 10)
            };

            // Attach the Bearer token in the Authorization header.
            // API Gateway uses this to verify the Cognito identity before invoking Lambda.
            const additionalParams = {
                headers: {
                    Authorization: `Bearer ${idToken}`,
                },
            };

            // Submit the reservation via POST /reservations.
            const response = await apigClient.reservationsPost({}, body, additionalParams);
            console.log('RESPONSE: ', response);

            if (response.status === 200) {
                // Reservation accepted: notify the user and navigate to the reservations list.
                // The actual confirmation/rejection is handled asynchronously via email.
                alert("Reservation processed! Check email for status update");
                window.location.href = "view-reservations.html";
            } else {
                alert("Failed to make reservation. Please try again.");
                console.error("Reservation error:", response);
            }
        } catch (error) {
            console.error("Error making reservation:", error);
            alert("An unexpected error occurred. Please try again.");
        }
    });

    // --- Event Listeners for re-fetching availability ---

    // Re-fetch time slots whenever the user picks a new date.
    dateInput.addEventListener("change", fetchAvailability);

    // Re-fetch time slots whenever the user changes the party size,
    // as availability may differ based on how many seats are needed.
    partySizeSelect.addEventListener("change", fetchAvailability);

    // Fetch initial availability on page load using the default date and party size.
    fetchAvailability();
});
