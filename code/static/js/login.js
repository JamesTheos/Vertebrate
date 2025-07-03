document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById("loginModal");
    const userInfo = document.querySelector(".user-info");
    const loginButton = document.querySelector(".button-style-login");
    const closeButton = document.getElementById("close-login");
    const userlogout = document.querySelector(".user-logout");

    let logged_in_status; // Initialize logged_in_status variable

    userInfo.onclick = function() {
        modal.style.display = "block";
    }

    closeButton.onclick = function() { 
        event.preventDefault();
        modal.style.display = "none"; 
    }

    function checkloginstatus() {
        fetch('/loginstatus', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            logged_in_status = data.logged_in; // Update the logged_in_status variable
            console.log('Logged in status:', logged_in_status);
        })
        .catch(error => console.error('Error:', error));
    }
    
    loginButton.onclick = async function() {
            console.log('loginstatus:', logged_in_status);
            checkloginstatus();
            const userName = document.getElementById("username").value;
            const password = document.getElementById("password").value;
            console.log(userName, password, logged_in_status);
            if(logged_in_status === undefined || logged_in_status === false) {
            try {
                const response = await fetch('/loginUser', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ username: userName, password: password })
                });
                const data = await response.json();
                if (data.redirect) {
                    window.location.href = data.redirect;//Redirect in the browser 
                    logged_in_status = data.logged_in; // Update the logged_in_status variable
                    console.log('Logged in status after logout:', logged_in_status);
                }
            } catch (error) {
                console.error('Error:', error);
            }
        }};
    
    userlogout.onclick = async function() {
        checkloginstatus();
        if(logged_in_status === undefined || logged_in_status === true){ 
            try {
                const response_logout = await fetch('/logoutUser', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                const data = await response_logout.json();
                if (data.redirect) {
                    window.location.href = data.redirect; // Redirect in the browser
                    logged_in_status = data.logged_in; // Update the logged_in_status variable
                    console.log('Logged in status after logout:', logged_in_status);
                }
            } catch (error) {
                console.error('Error:', error);
            }
        };
    }});