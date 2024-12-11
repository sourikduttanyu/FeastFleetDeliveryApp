document.addEventListener("DOMContentLoaded", async () => {
    const upcomingReservationsContainer = document.getElementById("upcoming-reservations");
    const pastReservationsContainer = document.getElementById("past-reservations");

    // Get user token
    const idToken = localStorage.getItem("idToken");
    if (!idToken) {
        alert("You need to log in to view reservations.");
        window.location.href = "login.html";
        return;
    }

    try {
        const apigClient = apigClientFactory.newClient();
        const additionalParams = {
            headers: {
                Authorization: `Bearer ${idToken}`,
            },
        };

        const response = await apigClient.reservationsGet({}, null, additionalParams);
        console.log("API Response:", response);

        if (response.status === 200) {
            const { past_reservations = [], upcoming_reservations = [] } = JSON.parse(response.data.body);

            // Helper function to create reservation cards
            const createReservationCard = (reservation) => {
                const card = document.createElement("div");
                card.classList.add("reservation-card");
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

                card.addEventListener("click", () => {
                    const encodedReservationId = encodeURIComponent(reservation.reservation_id); // Encode the full reservation_id
                    window.location.href = `view-reservation.html?reservation_id=${encodedReservationId}`;
                });

                return card;
            };

            // Populate upcoming reservations
            upcoming_reservations.forEach((reservation) => {
                const card = createReservationCard(reservation);
                upcomingReservationsContainer.appendChild(card);
            });

            // Populate past reservations
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
