document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const reservationId = decodeURIComponent(urlParams.get('reservation_id')); // Decode the reservation_id

    if (!reservationId) {
        alert("Reservation ID is missing.");
        window.location.href = "reservations.html";
        return;
    }

    console.log("RES_ID: ", reservationId);

    // Load reservation details
    async function loadReservationDetails() {
        try {
            const apigClient = apigClientFactory.newClient();
            const idToken = localStorage.getItem("idToken");
            if (!idToken) {
                alert("You need to log in to view reservations.");
                window.location.href = "login.html";
                return;
            }

            const params = {
                reservation_id: reservationId,
            };

            const additionalParams = {
                headers: {
                    Authorization: `Bearer ${idToken}`,
                },
            };

            const response = await apigClient.reservationsViewGet(params, null, additionalParams);
            console.log('RESPONSE ', response)

            if (response.status === 200) {
                const reservation = JSON.parse(response.data.body);
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

    // Cancel the reservation
    window.cancelReservation = async function () {
        if (!confirm("Are you sure you want to cancel this reservation?")) {
            return;
        }

        try {
            const apigClient = apigClientFactory.newClient();
            const idToken = localStorage.getItem("idToken");
            if (!idToken) {
                alert("You need to log in to cancel reservations.");
                window.location.href = "login.html";
                return;
            }

            const body = {
                reservation_id: reservationId,
            };

            const additionalParams = {
                headers: {
                    Authorization: `Bearer ${idToken}`,
                },
            };

            const response = await apigClient.reservationsDelete({}, body, additionalParams);

            if (response.status === 200) {
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

    // Return to reservations list
    window.returnToReservations = function () {
        window.location.href = "view-reservations.html";
    };

    // Load reservation details on page load
    loadReservationDetails();
});
