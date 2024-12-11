document.addEventListener("DOMContentLoaded", () => {
    const dateInput = document.getElementById("date");
    const partySizeSelect = document.getElementById("party-size");
    const timeList = document.getElementById("time-list");
    const reserveButton = document.getElementById("reserve-button");
    const urlParams = new URLSearchParams(window.location.search);

    // const restaurantId = "3c17f456-34f5-4a9b-94c4-ecd74c403950"; // Replace with the actual restaurant ID
    
    const restaurantId = urlParams.get('restaurant_id');
    const restaurant_name = urlParams.get('restaurant_name');

    if(restaurant_name){
        const container = document.querySelector(".calendar-section h2");
        container.innerHTML = restaurant_name;
    }

    console.log('RESTAURANT ID', restaurantId);
    // Initialize the default date and party size
    const today = new Date().toISOString().split("T")[0];
    dateInput.value = today;

    // Populate party size options (1 to 50)
    for (let i = 1; i <= 50; i++) {
        const option = document.createElement("option");
        option.value = i;
        option.textContent = i;
        partySizeSelect.appendChild(option);
    }
    partySizeSelect.value = 1;

    // Fetch availability from the backend
    async function fetchAvailability() {
        const selectedDate = dateInput.value;
        const partySize = partySizeSelect.value;

        try {
            const apigClient = apigClientFactory.newClient();
            const params = {
                restaurant_id: restaurantId,
                date: selectedDate,
                party_size: partySize
            };
            const response = await apigClient.reservationsAvailabilityGet(params, {}, {});
            console.log("API Response:", response);

            if (response.status === 200) {
                const responseBody = JSON.parse(response.data.body); // Parse the body as JSON
                const { available_times, message, opening_hour, closing_hour } = responseBody;

                if (message) {
                    displayMessage(message); // Display the message if the restaurant is closed or hours not found
                } else {
                    populateTimeSlots(available_times, opening_hour, closing_hour); // Populate the times
                }
            } else {
                console.error("Failed to fetch availability:", response);
            }
        } catch (error) {
            console.error("Error fetching availability:", error);
        }
    }

    // Display a message in place of times
    function displayMessage(message) {
        timeList.innerHTML = ""; // Clear existing times
        const messageDiv = document.createElement("div");
        messageDiv.textContent = message;
        messageDiv.style.color = "red";
        timeList.appendChild(messageDiv);
    }

    // Populate available time slots
    function populateTimeSlots(times, openingHour, closingHour) {
        timeList.innerHTML = ""; // Clear existing times
    
        if (!Array.isArray(times)) {
            console.error("Invalid times array:", times);
            alert("Failed to load time slots. Please try again later.");
            return;
        }
    
        times.forEach(([availability, time]) => {
            const timeSlot = document.createElement("div");
            timeSlot.classList.add("time-slot");
            timeSlot.textContent = time;
    
            if (availability === "U") {
                timeSlot.classList.add("unavailable"); // Style unavailable slots
            } else {
                timeSlot.addEventListener("click", () => {
                    // Remove the 'selected' class from all time slots
                    document.querySelectorAll(".time-slot").forEach((slot) =>
                        slot.classList.remove("selected")
                    );
                    // Add the 'selected' class to the clicked time slot
                    timeSlot.classList.add("selected");
                });
            }
    
            timeList.appendChild(timeSlot);
        });
    }

    function convertToMilitaryTime(time) {
        const [timePart, period] = time.split(" ");
        let [hours, minutes] = timePart.split(":").map(Number);
    
        if (period === "PM" && hours !== 12) {
            hours += 12; // Convert PM hours to military time
        } else if (period === "AM" && hours === 12) {
            hours = 0; // Convert 12 AM to 00 in military time
        }
    
        return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
    }
    
    // Handle reservation submission
    reserveButton.addEventListener("click", async () => {
        const selectedDate = dateInput.value;
        const partySize = partySizeSelect.value;
        const selectedTime = document.querySelector(".time-slot.selected")?.textContent;

        if (!selectedTime) {
            alert("Please select a time slot.");
            return;
        }

         // Convert selectedTime to military time format
        const militaryTime = convertToMilitaryTime(selectedTime);

        try {
            const apigClient = apigClientFactory.newClient();

            // Get the IdToken instead of the AccessToken
            const idToken = localStorage.getItem("idToken");
            if (!idToken) {
                alert("You need to log in to make a reservation.");
                window.location.href = "login.html";
                return;
            }

            const body = {
                restaurant_id: restaurantId,
                res_date: selectedDate,
                time: militaryTime,
                party_size: parseInt(partySize, 10)
            };

            const additionalParams = {
                headers: {
                    Authorization: `Bearer ${idToken}`, // Include "Bearer " prefix with IdToken
                },
            };

            const response = await apigClient.reservationsPost({}, body, additionalParams);
            console.log('RESPONSE: ', response);

            if (response.status === 200) {
                alert("Reservation processed! Check email for status update");
                window.location.href = "view-reservations.html"; // Redirect to reservations list
            } else {
                alert("Failed to make reservation. Please try again.");
                console.error("Reservation error:", response);
            }
        } catch (error) {
            console.error("Error making reservation:", error);
            alert("An unexpected error occurred. Please try again.");
        }
    });

    // Fetch availability whenever the date or party size changes
    dateInput.addEventListener("change", fetchAvailability);
    partySizeSelect.addEventListener("change", fetchAvailability);

    // Fetch initial availability
    fetchAvailability();
});