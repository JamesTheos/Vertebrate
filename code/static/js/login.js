document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById("loginModal");
    const userInfo = document.querySelector(".user-info");
    const loginButton = document.querySelector(".button-style-login");
    const closeButton = document.getElementById("close-login");
    const userlogout = document.querySelector(".user-logout");


    userInfo.onclick = function() {
        modal.style.display = "block";
    }

    closeButton.onclick = function() { 
        event.preventDefault();
        modal.style.display = "none"; 
    }
    
    loginButton.onclick = async function() {
            const userName = document.getElementById("username").value;
            const password = document.getElementById("password").value;
            console.log(userName, password);
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
                    }
            } catch (error) {
                console.error('Error:', error);
            }
        };
    
    userlogout.onclick = async function() {
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
                }
            } catch (error) {
                console.error('Error:', error);
            }
        };
    });