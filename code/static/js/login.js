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

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username: userName, password: password })
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Login successful:', result);
                modal.style.display = "none";
                location.reload(); 
            } else {
                console.error('Login failed:', response.statusText);
            }
        } catch (error) {
            console.error('Error:', error);
        }

        
    }

    

});