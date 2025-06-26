document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById("loginModal");
    const userInfo = document.querySelector(".user-info");
    const loginButton = document.querySelector(".button-style-login");
    const closeButton = document.getElementById("close-login");


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
                body: JSON.stringify({ username: userName, password: password})
            })
            .then(response => response.json())
            .then(data => {
                if (data.redirect) {
                    window.location.href = data.redirect; // Redirect in the browser
                } 
            });
        } catch (error) {
            console.error('Error:', error);
        }

        
    }

    

});