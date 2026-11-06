document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById("loginModal");
    const userInfo = document.querySelector(".user-info");
    const loginForm = document.getElementById("login-form");
    const closeButton = document.getElementById("close-login");
    const userlogout = document.querySelector(".user-logout");
    const userlogin = document.querySelector(".user-login");

    function openLogin() {
        modal.style.display = "block";
        document.getElementById("username").focus();
    }

    function closeLogin() {
        modal.style.display = "none";
    }

    // Esc closes the dialog
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && modal.style.display === 'block') closeLogin();
    });

    userInfo.onclick = openLogin;
    if (userlogin) userlogin.onclick = openLogin;

    closeButton.onclick = function(event) { 
        event.preventDefault();
        closeLogin();
    }
    
    loginForm.addEventListener('submit', async function(event) {
            event.preventDefault();  // never fall back to a native submit
            const userName = document.getElementById("username").value;
            const password = document.getElementById("password").value;
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
        });
    
    if (userlogout) userlogout.onclick = async function() {
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