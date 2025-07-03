document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById("loginModal");
    const userInfo = document.querySelector(".user-info");
    const loginButton = document.querySelector(".button-style-login");
    const closeButton = document.getElementById("close-login");
    const userlogout = document.querySelector(".user-logout");
    const logoutbutton = document.querySelector(".button-style-logout");

    logged_in_status = false; // Initialize logged_in_status variable

    userInfo.onclick = function() {
        modal.style.display = "block";
    }

    closeButton.onclick = function() { 
        event.preventDefault();
        modal.style.display = "none"; 
    }
    if(logged_in_status = false) {
    userlogout.style.display = "none"; // Hide the logout button if not logged in
    logoutbutton.style.display = "none"; // Hide the logout button if not logged in
    loginButton.onclick = async function() {
        const userName = document.getElementById("username").value;
        const password = document.getElementById("password").value;
        console.log(userName, password,logged_in_status);
        try {
            const response = await fetch('/loginUser', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username: userName, password: password})
            })
            .then(response => response.json())
            .then(data => {
                if (data.redirect) {
                    window.location.href = data.redirect; // Redirect in the browser
                    logged_in_status = data.logged_in; // Update the logged_in_status variable
                } 
            });
        } catch (error) {
            console.error('Error:', error);
        }

        
    }

    

}
else{
    userlogout.style.display = "block"; // Show the logout button if logged in
    logoutbutton.style.display = "block"; // Show the logout button if logged in
    userlogout.onclick = function() {  
    logoutbutton.onclick = async function() {
        try {
            const response = await fetch('/logoutUser', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.redirect) {
                    window.location.href = data.redirect; // Redirect in the browser
                    logged_in_status = data.logged_in; // Update the logged_in_status variable
                } 
            });
        } catch (error) {
            console.error('Error:', error);
        }
    }
}}});